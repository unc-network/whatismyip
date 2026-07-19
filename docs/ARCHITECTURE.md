# Architecture & Detection Flow

## Code structure

The application uses a Flask blueprint structure. `whatismyip/__init__.py` contains the `create_app()` factory; routes are split across `whatismyip/routes/` (`main.py` for the home page, `api.py` for `/hostinfo` and `/dns-result`, `pages.py` for static pages and error handlers, `metrics.py` for the dashboard). External API calls are organized by integration: `infoblox.py` (IPAM), `extreme.py` (XMC/NAC), `meraki.py` (Meraki Dashboard), and `utils.py` (geolocation, building lookup, shared helpers). Metrics storage lives in `whatismyip/db.py` and site config loading in `whatismyip/site_config.py`.

## Detection flow

### Step 1 — Client IP (from HTTP)

The visitor's IP is read from the HTTP connection at request time (`X-Forwarded-For` is respected when behind a proxy). This is the only thing known at the start of a request.

### Step 2 — Infoblox IPAM (queried by IP)

`get_address_objects(ip)` hits the Infoblox WAPI (`ipv4address` or `ipv6address` endpoint, depending on IP version). Returns whatever IPAM knows about that address:

- DNS hostnames, record types, and usage flags
- DHCP lease state
- Extended attributes: Admin Onyen, Administrator name, Admin Email, Department
- **MAC address** — only present when IPAM has an active DHCP lease for this IP; absent for static IPs, expired leases, and most IPv6 addresses

The MAC from IPAM is passed into Step 3 as the preferred lookup key.

### Step 3 — NAC / Extreme XMC (MAC-first, IP fallback)

`get_nac_info(ip, mac)` runs up to three XMC NBI calls, stopping early when data is found:

1. **By MAC** — `getEndSystemByMac(mac)`: attempted first if IPAM provided a MAC address in Step 2. NAC operates primarily on MAC addresses; IP-to-session mappings are populated by supplemental data feeds and may lag behind the current session.
2. **By IP fallback** — `getEndSystemByIp(ip)`: attempted if no MAC was available from IPAM, or if the MAC lookup returned nothing. Covers cases where IPAM has no active DHCP lease for the address.
3. **Device profile** — `getMacAddress(mac)`: once any MAC is known (from either NAC result above, or directly from the IPAM fallback), fetches the device's persistent profile — vendor, device type, registration info, etc.

**Important constraints:**

- NAC is only queried for campus IPv4 addresses. IPv6 campus clients skip NAC entirely.
- If both the IP lookup and the IPAM MAC path miss, no NAC data is returned and the NAC and device cards are hidden.

### Step 4 — Building lookup via NIT (by switch IP or AP building ID)

After NAC returns, `switchPortId` is inspected with a regex to determine connection type:

- **Wired** — `switchPortId` is a plain port string (e.g. `GigabitEthernet1/0/24`): calls `get_nit_building(switchIP)` which looks up the building by the switch's IP address.
- **Wireless** — `switchPortId` matches the AP pattern `<name> (<mac>):<ssid>`: the AP name is parsed for a building ID prefix (e.g. `EP-0162-...` → building `0162`), then `get_nit_building_by_id(bldg_id)` is called directly.

Both NIT calls return a building record with `official_name`, `full_name`, `address`, `building_id`, `latitude`, and `longitude`.

## Where each field comes from

| Field | Source | Notes |
| --- | --- | --- |
| IP address | HTTP connection | Always present |
| IP version, private/global flags | Python `ipaddress` stdlib | Always computed |
| ISP, geolocation, ASN | ip-api.com | Public IPs only |
| DNS hostnames, record types | Infoblox IPAM | Campus only |
| DHCP lease state, server, router | Infoblox IPAM | Campus only; DHCP leases only |
| MAC address | Infoblox IPAM (DHCP lease) | May be absent |
| Admin contact info | Infoblox extattrs | Campus only |
| Switch port / AP / policy | Extreme XMC (by IP, then MAC) | Campus IPv4 only |
| Device vendor / type profile | Extreme XMC `getMacAddress` | Requires a MAC from Step 2 or 3 |
| Building name, address, map | NIT building API | Derived from switch IP or AP name |
| AP name, SSID, VLAN | Meraki Dashboard API | Meraki wireless only |
| Signal quality (RSSI, SNR) | Meraki Dashboard API | Meraki wireless only |
