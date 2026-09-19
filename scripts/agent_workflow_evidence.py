"""Git-bound evidence fingerprints for Lean Agent Workflow.

Only digests/counts/toolchain facts are persisted. Raw diff bytes, untracked file
paths/content, environment values and claim tokens never enter the record.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

from agent_workflow_contracts import WORKFLOW_CONTRACT_VERSION, WorkflowContractError


class EvidenceError(RuntimeError):
    pass


def _run(root: Path, args: list[str], *, check: bool = True) -> bytes:
    try:
        completed = subprocess.run(
            args,
            cwd=root,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "LC_ALL": "C", "LANG": "C"},
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise EvidenceError(f"Command failed: {' '.join(args)}") from exc
    return completed.stdout


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(root: Path, *args: str) -> bytes:
    return _run(root, ["/usr/bin/git", *args])


def _tool_version(root: Path, executable: str, *args: str) -> str | None:
    try:
        output = _run(root, [executable, *args], check=True).decode("utf-8", "replace").strip()
    except EvidenceError:
        return None
    return output[:256]


def _untracked_digest(root: Path) -> tuple[str, int]:
    raw = _git(root, "ls-files", "--others", "--exclude-standard", "-z")
    names = [entry for entry in raw.split(b"\0") if entry]
    digest = hashlib.sha256()
    count = 0
    for encoded in sorted(names):
        try:
            relative = encoded.decode("utf-8", "strict")
        except UnicodeDecodeError as exc:
            raise EvidenceError("Untracked path is not valid UTF-8") from exc
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise EvidenceError("Untracked path escapes repository") from exc
        if not candidate.is_file() or candidate.is_symlink():
            continue
        stat = candidate.stat()
        if stat.st_size > 8 * 1024 * 1024:
            # Large untracked artifacts remain an input through metadata digest
            # without loading arbitrary blobs into memory.
            content_digest = f"large:{stat.st_size}".encode()
        else:
            content_digest = hashlib.sha256(candidate.read_bytes()).hexdigest().encode()
        # Path names are inputs to the digest but are not returned in the record.
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
        digest.update(b"\0")
        digest.update(content_digest)
        digest.update(b"\0")
        count += 1
    return digest.hexdigest(), count


def git_evidence_inputs(root: str | Path) -> dict[str, Any]:
    repository = Path(root).resolve()
    try:
        top = Path(_git(repository, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    except EvidenceError as exc:
        raise EvidenceError("Evidence fingerprint requires a Git repository") from exc
    if top != repository:
        raise EvidenceError("Evidence root must be the Git repository root")

    head = _git(repository, "rev-parse", "HEAD").decode("ascii", "strict").strip()
    if len(head) != 40 and len(head) != 64:
        raise EvidenceError("Unexpected Git HEAD shape")
    staged = _git(repository, "diff", "--cached", "--binary", "--no-ext-diff")
    unstaged = _git(repository, "diff", "--binary", "--no-ext-diff")
    untracked_sha, untracked_count = _untracked_digest(repository)

    toolchain = {
        "python": platform.python_version(),
        "node": _tool_version(repository, "/usr/bin/env", "node", "--version"),
        "git": _tool_version(repository, "/usr/bin/git", "--version"),
        "platform": f"{platform.system()}-{platform.machine()}",
    }
    return {
        "head": head,
        "stagedSha256": _sha(staged),
        "unstagedSha256": _sha(unstaged),
        "untrackedSha256": untracked_sha,
        "untrackedCount": untracked_count,
        "toolchain": toolchain,
    }


def fingerprint_inputs(inputs: Mapping[str, Any]) -> str:
    canonical = json.dumps(inputs, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def make_evidence_record(root: str | Path) -> dict[str, Any]:
    inputs = git_evidence_inputs(root)
    return {
        "version": WORKFLOW_CONTRACT_VERSION,
        "fingerprint": fingerprint_inputs(inputs),
        "inputs": inputs,
    }


def evidence_freshness(record: Mapping[str, Any], root: str | Path) -> dict[str, Any]:
    if record.get("version") != WORKFLOW_CONTRACT_VERSION:
        raise WorkflowContractError("Evidence record version mismatch")
    stored = record.get("inputs")
    fingerprint = record.get("fingerprint")
    if not isinstance(stored, Mapping) or not isinstance(fingerprint, str):
        raise WorkflowContractError("Evidence record is malformed")
    expected = fingerprint_inputs(stored)
    if fingerprint != expected:
        raise WorkflowContractError("Evidence record fingerprint does not match its inputs")
    current = git_evidence_inputs(root)
    current_fingerprint = fingerprint_inputs(current)
    changed = sorted(key for key in current if current.get(key) != stored.get(key))
    return {
        "version": WORKFLOW_CONTRACT_VERSION,
        "status": "FRESH" if current_fingerprint == fingerprint else "STALE",
        "fingerprint": fingerprint,
        "currentFingerprint": current_fingerprint,
        "changedInputs": changed,
    }
