# Contributing

Thank you for your interest in contributing to this project. Contributions from other institutions adapting the tool for their own campus networks are especially welcome.

> **Note:** The GitHub repository is a read-only mirror. The canonical repository is hosted on UNC's internal GitLab instance, which is not reachable from the public internet. Pull requests opened on GitHub cannot be merged directly — please open an issue on GitHub instead and we will incorporate the change on our end.

## Development setup

**Requirements:** Python 3.10 or later, pip, and git.

```bash
git clone <your-fork-url>
cd whatismyip

python -m venv env
source env/bin/activate        # Windows: env\Scripts\activate

pip install -r requirements.txt
pip install black pytest        # dev tools
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

## Running tests

```bash
pytest
```

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
