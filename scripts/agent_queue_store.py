"""Queue definition storage and read-side state derivation."""

from __future__ import annotations

import json
import shutil
import time
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any, Mapping

from agent_queue_common import (
    ALLOWED_STATUSES,
    LIST_FIELDS,
    MAX_LEASE_SECONDS,
    MIN_LEASE_SECONDS,
    QueueError,
    _RepositoryLock,
    atomic_write_json,
    ensure_string_list,
    exclusive_write_json,
    from_iso,
    require_nonempty,
    require_owner_generation,
    require_owner_session_hash,
    require_queue_id,
    to_iso,
    utc_now,
)


class QueueStoreBase:
    """Queue definitions and runtime claims rooted at one repository."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self.items_dir = self.root / ".agents" / "queue" / "items"
        self.runtime_dir = self.root / ".agent-runtime"
        self.claims_dir = self.runtime_dir / "claims"
        self.history_dir = self.runtime_dir / "history"
        self.lock_path = self.runtime_dir / "claim-global.lock"

    def _lock(self) -> _RepositoryLock:
        return _RepositoryLock(self.lock_path)

    def _item_path(self, item_id: str) -> Path:
        return self.items_dir / f"{require_queue_id(item_id)}.json"

    def _claim_dir(self, item_id: str) -> Path:
        return self.claims_dir / f"{require_queue_id(item_id)}.claim"

    def _claim_path(self, item_id: str) -> Path:
        return self._claim_dir(item_id) / "claim.json"

    def _load_json(self, path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise QueueError(f"File not found: {path.relative_to(self.root)}") from exc
        except json.JSONDecodeError as exc:
            raise QueueError(
                f"Invalid JSON in {path.relative_to(self.root)}: {exc}"
            ) from exc
        except OSError as exc:
            raise QueueError(f"Cannot read {path.relative_to(self.root)}: {exc}") from exc
        if not isinstance(payload, dict):
            raise QueueError(f"{path.relative_to(self.root)} must contain a JSON object")
        return payload

    def validate_item(
        self, item: Mapping[str, Any], *, expected_id: str | None = None
    ) -> dict[str, Any]:
        normalized = dict(item)
        for field in (
            "id",
            "title",
            "status",
            "workset",
            "task",
            "objective",
            "createdAt",
            "updatedAt",
        ):
            normalized[field] = require_nonempty(normalized.get(field), field)

        item_id = require_queue_id(normalized["id"])
        if expected_id is not None and item_id != expected_id:
            raise QueueError(
                f"Queue item id {item_id} does not match filename id {expected_id}"
            )
        if normalized["status"] not in ALLOWED_STATUSES:
            raise QueueError(
                f"status must be one of {sorted(ALLOWED_STATUSES)}, "
                f"got {normalized['status']!r}"
            )
        priority = normalized.get("priority", 100)
        if not isinstance(priority, int) or isinstance(priority, bool):
            raise QueueError("priority must be an integer")
        normalized["priority"] = priority

        for field in LIST_FIELDS:
            normalized[field] = ensure_string_list(normalized.get(field, []), field)
        normalized["dependencies"] = [
            require_queue_id(entry) for entry in normalized["dependencies"]
        ]
        if item_id in normalized["dependencies"]:
            raise QueueError(f"{item_id} cannot depend on itself")
        from_iso(normalized["createdAt"])
        from_iso(normalized["updatedAt"])

        if normalized["status"] == "DONE":
            completion = normalized.get("completion")
            if not isinstance(completion, dict):
                raise QueueError("DONE item must include a completion object")
            require_nonempty(completion.get("agentId"), "completion.agentId")
            from_iso(
                require_nonempty(
                    completion.get("completedAt"), "completion.completedAt"
                )
            )
            evidence = ensure_string_list(
                completion.get("evidence"), "completion.evidence"
            )
            if not evidence:
                raise QueueError("DONE item must include at least one evidence entry")

        if normalized["status"] == "BLOCKED":
            blocked = normalized.get("blocked")
            if not isinstance(blocked, dict):
                raise QueueError("BLOCKED item must include a blocked object")
            require_nonempty(blocked.get("reason"), "blocked.reason")
            if blocked.get("blockedAt"):
                from_iso(blocked["blockedAt"])
        return normalized

    def load_item(self, item_id: str) -> dict[str, Any]:
        item_id = require_queue_id(item_id)
        return self.validate_item(
            self._load_json(self._item_path(item_id)), expected_id=item_id
        )

    def load_items(self) -> dict[str, dict[str, Any]]:
        items: dict[str, dict[str, Any]] = {}
        if not self.items_dir.exists():
            return items
        for path in sorted(self.items_dir.glob("Q*.json")):
            item = self.validate_item(self._load_json(path), expected_id=path.stem)
            if item["id"] in items:
                raise QueueError(f"Duplicate queue id: {item['id']}")
            items[item["id"]] = item
        return items

    def _load_claim(self, item_id: str) -> dict[str, Any] | None:
        path = self._claim_path(item_id)
        if not path.exists():
            return None
        claim = self._load_json(path)
        for field in (
            "itemId",
            "agentId",
            "token",
            "claimedAt",
            "heartbeatAt",
            "expiresAt",
        ):
            require_nonempty(claim.get(field), f"claim.{field}")
        if claim["itemId"] != require_queue_id(item_id):
            raise QueueError(f"Claim item mismatch for {item_id}")
        owner_hash = claim.get("ownerSessionHash")
        owner_generation = claim.get("ownerGeneration")
        if owner_hash is None and owner_generation is None:
            pass  # Claims written before session-generation recovery remain readable.
        elif owner_hash is None or owner_generation is None:
            raise QueueError(f"Incomplete owner metadata for {item_id}")
        else:
            require_owner_session_hash(owner_hash)
            require_owner_generation(owner_generation)
        lease = claim.get("leaseSeconds")
        if (
            not isinstance(lease, int)
            or not MIN_LEASE_SECONDS <= lease <= MAX_LEASE_SECONDS
        ):
            raise QueueError(f"Invalid lease in claim for {item_id}")
        for field in ("claimedAt", "heartbeatAt", "expiresAt"):
            from_iso(claim[field])
        return claim

    @staticmethod
    def _claim_is_stale(claim: Mapping[str, Any]) -> bool:
        heartbeat = from_iso(str(claim["heartbeatAt"]))
        return utc_now() >= heartbeat + timedelta(
            seconds=int(claim["leaseSeconds"])
        )

    def _archive_claim(self, claim: Mapping[str, Any], event: str) -> dict[str, Any]:
        item_id = str(claim["itemId"])
        archived = {
            "event": event,
            "archivedAt": to_iso(),
            "claim": {key: value for key, value in claim.items() if key != "token"},
        }
        atomic_write_json(
            self.history_dir
            / f"{item_id}-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}.json",
            archived,
        )
        shutil.rmtree(self._claim_dir(item_id), ignore_errors=True)
        return {"itemId": item_id, "event": event, "agentId": claim.get("agentId")}

    def _recover_locked(
        self, items: Mapping[str, Mapping[str, Any]]
    ) -> list[dict[str, Any]]:
        recovered: list[dict[str, Any]] = []
        if not self.claims_dir.exists():
            return recovered
        for claim_dir in sorted(self.claims_dir.glob("Q*.claim")):
            item_id = claim_dir.name.removesuffix(".claim")
            try:
                claim = self._load_claim(item_id)
            except QueueError:
                continue
            if claim is None:
                continue
            item = items.get(item_id)
            if item is None:
                recovered.append(self._archive_claim(claim, "orphan-recovered"))
            elif item["status"] in {"DONE", "CANCELLED", "BLOCKED"}:
                recovered.append(self._archive_claim(claim, "terminal-recovered"))
            elif self._claim_is_stale(claim):
                recovered.append(self._archive_claim(claim, "stale-recovered"))
        return recovered

    def _active_claims(self) -> list[dict[str, Any]]:
        claims: list[dict[str, Any]] = []
        if not self.claims_dir.exists():
            return claims
        for claim_dir in sorted(self.claims_dir.glob("Q*.claim")):
            item_id = claim_dir.name.removesuffix(".claim")
            claim = self._load_claim(item_id)
            if claim is not None and not self._claim_is_stale(claim):
                claims.append(claim)
        return claims

    @staticmethod
    def _validate_graph(items: Mapping[str, Mapping[str, Any]]) -> None:
        for item_id, item in items.items():
            for dependency in item["dependencies"]:
                if dependency not in items:
                    raise QueueError(f"{item_id} depends on missing item {dependency}")

        state: dict[str, int] = {}
        path: list[str] = []

        def visit(item_id: str) -> None:
            marker = state.get(item_id, 0)
            if marker == 2:
                return
            if marker == 1:
                cycle_start = path.index(item_id)
                cycle = path[cycle_start:] + [item_id]
                raise QueueError(f"Dependency cycle: {' -> '.join(cycle)}")
            state[item_id] = 1
            path.append(item_id)
            for dependency in items[item_id]["dependencies"]:
                visit(dependency)
            path.pop()
            state[item_id] = 2

        for item_id in items:
            visit(item_id)

    def validate_all(self) -> dict[str, Any]:
        errors: list[str] = []
        try:
            items = self.load_items()
            self._validate_graph(items)
        except QueueError as exc:
            errors.append(str(exc))
            try:
                items = self.load_items()
            except QueueError:
                items = {}
        return {"valid": not errors, "itemCount": len(items), "errors": errors}

    def enqueue(self, item: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock():
            normalized = self.validate_item(item)
            items = self.load_items()
            if normalized["id"] in items or self._item_path(normalized["id"]).exists():
                raise QueueError(f"Queue item already exists: {normalized['id']}")
            candidate = dict(items)
            candidate[normalized["id"]] = normalized
            self._validate_graph(candidate)
            exclusive_write_json(self._item_path(normalized["id"]), normalized)
            return normalized

    def _derived_status(
        self,
        item: Mapping[str, Any],
        items: Mapping[str, Mapping[str, Any]],
        claim: Mapping[str, Any] | None,
    ) -> str:
        if item["status"] != "TODO":
            return str(item["status"])
        if claim is not None:
            return "STALE_CLAIM" if self._claim_is_stale(claim) else "CLAIMED"
        if any(items[dep]["status"] != "DONE" for dep in item["dependencies"]):
            return "WAITING"
        return "READY"

    def list_rows(self) -> list[dict[str, Any]]:
        items = self.load_items()
        self._validate_graph(items)
        rows: list[dict[str, Any]] = []
        for item in sorted(
            items.values(), key=lambda value: (value["priority"], value["id"])
        ):
            claim = self._load_claim(item["id"])
            public_claim = None
            if claim is not None:
                public_claim = {
                    key: value for key, value in claim.items() if key != "token"
                }
            rows.append(
                {
                    **item,
                    "derivedStatus": self._derived_status(item, items, claim),
                    "claim": public_claim,
                }
            )
        return rows

    def show(self, item_id: str) -> dict[str, Any]:
        for row in self.list_rows():
            if row["id"] == require_queue_id(item_id):
                return row
        raise QueueError(f"Queue item not found: {item_id}")

    @staticmethod
    def _validate_lease(lease_seconds: int) -> None:
        if not isinstance(lease_seconds, int) or not (
            MIN_LEASE_SECONDS <= lease_seconds <= MAX_LEASE_SECONDS
        ):
            raise QueueError(
                f"lease must be between {MIN_LEASE_SECONDS} and "
                f"{MAX_LEASE_SECONDS} seconds"
            )
