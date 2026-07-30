# Project Guide — What Is My IP? (whatismyip.unc.edu)

A Flask web application that shows UNC Chapel Hill users their IP address, campus network details, VPN status, DNS provider, and connectivity diagnostics. The tool is intended for institutional adaptation — other universities can fork it by editing `data/config.toml` and the branding sections of templates.

---

## Tech Stack

- **Backend:** Python / Flask, Jinja2 templates, Gunicorn, deployed on OpenShift
- **Frontend:** Vanilla JS with jQuery, MDB Bootstrap (Material Design Bootstrap), Font Awesome 6, Leaflet maps, Chart.js — **no build step, no bundler**. Edit `.js` and `.css` files directly.
- **CSS:** `whatismyip/static/css/whatismyip.css` is the only custom stylesheet. All third-party CSS (MDB, Leaflet, Font Awesome) is vendored in `static/css/` and must not be edited.
- **JS:** `whatismyip/static/js/whatismyip.js` is the only custom script. Everything else in `static/js/` is vendored.
- **Database:** SQLite (`data/metrics.sqlite3`) for usage metrics only — not user data.

---

## File Structure

```
whatismyip/
  __init__.py          ← app factory, __version__
  routes/
    api.py             ← /hostinfo endpoint (main data endpoint)
    main.py            ← home page route
    pages.py           ← speedtest, faq, connectivity, about, metrics
    metrics.py         ← metrics recording
  infoblox.py          ← Infoblox IPAM client
  meraki.py            ← Meraki API client
  extreme.py           ← Extreme Networks NAC client
  site_config.py       ← loads data/config.toml into app context
  templates/
    base.html          ← shared layout, navbar, footer
    home.html          ← main page (IP display, all cards)
    faq.html           ← FAQ accordion
    connectivity.html  ← connectivity test page
    speedtest.html     ← Ookla embed
    metrics.html       ← usage charts (staff-facing)
  static/
    css/whatismyip.css ← all custom styles
    js/whatismyip.js   ← all custom JS
data/
  config.toml          ← site configuration (institution-specific)
  config.toml.example  ← template for new deployments
docs/
  js-execution-flow.md ← full JS architecture walkthrough
  intro-message-matrix.md ← all possible intro message states
  ARCHITECTURE.md      ← system architecture overview
  DOCKER.md            ← Docker deployment guide
  OPENSHIFT.md         ← OpenShift deployment guide
tests/                 ← pytest suite
```

---

## Configuration

All institution-specific settings live in `data/config.toml`. The app reads this at startup via `site_config.py` and injects values into the Jinja2 template context as `context.*`. Key fields include API URLs, Infoblox credentials, VPN install URL, and feature flags. Do not hardcode institution-specific values in templates or routes — always route them through `config.toml`.

---

## CSS Conventions

- **Body link underlines:** `main a:not(.btn)` — scoped to `<main>` so the footer (a sibling of `<main>`) and navbar are naturally excluded with no override rules needed.
- **Footer links:** `.main-footer a` and `.main-footer a:hover` — standalone block, no conflict with the body rule.
- **Theming:** All colors are CSS custom properties defined in `:root` (light) and `[data-theme="dark"]` / `@media (prefers-color-scheme: dark)` (dark). Never hardcode color values in component rules — always use a `var(--token)`.
- **WCAG 2.2 AA:** The site received formal accessibility approval for v1.10.4 in TeamDynamix ticket 427971. Sherose Badruddin confirmed the changes and stated that the site is WCAG 2.2 AA compliant. When adding new UI, verify contrast ratios before committing. Carolina Blue (#4b9cd3) fails on white for body text — use `#2C5080` (light mode) or the dark-mode token instead.

---

## JS Architecture — Key Patterns

Read `docs/js-execution-flow.md` for the full walkthrough. Critical non-obvious facts:

**Global state** (declared at module scope, shared between concurrent callbacks):

| Variable | Purpose |
|---|---|
| `reportDataIPv4` / `reportDataIPv6` | Full API responses. Null until the respective callback succeeds. |
| `default_version` | `4` or `6` — which protocol the server used to serve the page. Controls display order and report labeling only. Does NOT control which endpoint is called. |
| `ipv4Resolved` / `ipv6Resolved` | Set true on both success AND error. Gate `checkProxyNotice()` until both protocols settle. |
| `proxyNoticeShown` | Prevents the proxy/relay notice from firing twice. |

**Two concurrent AJAX calls fire at page load** — `test_ipv4_url()` always hits the IPv4 endpoint, `test_ipv6_url()` always hits the IPv6 endpoint, regardless of `default_version`. Either can complete first.

**Pre-declared HTML slots** — `#intro-sub-nat`, `#intro-sub-mismatch`, and `#intro-sub-proxy` are in the initial HTML as hidden divs. Each function owns its slot and shows/populates it independently. Do not dynamically append sub-lines — ordering is determined by DOM position.

**`set_intro_text()` guard** — once `#intro-main-status` has been set with a specific purpose (VPN, Wireless), a subsequent null-purpose call is ignored. This prevents the IPv4 callback from overwriting a VPN message set by IPv6.

**NAC/Meraki data is IPv4-only** — always read from `reportDataIPv4` in the report function, never from `rPrimary`/`rSecondary`.

**Report labeling** — `rPrimary`/`rSecondary` are selected by `default_version`; `r4`/`r6` are fixed protocol references. NAC, Meraki, and building sections always use `r4`.

---

## API / Data Sources

| Source | What it provides |
|---|---|
| `/hostinfo` (our API) | Campus IP, is_campus flag, Infoblox network details, NAC port, Meraki AP data |
| ip-api.com | ISP, org, geolocation, proxy flag for external IP addresses |
| api4.ipify.org | External IPv4 as seen from the internet (NAT detection) |
| Infoblox IPAM | Network CIDR, gateway, DNS servers, extensible attributes (Purpose, VPN Group, Administrator) |
| Extreme Networks NAC | Switch port, MAC, connection policy |
| Meraki API | SSID, AP name, RSSI, building coordinates |

**Infoblox extensible attributes (EAs):** `Purpose` (e.g. `"VPN"`, `"Wireless"`, `"Campus"`) drives the main status line wording and NAT message variant. `VPN Group` is displayed in the Network Configuration card for VPN users. `Administrator` is displayed as Network Contact.

---

## Accessibility Requirements (WCAG 2.2 AA)

Sherose Badruddin at the UNC Digital Accessibility Office formally approved the accessibility changes for v1.10.4 in TeamDynamix ticket 427971, confirming that the site is WCAG 2.2 AA compliant. Patterns to preserve:

- **IP address cards:** Use `aria-labelledby` pointing to the address `<h2>`, not `aria-label`. The IP must be the element's accessible name so screen readers announce it.
- **Heading hierarchy:** FAQ page is H1 → H2 (section labels) → H3 (accordion items). Do not add H2 elements inside accordion items.
- **`aria-live` regions:** `#intro_text` (home page status) has `aria-live="polite"`. The address cards do not — they are static after load.
- **Status badges:** Use the `conn-badge-*` chip classes for connectivity status, not raw `text-success` / `text-danger` utilities (insufficient contrast).
- **Focus indicators:** All interactive elements have explicit `focus-visible` outlines. Do not suppress them.
- **Link underlines:** Required for body links (WCAG 1.4.1) — the `main a:not(.btn)` rule is intentional.

Two open recommendations from the auditor (planned for a future release, not yet implemented):
1. Site Statistics: visible "View data table" toggle for chart data
2. Site Statistics: plain-language trend summary for each chart

---

## Versioning and Changelog

- Version is in `whatismyip/__init__.py` as `__version__`.
- Follow semantic versioning: patch (x.x.N) for bug fixes, minor (x.N.0) for new features.
- `CHANGELOG.md` follows Keep a Changelog conventions. Add an entry for every production push.
- Current production version: **v1.10.4** (pushed 2026-07-29).

---

## Running Locally

```bash
python -m pytest          # run test suite
flask --app whatismyip run  # dev server (reads .env for config)
```

The app requires a `.env` file with API credentials and URLs. See `data/config.toml.example` for the full list of required settings.
