"""Idempotent Lean finalize/reconciliation and event snapshots.

QueueStore remains the source of truth for queue ownership/completion. This
module adds a token-free ignored reconciliation journal so a crash after queue
completion can be resumed without replaying completion or re-claiming work.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from agent_queue_common import atomic_write_json, require_queue_id, to_iso
from agent_queue_core import QueueStore
from agent_workflow_contracts import (
    WORKFLOW_CONTRACT_VERSION,
    WorkflowContractError,
    validate_handoff,
)
from agent_workflow_evidence import evidence_freshness

FINALIZE_VERSION = "1.0.0"
FINALIZE_STATES = {"PREPARED", "RECONCILIATION_REQUIRED", "SYNCED"}


class FinalizeError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FinalizeError(f"{field} must be a non-empty string")
    return value.strip()


def _has_forbidden_token_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower().replace("_", "").replace("-", "")
            if normalized in {"token", "claimtoken"}:
                return True
            if _has_forbidden_token_key(child):
                return True
    elif isinstance(value, list):
        return any(_has_forbidden_token_key(child) for child in value)
    return False


def _validate_sync_plan(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise FinalizeError("syncPlan must be a non-empty list")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, entry in enumerate(value):
        if not isinstance(entry, Mapping):
            raise FinalizeError(f"syncPlan[{index}] must be an object")
        path = _nonempty(entry.get("path"), f"syncPlan[{index}].path")
        if path.startswith("/") or path.startswith("../") or "/../" in path or "\\" in path:
            raise FinalizeError("syncPlan path must be repository-relative")
        if path in seen:
            raise FinalizeError("syncPlan contains duplicate paths")
        seen.add(path)
        must_contain = entry.get("mustContain")
        if not isinstance(must_contain, list) or not must_contain:
            raise FinalizeError(f"syncPlan[{index}].mustContain must be non-empty")
        normalized: list[str] = []
        for marker in must_contain:
            marker_text = _nonempty(marker, f"syncPlan[{index}].mustContain")
            if len(marker_text) > 4096:
                raise FinalizeError("sync marker is too long")
            normalized.append(marker_text)
        if len(normalized) != len(set(normalized)):
            raise FinalizeError("syncPlan markers must be unique")
        result.append({"path": path, "mustContain": normalized})
    return result


def _sync_status(root: Path, plan: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    missing: list[dict[str, Any]] = []
    for entry in plan:
        path = root / str(entry["path"])
        try:
            resolved = path.resolve()
            resolved.relative_to(root)
            content = resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeError, ValueError):
            missing.append({"pathHash": hashlib.sha256(str(entry["path"]).encode()).hexdigest(), "missingMarkerCount": len(entry["mustContain"])})
            continue
        absent = [marker for marker in entry["mustContain"] if marker not in content]
        if absent:
            missing.append({"pathHash": hashlib.sha256(str(entry["path"]).encode()).hexdigest(), "missingMarkerCount": len(absent)})
    return {"complete": not missing, "pending": missing}


class FinalizeJournal:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.directory = self.root / ".agent-runtime" / "finalize"

    def path(self, item_id: str) -> Path:
        return self.directory / f"{require_queue_id(item_id)}.json"

    def load(self, item_id: str) -> dict[str, Any] | None:
        path = self.path(item_id)
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise FinalizeError(f"Cannot read finalize record for {item_id}") from exc
        if not isinstance(value, dict) or value.get("version") != FINALIZE_VERSION or value.get("state") not in FINALIZE_STATES:
            raise FinalizeError(f"Invalid finalize record for {item_id}")
        if _has_forbidden_token_key(value):
            raise FinalizeError("Finalize record contains forbidden token field")
        return value

    def write(self, item_id: str, record: Mapping[str, Any]) -> dict[str, Any]:
        self.directory.mkdir(parents=True, exist_ok=True)
        normalized = dict(record)
        if _has_forbidden_token_key(normalized):
            raise FinalizeError("Finalize record must not persist claim tokens")
        atomic_write_json(self.path(item_id), normalized)
        return normalized


def _request_parts(payload: Mapping[str, Any]) -> tuple[str, dict[str, Any], Mapping[str, Any], list[dict[str, Any]], str]:
    if payload.get("version") != WORKFLOW_CONTRACT_VERSION:
        raise FinalizeError(f"version must be {WORKFLOW_CONTRACT_VERSION}")
    item_id = require_queue_id(_nonempty(payload.get("item"), "item"))
    handoff_raw = payload.get("handoff")
    evidence = payload.get("evidence")
    if not isinstance(handoff_raw, Mapping) or not isinstance(evidence, Mapping):
        raise FinalizeError("handoff and evidence must be objects")
    try:
        handoff = validate_handoff(handoff_raw)
    except WorkflowContractError as exc:
        raise FinalizeError(str(exc)) from exc
    if handoff["item"] != item_id or handoff["outcome"] != "DONE":
        raise FinalizeError("Finalize accepts only matching DONE handoffs")
    sync_plan = _validate_sync_plan(payload.get("syncPlan"))
    evidence_fingerprint = _nonempty(evidence.get("fingerprint"), "evidence.fingerprint")
    if handoff["evidenceFingerprint"] != evidence_fingerprint:
        raise FinalizeError("Handoff/evidence fingerprint mismatch")
    idempotency_key = _sha(
        {
            "version": FINALIZE_VERSION,
            "item": item_id,
            "handoff": handoff,
            "evidenceFingerprint": evidence_fingerprint,
            "syncPlan": sync_plan,
        }
    )
    return item_id, handoff, evidence, sync_plan, idempotency_key


def _completion_evidence(handoff: Mapping[str, Any], idempotency_key: str) -> list[str]:
    evidence = [f"lean-finalize:{idempotency_key}", f"evidence-fingerprint:{handoff['evidenceFingerprint']}"]
    for entry in handoff["validation"]:
        evidence.append(f"{entry['check']}: {entry['result']}")
    return evidence


def _record_prepared(
    item_id: str,
    handoff: Mapping[str, Any],
    evidence: Mapping[str, Any],
    sync_plan: Sequence[Mapping[str, Any]],
    idempotency_key: str,
) -> dict[str, Any]:
    return {
        "version": FINALIZE_VERSION,
        "item": item_id,
        "state": "PREPARED",
        "idempotencyKey": idempotency_key,
        "preparedAt": to_iso(),
        "evidenceFingerprint": handoff["evidenceFingerprint"],
        "evidence": dict(evidence),
        "handoffDigest": _sha(handoff),
        "completionEvidence": _completion_evidence(handoff, idempotency_key),
        "syncPlan": list(sync_plan),
        "syncPlanDigest": _sha(sync_plan),
        "queueCompletedAt": None,
        "syncedAt": None,
    }


def _queue_marker_matches(item: Mapping[str, Any], idempotency_key: str) -> bool:
    completion = item.get("completion")
    if not isinstance(completion, Mapping):
        return False
    evidence = completion.get("evidence")
    return isinstance(evidence, list) and f"lean-finalize:{idempotency_key}" in evidence


def finalize_item(
    root: str | Path,
    payload: Mapping[str, Any],
    *,
    token: str,
    after_prepare: Callable[[], None] | None = None,
    after_complete: Callable[[], None] | None = None,
) -> dict[str, Any]:
    repository = Path(root).resolve()
    item_id, handoff, evidence, sync_plan, idempotency_key = _request_parts(payload)
    journal = FinalizeJournal(repository)
    existing = journal.load(item_id)
    if existing is not None:
        if existing.get("idempotencyKey") != idempotency_key:
            raise FinalizeError(f"Finalize conflict for {item_id}")
        return resume_finalize(repository, item_id, token=token)

    freshness = evidence_freshness(evidence, repository)
    if freshness["status"] != "FRESH":
        raise FinalizeError("Evidence is STALE; rerun verification before finalize")
    if not isinstance(token, str) or not token:
        raise FinalizeError("Active claim token is required for initial finalize")

    store = QueueStore(repository)
    # Public heartbeat validates current token ownership/lease through the
    # existing queue facade. The token is never copied into our journal.
    store.heartbeat(item_id, token=token)
    prepared = journal.write(item_id, _record_prepared(item_id, handoff, evidence, sync_plan, idempotency_key))
    if after_prepare is not None:
        after_prepare()
    completed = store.complete(item_id, token=token, evidence=prepared["completionEvidence"])
    if after_complete is not None:
        after_complete()
    prepared["state"] = "RECONCILIATION_REQUIRED"
    prepared["queueCompletedAt"] = completed["completion"]["completedAt"]
    prepared["reconciliation"] = _sync_status(repository, sync_plan)
    return journal.write(item_id, prepared)


def resume_finalize(
    root: str | Path,
    item_id: str,
    *,
    token: str | None = None,
    acknowledge_sync: bool = False,
) -> dict[str, Any]:
    repository = Path(root).resolve()
    item_id = require_queue_id(item_id)
    journal = FinalizeJournal(repository)
    record = journal.load(item_id)
    if record is None:
        raise FinalizeError(f"No finalize record for {item_id}")
    store = QueueStore(repository)
    item = store.load_item(item_id)
    marker = str(record["idempotencyKey"])

    if record["state"] == "PREPARED":
        if item["status"] == "DONE":
            if not _queue_marker_matches(item, marker):
                raise FinalizeError("Queue item was completed by a different operation")
            record["state"] = "RECONCILIATION_REQUIRED"
            record["queueCompletedAt"] = item["completion"]["completedAt"]
            record["reconciliation"] = _sync_status(repository, record["syncPlan"])
            journal.write(item_id, record)
        elif item["status"] == "TODO":
            if not token:
                raise FinalizeError("Original active claim token is required while queue completion is still pending")
            evidence_record = record.get("evidence")
            if not isinstance(evidence_record, Mapping):
                raise FinalizeError("Prepared finalize is missing evidence inputs")
            freshness = evidence_freshness(evidence_record, repository)
            if freshness["status"] != "FRESH":
                raise FinalizeError("Prepared finalize evidence became STALE before queue completion")
            store.heartbeat(item_id, token=token)
            completion_evidence = record.get("completionEvidence")
            if not isinstance(completion_evidence, list) or not completion_evidence:
                raise FinalizeError("Prepared finalize is missing completion evidence")
            completed = store.complete(
                item_id,
                token=token,
                evidence=completion_evidence,
            )
            record["state"] = "RECONCILIATION_REQUIRED"
            record["queueCompletedAt"] = completed["completion"]["completedAt"]
            record["reconciliation"] = _sync_status(repository, record["syncPlan"])
            journal.write(item_id, record)
        else:
            raise FinalizeError(f"Cannot resume finalize from queue status {item['status']}")

    reconciliation = _sync_status(repository, record["syncPlan"])
    record["reconciliation"] = reconciliation
    if acknowledge_sync:
        if not reconciliation["complete"]:
            raise FinalizeError("Tracker synchronization markers are still missing")
        record["state"] = "SYNCED"
        record["syncedAt"] = to_iso()
        return journal.write(item_id, record)
    if record["state"] == "SYNCED" and not reconciliation["complete"]:
        # External tracker drift never remains silently SYNCED.
        record["state"] = "RECONCILIATION_REQUIRED"
        record["syncedAt"] = None
        return journal.write(item_id, record)
    return journal.write(item_id, record)


def event_snapshot(root: str | Path) -> dict[str, Any]:
    repository = Path(root).resolve()
    store = QueueStore(repository)
    journal = FinalizeJournal(repository)
    items: dict[str, Any] = {}
    ready: list[str] = []
    reconciliation_required: list[str] = []
    for row in store.list_rows():
        item_id = row["id"]
        claim = row.get("claim")
        finalize = journal.load(item_id)
        public_claim = None
        if isinstance(claim, Mapping):
            public_claim = {
                "agentId": claim.get("agentId"),
                "claimedAt": claim.get("claimedAt"),
                "heartbeatAt": claim.get("heartbeatAt"),
                "expiresAt": claim.get("expiresAt"),
            }
        summary = {
            "status": row["status"],
            "derivedStatus": row["derivedStatus"],
            "workset": row["workset"],
            "task": row["task"],
            "claim": public_claim,
            "finalizeState": finalize.get("state") if finalize else None,
        }
        items[item_id] = summary
        if row["derivedStatus"] == "READY":
            ready.append(item_id)
        if finalize and finalize.get("state") == "RECONCILIATION_REQUIRED":
            reconciliation_required.append(item_id)
    revision = _sha(items)
    return {
        "version": FINALIZE_VERSION,
        "revision": revision,
        "reconciledFromAuthority": True,
        "items": items,
        "readyItems": ready,
        "reconciliationRequired": reconciliation_required,
    }


def event_delta(root: str | Path, previous: Mapping[str, Any]) -> dict[str, Any]:
    current = event_snapshot(root)
    prior_items = previous.get("items") if isinstance(previous, Mapping) else None
    if not isinstance(prior_items, Mapping):
        raise FinalizeError("Previous event snapshot is malformed")
    changed = {
        item_id: current["items"][item_id]
        for item_id in sorted(set(prior_items) | set(current["items"]))
        if prior_items.get(item_id) != current["items"].get(item_id)
    }
    removed = sorted(set(prior_items) - set(current["items"]))
    return {
        "version": FINALIZE_VERSION,
        "fromRevision": previous.get("revision"),
        "toRevision": current["revision"],
        "changed": changed,
        "removed": removed,
        "readyItems": current["readyItems"],
        "reconciliationRequired": current["reconciliationRequired"],
        "reconciledFromAuthority": True,
    }
