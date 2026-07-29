# Intro Message Matrix — What Is My IP?

All possible states of `#intro_text` on the home page — main status line plus optional sub-lines.

---

## Message Catalog

### Loading state

> ↻ Testing connection…

### Error state

> ! Connection details could not be retrieved. Refresh to try again.

Fires if the primary (IPv4) API call fails. Report button stays disabled.

### Main status lines

Set by `set_intro_text(is_campus, network_purpose)`. Called by both the IPv4 and IPv6 callbacks; the later callback updates in place, preserving any sub-lines already shown. Once a specific-purpose message (VPN, Wireless) has been set, a subsequent null-purpose call is ignored.

| Condition | Message |
| --- | --- |
| `is_campus = false` | You are connected from off campus over the Internet. |
| `is_campus = true`, purpose ≠ VPN/Wireless | You are connected to the campus network. |
| `is_campus = true`, purpose = "Wireless" | You are connected to the campus wireless network. |
| `is_campus = true`, purpose = "VPN" | You are connected through the campus VPN. |

The off-campus variant also shows a Campus VPN card if `vpn_install_url` is configured.

---

## NAT Sub-line

Source: `renderNATResult()` via `checkNATType()` → `fetchExternalIPv4()` (ipify, 5 s timeout).

**Key architectural fact:** `test_ipv4_url()` **always** calls the IPv4 endpoint (`ipv4_url`) regardless of whether `default_version` is 4 or 6. The NAT check is therefore independent of the default protocol — it fires whenever the IPv4 API call succeeds **and** ipify returns an address that differs from the campus-seen IPv4 address. The `isV6` guard inside `renderNATResult()` is defensive dead code that can never be triggered in practice.

| Context | Message |
| --- | --- |
| `networkPurpose` truthy and ≠ "VPN" | Your internet traffic exits the campus network as `{x.x.x.x}`. |
| `networkPurpose` = "VPN" | Internet traffic bypasses the VPN tunnel and exits via `{x.x.x.x}`. |
| `networkPurpose` falsy (off-campus) | Your internet traffic appears to use a different address (`{x.x.x.x}`) than your campus connection. |

---

## IPv4 / IPv6 Mismatch Sub-line — and Proxy Notice

Source: `checkAddressMismatch()` — called at the end of **both** the IPv4 and IPv6 callbacks. Requires both `reportDataIPv4` and `reportDataIPv6` to be loaded.

**Path A — both agree on is_campus (or single-stack):** `checkProxyNotice()` is called from all four callback paths (both success, both error) but gates on both `ipv4Resolved` and `ipv6Resolved` before doing any work. It fires if at least one off-campus result exists and any result's ISP or org matches a relay/proxy pattern, or `iplocation.proxy` is true. A `proxyNoticeShown` flag prevents double-firing. Single-stack clients are covered: both error callbacks also call `checkProxyNotice()`.

| Condition | Message |
| --- | --- |
| Any ISP or org matches `/icloud\|private relay/i` | iCloud Private Relay is active — your actual network location may differ from what is shown. |
| Any org matches `/cloudflare warp/i`, or `iplocation.proxy = true` | A VPN or proxy service is active — your actual network location may differ from what is shown. |
| Neither | *(no note shown)* |

**Path B — results disagree on `is_campus`:** a mismatch note is shown based on the off-campus result. `checkProxyNotice()` skips if a mismatch note was already shown.

| Condition | Message |
| --- | --- |
| Off-campus ISP **or org** matches `/icloud\|private relay/i` | iCloud Private Relay is routing one of your addresses off-campus. |
| Off-campus `iplocation.proxy = true`, or org matches `/cloudflare warp/i` | A VPN or proxy service is routing one of your addresses off-campus. |
| Neither of the above | Your two addresses are on different networks — one campus, one off-campus. |

---

## Combined Scenario Matrix

Main line reflects whichever callback completes last (typically IPv6). NAT and mismatch sub-lines are independent — both can appear simultaneously.

| Scenario | Main line | NAT sub-line? | Mismatch sub-line? |
| --- | --- | --- | --- |
| IPv4-only, off-campus | Off-campus | Possible — if ipify differs | — single stack |
| IPv4-only, campus wired | Campus | Possible — exits as NAT IP | — single stack |
| IPv4-only, campus wireless | Wireless | Possible — exits as NAT IP | — single stack |
| IPv4-only, campus VPN | VPN | Possible — split-tunnel warning | — single stack |
| IPv4-only, off-campus, iCloud/proxy active | Off-campus | Possible — if ipify differs | Proxy notice (via IPv6 error callback) |
| IPv6-only, any connection | Campus / Wireless / VPN / Off-campus | No — IPv4 endpoint call fails (no IPv4 path) | — single stack |
| IPv6-only, off-campus, iCloud/proxy active | Off-campus | No IPv4 path | Proxy notice (via IPv6 success callback, `reportDataIPv4` null) |
| Dual-stack, both off-campus, no proxy | Off-campus | Possible — if IPv4 & ipify differ | — both agree, no note |
| Dual-stack, both off-campus, iCloud/proxy active | Off-campus | Possible — if IPv4 & ipify differ | Proxy notice (via IPv6 success callback) |
| Dual-stack, both on-campus (same purpose) | Campus / Wireless / VPN | Possible — from IPv4 side | — both agree |
| Dual-stack, both on-campus (different purposes, e.g. VPN + campus) | last-callback purpose | Possible — from IPv4 side | — both is_campus = true |
| Dual-stack, IPv4 campus / IPv6 off-campus | usually Off-campus (IPv6 fires last) | Possible — from IPv4 side | Yes — iCloud / proxy / generic |
| Dual-stack, IPv4 off-campus / IPv6 on-campus | usually On-campus (IPv6 fires last) | Possible — off-campus variant | Yes — iCloud / proxy / generic |

Note for dual-stack: the NAT check always runs on the IPv4 side regardless of which protocol is primary (IPv4 or IPv6 as `default_version`).

---

## Execution Sequence

1. **Page load** — Initial HTML rendered server-side. `#intro-main-status` (showing spinner) and three hidden sub-line slots (`#intro-sub-nat`, `#intro-sub-mismatch`, `#intro-sub-proxy`) are already in the DOM.

2. **IPv4 callback** — `set_intro_text()` updates `#intro-main-status` from the spinner to the real status line. Stores result as `reportDataIPv4`. Calls `checkAddressMismatch()` — returns early because `reportDataIPv6` is not yet loaded. Also kicks off `checkNATType()` with the IPv4 `client_address`.

3. **ipify (async, concurrent with IPv6 callback)** — `fetchExternalIPv4()` calls `api4.ipify.org`. If result differs from campus IPv4 address, `renderNATResult()` populates and shows `#intro-sub-nat`. Fires regardless of `default_version`.

4. **IPv6 callback** — `set_intro_text()` updates `#intro-main-status` in-place (null-purpose call is ignored if IPv4 already set a specific-purpose message). Stores result as `reportDataIPv6`. Calls `checkAddressMismatch()` — now both are loaded; if campus status differs, populates `#intro-sub-mismatch`. Calls `checkProxyNotice()` — if IPv4 has also settled, runs the proxy check and may populate `#intro-sub-proxy`.

5. **Final state** — Main line reflects the **last callback to complete** (either order is possible). Sub-line slots are visible only if populated; at most two can be visible at once (NAT + mismatch). Proxy and mismatch notices are mutually exclusive by logic.
