# Changelog

All notable changes to this project will be documented here. This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) conventions.

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
