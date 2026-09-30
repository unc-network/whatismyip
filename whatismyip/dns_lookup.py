"""Direct DNS resolver queries and answer comparison helpers."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import dns.exception
import dns.flags
import dns.message
import dns.query
import dns.rcode
import dns.rdatatype

_LOGGER = logging.getLogger(__name__)
_DNS_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="dns-lookup")
_MAX_ANSWER_RECORDS = 100
_MAX_RDATA_CHARS = 4096
_MAX_TOTAL_RDATA_CHARS = 65536


def query_resolvers(
    name: str,
    record_type: str,
    resolvers: list[dict[str, str]],
    timeout: float,
) -> list[dict[str, Any]]:
    """Query configured resolvers concurrently while preserving display order."""
    if not resolvers:
        return []

    futures = [
        _DNS_EXECUTOR.submit(_query_resolver, name, record_type, target, timeout)
        for target in resolvers
    ]
    return [future.result() for future in futures]


def _query_resolver(
    name: str,
    record_type: str,
    target: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    """Return a normalized DNS response from one explicit resolver."""
    started = time.monotonic()
    result: dict[str, Any] = {
        "id": target["id"],
        "label": target["label"],
        "address": target["address"],
        "status": "error",
        "rcode": None,
        "latency_ms": None,
        "negative_ttl": None,
        "answers": [],
        "cname_chains": [],
        "answers_truncated": False,
        "error": None,
    }

    try:
        request_message = dns.message.make_query(name, record_type)
        response = dns.query.udp(
            request_message,
            target["address"],
            timeout=timeout,
            ignore_unexpected=True,
        )
        if response.flags & dns.flags.TC:
            response = dns.query.tcp(
                request_message,
                target["address"],
                timeout=timeout,
            )

        result["latency_ms"] = round((time.monotonic() - started) * 1000)
        result["rcode"] = dns.rcode.to_text(response.rcode())
        result["answers"], result["answers_truncated"] = _answer_records(response)
        result["negative_ttl"] = _negative_ttl(response)

        if response.rcode() == dns.rcode.NXDOMAIN:
            result["status"] = "nxdomain"
        elif response.rcode() != dns.rcode.NOERROR:
            result["status"] = "dns_error"
            result["error"] = f"Resolver returned {result['rcode']}"
        elif result["answers"]:
            result["status"] = "success"
        else:
            result["status"] = "no_answer"
    except dns.exception.Timeout:
        result["status"] = "timeout"
        result["error"] = "The DNS query timed out."
    except (dns.exception.DNSException, OSError, ValueError) as exc:
        _LOGGER.warning(
            "DNS query through %s failed: %s", target["id"], exc, exc_info=True
        )
        result["status"] = "error"
        result["error"] = "The DNS query failed."

    result["cname_chains"] = _build_cname_chains(name, result["answers"])
    return result


def _dns_name_key(value: object) -> str:
    """Return a comparison key for an absolute or relative DNS name."""
    return str(value).strip().rstrip(".").casefold()


def _build_cname_chains(
    query_name: str, answers: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Order CNAME records from each alias through its terminal answer."""
    aliases: dict[str, dict[str, Any]] = {}
    records_by_owner: dict[str, list[dict[str, Any]]] = {}
    display_names: dict[str, str] = {}

    for answer in answers:
        owner_key = _dns_name_key(answer.get("name", ""))
        if not owner_key:
            continue
        display_names.setdefault(owner_key, str(answer["name"]))
        if answer.get("type") == "CNAME":
            target_key = _dns_name_key(answer.get("data", ""))
            if target_key and owner_key not in aliases:
                aliases[owner_key] = answer
                display_names.setdefault(target_key, str(answer["data"]))
        else:
            records_by_owner.setdefault(owner_key, []).append(answer)

    if not aliases:
        return []

    target_keys = {
        _dns_name_key(answer["data"])
        for answer in aliases.values()
        if _dns_name_key(answer.get("data", ""))
    }
    query_key = _dns_name_key(query_name)
    starts = []
    if query_key in aliases:
        starts.append(query_key)
    starts.extend(sorted(set(aliases) - target_keys - set(starts)))
    starts.extend(sorted(set(aliases) - set(starts)))

    chains = []
    used_owners: set[str] = set()
    for start in starts:
        if start in used_owners:
            continue
        current = start
        seen: set[str] = set()
        steps = []
        while current in aliases and current not in seen:
            seen.add(current)
            used_owners.add(current)
            answer = aliases[current]
            target_key = _dns_name_key(answer["data"])
            steps.append(
                {
                    "name": display_names[current],
                    "target": display_names.get(target_key, str(answer["data"])),
                    "ttl": answer["ttl"],
                }
            )
            current = target_key

        if steps:
            chains.append(
                {
                    "steps": steps,
                    "terminal_name": display_names.get(current, steps[-1]["target"]),
                    "terminal_records": [
                        {
                            "type": answer["type"],
                            "data": answer["data"],
                            "ttl": answer["ttl"],
                        }
                        for answer in records_by_owner.get(current, [])
                    ],
                    "loop_detected": current in seen,
                }
            )

    return chains


def _answer_records(
    response: dns.message.Message,
) -> tuple[list[dict[str, Any]], bool]:
    records: list[dict[str, Any]] = []
    total_rdata_chars = 0
    truncated = False
    for rrset in response.answer:
        record_type = dns.rdatatype.to_text(rrset.rdtype)
        owner = rrset.name.to_text()
        for item in rrset:
            if len(records) >= _MAX_ANSWER_RECORDS:
                return records, True

            data = item.to_text()
            if len(data) > _MAX_RDATA_CHARS:
                data = data[: _MAX_RDATA_CHARS - 1] + "…"
                truncated = True

            remaining = _MAX_TOTAL_RDATA_CHARS - total_rdata_chars
            if remaining <= 0:
                return records, True
            if len(data) > remaining:
                data = data[: max(0, remaining - 1)] + "…"
                truncated = True

            records.append(
                {
                    "name": owner,
                    "type": record_type,
                    "ttl": rrset.ttl,
                    "data": data,
                }
            )
            total_rdata_chars += len(data)
            if total_rdata_chars >= _MAX_TOTAL_RDATA_CHARS:
                return records, True
    return records, truncated


def _negative_ttl(response: dns.message.Message) -> int | None:
    """Return the RFC 2308 negative-cache TTL from an authority SOA, if any."""
    for rrset in response.authority:
        if rrset.rdtype != dns.rdatatype.SOA:
            continue
        minimums = [int(item.minimum) for item in rrset]
        if minimums:
            return min(int(rrset.ttl), min(minimums))
    return None


def compare_answers(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Build union rows that align internal and public answers without TTLs."""
    keyed_results: dict[str, dict[tuple[str, str, str], int]] = {}
    record_details: dict[tuple[str, str, str], dict[str, str]] = {}

    for result in results:
        keyed: dict[tuple[str, str, str], int] = {}
        for answer in result.get("answers", []):
            key = (answer["name"], answer["type"], answer["data"])
            keyed[key] = answer["ttl"]
            record_details[key] = {
                "name": answer["name"],
                "type": answer["type"],
                "data": answer["data"],
            }
        keyed_results[result["id"]] = keyed

    internal = keyed_results.get("internal", {})
    public = keyed_results.get("public", {})
    rows = []
    for key in sorted(record_details, key=lambda item: (item[1], item[0], item[2])):
        details = record_details[key]
        in_internal = key in internal
        in_public = key in public
        rows.append(
            {
                **details,
                "internal_ttl": internal.get(key),
                "public_ttl": public.get(key),
                "comparison": (
                    "both"
                    if in_internal and in_public
                    else "internal_only" if in_internal else "public_only"
                ),
            }
        )

    internal_result = next((item for item in results if item["id"] == "internal"), None)
    public_result = next((item for item in results if item["id"] == "public"), None)
    answers_truncated = any(
        result.get("answers_truncated", False) for result in results
    )
    comparable_statuses = {"success", "no_answer", "nxdomain"}
    comparable = bool(
        internal_result
        and public_result
        and not answers_truncated
        and internal_result.get("status") in comparable_statuses
        and public_result.get("status") in comparable_statuses
    )
    same_answers = None
    if comparable:
        same_answers = internal_result.get("rcode") == public_result.get(
            "rcode"
        ) and set(internal) == set(public)

    return {
        "rows": rows,
        "comparable": comparable,
        "same_answers": same_answers,
        "answers_truncated": answers_truncated,
    }
