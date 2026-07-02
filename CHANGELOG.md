# Changelog

All notable changes to this project will be documented here. This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) conventions.

## [1.5.0] - 2026-07-02

### Changed

- **Wireless connection path diagram now includes the wireless controller** — the controller IP (`switchIP` from NAC) is shown as the final node in the connection path for all wireless connections. For named AP connections where a building is resolved, the order is Device → AP → Building → Controller. For Meraki-style connections where no building is available, the order is Device → AP → Controller. The controller is rendered with a server icon to distinguish it from campus access switches.

---

## [1.4.2] - 2026-07-01

### Fixed

- **NAC lookup order corrected to MAC-first** — `get_nac_info` now attempts `getEndSystemByMac` before `getEndSystemByIp` when IPAM returned a MAC address in the address object lookup. XMC operates primarily on MAC addresses; IP-to-session mappings are populated by supplemental data feeds and can lag behind the current session. The previous IP-first order caused unnecessary misses for devices whose NAC session record had not yet been updated with the current IP. IP lookup is now the fallback for addresses where IPAM has no active DHCP lease (static IPs, expired leases, most IPv6 addresses).
- **MAC address case normalization for XMC queries** — IPAM returns MAC addresses in lowercase (e.g. `22:b3:c6:57:7e:60`) but XMC's GraphQL API expects uppercase hex. The MAC is now converted to uppercase before being passed to `getEndSystemByMac`, preventing silent lookup failures for DHCP-leased addresses.
- **NAC IP fallback not triggering on XMC errors** — `getEndSystemByMac` returns `False` on an API/network error and `None` when the record is simply not found. The fallback condition was checking `is None`, so an XMC error would suppress the IP fallback entirely. Changed to `if not end_system_data` to catch both cases.
- **`NameError` in `get_nac_info` when IPAM provides no MAC** — `end_system_data` was only assigned inside the `if mac:` block, causing a `NameError` on the subsequent fallback check for addresses with no IPAM MAC. Initialized to `None` before the block.
- **Meraki wireless connections misidentified as wired** — `switchPortId` values in `MAC:SSID` format (e.g. `CC-6E-2A-D6-2E-40:eduroam`) were not matched by the existing wireless regex, which expects a named AP prefix (`AP-NAME (MAC):SSID`). A second pattern now detects the MAC-only format and correctly sets `connection_type` to `wireless`. Building lookup is not available for this format without a Meraki API call (noted for a future enhancement).
- **OpenShift S2I build failure** — adding `setup.cfg` for pytest-cov configuration caused OpenShift's Source-to-Image builder to treat the project as an installable Python package and fail with "Neither setup.py nor pyproject.toml found." Moved coverage configuration to `.coveragerc`, which S2I ignores.
- **Pipeline `tag_release` job never ran on production merges** — the branch condition was hardcoded to `"main"` but the production branch is `master`. Corrected to `"master"` so the job now appears and runs on merges to the production branch.

### Added

- **NAC miss warning log** — when a campus IP address exhausts both the MAC and IP lookups in XMC without finding an end system record, a `WARNING` is now emitted to the application log including the IP and MAC (if available). Aids diagnosis of devices that appear on campus but have no NAC session.

---

## [1.4.1] - 2026-07-01

### Added

- **Ruff linter** — `ruff.toml` configured with appropriate ignores; `ruff_lint` job added to the CI lint stage alongside black.
- **Bandit security scan** — `security_scan_bandit` CI job checks for code-level security issues at medium severity/confidence. `extreme.py` is excluded (legacy CLI tool with its own patterns).
- **Test coverage reporting** — `pytest-cov` added to the test job with a 50% floor measured against `__init__.py`. `extreme.py` and `utils.py` are excluded from measurement as they require live external infrastructure. Coverage config lives in `setup.cfg`.
- **Pip dependency caching** — shared pip cache across CI jobs keyed on `requirements.txt`, reducing install time on repeated pipeline runs.
- **Automated release tagging** — `tag_release` CI job runs on `main`, extracts the version from `__init__.py`, and pushes an annotated git tag if one does not already exist.

### Changed

- **`pip-audit` now blocks the pipeline** — removed `allow_failure: true`; CVE findings in dependencies will fail the build.

### Fixed

- Two format string bugs in `extreme.py` — `"ERROR: get MAC '' failed '%s'"` was missing the MAC address argument; corrected to `"ERROR: get MAC '%s' failed '%s'"`.
- Removed unused `proxy_address` and `proxy_detected` variable assignments from `utils.py`.
- Bare `except:` clause in `extreme.py` tightened to `except Exception:`.
- Duplicate `import ipaddress` removed from `__init__.py`; import consolidated at the top of the file.

---

## [1.4.0] - 2026-07-01

### Added

- **Clock sync check** — the Your Device card includes a Clock row showing whether the device's system clock is synchronized with the server. Offsets under 30 seconds show a green "Synchronized" status; 30 seconds to 5 minutes show a warning with the measured offset; over 5 minutes show an error noting potential authentication and VPN failures.
- **Connectivity Tests page** (`/connectivity`) — a new page runs client-side reachability tests against a configurable list of campus and internet targets. Tests run automatically on page load and can be re-run on demand. Each target shows live status (reachable with latency, timed out, or unreachable). Targets are configured via `[[connectivity.targets]]` entries in `data/config.toml`. A footnote explains that results use browser fetch in `no-cors` mode and reflect the visitor's network path, not the server's.

### Changed

- **Connectivity nav link added** between Speed Test and About in the main navigation.
- **Collapsible navbar on small screens** — the main navigation now collapses below 768 px into a hamburger toggle. A vanilla JS handler wires up the toggle on all pages (MDB JS is only loaded on the home page). The active-page indicator switches from a bottom border to a left border when the menu is open vertically.
- **IP address font scales with viewport** — the hero IP bars use `font-size: clamp(1.1rem, 4.5vw, 2.6rem)` so the size shrinks smoothly on narrow screens rather than snapping at a fixed breakpoint. `<wbr>` break hints are inserted after each `.` and `:` separator so the browser wraps at segment boundaries rather than mid-digit.

### Fixed

- **Connectivity page horizontal scroll on mobile** — the card header used `flex-shrink-0` on the target name, preventing it from shrinking. Long names such as "Undergraduate Library" combined with a `text-nowrap` status badge forced cards wider than the viewport, causing a page-level horizontal scroll that clipped the footnote and footer. Removing `flex-shrink-0` allows long names to wrap within the card instead.

---

## [1.3.0] - 2026-06-30

### Added

- **Error state for failed API calls** — if the primary connection lookup fails (network error or server error), the status row updates to a warning message with a "Refresh to try again" link instead of remaining stuck on "Testing connection…". The Report button stays disabled until a successful response is received.
- **Campus address not in IPAM notice** — when a visitor is identified as on-campus but the IP address is not found in IPAM, an inline note appears in the address detail card where the network and VLAN rows would otherwise be, rather than leaving those rows silently absent.
- **Consistent page heading pattern** — FAQ, About, Speed Test, and Site Statistics pages now open with a carolina blue `<h1>` heading and a muted subtitle, replacing the previous card-wrapped intro sections and eliminating title redundancy with the active navbar link.
- **Site Statistics dashboard redesign** — stat cards now display carolina blue numbers with on-campus and off-campus percentage captions; the static "Reporting period" card is replaced by a computed daily average. Three section labels (Traffic, Visitors, Network) with dividers group the charts and tables. Font Awesome icons added to all card titles for consistency with the rest of the site.

### Changed

- **Dark navy navbar and footer** — the navbar and footer now use a dark navy background (`--unc-navy` in light mode, `--unc-bolin-creek` for dark mode contrast) via CSS custom properties (`--site-chrome`, `--site-chrome-text`, `--site-chrome-link`). Navbar links are uppercase with letter-spacing, matching the ITS website style; hover color is Carolina Blue. Footer links use a lighter tint for legibility on the dark background.
- **Full-width navbar** — the navbar color now extends edge-to-edge, matching the ITS website layout. The link container remains constrained to the page width.
- **Compressed page title area** — vertical padding reduced and logo scaled down to match ITS website spacing conventions. Italic style removed from the site title. Tagline "Network diagnostics · UNC Information Technology Services" added below the title.
- **IP address bars redesigned as a hero element** — carolina blue tonal gradient background, larger IP text (2.6 rem, 700 weight), and elevated box shadow. IP version labels restored to the left side to keep the bars compact.
- **Loading animation on second IP bar** — a skeleton pulse plays while the second address is being detected, replaced by the result when it arrives.
- **Report button relocated** — moved from the navbar to the status row on the home page, right-justified alongside the connection status message. Keeps the navbar uncluttered and keeps the button adjacent to the data it exports.
- **Home page intro paragraph removed** — the three-sentence lead-in paragraph is removed. SEO coverage is maintained through the existing meta description, keywords, and JSON-LD structured data.
- **Section divider** added between the address bars and the card row on the home page.
- **Site Statistics:** "DNS provider" card renamed to "Internet DNS provider" for consistency with home page terminology.

### Fixed

- Footer social icons were invisible on the dark navy footer in both themes because a hardcoded inline `color` value overrode the CSS custom property. Removed the inline style so icons correctly inherit `--site-chrome-link`.
- FAQ and About pages had a double-nested `<div class="container">` wrapper; the base template already provides the container. Removed the redundant wrapper.
- Site Statistics last card row had no bottom margin, causing content to touch the footer. Added `mb-4` to the final row.
- Open Source card on the About page now uses the subtle tinted background (`--site-subtle-bg`) to match the visual treatment of the bottom card on the home page.
- Static asset cache busting: all CSS and JS `url_for` references across every template now append `?v={{ app_version }}` so browser caches are invalidated automatically on each version bump, preventing stale styles or scripts after a deploy.
- Mixed-network address detection: when a device's IPv4 and IPv6 addresses resolve to different networks (e.g., campus IPv4 with iCloud Private Relay routing IPv6 off-campus), a supplementary note is appended to the connection status message. Detects iCloud Private Relay by ISP name, VPN/proxy by the ip-api proxy flag, and falls back to a generic split-network message for other cases.

---

## [1.2.0] - 2026-06-30

### Added

- **NAC connection path diagram** displayed by default between the address bars and the More Details section. For wired connections the diagram shows: Your Device → Switch Port → Switch IP → Building. For wireless connections: Your Device → Access Point (with SSID) → Building. Nodes are rendered as circular icon badges connected by solid (wired) or dashed (wireless) lines.
- Connection path diagram adapts to screen size: vertical stacked layout on mobile (icon left, label right, short vertical connector), horizontal layout on larger screens.
- More Details button relocated from the connectivity card into the connection path row, right-justified and bottom-aligned, so it remains adjacent to the section it expands.

### Changed

- ISP and Org rows reordered in the address detail cards so Org appears immediately below ISP (both describe the same network entity).
- City and Region rows consolidated into a single **Location** row displayed as "City, State" — saves one row of vertical space. Falls back gracefully if only one value is returned by the location API.
- Detail cards (network config, building, device) now expand to the full page width rather than being capped at 560 px.

### Fixed

- More Details button was hidden for visitors without NAC data because the button moved inside the connection path row (`#nac-diagram-row`) which was only shown when NAC end system data was present. Fixed so any data that populates the expanded section also reveals the row and button.

---

## [1.1.0] - 2026-06-29

### Added

- Support report download: a **Report** button in the navigation bar (home page only) generates a self-contained, print-ready HTML page containing the user's IP addresses, connection status, campus network details, NAC information, network configuration, DNS results, and device details. The button is disabled until connection data has loaded, then activates automatically. Clicking it opens a new window from which the user can Save as PDF via the browser's Print dialog and attach the file to a help ticket.
- FAQ entry explaining how to use the Report feature, including keyboard shortcuts and popup blocker guidance.
- DNS metrics: client-side DNS test results are now reported back to the server for aggregate tracking. DNS provider (geo and IP from ip-api.com) and DNS security filtering status (active/inactive/inconclusive) are recorded as separate `dns_result` events so neither depends on the other's timing. The metrics database schema gains `dns_filtering`, `dns_ip`, `dns_geo`, `edns_ip`, and `edns_geo` columns with backward-compatible migrations.
- Site Statistics page gains two new charts: **DNS security filtering** doughnut (active/inactive/unable to verify split, with summary count table) and **DNS provider** breakdown table (top providers by geo label).
- All doughnut charts on the Site Statistics page now include a summary table beneath them showing exact counts and percentages.
- Protocol version chart changed from a doughnut to a vertical bar chart for better use of space and readability when only one or two protocols are present.
- Protocol version bar chart summary table removed; the y-axis and x-axis labels already convey the same information.

### Fixed

- Duplicate log lines in production: Flask's logger was propagating to Python's root logger, which gunicorn also captures, causing every `app.logger` call to appear twice. Fixed by setting `app.logger.propagate = False`.
- Reverse DNS lookup failures downgraded from WARNING to DEBUG; PTR records are absent for the majority of ISP and IPv6 addresses, making this a normal condition rather than an actionable warning.
- On-campus IPs with no matching network in IPAM now log at ERROR level with a distinct message (`has no matching network in IPAM`) rather than being silently folded into the no-Purpose warning.
- On-campus IPs found in IPAM but missing a Purpose extattr continue to log at WARNING, now clearly separated from the no-match case above.

---

## [1.0.2] - 2026-06-29

### Changed

- Header logo replaced with a new flat-style AI-generated illustration with a clean transparent background; favicon and web app manifest icon set regenerated from the new source
- Map card visible on initial page load with a subtle placeholder background instead of appearing after AJAX returns, eliminating horizontal layout shift of the address bar column (CLS improvement)
- Connection status line pre-populated with "Testing connection…" spinner on initial render instead of being empty, reserving space before the real status is written (CLS improvement)
- Leaflet map marker stamped with the location name as `alt` text; map container given `role="img"` and `aria-label` for screen readers

---

## [1.0.1] - 2026-06-28

### Added

- `?simulate=1` URL parameter returns anonymized RFC 5737 / RFC 3849 demo data (`192.0.2.50`, `2001:db8::50`) for both IPv4 and IPv6 hostinfo calls — useful for screenshots and local UI development without campus network access
- Screenshot added to `docs/` and displayed in README

### Changed

- Header logo replaced with a new flat-style illustration; favicon and web app manifest icon set regenerated from the new source; old favicon files removed from `static/img/`

### Fixed

- Dark mode: FAQ accordion items now inherit `--site-surface` / `--site-text` theme variables; collapsed chevron icon inverted for visibility
- Dark mode: Leaflet map tile pane rendered with CSS `invert` + `hue-rotate` filter so the map tracks the theme toggle automatically
- Dark mode: Metrics doughnut charts — replaced `#2C5080` (matches dark card surface, invisible) with lighter alternatives; added 2 px segment borders using the card surface color so adjacent slices remain distinct

---

## [1.0.0] - 2026-06-28

### Added

- Site-wide navigation bar (Home, Speed Test, About, FAQ, Site Statistics) with active-page highlighting and dark mode support
- Dedicated Speed Test page (`/speedtest`) with the Ookla Speedtest Custom iframe; home page links to it rather than embedding it inline
- FAQ page with accordion format, color-coded question groups, Font Awesome icons, and JSON-LD structured data
- Organization breakdown card on the metrics dashboard alongside ISP and country breakdowns
- UNC utility bar served locally (HTML + CSS) — eliminates the deferred external script that was causing a flash of unstyled content on page load
- HTTP caching: `Cache-Control: public, max-age=300` on HTML pages; `max-age=86400` on static assets; 5-minute in-memory TTL on the metrics SQLite queries
- `alt=""` stamped on Leaflet-generated map tile and marker images via MutationObserver (fixes Bing Webmaster Tools SEO notice)
- Application version (`1.0.0`) defined in `__init__.py`, injected into all templates, and displayed in the footer
- `data/config.toml.example` committed to the repository for easier onboarding
- `SECURITY.md` with responsible disclosure instructions
- `CONTRIBUTING.md` with development setup and contribution guidelines

### Changed

- Metrics page terminology: "lookups" → "visits", "Usage Metrics" → "Site Statistics" throughout UI, meta tags, and JSON-LD
- About and FAQ pages restyled: content pulled out of cards to match the site's wider layout; accordion replaces flat list on FAQ
- Page headings removed from About, FAQ, and Metrics pages (redundant with the navbar active state)
- Speedtest Server external link removed from footer
- Footer copyright line now includes the application version number
- IPv6 address overflow fixed on mobile using `overflow-wrap: anywhere` and `min-width: 0` on flex children
- `display-7` Bootstrap class (non-existent) removed from address headings on home page
- Navbar uses `flex-wrap: wrap` so links reflow gracefully on very narrow screens

### Fixed

- `data/` gitignore pattern changed from `data/` to `data/*` so the `!data/config.toml.example` negation rule takes effect correctly

---

## [0.x] - 2022-03-23 through 2026-06-27

Four years of active development and production use at UNC Chapel Hill ITS. This period covers the initial build, dual-stack IPv4/IPv6 detection, Infoblox IPAM integration, Extreme Networks NAC integration, geolocation, DNS security filtering, the metrics dashboard, dark mode, map support, and numerous refinements based on real-world use.

The full history of contributions during this period is available in the git log.
