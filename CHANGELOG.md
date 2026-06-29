# Changelog

All notable changes to this project will be documented here. This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) conventions.

## [1.0.1] - 2026-06-28

### Added

- `?simulate=1` URL parameter returns anonymized RFC 5737 / RFC 3849 demo data (`192.0.2.50`, `2001:db8::50`) for both IPv4 and IPv6 hostinfo calls — useful for screenshots and local UI development without campus network access
- Screenshot added to `docs/` and displayed in README

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
