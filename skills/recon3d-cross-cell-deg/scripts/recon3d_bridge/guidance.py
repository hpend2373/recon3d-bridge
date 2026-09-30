"""Optional review ordering. Never removes a candidate or assigns evidence grades."""

from __future__ import annotations

import hashlib
import json
from typing import Callable

from .client import APIError, ContractError, JevClient


PRIORITY_QUESTION = {
    "type": "score",
    "instructions": (
        "How useful is this already enumerated candidate for early manual review? "
        "Use only the supplied summary. Prioritize informative, checkable routes. "
        "Missing evidence remains missing. This is a queue-order suggestion; it does "
        "not establish feasibility, flux, transfer, causality, RNA support, or a p-value. "
        "Every candidate will still require deterministic and evidence review."
    ),
    "criteria": [
        "Insufficient detail to prioritize; keep it in the full review queue.",
        "Some checkable details; ordinary review priority.",
        "Clear and informative details; useful to inspect early.",
    ],
}


def prioritize(candidates: list[dict], *, client: JevClient | None = None,
               checkpoint: Callable[[dict], None] | None = None) -> dict:
    """Score ALL supplied candidates or retain their supplied order without a client.

    Expected input: [{"id": "route-id", "summary": <text/object/array>}, ...].
    Extra fields are retained but never sent to the API. Errors leave a candidate
    pending and are recorded; all remaining candidates are still attempted.
    This function does not enumerate Recon3D paths or perform scientific review.
    """
    if not isinstance(candidates, list):
        raise ContractError("candidates must be a JSON array")
    ids = set()
    for item in candidates:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            raise ContractError("each candidate needs a nonempty string id")
        if item["id"] in ids:
            raise ContractError("candidate IDs must be unique")
        ids.add(item["id"])
        if not isinstance(item.get("summary"), (str, dict, list)):
            raise ContractError("each candidate needs a text/JSON summary")
    try:
        encoded = json.dumps(candidates, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    except (ValueError, TypeError) as exc:
        raise ContractError("candidates must contain finite JSON") from exc
    entries = [{"candidate": item, "original_index": i, "guidance_status": "pending" if client else "not_requested",
                "review_status": "pending"} for i, item in enumerate(candidates)]
    report = {
        "schema_version": 1, "input_sha256": hashlib.sha256(encoded).hexdigest(),
        "provider": "systemone" if client else "supplied_order",
        "endpoint": client.base_url if client else None,
        "requested_model": client.model if client else None,
        "candidate_count": len(entries), "scored_count": 0,
        "guidance_complete": client is None,
        "review_complete": False, "review_pending_count": len(entries),
        "interpretation": "Model guidance only; no biological evidence grade is assigned.",
        "entries": entries,
    }
    if checkpoint:
        checkpoint(report)
    if client is None:
        return report
    for entry in entries:
        try:
            response = client.evaluate(state={"candidate_summary": entry["candidate"]["summary"]},
                                       questions={"review_priority": PRIORITY_QUESTION})
            entry["guidance"] = response["answers"]["review_priority"]
            entry["resolved_model"] = response["model"]
            entry["usage"] = response["usage"]
            entry["guidance_status"] = "scored"
            report["scored_count"] += 1
        except (APIError, ContractError) as exc:
            entry["guidance_status"] = "error"
            entry["error"] = str(exc)
        if checkpoint:
            checkpoint(report)
    # Failed guidance remains visible and in original order after scored entries.
    entries.sort(key=lambda entry: (
        entry["guidance_status"] != "scored",
        -entry.get("guidance", {}).get("score", 0), entry["original_index"],
    ))
    report["guidance_complete"] = report["scored_count"] == len(entries)
    if checkpoint:
        checkpoint(report)
    return report
