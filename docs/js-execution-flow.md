# JavaScript Execution Flow — What Is My IP?

A plain-English walkthrough of `whatismyip.js` from page load to final rendered state.

---

## Global State

Before anything runs, these variables are declared at module scope. They act as the shared memory between the two concurrent AJAX callbacks.

| Variable | Purpose |
| --- | --- |
| `reportDataIPv4` | Full API response from the **IPv4** endpoint. Null until that call succeeds. |
| `reportDataIPv6` | Full API response from the **IPv6** endpoint. Null until that call succeeds. |
| `reportNetworkPurpose` | Network purpose string (e.g. `"Wireless"`, `"VPN"`). Whichever callback completes last wins. |
| `reportInternetIp` | External IP returned by ipify. Set only when the NAT sub-line fires. |
| `proxyNoticeShown` | Flag preventing the iCloud/proxy sub-line from appearing twice. |
| `ipv4Resolved` | Set to true when the IPv4 callback completes (success or error). |
| `ipv6Resolved` | Set to true when the IPv6 callback completes (success or error). |
| `reportConnectV4/V6` | Connectivity status strings used in the downloadable report. |
| `reportDns*` | DNS check results, populated by a separate `get_dns_info()` flow. |

---

## Phase 1 — Page Load (`document.ready`)

The server renders the initial HTML including two hidden JSON blobs: `is_campus` and `default_address`. `document.ready` reads them to determine which protocol connected the user to the page.

```text
default_address contains ":"  →  default_version = 6  (IPv6 loaded the page)
default_address has no ":"   →  default_version = 4  (IPv4 loaded the page)
```

`default_version` controls **display order only** — which address bar appears on top, which label appears in the Campus Connectivity card. It does NOT control which URL is called.

Immediately after setting `default_version`, three things fire simultaneously:

```text
test_ipv4_url(default_version)   ← always calls the IPv4 endpoint
test_ipv6_url(default_version)   ← always calls the IPv6 endpoint
get_dns_info()                   ← deferred via requestIdleCallback
```

---

## Phase 2 — IPv4 Callback (`test_ipv4_url`)

**Fires concurrently with Phase 4** — both AJAX calls are launched simultaneously at page load. Either can complete first. **Always calls `ipv4_url/hostinfo`.** The `default_version` parameter only affects which DOM elements get updated.

On success, in order:

1. **`set_intro_text(is_campus, purpose)`** — always called. Updates `#intro-main-status` from the loading spinner to the real status line. If the element has already been set by the other callback with a specific purpose (VPN, Wireless), a null-purpose call from this side is ignored so the more specific message is preserved.

2. **Address bar** — shows the IPv4 address in the top bar (if `default_version == 4`) or the second bar (if `default_version == 6`).

3. **Address details card** — populates IPv4 ISP, Org, Location, ASN, DNS names, MAC, comment, username rows.

4. **Map** — plots the user's location using Meraki AP coordinates, building coordinates, or ip-api.com lat/lon as a fallback.

5. **Wireless / Meraki card** — populates SSID, AP name, signal strength if the result includes NAC/Meraki data.

6. **Building card** — populates building name and address if present.

7. **Device card** — populates user agent details.

8. **Network config card (IPv4 section)** — populates netmask, gateway, DNS servers, domain.

9. **`reportNetworkPurpose = result['network']['purpose']`** — stores the purpose string.

10. **`reportDataIPv4 = result`** — stores the full result.

11. **`ipv4Resolved = true`** — marks the IPv4 protocol as settled.

12. **`checkAddressMismatch()`** — requires both `reportDataIPv4` and `reportDataIPv6` to be non-null. Returns immediately if the IPv6 result is not yet available.

13. **`checkProxyNotice()`** — requires both `ipv4Resolved` and `ipv6Resolved`. Returns immediately if the IPv6 callback has not yet settled.

14. **`checkNATType(result['client_address'])`** — kicks off the ipify check (Phase 3 below). This is async — it does not block or wait here.

15. **`reportConnectV4/V6 = 'Supported'`** — updates the connectivity status for the report.

16. **Report button enabled.**

On error: marks the IPv4 bar "Not supported." If IPv4 was the default protocol (`default_version == 4`), calls `showPrimaryLoadError()`. Sets `ipv4Resolved = true` and calls `checkProxyNotice()` — if IPv6 has already settled, this triggers the proxy check with the full picture.

---

## Phase 3 — ipify Check (`checkNATType` / `fetchExternalIPv4` / `renderNATResult`)

**Fires concurrently with Phases 2 and 4** — the ipify fetch starts inside the Phase 2 success handler and runs independently. It may complete before or after the IPv6 callback.

```text
checkNATType(serverIp)
  └─ fetchExternalIPv4()          ← fetch to api4.ipify.org, 5 s timeout
       └─ renderNATResult(serverIp, externalIp, reportNetworkPurpose)
```

`renderNATResult` decides whether to show the NAT sub-line:

- Returns immediately if `serverIp` is IPv6 (dead-code guard — never reached in practice since only the IPv4 callback calls `checkNATType`).
- Returns if `externalIp` is null or matches `serverIp` (no NAT — paths agree).
- Returns if `proxyNoticeShown` is true (both protocols have settled and a relay was detected).
- Returns if either result (`reportDataIPv4` or `reportDataIPv6`) shows iCloud, Private Relay, Cloudflare WARP, or `proxy = true` — relay services rotate exit IPs between requests so the difference is not meaningful.
- Otherwise populates and shows `#intro-sub-nat` with one of three messages based on `reportNetworkPurpose`:
  - VPN → "Internet traffic bypasses the VPN tunnel and exits via `{ip}`."
  - Campus/wireless → "Your internet traffic exits the campus network as `{ip}`."
  - Off-campus (falsy purpose) → "Your internet traffic appears to use a different address (`{ip}`) than your campus connection."

The `#intro-sub-nat` slot is declared in the initial HTML, so it is always present in the DOM when `renderNATResult` runs.

---

## Phase 4 — IPv6 Callback (`test_ipv6_url`)

**Fires concurrently with Phase 2** — both AJAX calls are launched simultaneously at page load. Either can complete first. Phase 3 (ipify) may also complete during this time. **Always calls `ipv6_url/hostinfo`.**

On success, in order:

1. **Address bar** — shows the IPv6 address in the top bar (if `default_version == 6`) or the second bar (if `default_version == 4`).

2. **`set_intro_text(is_campus, purpose)`** — called **only when `default_version == 6`** (IPv6 loaded the page). When IPv4 loaded the page, this is skipped — the main line was already set in Phase 2 and the IPv6 result is supplemental.

3. **Address details card** — populates IPv6 ISP, Org, Location, ASN, DNS names, MAC, comment, username rows.

4. **Network config card (IPv6 section)** — populates router, domain, contact rows.

5. **`reportNetworkPurpose = result['network']['purpose']`** — updates the shared purpose string (last callback wins).

6. **`reportDataIPv6 = result`** — stores the full result.

7. **`ipv6Resolved = true`** — marks the IPv6 protocol as settled.

8. **`checkAddressMismatch()`** — requires both `reportDataIPv4` and `reportDataIPv6` to be non-null. Returns immediately if the IPv4 result is not yet available.

9. **`checkProxyNotice()`** — requires both `ipv4Resolved` and `ipv6Resolved`. If IPv4 has already settled, this is the call that triggers the actual proxy check.

10. **`reportConnectV4/V6 = 'Supported'`** — updates connectivity status.

On error: marks IPv6 bar "Not supported." If IPv6 was the default protocol (`default_version == 6`), calls `showPrimaryLoadError()`. Sets `ipv6Resolved = true` and calls `checkProxyNotice()` — if IPv4 has already settled, this triggers the proxy check using only the IPv4 result (single-stack IPv4 case).

---

## Coordination Functions

`checkAddressMismatch` runs at the end of both success callbacks. `checkProxyNotice` runs at the end of all four callback paths (both success, both error) but gates on both resolved flags before doing any work.

### `checkAddressMismatch()`

```text
Both reportDataIPv4 and reportDataIPv6 must be non-null → otherwise return.
is_campus matches between them → return (both agree; no mismatch note needed).
is_campus differs → populate #intro-sub-mismatch based on the off-campus result's ISP/org/proxy flag.
```

Three possible mismatch notes:

- iCloud/Private Relay in off-campus ISP or org → "iCloud Private Relay is routing one of your addresses off-campus."
- `proxy = true` or Cloudflare WARP in off-campus org → "A VPN or proxy service is routing one of your addresses off-campus."
- Neither → "Your two addresses are on different networks — one campus, one off-campus."

### `checkProxyNotice()`

Called from all four callback paths but guards on both `ipv4Resolved` and `ipv6Resolved` being true before doing any work. Whichever callback settles last triggers the actual check.

```text
proxyNoticeShown already true → return (prevents double-firing).
ipv4Resolved or ipv6Resolved not yet true → return (wait for both to settle).
Both loaded and is_campus differs → return (mismatch already handled it).
No off-campus result available → return (nothing to warn about).
Check isp and org on any available result for /icloud|private relay/i or /cloudflare warp/i, or proxy flag.
Match found → set proxyNoticeShown = true, populate #intro-sub-proxy.
No match → return silently.
```

Two possible proxy notices:

- iCloud/Private Relay detected → "iCloud Private Relay is active — your actual network location may differ from what is shown."
- Cloudflare WARP or `proxy = true` → "A VPN or proxy service is active — your actual network location may differ from what is shown."

---

## Typical Timing Diagram

```text
page load
│
├─ test_ipv4_url()  ─────────────────────────────────────────┐ IPv4 AJAX
│                                                            ↓              ↓
│                                                   [IPv4 success]    [IPv4 error]
│                                                   set_intro_text()  mark bar failed
│                                                   render cards, map ipv4Resolved = true
│                                                   reportDataIPv4 = result  checkProxyNotice()
│                                                   ipv4Resolved = true        → waits if !ipv6Resolved
│                                                   checkAddressMismatch()
│                                                     → waits if reportDataIPv6 null
│                                                   checkProxyNotice()
│                                                     → waits if !ipv6Resolved
│                                                   checkNATType() ← ipify fetch starts (async)
│
├─ test_ipv6_url() ────────────────────────────────────────┐ IPv6 AJAX
│                                                          ↓              ↓
│                                                 [IPv6 success]    [IPv6 error]
│                                                 render cards      mark bar failed
│                                                 reportDataIPv6 = result  ipv6Resolved = true
│                                                 ipv6Resolved = true       checkProxyNotice()
│                                                 checkAddressMismatch()      → runs if ipv4Resolved,
│                                                   → waits if reportDataIPv4 null  checks what's available
│                                                 checkProxyNotice()
│                                                   → runs if ipv4Resolved,
│                                                     checks both results
│
└─ get_dns_info() (idle)
         ↓
    [DNS checks complete separately — no interaction with the above]

                              ↓ (concurrent with both callbacks)
                         [ipify responds]
                         renderNATResult()  → populates #intro-sub-nat if applicable
```

The NAT sub-line and the mismatch/proxy sub-lines are completely independent and can appear in either order. All three write to pre-declared slots in the initial HTML. `checkProxyNotice` always waits for both protocols to settle before running, so whichever callback finishes last triggers the actual proxy check with the complete picture.

---

## Sub-line Slots

Three hidden `<div>` slots are declared in the initial HTML beneath `#intro-main-status`. Each is populated and shown independently; ordering is fixed by their position in the DOM regardless of which callback fires first.

| Slot ID | Source | When shown |
| --- | --- | --- |
| `#intro-sub-nat` | `renderNATResult()` via ipify (Phase 3) | IPv4 address differs from ipify, no relay detected |
| `#intro-sub-mismatch` | `checkAddressMismatch()` (both success callbacks) | IPv4 and IPv6 disagree on `is_campus` |
| `#intro-sub-proxy` | `checkProxyNotice()` (all four callback paths) | Both agree off-campus, relay/proxy detected |

Mismatch and proxy are mutually exclusive by logic: `checkProxyNotice` skips if `is_campus` differs. The NAT slot is suppressed when a relay is detected (checks `proxyNoticeShown`, both results' isp/org for iCloud / Private Relay / Cloudflare WARP, and both proxy flags), so it won't appear alongside the proxy notice. In practice at most two slots are visible at once (NAT + mismatch).
