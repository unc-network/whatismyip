# Changelog

All notable changes to this project will be documented here. This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) conventions.

## [1.9.4] - 2026-07-21

### Fixed

- **Intro status sub-line race condition (IPv6-default path)** — when the browser's default connection is IPv6, the primary (IPv4) callback previously never called `set_intro_text`, so the sub-line container was uninitialized at the time the external IP lookup completed. If the ipify response arrived before the secondary callback, the "Your internet traffic exits via…" sub-line was appended to the spinner element and then wiped when the secondary callback replaced the entire intro container. The primary callback now always seeds the intro status regardless of default version, so the container is always initialized before `checkNATType` resolves.

### Changed

- **IP lookups chart — stacked by protocol** — the "IP lookups over time" line chart is now a stacked area chart showing IPv4 and IPv6 as separate layers. The total height per day is unchanged; the IPv6 contribution is visible as a darker navy band at the bottom with the light-blue IPv4 area stacked above. Tooltip shows each protocol's count and a total footer. A legend is shown top-right.
- **Metrics page views tracked** — visits to the `/metrics` dashboard are now included in the page views breakdown table and over-time chart alongside Home, About, FAQ, Speed Test, and Connectivity.
- **Page views chart visual balance** — the page views card body uses a flex-column layout so the chart fills the available height and better aligns with the breakdown table card beside it.
- **Metrics query consolidation** — the three separate `COUNT` queries for total, on-campus, and off-campus lookup totals are now a single aggregation query, reducing table scans from three to one on each cache miss.

## [1.9.3] - 2026-07-21

### Fixed

- **Intro status sub-line race condition** — the "Your internet traffic appears to use a different address" line was intermittently wiped when the IPv6 callback fired and called `set_intro_text` after the external IP lookup had already appended the sub-line. The main status message is now updated in place rather than replacing the full container, so appended sub-lines are preserved regardless of callback timing.

### Changed

- **Metrics charts exclude current day** — the IP lookups and page views over time charts now show only complete days, ending at yesterday. Today's partial count is no longer the final data point, eliminating the misleading drop at the right edge of both charts.
- **Metrics cache TTL extended** — the dashboard aggregation cache increased from 5 minutes to 30 minutes. Complete-day data is stable until midnight, so the prior 5-minute TTL was unnecessarily frequent for a dataset of this size.
- **Simulate mode additions** — simulated network configuration now includes a contact name, and the network CIDR, subnet mask, and gateway are corrected to be consistent with the simulated device address.

## [1.9.2] - 2026-07-19

### Added

- **Network Contact row** — the Network Configuration card now shows the network administrator name (sourced from the Infoblox "Administrator" extended attribute) when present. The row is hidden when no contact is recorded.

### Changed

- **Wireless Connection card row order** — rows reorganized into four logical groups: connection state (Last Seen, Client MAC, Status, Signal RSSI, Signal/Noise), identity (User, SSID, VLAN), device details (Capabilities, Manufacturer, Device, OS), and infrastructure (Access Point, AP MAC, AP Model, Controller).
- **EDNS Client Subnet display** — now formatted the same as Internet DNS Provider: organization on the first line, country on the second, IP on the third. Previously the raw "Country - Organization" string was displayed unsplit.
- **About page** — removed the "Further detail is available via NIT" list item; it is only relevant to authorised staff and adds noise for general users.
- **Simulate mode** — DNS and EDNS rows now inject static campus-realistic data instead of making a live ip-api.com call; the simulated network range, subnet mask, and gateway are now self-consistent with the device address; all infrastructure addresses and identifiers use RFC 5737 documentation values (`192.0.2.x`) and locally-administered MACs; real external IP no longer leaked via the NAT egress message.

### Documentation

- **Simulate mode documented** — `README.md` now includes a dedicated section explaining `?simulate=4` / `?simulate=6`, what the simulated session covers, and that it is safe to use in production for demos.
- **Detection flow extracted** — the 4-step enrichment pipeline and field source table moved from `README.md` to `docs/ARCHITECTURE.md` to keep the README focused on setup and deployment.
- **Deployment guides moved** — `DOCKER.md` and `OPENSHIFT.md` relocated to `docs/` to reduce root-level clutter; README links updated.
- **Screenshot updated** — README hero image updated to `docs/whatismyip.jpeg`.

## [1.9.1] - 2026-07-13

### Changed

- **Metrics dashboard terminology** — "visits" replaced with "lookups" throughout the IP lookup stat cards, table column headers, and chart tooltips. DNS card column headers changed from "Tests" to "Lookups" for consistency. Page view data retains "views".
- **Metrics dashboard sections reorganised** — Connection origin and Network type cards moved from the Network section into Visitors (where they conceptually belong). The remaining section renamed from "Network" to "DNS", now containing only the Campus DNS Security and Internet DNS provider cards.

## [1.9.0] - 2026-07-13

### Added

- **Page view tracking** — a new `page_views` SQLite table records a timestamped entry on each visit to Home, About, FAQ, Speed Test, and Connectivity. `/health` visits are excluded.
- **Page views over time chart** — the `/metrics` dashboard now shows a windowed daily line chart of page views alongside the existing IP lookup trend, and an all-time breakdown table (page, views, share) below it.
- **Dedicated `/health` endpoint** — lightweight plain-text `200 OK` with no template or database overhead, for liveness and readiness probes. Replaces the previous `/about` probe target. Docker Compose healthcheck updated to use it; OpenShift probe will be updated once this version reaches production.
- **OpenShift deployment guide** — `OPENSHIFT.md` covers the full deployment workflow: S2I build setup, secret creation for all integrations, PVC provisioning, Route setup, config.toml upload, and day-to-day operations (logs, rollback, backup). Includes notes on the Recreate strategy requirement (SQLite + ReadWriteOnce PVC) and dual-stack DNS setup.
- **`openshift/deployment.yaml`** — clean deployment manifest derived from the UNC production deployment: runtime metadata stripped, `CHANGEME` placeholders for institution-specific values, all optional integration secrets marked `optional: true`, and probes targeting `/health`.
- **`openshift/pvc.yaml`** — PersistentVolumeClaim manifest for the data directory.

### Changed

- **Metrics dashboard layout** — Traffic section reorganised into two balanced rows: IP lookups over time + Protocol version (row 1); Page views over time + Page views breakdown table (row 2). The lookup trend chart is now labelled "IP lookups over time" to clearly distinguish it from page view counts.

## [1.8.0] - 2026-07-11

### Added

- **Docker deployment support** — the repository now ships a production-ready Docker Compose configuration so other institutions can run the tool without OpenShift or Kubernetes. Includes a minimal `Dockerfile` (Python 3.11-slim, non-root `appuser`, gunicorn), a `docker-compose.yml` with an nginx sidecar for SSL termination, and a sample `nginx/nginx.conf` with HTTP→HTTPS redirect and correct `X-Forwarded-For` passthrough. The Flask container is on an internal Docker network only (no host port binding); only nginx ports 80 and 443 are published externally.
- **`DOCKER.md`** — comprehensive step-by-step deployment guide written for network teams with Docker experience but without Python development background. Covers setup, SSL certificates (including self-signed for testing), environment variables, all optional campus integrations (Infoblox, XMC, Meraki), day-to-day operations (logs, update, backup), branding customization, and troubleshooting.
- **`nginx/certs/` directory tracked** — the directory is now committed (via `.gitkeep`) so a fresh clone has the expected bind-mount path in place; actual certificate files (`*.pem`, `*.key`, etc.) remain gitignored.

## [1.7.4] - 2026-07-10

### Fixed

- **X-Forwarded-For single-IP crash** — `get_client_address` raised `IndexError` when the header contained exactly one IP address (the common single-proxy case). The else branch now correctly falls back to `fwd_list[0]` instead of `fwd_list[-2]`.
- **MAC address validation before GraphQL interpolation** — `getMacAddress` and `getEndSystemByMac` in the XMC NBI client now reject values that do not match the expected MAC format before inserting them into the GraphQL query string, preventing injection from a malformed internal data source.
- **Unbounded string input on `/dns-result`** — `dns_ip`, `dns_geo`, `edns_ip`, and `edns_geo` fields posted by the client are now truncated to a maximum length (64 / 200 chars) before being stored in the metrics database, preventing disk exhaustion from a flood of large payloads.
- **ip-api.com rate limit handling** — geolocation results are now cached in memory per IP for 5 minutes (up to 1,000 entries), reducing external API calls for repeat visitors. HTTP 429 responses from ip-api.com now log a distinct warning including the window reset time (`X-Ttl` header) instead of the generic failure message.
- **DNS test error visibility** — browser-side DNS provider test failures now display "Unavailable" in the DNS row instead of leaving it blank.
- **IndexNow ping missing `/metrics`** — `scripts/indexnow_ping.py` now includes the Site Statistics page, matching all six URLs in the sitemap.
- **Sitemap date updated** — home page `lastmod` updated to 2026-07-10.

## [1.7.3] - 2026-07-08

### Changed

- **RSSI Fair/Poor threshold adjusted** — updated from −75 dBm to −70 dBm per wireless team guidance. Thresholds are now: ≥ −65 dBm Good, ≥ −70 dBm Fair, < −70 dBm Poor.
- **Internet DNS Provider display reformatted** — the provider string is now split across three lines in order: company name, country, IP address. Previously the single "Country - Company" string wrapped awkwardly mid-word.

## [1.7.2] - 2026-07-05

### Fixed

- **Leaflet map tile alt text** — Leaflet generates tile `<img>` elements with `alt=""` which Bing Webmaster Tools flags as missing alt. A MutationObserver now stamps `alt="OpenStreetMap tile"` on every tile image as it is added to the DOM, resolving the SEO notice.
- **Meta description length** — the home page meta description was 175 characters, exceeding Bing's 150–160 character limit. Trimmed to 153 characters without losing keyword coverage.

### Changed

- **DNS provider FAQ entry added** — new accordion question "What does the DNS provider check show?" explains the DNS leak test angle: on campus or VPN users should see UNC or Akamai (UNC forwards all DNS queries through Akamai for security filtering); seeing a home ISP instead indicates a DNS leak or misconfiguration. Includes scenarios for privacy DNS services. JSON-LD structured data updated to match.
- **Site meta tags updated for DNS detection** — keywords expanded to include "DNS leak test", "DNS provider", "DNS resolver"; descriptions across meta, Open Graph, and Twitter cards now call out DNS provider detection alongside DNS security filtering.
- **Home page and FAQ feature lists updated** — "What does this tool show?" sections on both pages now include Wi-Fi connection details and DNS provider detection as campus features. JSON-LD featureList updated to include "DNS provider detection" and "DNS leak test".
- **NAC redundant group description fields hidden** — the two raw group description fields from XMC are no longer shown in the NAC table since the same information is already present in the Groups row.
- **Wireless Connection card adds Last Seen and Client MAC** — the Meraki client search response already includes a last-seen timestamp and the client MAC address; both are now surfaced in the Wireless Connection card. The MAC displays a warning indicator if it does not match the MAC on record in IPAM, which can signal MAC randomization or an association mismatch.

## [1.7.1] - 2026-07-05

### Added

- **Device Address row in network configuration** — the IPv4 and IPv6 sections of the Network Configuration card now open with the detected device address as the first row, making it immediately clear which address the section describes.
- **Simulate mode clock sync** — the `?simulate=` API response now includes a live `server_time` timestamp so the clock synchronization check runs and displays correctly in demo mode without a real campus connection.

### Changed

- **More Details layout reorganized** — left column: Your Device → Campus Building → Network Access Control; right column: Network Configuration → Wireless Connection. Campus infrastructure is grouped on the left; network and wireless detail on the right. Column widths are fixed so the layout is consistent regardless of which cards appear.
- **Wireless Connection card now shows Aruba data** — when a campus device is on an Aruba wireless network (no Meraki enrichment), the SSID, access point name, AP MAC, and controller IP from the NAC record are now surfaced in the Wireless Connection card. Previously this data was buried in the NAC table.
- **NAC table restructured** — rows now render in a fixed logical order: Connected time → IP Address → MAC Address → NAC appliance fields (group, profile, appliance) → Policy → Reason → Groups → switch data. "Controller" relabeled "Wireless Controller" for clarity. Wired connections show Switch IP and Port; wireless shows Wireless Controller and AP MAC.
- **Signal quality display** — RSSI and SNR readings now use the same icon-and-color pattern as the clock sync indicator: a green check for Good, yellow warning triangle for Fair, and red X for Poor. Thresholds: RSSI ≥ −65 dBm / SNR ≥ 25 dB = Good; ≥ −75 / ≥ 15 = Fair; below = Poor.
- **Location row includes country** — the Location row in the address detail cards now reads "City, Region, Country" in a single row. The separate Country row has been removed.
- **Internal code organization** — Infoblox IPAM calls moved to a dedicated `infoblox.py` module, consistent with the existing Meraki and Extreme integrations. Off-campus visitors no longer trigger any campus-specific API calls.
- **Sitemap updated** — entries reordered to match navbar then footer order (Home → Speed Test → Connectivity → FAQ → About → Site Statistics); priorities aligned to decrease with nav position; `lastmod` dates updated.

### Fixed

- **NAC card blank in simulate mode** — `esc` was defined inside `buildNacDiagram` and not available in the AJAX callback that populates the NAC table rows. The NAC section now uses a locally-scoped `escHtml` helper, restoring correct display in simulate mode.
- **Redundant NAC group description fields hidden** — the two raw group description fields from XMC are no longer shown in the NAC table since the same information is already present in the Groups row.

## [1.7.0] - 2026-07-04

### Added

- **Cisco Meraki wireless enrichment** — when a campus device is connected to a Meraki AP, the server now optionally queries the Meraki Dashboard API to enrich the connection data. AP name lookup populates the connection diagram and feeds the existing building lookup flow. Client lookup retrieves manufacturer, device description, wireless status, SSID, VLAN, and capabilities. Both calls fail silently — Aruba clients and unconfigured deployments are completely unaffected. Enabled by setting `FLASK_MERAKI_API_KEY` and `FLASK_MERAKI_ORG_ID` environment variables.
- **Wireless Connection card** — Meraki wireless details (manufacturer, device, OS, user, status, SSID, VLAN, signal quality, AP model) are presented in their own dedicated card in the More Details section.
- **Wi-Fi signal quality** — the Wireless Connection card shows current signal strength (RSSI in dBm) and signal-to-noise ratio (SNR in dB), each labeled Good, Fair, or Poor. The same values are annotated directly on the dashed wireless link in the connection path diagram.

### Changed

- **More Details layout reorganized** — cards are now arranged with wireless-relevant information on the left (Wireless Connection, Your Device, Network Configuration) and campus infrastructure detail on the right (Network Access Control, Campus Building). This order better matches the information most wireless users are looking for first.

## [1.6.3] - 2026-07-03

### Fixed

- **Campus DNS Security label on metrics page** — the Site Statistics page still showed "DNS security filtering" as the card title; updated to match the rename in 1.6.2.

### Changed

- **Canonical URL consolidated** — `<link rel="canonical">` moved from individual page templates into `base.html`, using `site_url + request.path` automatically. Error pages (404, 500) suppress the tag via a block override. Any future page template gets the correct canonical for free.
- **Navbar simplified** — Site Statistics removed from the top navigation; it remains accessible via the footer. This also prepares for a potential future password-protection of that page without leaving a broken nav link.
- **Footer "Explore" trimmed** — reduced to three links (FAQ, About, Site Statistics), removing Speed Test and Connectivity which are already prominent in the navbar.

### Added

- **IndexNow ping script** — `scripts/indexnow_ping.py` reads the `indexnow_key` from `data/config.toml` and `SERVER_URL` from `.env`, then POSTs all public pages to Bing IndexNow. Run manually from the repo root after confirming a production deployment is live. Refuses to run if `SERVER_URL` points to localhost.

## [1.6.2] - 2026-07-03

### Fixed

- **IP protocol label pill** — the `IPv4`/`IPv6` badge inside the address copy card was restyled to match the card's color scheme: dark semi-transparent background (`rgba(0,0,0,0.35)`) with white text, consistent with the IP address and copy icon. Removed `text-transform: uppercase` so the label reads `IPv4`/`IPv6` matching the Campus Connectivity and Address Details cards. Empty state (during page load before the label is populated) no longer shows a visible placeholder chip.
- **Campus Connectivity card spacing** — the Campus DNS Security and Internet DNS Provider rows now sit flush against the connectivity test rows, visually reading as a single unified table. Previously a 1rem Bootstrap table margin and extra top margin created a noticeable gap between the two sections.

### Changed

- **"DNS Security Filtering" renamed to "Campus DNS Security"** — the label in the Campus Connectivity card, the downloadable support report, and the FAQ question have all been updated to clarify that this is a campus-specific protection. The UNC knowledge base article link in the FAQ retains the official UNC service name.
- **Navbar and footer order** — FAQ moved before About in the navbar to surface the most commonly-needed informational page sooner. The footer "Explore" column reordered to match (Speed Test → Connectivity → FAQ → About → Site Statistics); Connectivity was also missing from the footer and has been added.

---

## [1.6.1] - 2026-07-03

### Fixed

- **Duplicate `<h1>` tags on all non-home pages** — the site title in the base template was an `<h1>`, causing every interior page to have two `<h1>` elements (the site title and the page heading). The base template now renders the site title as a `<p class="site-title">` styled to match; `home.html` overrides the block back to `<h1>` so the home page retains a single correct heading for SEO.
- **Leaflet map tile images missing alt text** — Leaflet generated tile `<img>` elements with `alt=""` (empty), which Bing Webmaster Tools flagged as missing. Added `alt: 'OpenStreetMap tile'` to the `L.tileLayer` options so Leaflet sets a descriptive alt on every tile natively.
- **WCAG 2.2 Level AA accessibility** — comprehensive review and remediation across all templates, CSS, and JavaScript against the W3C standard. Critical fixes: dynamic diagnostic results now use `aria-live="polite"` so screen readers announce connection status, DNS results, and connectivity test outcomes without manual navigation; the IP copy cards no longer suppress focus outlines (`:focus { outline: none }` removed); the download report control is now a native `<button disabled>` instead of an `<a aria-disabled>` so keyboard activation is correctly blocked while data loads. Major fixes: FAQ section label colors darkened in light mode (Bootstrap `text-warning`/`text-info`/`text-primary` at 0.75rem failed 4.5:1 on white) with matching dark-mode overrides; footer section headings changed from `<p>` to `<h2>` elements for heading navigation; redundant `aria-label` attributes removed from footer links where visible text already serves as the accessible name; 500 error page given a distinct `<title>`; skip navigation restructured so "Skip to main content" is the first focusable element in the page and the two skip landmarks have distinct names. Minor fixes: all dynamically-injected Font Awesome icons given `aria-hidden="true"` (decorative) or `role="img" aria-label` (content-carrying); `#copy-notification` aria-live region moved to HTML so screen readers register it at page load rather than first click; social media icon links padded to meet the 24×24 px minimum touch target (WCAG 2.5.8); all data tables given `<caption class="visually-hidden">` and `scope="row"` on header cells; Leaflet marker popup no longer auto-opens inside a `role="img"` container; theme toggle button moved after heading content in DOM so tab order matches visual left-to-right sequence; connectivity page status cells given `aria-live="polite"`.

### Changed

- **README updated** — architecture and detection flow sections now reflect the blueprint structure introduced in 1.5.0; gunicorn command corrected from `"whatismyip:app"` to `wsgi:application`; running tests section expanded to include the coverage invocation.
- **FAQ external services entry corrected** — the answer previously said "yes, in one case" but the browser contacts up to three external services (ip-api.com for DNS provider, ipify.org for internet IP, and the DNS security test domain). All three are now listed accurately.
- **`.gitignore` updated** — added `.ruff_cache/` and `.claude/`.

---

## [1.6.0] - 2026-07-02

### Added

- **Internet path detection** — the page now makes a client-side request to ipify.org to check what IPv4 address internet servers see for the visitor's connection. This is compared against the address the campus server detected. When they differ, a note is appended to the connection status message explaining the situation with context-aware wording: split-tunnel VPN (campus VPN address + internet exits directly), campus NAT (wireless and other networks that use a different public IP for internet-bound traffic), or a generic split-path message when network purpose data is not available. The detected internet address is also included in the downloadable support report under the Connectivity section. A FAQ entry explains why the tool contacts an external service.

---

## [1.5.0] - 2026-07-02

### Changed

- **Wireless connection path diagram now includes the wireless controller** — the controller IP (`switchIP` from NAC) is shown as the final node in the connection path for all wireless connections. For named AP connections where a building is resolved, the order is Device → AP → Building → Controller. For Meraki-style connections where no building is available, the order is Device → AP → Controller. The controller is rendered with a server icon to distinguish it from campus access switches.
- **Application refactored to Flask application factory pattern** — `__init__.py` replaced with a `create_app()` factory; routes split into four blueprints (`main`, `api`, `pages`, `metrics`). Enables proper test isolation and is required for gunicorn multi-worker deployments.
- **Star imports removed** — all `from module import *` replaced with explicit named imports throughout.
- **Utility return type consistency** — `get_network`, `get_address_objects`, `get_ip_location`, `get_nit_building`, and `get_nit_building_by_id` now return `None` instead of `{}` when no result is found. An empty dict is truthy in JavaScript (causing the frontend to treat absent data as present); `None` serializes to `null` and is correctly treated as absent. A side effect: IP location API timeouts now trigger the same fallback dict as other failures rather than silently returning empty data.
- **Ruff lint rules expanded** — isort (`I`), pyupgrade (`UP`), and warnings (`W`) rule sets enabled. Import ordering enforced; `logger.warn()` corrected to `logger.warning()` (deprecated alias); percent-format logger calls converted to f-strings; Python 3.10+ union type syntax adopted throughout.
- **Dead code removed** — commented-out `getWhoIs` block and the unused `get_forwarded_address` function deleted from `utils.py`.
- **Type annotations added** to all public functions across `utils.py`, `db.py`, `site_config.py`, and all route modules.

### Added

- **Test suite expanded to 41 tests** — new test modules cover `db.py` (metrics store, event logging, dashboard queries), `pages.py` (static pages, redirects, error handlers, IndexNow key serving), and `site_config.py` (valid config, invalid CIDR skipping, unknown map provider fallback, missing/broken TOML). SQLite tests use `tmp_path` fixtures for isolation from the production PVC mount.

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
