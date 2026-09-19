#!/usr/bin/env python3
"""Lean Agent Workflow CLI.

The CLI is intentionally additive to agent_queue.py. It performs deterministic
coordination helpers; queue ownership and mutation remain delegated to the
existing QueueStore facade.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from agent_workflow_contracts import (
    WorkflowContractError,
    evaluate_escalation,
    route_work,
    validate_handoff,
    validate_work_packet,
)
from agent_workflow_evidence import (
    EvidenceError,
    evidence_freshness,
    make_evidence_record,
)
from agent_workflow_finalize import (
    FinalizeError,
    event_delta,
    event_snapshot,
    finalize_item,
    resume_finalize,
)


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_json(path: str) -> Mapping[str, Any]:
    try:
        if path == "-":
            value = json.load(sys.stdin)
        else:
            value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WorkflowContractError(f"Cannot load JSON input: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowContractError("JSON input must be an object")
    return value


def _emit(value: Any) -> None:
    json.dump(value, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lean Agent Workflow helpers")
    parser.add_argument("--root", type=Path, default=_root())
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("route", "escalate", "validate-packet", "validate-handoff"):
        item = sub.add_parser(name)
        item.add_argument("--input", required=True, help="JSON file path or - for stdin")
    fingerprint = sub.add_parser("fingerprint")
    fingerprint.add_argument("--output")
    freshness = sub.add_parser("freshness")
    freshness.add_argument("--input", required=True)
    finalize = sub.add_parser("finalize")
    finalize.add_argument("--input", required=True)
    finalize.add_argument("--token")
    resume = sub.add_parser("resume-finalize")
    resume.add_argument("--item", required=True)
    resume.add_argument("--token")
    resume.add_argument("--ack-sync", action="store_true")
    events = sub.add_parser("events")
    events.add_argument("--previous", help="Prior event snapshot JSON; omit for full snapshot")
    return parser


def run(arguments: argparse.Namespace) -> Any:
    root = arguments.root.resolve()
    if arguments.command == "route":
        return route_work(_load_json(arguments.input)).as_dict()
    if arguments.command == "escalate":
        return evaluate_escalation(_load_json(arguments.input)).as_dict()
    if arguments.command == "validate-packet":
        return validate_work_packet(_load_json(arguments.input))
    if arguments.command == "validate-handoff":
        return validate_handoff(_load_json(arguments.input))
    if arguments.command == "fingerprint":
        result = make_evidence_record(root)
        if arguments.output:
            Path(arguments.output).write_text(
                json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return result
    if arguments.command == "freshness":
        return evidence_freshness(_load_json(arguments.input), root)
    if arguments.command == "finalize":
        token = arguments.token or os.getenv("AGENT_CLAIM_TOKEN", "")
        return finalize_item(root, _load_json(arguments.input), token=token)
    if arguments.command == "resume-finalize":
        token = arguments.token or os.getenv("AGENT_CLAIM_TOKEN")
        return resume_finalize(root, arguments.item, token=token, acknowledge_sync=arguments.ack_sync)
    if arguments.command == "events":
        if arguments.previous:
            return event_delta(root, _load_json(arguments.previous))
        return event_snapshot(root)
    raise WorkflowContractError(f"Unknown command {arguments.command}")


def main(argv: Sequence[str] | None = None) -> int:
    try:
        result = run(build_parser().parse_args(argv))
        _emit(result)
        return 0
    except (WorkflowContractError, EvidenceError, FinalizeError) as exc:
        _emit({"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
