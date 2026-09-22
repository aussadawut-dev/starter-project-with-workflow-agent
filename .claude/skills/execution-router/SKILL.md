---
name: execution-router
description: Entry-point triage for every request. Classifies work, scopes context, chooses the smallest safe topology/effort, and routes tracked work through queue claim, verification, synchronization, and publication controls.
---

# Execution Router

Read [the execution-router rule](../../rules/execution-router.md) before routing non-trivial work.

1. **ROUTE** — CLASSIFY + LOCATE. Use `scripts/agent_workflow.py route` for versioned work shape. Returns adaptive worker count, review mode, and provider-agnostic effort policy; high-risk flags only increase severity.
2. **PREPARE** — DECIDE + PLAN + QUEUE. Validate bounded Work Packets with `validate-packet`. Invoke Planner only for unresolved decisions, materially complex/high-risk planning, or failed checkpoint that invalidates plan; parallelism alone does not require Planner turn.
3. **EXECUTE** — Before spawning, apply provider-specific dispatch contract in [agent topology](../../rules/agent-topology.md): Codex uses explicit `model` + `reasoning_effort` and `fork_turns: "none"`; Claude uses explicit per-invocation `model` (or verified matching agent definition), checks forced-model overrides, and uses only supported Claude effort controls. Resolve role's logical effort before selecting runtime values. Never inherit Controller's model. Pass bounded Work Packet. CLAIM then implement only owned scope. Start at route's baseline effort and bounded context. Do not recursively spawn subagents unless independent queue-ready work exists.
4. **RECOVER** — On failure, classify cause before retrying. Use `scripts/agent_workflow.py escalate --input failure.json`: environment/tool/authority failures remain at same effort; missing context expands bounded context first; reasoning/implementation/planning failures may temporarily escalate one level. Escalation is item-scoped and resets after item.
5. **VERIFY** — Run worker-targeted checks first. Use risk-triggered review; do not fan out reviewers by default. Capture `fingerprint` only after checks that justify completion.
6. **FINALIZE** — Validate compact handoff, complete QueueStore item once, reconcile tracker markers, then publish/close only with separate authority. Use `events` snapshot/delta on reconnect instead of routine polling.

The original `agent_queue.py` claim/heartbeat/complete workflow remains supported as the rollback-compatible path.

Route to:

- [work tracking](../work-tracking/SKILL.md) for persistent Medium/Large work;
- [queue claim](../queue-claim/SKILL.md) for Worker ownership;
- [review workset](../review-workset/SKILL.md) for the combined gate.

Do not restart intake, reload broad history, or re-ask accepted decisions already recorded in the active requirement/tracker.
