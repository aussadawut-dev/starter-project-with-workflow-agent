"""Mutating queue claim lifecycle built on the validated queue store."""

from __future__ import annotations

import os
import secrets
import shutil
from datetime import timedelta
from typing import Any, Mapping, Sequence

from agent_queue_common import (
    ClaimResult,
    DEFAULT_LEASE_SECONDS,
    QueueError,
    atomic_write_json,
    ensure_string_list,
    require_nonempty,
    require_owner_generation,
    require_owner_session_hash,
    require_recovery_reason,
    require_queue_id,
    to_iso,
    utc_now,
)
from agent_queue_store import QueueStoreBase


class QueueStore(QueueStoreBase):
    def _claim_locked(
        self,
        item: Mapping[str, Any],
        items: Mapping[str, Mapping[str, Any]],
        *,
        agent_id: str,
        capabilities: Sequence[str],
        lease_seconds: int,
        allow_multiple: bool,
        owner_session_hash: str | None,
        owner_generation: int | None,
    ) -> ClaimResult:
        agent_id = require_nonempty(agent_id, "agent_id")
        self._validate_lease(lease_seconds)
        if owner_session_hash is None and owner_generation is None:
            pass
        elif owner_session_hash is None or owner_generation is None:
            raise QueueError("owner session metadata is incomplete")
        else:
            owner_session_hash = require_owner_session_hash(owner_session_hash)
            owner_generation = require_owner_generation(owner_generation)
        capability_set = set(capabilities)
        active_claims = self._active_claims()

        if not allow_multiple and any(
            claim["agentId"] == agent_id for claim in active_claims
        ):
            raise QueueError(f"Agent {agent_id} already owns active claim")
        if self._load_claim(item["id"]) is not None:
            raise QueueError(f"{item['id']} already has an active claim")
        if item["status"] != "TODO":
            raise QueueError(f"{item['id']} is not TODO")
        unfinished = [
            dependency
            for dependency in item["dependencies"]
            if items[dependency]["status"] != "DONE"
        ]
        if unfinished:
            raise QueueError(
                f"{item['id']} has unfinished dependencies: {', '.join(unfinished)}"
            )
        missing = set(item["requiredCapabilities"]) - capability_set
        if missing:
            raise QueueError(
                f"Missing required capabilities for {item['id']}: {', '.join(sorted(missing))}"
            )

        requested_scopes = set(item["exclusiveScopes"])
        for claim in active_claims:
            claimed_item = items.get(claim["itemId"])
            if claimed_item is None:
                continue
            conflict = requested_scopes.intersection(claimed_item["exclusiveScopes"])
            if conflict:
                raise QueueError(
                    "Exclusive scope conflict with "
                    f"{claim['itemId']}: {', '.join(sorted(conflict))}"
                )

        now = utc_now()
        claim = {
            "itemId": item["id"],
            "agentId": agent_id,
            "token": secrets.token_urlsafe(32),
            "capabilities": sorted(capability_set),
            "leaseSeconds": lease_seconds,
            "claimedAt": to_iso(now),
            "heartbeatAt": to_iso(now),
            "expiresAt": to_iso(now + timedelta(seconds=lease_seconds)),
        }
        if owner_session_hash is not None and owner_generation is not None:
            claim["ownerSessionHash"] = owner_session_hash
            claim["ownerGeneration"] = owner_generation
        claim_dir = self._claim_dir(item["id"])
        self.claims_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.mkdir(claim_dir)
        except FileExistsError as exc:
            raise QueueError(f"{item['id']} already has an active claim") from exc
        try:
            atomic_write_json(self._claim_path(item["id"]), claim)
        except Exception:
            shutil.rmtree(claim_dir, ignore_errors=True)
            raise
        return ClaimResult(dict(item), claim)

    def claim(
        self,
        item_id: str,
        *,
        agent_id: str,
        capabilities: Sequence[str] = (),
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        allow_multiple: bool = False,
        owner_session_hash: str | None = None,
        owner_generation: int | None = None,
    ) -> ClaimResult:
        with self._lock():
            items = self.load_items()
            self._validate_graph(items)
            self._recover_locked(items)
            item_id = require_queue_id(item_id)
            if item_id not in items:
                raise QueueError(f"Queue item not found: {item_id}")
            return self._claim_locked(
                items[item_id],
                items,
                agent_id=agent_id,
                capabilities=capabilities,
                lease_seconds=lease_seconds,
                allow_multiple=allow_multiple,
                owner_session_hash=owner_session_hash,
                owner_generation=owner_generation,
            )

    def claim_next(
        self,
        *,
        agent_id: str,
        capabilities: Sequence[str] = (),
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
        allow_multiple: bool = False,
        owner_session_hash: str | None = None,
        owner_generation: int | None = None,
    ) -> ClaimResult:
        with self._lock():
            items = self.load_items()
            self._validate_graph(items)
            self._recover_locked(items)
            if not allow_multiple and any(
                claim["agentId"] == agent_id for claim in self._active_claims()
            ):
                raise QueueError(f"Agent {agent_id} already owns active claim")

            capability_set = set(capabilities)
            active_claims = self._active_claims()
            active_scopes: set[str] = set()
            for claim in active_claims:
                claimed_item = items.get(claim["itemId"])
                if claimed_item:
                    active_scopes.update(claimed_item["exclusiveScopes"])

            for item in sorted(
                items.values(), key=lambda value: (value["priority"], value["id"])
            ):
                if item["status"] != "TODO" or self._load_claim(item["id"]):
                    continue
                if any(
                    items[dependency]["status"] != "DONE"
                    for dependency in item["dependencies"]
                ):
                    continue
                if not set(item["requiredCapabilities"]).issubset(capability_set):
                    continue
                if set(item["exclusiveScopes"]).intersection(active_scopes):
                    continue
                return self._claim_locked(
                    item,
                    items,
                    agent_id=agent_id,
                    capabilities=capabilities,
                    lease_seconds=lease_seconds,
                    allow_multiple=allow_multiple,
                    owner_session_hash=owner_session_hash,
                    owner_generation=owner_generation,
                )
            raise QueueError("No eligible queue item")

    def _owned_claim(self, item_id: str, token: str) -> dict[str, Any]:
        claim = self._load_claim(item_id)
        if claim is None or not secrets.compare_digest(str(claim.get("token", "")), token):
            raise QueueError(f"Token does not own claim for {item_id}")
        if self._claim_is_stale(claim):
            self._archive_claim(claim, "stale-recovered")
            raise QueueError(f"Claim lease expired for {item_id}")
        return claim

    def recover_generation(
        self,
        item_id: str,
        *,
        agent_id: str,
        owner_session_hash: str,
        owner_generation: int,
        reason: str,
    ) -> dict[str, Any]:
        """Release a claim stranded by a session reload without accepting its token."""
        item_id = require_queue_id(item_id)
        agent_id = require_nonempty(agent_id, "agent_id")
        owner_session_hash = require_owner_session_hash(owner_session_hash)
        owner_generation = require_owner_generation(owner_generation)
        reason = require_recovery_reason(reason)
        with self._lock():
            claim = self._load_claim(item_id)
            if claim is None:
                raise QueueError(f"No active claim for {item_id}")
            if claim["agentId"] != agent_id:
                raise QueueError(f"Claim agent mismatch for {item_id}")
            stored_hash = claim.get("ownerSessionHash")
            stored_generation = claim.get("ownerGeneration")
            legacy = stored_hash is None and stored_generation is None
            if not legacy and (
                stored_hash != owner_session_hash or stored_generation == owner_generation
            ):
                raise QueueError(f"Claim generation does not require recovery for {item_id}")
            claim["recoveryReason"] = reason
            event = self._archive_claim(
                claim, "legacy-claim-recovered" if legacy else "session-generation-recovered"
            )
            event["recoveryKind"] = "legacy" if legacy else "generation"
            return event

    def heartbeat(self, item_id: str, *, token: str) -> dict[str, Any]:
        with self._lock():
            claim = self._owned_claim(require_queue_id(item_id), token)
            now = utc_now()
            claim["heartbeatAt"] = to_iso(now)
            claim["expiresAt"] = to_iso(
                now + timedelta(seconds=int(claim["leaseSeconds"]))
            )
            atomic_write_json(self._claim_path(item_id), claim)
            return {key: value for key, value in claim.items() if key != "token"}

    def release(self, item_id: str, *, token: str, reason: str) -> dict[str, Any]:
        reason = require_nonempty(reason, "reason")
        with self._lock():
            claim = self._owned_claim(require_queue_id(item_id), token)
            claim["releaseReason"] = reason
            event = self._archive_claim(claim, "released")
            event["reason"] = reason
            return event

    @staticmethod
    def _append_history(item: dict[str, Any], event: Mapping[str, Any]) -> None:
        history = item.setdefault("stateHistory", [])
        if not isinstance(history, list):
            raise QueueError("stateHistory must be an array")
        history.append(dict(event))

    def complete(
        self, item_id: str, *, token: str, evidence: Sequence[str]
    ) -> dict[str, Any]:
        evidence_list = ensure_string_list(list(evidence), "evidence")
        if not evidence_list:
            raise QueueError("Completion evidence is required")
        with self._lock():
            item_id = require_queue_id(item_id)
            claim = self._owned_claim(item_id, token)
            item = self.load_item(item_id)
            completed_at = to_iso()
            item["status"] = "DONE"
            item["updatedAt"] = completed_at
            item.pop("blocked", None)
            item["completion"] = {
                "agentId": claim["agentId"],
                "completedAt": completed_at,
                "evidence": evidence_list,
            }
            self._append_history(
                item,
                {"event": "completed", "at": completed_at, "agentId": claim["agentId"]},
            )
            validated = self.validate_item(item, expected_id=item_id)
            atomic_write_json(self._item_path(item_id), validated)
            self._archive_claim(claim, "completed")
            return validated

    def block(self, item_id: str, *, token: str, reason: str) -> dict[str, Any]:
        reason = require_nonempty(reason, "reason")
        with self._lock():
            item_id = require_queue_id(item_id)
            claim = self._owned_claim(item_id, token)
            item = self.load_item(item_id)
            blocked_at = to_iso()
            item["status"] = "BLOCKED"
            item["updatedAt"] = blocked_at
            item.pop("completion", None)
            item["blocked"] = {
                "agentId": claim["agentId"],
                "blockedAt": blocked_at,
                "reason": reason,
            }
            self._append_history(
                item,
                {
                    "event": "blocked",
                    "at": blocked_at,
                    "agentId": claim["agentId"],
                    "reason": reason,
                },
            )
            validated = self.validate_item(item, expected_id=item_id)
            atomic_write_json(self._item_path(item_id), validated)
            self._archive_claim(claim, "blocked")
            return validated

    def unblock(self, item_id: str, *, reason: str) -> dict[str, Any]:
        reason = require_nonempty(reason, "reason")
        with self._lock():
            item_id = require_queue_id(item_id)
            item = self.load_item(item_id)
            if item["status"] != "BLOCKED":
                raise QueueError(f"{item_id} is not BLOCKED")
            unblocked_at = to_iso()
            previous = item.pop("blocked", None)
            item["status"] = "TODO"
            item["updatedAt"] = unblocked_at
            self._append_history(
                item,
                {
                    "event": "unblocked",
                    "at": unblocked_at,
                    "reason": reason,
                    "previousBlock": previous,
                },
            )
            validated = self.validate_item(item, expected_id=item_id)
            atomic_write_json(self._item_path(item_id), validated)
            return validated

    def recover_stale(self) -> list[dict[str, Any]]:
        with self._lock():
            items = self.load_items()
            return self._recover_locked(items)
