# Contributing

Thank you for your interest in contributing to this project. Contributions from other institutions adapting the tool for their own campus networks are especially welcome.

> **Note:** The GitHub repository is a read-only mirror. The canonical repository is hosted on UNC's internal GitLab instance, which is not reachable from the public internet. Pull requests opened on GitHub cannot be merged directly — please open an issue on GitHub instead and we will incorporate the change on our end.

## Development setup

**Requirements:** Python 3.12 recommended (Python 3.11 minimum), pip, and git. CI and Docker use Python 3.12.16.

```bash
git clone <your-fork-url>
cd whatismyip

python -m venv env
source env/bin/activate        # Windows: env\Scripts\activate

python -m pip install --require-hashes -r requirements-dev.txt
```

Copy the example config and edit it for your environment:

```bash
cp data/config.toml.example data/config.toml
```

At minimum, set your `SERVER_URL` and `CAMPUS_NETWORKS` in `data/config.toml`. See the [README](README.md) for the full configuration reference.

Run the development server:

```bash
flask --app whatismyip run --debug
```

The site will be available at `http://127.0.0.1:5000`.

## Code style

This project uses [Black](https://black.readthedocs.io/) for Python formatting. Before submitting a merge request, run:

```bash
black .
```

The CI pipeline runs `black --check` on every push and will fail if formatting is not applied.

Python dependencies and CI tools are locked in `requirements.txt` and `requirements-dev.txt`. Edit the corresponding `.in` files and follow the [dependency update instructions](README.md#updating-python-dependencies) to regenerate both locks.

## Running tests

```bash
pytest
```

## Dependency security checks

The site is intentionally public on the Internet. Check both dependency sets
when updating libraries; CI runs these checks on every push:

```bash
pip-audit --strict --require-hashes --disable-pip -r requirements-dev.txt
python scripts/audit_browser_libraries.py
```

`browser-libraries.json` records exact npm package versions and SHA-256 hashes
for the vendored browser assets. When updating a library, verify the upstream
package integrity, copy its official distribution, and update its version and
file hashes in the inventory. Local filenames may differ from upstream names;
the Leaflet stylesheet uses the official unminified CSS under its existing URL.
No npm install or frontend build is needed. Use `--offline` to verify asset
hashes locally without checking advisories. The online check fails if OSV is
unavailable, returns incomplete results, or reports an affected dependency.

Advisory results reflect the database at the time of the check. Run the pipeline
on a schedule as well as on pushes to catch newly published advisories while
the code is unchanged. These checks cover library dependencies, not the
OpenShift base image, OS packages, or application configuration.

## Submitting changes

1. Fork the repository and create a branch from `develop`.
2. Make your changes and ensure `black .` and `pytest` both pass.
3. Open a merge request against the `develop` branch with a clear description of what changed and why.

For bug reports or feature requests, open an issue. For security vulnerabilities, follow the process in [SECURITY.md](SECURITY.md).

## Customizing for your institution

Most institution-specific content is isolated to:

- `data/config.toml` — network ranges, API credentials, site name
- `whatismyip/templates/base.html` — utility bar, footer branding, social links
- `whatismyip/static/css/whatismyip.css` — color palette (`--unc-*` variables)

Search the templates for `CUSTOMIZE:` comments — they mark every place that needs updating for a new institution.
