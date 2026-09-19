#!/usr/bin/env python3
"""Atomic, file-backed queue claims for repository-local coding agents.

Tracked queue definitions live under ``.agents/queue/items``. Ephemeral
lease/token state lives under ``.agent-runtime`` and must remain ignored by
Git. All operations that can change ownership are serialized by an atomic
repository-local directory lock.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

QUEUE_ID_RE = re.compile(r"^Q[0-9]{4,}$")
OWNER_SESSION_HASH_RE = re.compile(r"^[a-f0-9]{64}$")
ALLOWED_STATUSES = {"TODO", "BLOCKED", "DONE", "CANCELLED"}
DEFAULT_LEASE_SECONDS = 1800
MIN_LEASE_SECONDS = 60
MAX_LEASE_SECONDS = 86400
MAX_RECOVERY_REASON_BYTES = 2048
LOCK_TIMEOUT_SECONDS = 5.0
LOCK_STALE_SECONDS = 30.0
LIST_FIELDS = (
    "dependencies",
    "requiredCapabilities",
    "exclusiveScopes",
    "acceptanceCriteria",
    "relevantRules",
    "primaryFiles",
    "doNotTouch",
    "requiredValidation",
)


class QueueError(RuntimeError):
    """Expected queue operation failure."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(value: datetime | None = None) -> str:
    return (value or utc_now()).astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )


def from_iso(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise QueueError(f"Invalid ISO timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def require_queue_id(value: str) -> str:
    if not isinstance(value, str) or not QUEUE_ID_RE.fullmatch(value):
        raise QueueError(
            f"Invalid queue id {value!r}; expected Q followed by at least four digits"
        )
    return value


def require_nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QueueError(f"{field} must be a non-empty string")
    return value


def require_owner_session_hash(value: Any) -> str:
    if not isinstance(value, str) or not OWNER_SESSION_HASH_RE.fullmatch(value):
        raise QueueError("owner_session_hash must be a sha256 hex digest")
    return value


def require_owner_generation(value: Any) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 1
        or value > 2**53 - 1
    ):
        raise QueueError("owner_generation must be a positive safe integer")
    return value


def require_recovery_reason(value: Any) -> str:
    reason = require_nonempty(value, "reason")
    if len(reason.encode("utf-8")) > MAX_RECOVERY_REASON_BYTES or any(
        ord(char) < 0x20 or 0x7F <= ord(char) <= 0x9F for char in reason
    ):
        raise QueueError("reason is invalid or too long")
    return reason


def ensure_string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise QueueError(f"{field} must be a list of non-empty strings")
    normalized = [require_nonempty(entry, field) for entry in value]
    if len(normalized) != len(set(normalized)):
        raise QueueError(f"{field} must not contain duplicate entries")
    return normalized


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def exclusive_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise QueueError(f"Queue item already exists: {path.name}") from exc


@dataclass(frozen=True)
class ClaimResult:
    item: dict[str, Any]
    claim: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"item": self.item, "claim": self.claim}


class _RepositoryLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.owner = uuid.uuid4().hex
        self.acquired = False

    def __enter__(self) -> "_RepositoryLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                os.mkdir(self.path)
                atomic_write_json(
                    self.path / "owner.json",
                    {
                        "owner": self.owner,
                        "pid": os.getpid(),
                        "host": socket.gethostname(),
                        "acquiredAt": to_iso(),
                    },
                )
                self.acquired = True
                return self
            except FileExistsError:
                try:
                    age = time.time() - self.path.stat().st_mtime
                except FileNotFoundError:
                    continue
                if age > LOCK_STALE_SECONDS:
                    stale = self.path.with_name(
                        f"{self.path.name}.stale-{uuid.uuid4().hex}"
                    )
                    try:
                        os.replace(self.path, stale)
                    except (FileNotFoundError, OSError):
                        pass
                    else:
                        shutil.rmtree(stale, ignore_errors=True)
                        continue
                if time.monotonic() >= deadline:
                    raise QueueError("Timed out waiting for queue coordination lock")
                time.sleep(0.05)

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if not self.acquired:
            return
        try:
            owner = json.loads(
                (self.path / "owner.json").read_text(encoding="utf-8")
            ).get("owner")
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            owner = None
        if owner == self.owner:
            shutil.rmtree(self.path, ignore_errors=True)
