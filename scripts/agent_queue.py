#!/usr/bin/env python3
"""CLI and compatibility exports for the repository-local agent queue."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

from agent_queue_core import (
    DEFAULT_LEASE,
    ClaimResult,
    QueueError,
    QueueStore,
    to_iso,
    utc_now,
)


def default_root() -> Path: return Path(__file__).resolve().parents[1]
def get_token(value: str | None) -> str:
    result = value or os.getenv("AGENT_CLAIM_TOKEN", "")
    if not result: raise QueueError("Provide --token or AGENT_CLAIM_TOKEN")
    return result
def get_agent(value: str | None) -> str:
    result = value or os.getenv("AGENT_ID", "")
    if not result.strip(): raise QueueError("Provide --agent or AGENT_ID")
    return result.strip()
def build_parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(description="Atomic lease-based agent queue"); p.add_argument("--root", type=Path, default=default_root()); sub=p.add_subparsers(dest="command", required=True)
    lp=sub.add_parser("list"); lp.add_argument("--json", action="store_true"); sp=sub.add_parser("show"); sp.add_argument("--id", required=True)
    ep=sub.add_parser("enqueue")
    for f in ("id","title","workset","task","objective"): ep.add_argument(f"--{f}", required=True)
    ep.add_argument("--priority", type=int, default=100)
    for f in ("dependency","capability","scope","acceptance-criterion","rule","primary-file","do-not-touch","validation"): ep.add_argument(f"--{f}", action="append", default=[])
    for name in ("claim","claim-next"):
        cp=sub.add_parser(name); cp.add_argument("--id", required=True) if name=="claim" else None; cp.add_argument("--agent"); cp.add_argument("--capability", action="append", default=[]); cp.add_argument("--lease", type=int, default=DEFAULT_LEASE); cp.add_argument("--allow-multiple", action="store_true")
    for name in ("heartbeat","release","complete","block"):
        op=sub.add_parser(name); op.add_argument("--id", required=True); op.add_argument("--token"); op.add_argument("--reason", required=True) if name in ("release","block") else None; op.add_argument("--evidence", action="append", required=True) if name=="complete" else None
    up=sub.add_parser("unblock"); up.add_argument("--id", required=True); up.add_argument("--reason", required=True); sub.add_parser("recover"); sub.add_parser("validate"); return p
def emit(value: Any, stream: Any=sys.stdout) -> None: json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True); stream.write("\n")
def run(a: argparse.Namespace) -> Any:
    s=QueueStore(a.root)
    if a.command=="list":
        rows=s.list_rows(); emit(rows) if a.json else print("Queue is empty." if not rows else "\n".join(f"{r['id']} {r['derivedStatus']} P{r['priority']} {r['workset']}/{r['task']} {r['title']}" for r in rows)); return rows
    if a.command=="show": result=s.show(a.id)
    elif a.command=="validate": result=s.validate_all()
    elif a.command=="recover": result={"recovered":s.recover_stale()}
    elif a.command=="enqueue":
        stamp=to_iso(); result=s.enqueue({"$schema":"../schema/queue-item.schema.json","id":a.id,"title":a.title,"status":"TODO","priority":a.priority,"workset":a.workset,"task":a.task,"objective":a.objective,"dependencies":a.dependency,"requiredCapabilities":a.capability,"exclusiveScopes":a.scope,"acceptanceCriteria":a.acceptance_criterion,"relevantRules":a.rule,"primaryFiles":a.primary_file,"doNotTouch":a.do_not_touch,"requiredValidation":a.validation,"createdAt":stamp,"updatedAt":stamp})
    elif a.command in ("claim","claim-next"):
        kw={"agent_id":get_agent(a.agent),"capabilities":a.capability,"lease_seconds":a.lease,"allow_multiple":a.allow_multiple}; result=s.claim(a.id,**kw) if a.command=="claim" else s.claim_next(**kw)
    elif a.command=="heartbeat": result=s.heartbeat(a.id,token=get_token(a.token))
    elif a.command=="release": result=s.release(a.id,token=get_token(a.token),reason=a.reason)
    elif a.command=="complete": result=s.complete(a.id,token=get_token(a.token),evidence=a.evidence)
    elif a.command=="block": result=s.block(a.id,token=get_token(a.token),reason=a.reason)
    elif a.command=="unblock": result=s.unblock(a.id,reason=a.reason)
    else: raise QueueError(f"Unknown command: {a.command}")
    emit(result.as_dict() if isinstance(result,ClaimResult) else result); return result
def main(argv: Sequence[str] | None=None) -> int:
    try:
        result=run(build_parser().parse_args(argv)); return 0 if not isinstance(result,dict) or result.get("valid",True) else 2
    except QueueError as exc: emit({"ok":False,"error":{"type":"QueueError","message":str(exc)}},sys.stderr); return 2
if __name__=="__main__": raise SystemExit(main())
