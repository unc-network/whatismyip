# Deploying with Docker

This guide walks through standing up **What Is My IP** on any server with Docker and Docker Compose. It is written for network teams who are comfortable with Docker but are not Python developers.

The tool works in two tiers:

| Tier | What it provides | What you need |
| ---- | ---------------- | ------------- |
| **Basic** | IP address, geolocation, DNS provider, connectivity tests | Docker + a config file |
| **Campus-integrated** | All of the above, plus campus network details, NAC endpoint info, and wireless enrichment | Basic + credentials for your IPAM/NAC/wireless systems |

Start with the basic tier. Add campus integrations one at a time as you have the credentials ready.

---

## Prerequisites

- **Docker Engine 20.10+** or **Docker Desktop** — [install guide](https://docs.docker.com/get-docker/)
- **Docker Compose v2** — included with Docker Desktop; on Linux install with `sudo apt install docker-compose-plugin` or equivalent
- A **domain name** pointed at your server
- A **reverse proxy** to handle HTTPS (nginx, Apache, Traefik, Caddy — examples below)

---

## Quick start

### 1. Get the code

```bash
git clone https://github.com/your-org/whatismyip.git
cd whatismyip
```

### 2. Create your site configuration

```bash
cp data/config.toml.example data/config.toml
```

Open `data/config.toml` in a text editor and fill in at minimum:

```toml
[site]
name = "Your Institution Name"
city = "Your City"
region = "Your State"
country_code = "US"
country_name = "United States"
lat = 35.9049     # your campus latitude
lon = -79.0469    # your campus longitude

[campus]
networks = [
    "192.0.2.0/24",     # replace with your campus public IP ranges
    "10.0.0.0/8",       # replace with your private ranges
]
```

See [Configuration](#configuration) below for all options.

### 3. Create your environment file

```bash
cp .env.example .env
```

Open `.env` and set these two required values:

```bash
# Generate a random key: python3 -c "import secrets; print(secrets.token_hex(32))"
FLASK_SECRET_KEY=paste-your-random-key-here

# The public URL where your site will be hosted
FLASK_SERVER_URL=https://whatismyip.yourinstitution.edu
FLASK_IPV4_SERVER_URL=https://whatismyip.yourinstitution.edu
```

Leave everything else commented out for now.

### 4. Add your SSL certificate

The included nginx container handles HTTPS. Place your certificate files in `nginx/certs/`:

```bash
mkdir -p nginx/certs
cp /path/to/your/institution.pem  nginx/certs/cert.pem
cp /path/to/your/institution.key  nginx/certs/key.pem
```

**Don't have a cert yet?** Generate a self-signed one for testing:

```bash
mkdir -p nginx/certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/certs/key.pem -out nginx/certs/cert.pem \
  -subj "/CN=whatismyip.yourinstitution.edu"
```

Browsers will show a security warning for self-signed certs — that's expected in testing. Replace with your institution's certificate before going live.

### 5. Set your domain name in the nginx config

Open `nginx/nginx.conf` and replace the two `CHANGEME` placeholders with your domain:

```nginx
server_name whatismyip.yourinstitution.edu;
```

### 6. Build and start

```bash
docker compose up -d
```

This builds the app image, pulls nginx, and starts both containers. The first build takes about a minute.

### 7. Verify it started

```bash
docker compose logs -f
```

Look for `Listening at: http://0.0.0.0:8000` from the app and nginx startup messages. Open `https://whatismyip.yourinstitution.edu` in a browser to confirm.

---

## Configuration

All site-specific configuration lives in `data/config.toml`. Edit it and restart the container to apply changes:

```bash
docker compose restart
```

### `[site]` — institution details

```toml
[site]
name = "State University ITS"   # shown when campus IPs can't be geolocated
city = "Springfield"
region = "Illinois"
country_code = "US"
country_name = "United States"
lat = 39.7817        # campus lat/lon for the map marker on campus IPs
lon = -89.6501
```

### `[campus]` — your network ranges

The most important section. List every IP range your users might connect from on campus. Visitors matching these ranges receive the full campus diagnostic; everyone else gets the basic IP + geolocation view.

```toml
[campus]
networks = [
    "198.51.100.0/24",    # example public range
    "203.0.113.0/24",     # another public range
    "10.0.0.0/8",         # private range
    "172.16.0.0/12",
    "192.168.0.0/16",
    "2001:db8::/32",      # IPv6 range
]
```

### `[dns]` — security filter test

If your campus uses DNS-based security filtering (Cisco Umbrella, Akamai ETP, Cloudflare Gateway, etc.), set the test URL here. The tool will check whether filtering is active for each visitor.

```toml
[dns]
# A URL your DNS filtering service is known to block
security_filter_test_url = "https://www.akamaietpphishingtest.com/"
# Other examples:
# security_filter_test_url = "https://internetbadguys.com/"         # Cisco Umbrella
# security_filter_test_url = "https://malware.testcategory.com/"    # Cloudflare Gateway
```

Leave the value as `""` to disable this test.

### `[map]` — map provider

```toml
[map]
provider = "leaflet"   # free, OpenStreetMap — no API key needed
# provider = "google"  # requires FLASK_GOOGLE_MAPS_API_KEY in .env
```

### `[connectivity]` — connectivity test targets

The `/connectivity` page tests reachability to a list of URLs from the visitor's browser. Customize these for your institution:

```toml
[[connectivity.targets]]
name = "What Is My IP"
url = "https://whatismyip.yourinstitution.edu/"
description = "This tool"
type = "self"

[[connectivity.targets]]
name = "Institution Homepage"
url = "https://www.yourinstitution.edu/"
description = "Main website"
type = "internet"

[[connectivity.targets]]
name = "IT Help Desk"
url = "https://help.yourinstitution.edu/"
description = "IT support portal"
type = "campus"
```

---

## Environment variables

The `.env.example` file documents every available variable. For a basic deployment you only need:

| Variable | Required | Description |
| -------- | -------- | ----------- |
| `FLASK_SECRET_KEY` | Yes | Random string for session security — generate once, keep private |
| `FLASK_SERVER_URL` | Yes | Your public HTTPS URL, e.g. `https://whatismyip.yourinstitution.edu` |
| `FLASK_IPV4_SERVER_URL` | Yes | Same as SERVER_URL for single-stack; separate hostname for dual-stack |
| `FLASK_IPV6_SERVER_URL` | No | IPv6 hostname for dual-stack detection; leave blank to disable |
| `FLASK_METRICS_USERNAME` | No | HTTP Basic Auth username for the `/metrics` page |
| `FLASK_METRICS_PASSWORD` | No | HTTP Basic Auth password for the `/metrics` page |

See [Campus integrations](#campus-integrations) for the optional API credentials.

---

## Reverse proxy setup

The Docker container speaks plain HTTP on port 8080. **Your reverse proxy handles HTTPS.** Below are minimal examples — adapt for your institution's certificate infrastructure.

### nginx

```nginx
server {
    listen 443 ssl;
    server_name whatismyip.yourinstitution.edu;

    ssl_certificate     /path/to/your/cert.pem;
    ssl_certificate_key /path/to/your/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host              $host;
        proxy_set_header X-Forwarded-For  $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name whatismyip.yourinstitution.edu;
    return 301 https://$host$request_uri;
}
```

### Apache

```apache
<VirtualHost *:443>
    ServerName whatismyip.yourinstitution.edu

    SSLEngine on
    SSLCertificateFile    /path/to/your/cert.pem
    SSLCertificateKeyFile /path/to/your/key.pem

    ProxyPass        / http://127.0.0.1:8080/
    ProxyPassReverse / http://127.0.0.1:8080/
    ProxyPreserveHost On
    RequestHeader set X-Forwarded-Proto "https"
</VirtualHost>
```

### Traefik (Docker Compose)

If you already run Traefik as a container, add these labels to the `whatismyip` service in `docker-compose.yml`:

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.whatismyip.rule=Host(`whatismyip.yourinstitution.edu`)"
  - "traefik.http.routers.whatismyip.entrypoints=websecure"
  - "traefik.http.routers.whatismyip.tls=true"
```

---

## Campus integrations

These are all optional. The tool degrades gracefully — if credentials aren't configured, those sections simply don't appear for campus visitors.

### Infoblox IPAM

Adds campus network name, VLAN, DHCP details, and MAC address lookup.

```bash
# in .env
FLASK_IB_SERVER=ipam.yourinstitution.edu
FLASK_IB_USERNAME=readonly-api-user
FLASK_IB_PASSWORD=your-password
```

Requires a read-only account on your Infoblox WAPI (v2.10+).

### Extreme Networks XMC / XIQ-SE

Adds NAC endpoint data: switch port, policy, connection type, and endpoint group membership.

```bash
# in .env
FLASK_XMC_SERVER=xmc.yourinstitution.edu
FLASK_XMC_CLIENT_ID=your-client-id
FLASK_XMC_SECRET=your-secret
```

Create a read-only OAuth client in XMC under **Administration → Client Credentials**.

### Cisco Meraki

Adds wireless AP name, signal quality (RSSI/SNR), and client device details for visitors connected through Meraki APs.

```bash
# in .env
FLASK_MERAKI_API_KEY=your-read-only-api-key
FLASK_MERAKI_ORG_ID=your-organization-id
```

Generate a **read-only** API key in the Meraki Dashboard under your profile. Find your organization ID at `https://api.meraki.com/api/v1/organizations` using your API key.

> **Note:** The Meraki integration only enriches visitors who appear in your NAC data as Meraki-managed wireless clients. It does not require Meraki to be your only wireless platform.

---

## Day-to-day operations

### View logs

```bash
docker compose logs -f
```

### Stop and start

```bash
docker compose down
docker compose up -d
```

### Update to a new release

```bash
git pull
docker compose up -d --build
```

This rebuilds the image with the new code and restarts the container. The `data/` volume (your config and metrics database) is preserved.

### Check container health

```bash
docker compose ps
```

A healthy container shows `(healthy)` in the status column.

### Backup

Everything persistent lives in `./data/`. Back up this directory:

```bash
tar -czf whatismyip-backup-$(date +%Y%m%d).tar.gz data/
```

---

## Branding and customization

The templates and static assets reference UNC Chapel Hill branding. To adapt for your institution:

- **Institution name in the page footer and title**: edit `whatismyip/templates/base.html`
- **Home page description**: edit `whatismyip/templates/home.html`
- **Favicon and logo**: replace `whatismyip/static/` assets
- **Color scheme**: the app uses Bootstrap/MDB classes — override in `whatismyip/static/`

After editing templates or static files, rebuild the image:

```bash
docker compose up -d --build
```

---

## Troubleshooting

**Container exits immediately**
Check logs: `docker compose logs`. The most common cause is a missing or malformed `data/config.toml` or a `FLASK_SECRET_KEY` that was not set.

**"All visitors show as off-campus"**
Your `campus.networks` in `data/config.toml` does not include the IP ranges your users are connecting from. Confirm the visitor's IP against your network documentation and add the matching CIDR block.

**Campus integrations not showing**
Confirm the relevant env vars are set: `docker compose exec whatismyip env | grep FLASK_IB` (or `XMC`, `MERAKI`). Blank values mean the integration is disabled. Also check logs for connection errors to those systems.

**Map doesn't show a campus location**
The map defaults to the visitor's geolocation. For campus IPs to show the campus pin, set `lat` and `lon` in the `[site]` section of `config.toml`.

**Port 8080 already in use**
Change the host port in `docker-compose.yml`: `"8081:8000"` uses host port 8081 instead.
