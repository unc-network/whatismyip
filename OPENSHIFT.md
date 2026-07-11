# Deploying on OpenShift

This guide walks through deploying **What Is My IP** on OpenShift using Source-to-Image (S2I) — the same approach used in production at UNC. It is written for teams who manage OpenShift projects but are not necessarily Python developers.

The application runs as a single pod backed by a PersistentVolumeClaim for configuration and metrics storage.

---

## Prerequisites

- **`oc` CLI** logged in to your cluster with project admin rights — [install guide](https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html)
- A **project (namespace)** already created: `oc new-project YOUR-PROJECT`
- A **domain name** and OpenShift **Route** to expose the app externally
- Your Git repository URL (fork or internal mirror of this repo)

---

## Quick start

### 1. Get the code

```bash
git clone https://github.com/your-org/whatismyip.git
cd whatismyip
```

### 2. Switch to your project

```bash
oc project YOUR-PROJECT
```

### 3. Create the required secret

The one required secret holds the Flask session key and, optionally, metrics dashboard credentials:

```bash
oc create secret generic whatismyip \
  --from-literal=FLASK_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))") \
  --from-literal=FLASK_METRICS_USERNAME=admin \
  --from-literal=FLASK_METRICS_PASSWORD=your-chosen-password
```

Leave `FLASK_METRICS_USERNAME` and `FLASK_METRICS_PASSWORD` blank (or omit them) to make `/metrics` public.

### 4. Create optional integration secrets

Skip any integration your institution does not use — the app degrades gracefully when secrets are absent.

**Infoblox IPAM:**
```bash
oc create secret generic infoblox \
  --from-literal=SERVER=ipam.yourinstitution.edu \
  --from-literal=USERNAME=readonly-api-user \
  --from-literal=PASSWORD=your-password
```

**Extreme Networks XMC / XIQ-SE:**
```bash
oc create secret generic netsight \
  --from-literal=SERVER=xmc.yourinstitution.edu \
  --from-literal=CLIENT_ID=your-client-id \
  --from-literal=SECRET=your-secret
```

**Building directory API:**
```bash
oc create secret generic nit-public \
  --from-literal=SERVER=buildings.yourinstitution.edu \
  --from-literal=AUTH_KEY=your-auth-key
```

**Cisco Meraki:**
```bash
oc create secret generic meraki \
  --from-literal=API_KEY=your-read-only-api-key \
  --from-literal=ORG_ID=your-org-id
```

**Google Maps** (only if using `[map] provider = "google"` in config.toml):
```bash
oc create secret generic google-maps-api \
  --from-literal=KEY=your-api-key
```

### 5. Create the persistent volume

```bash
oc apply -f openshift/pvc.yaml
```

This creates a 1 GiB PVC named `whatismyip-data` for `config.toml` and the metrics database.

### 6. Build and deploy from source (S2I)

```bash
oc new-app python~https://github.com/your-org/whatismyip.git \
  --name=whatismyip \
  --strategy=source
```

This creates an ImageStream, a BuildConfig, and a Deployment. OpenShift will build the image from your repository and deploy it automatically.

Watch the build:
```bash
oc logs -f buildconfig/whatismyip
```

### 7. Edit the deployment

Once the initial build completes, apply the deployment template from this repository:

```bash
# Edit openshift/deployment.yaml first:
#   - Replace CHANGEME (namespace) with your project name
#   - Set FLASK_SERVER_URL, FLASK_IPV4_SERVER_URL, FLASK_IPV6_SERVER_URL
#   - Optionally remove integrations you aren't using

oc apply -f openshift/deployment.yaml
```

### 8. Expose the application

```bash
# Create a service if oc new-app didn't create one
oc expose deployment whatismyip --port=8080

# Create a secure Route (edge termination — OpenShift handles TLS)
oc create route edge whatismyip \
  --service=whatismyip \
  --hostname=whatismyip.yourinstitution.edu \
  --insecure-policy=Redirect
```

### 9. Upload your site configuration

The app reads its campus network ranges and site details from `data/config.toml`. Copy your configuration to the PVC after the pod starts:

```bash
# Copy your config into the running pod
oc cp data/config.toml $(oc get pod -l app=whatismyip -o name | head -1):/opt/app-root/src/data/config.toml

# Restart to apply
oc rollout restart deployment/whatismyip
```

See [Configuration](#configuration) below for all config.toml options.

### 10. Verify

```bash
oc get pods -l app=whatismyip
oc logs -l app=whatismyip
```

A healthy pod shows `Running` with `1/1` ready. Open your route URL to confirm.

---

## Configuration

Campus network ranges and site details live in `data/config.toml` on the PVC. Edit it and restart the deployment to apply changes.

```toml
[site]
name = "Your Institution ITS"
city = "Your City"
region = "Your State"
country_code = "US"
country_name = "United States"
lat = 0.0        # campus latitude — used for map pin on campus IPs
lon = 0.0        # campus longitude

[campus]
networks = [
    "198.51.100.0/24",    # your public ranges
    "10.0.0.0/8",         # private ranges
    "2001:db8::/32",      # IPv6
]

[dns]
# URL your DNS filtering service blocks — leave empty to disable the check
security_filter_test_url = ""

[map]
provider = "leaflet"    # free OpenStreetMap; use "google" with FLASK_GOOGLE_MAPS_API_KEY
```

---

## Day-to-day operations

### View logs
```bash
oc logs -f deployment/whatismyip
```

### Restart (to pick up config.toml changes)
```bash
oc rollout restart deployment/whatismyip
```

### Rebuild after a code update
```bash
oc start-build whatismyip --follow
```

### Roll back to the previous image
```bash
oc rollout undo deployment/whatismyip
```

### Back up the metrics database
```bash
oc cp $(oc get pod -l app=whatismyip -o name | head -1):/opt/app-root/src/data/metrics.sqlite3 ./metrics-backup-$(date +%Y%m%d).sqlite3
```

---

## Files in this directory

| File | Purpose |
| ---- | ------- |
| `deployment.yaml` | Deployment manifest — apply after `oc new-app` builds the image |
| `pvc.yaml` | PersistentVolumeClaim for config and metrics storage |

---

## Notes

**Recreate deployment strategy** — the deployment uses `strategy: Recreate` rather than `RollingUpdate`. This is intentional: the metrics store is a SQLite database on a `ReadWriteOnce` PVC, and two pods mounting the same volume concurrently would risk corruption. Recreate ensures the old pod stops completely before the new one starts. Expect ~10 seconds of downtime during updates.

**Health probes** — both the readiness and liveness probes target `/health`, a lightweight endpoint that returns `200 OK` with no database or template overhead. This replaced the earlier `/about` probe target.

**Metrics credentials naming** — the deployment template uses `FLASK_METRICS_USERNAME` and `FLASK_METRICS_PASSWORD` (with the `FLASK_` prefix), which is the correct form for Flask's `from_prefixed_env()` config loading. If you are migrating an existing deployment that used `METRICS_USERNAME` / `METRICS_PASSWORD` without the prefix, update your secret and env var names accordingly.

**Dual-stack DNS** — the `FLASK_IPV4_SERVER_URL` hostname must have only an A record (no AAAA), and `FLASK_IPV6_SERVER_URL` must have only a AAAA record. This forces the browser to use one specific address family when fetching `/hostinfo`, enabling dual-stack detection. If your institution does not have IPv6, set `FLASK_IPV6_SERVER_URL` to an empty string.
