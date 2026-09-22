# IMP - Merge MCP V3.1 capability-vector topology into agent governance

Created: 2026-09-22
Source: user-supplied spec `~/Downloads/mcp-v3-agent-topology-2.md` ("MCP V3.1 — Dynamic Agent Topology"), pasted in chat with instruction "update agent topo"
Status: IMPLEMENTED

## Outcome

Business/technical outcome: Bring `.claude/rules/agent-topology.md` and its supporting runtime config/role files up to date with the V3.1 design (capability-vector model selection replacing flat role->model mapping, measurable escalation predicates, hysteresis limits, budget authority, richer handoff, binding review invariants) while preserving this repo's existing queue/tracker/dispatch mechanics.
Primary actor: Any Claude Code session acting as Controller in this repo.
Value: Keeps the canonical policy layer aligned with the user's current design doc; replaces the current placeholder config (every role mapped to the same `claude-sonnet-4-6`) with real tiered model selection driven by a capability registry.

## Scope

```text
IN   .claude/rules/agent-topology.md (primary rewrite)
IN   .claude/runtime/agent-models.json (capability-vector registry)
IN   .claude/agents/{request-evaluator,planner,worker,simple-worker,lead-reviewer}.md (model: frontmatter tiering)
IN   docs/tracking/TEMPLATE.md + .claude/rules/tracking.md (one-line Budget field in Execution snapshot, needed by the new Budget section)
OUT  scripts/agent_workflow_contracts.py and other scripts/tests (Lean helper is an intentionally partial approximation; not required to mirror the policy doc 1:1 - confirmed no code/tests reference agent-models.json or specific model IDs)
OUT  .claude/rules/execution-router.md structural changes (kept compatible; only benefits from fixing the prepare-dispatch/validate-dispatch reference inside agent-topology.md's own gate section)
OUT  renaming existing concepts (execution-router stays as-is; no "Dispatcher"/"Node Self-Assessment" renames - would only create duplicate terminology for the same mechanism)
```

## Constraints

- Must not silently drift doc vs. runtime: any new concept introduced in prose must resolve to something either already mechanically true, or explicitly marked as policy-only/manual.
- This repo is Claude-Code-only (Codex dispatch contract was explicitly removed in a prior commit); the new registry must not reintroduce cross-provider entries that can't actually be dispatched here.
- No numeric "effort" dial is confirmed exposed by the live Agent tool (enum is model only: sonnet/opus/haiku/fable). Effort language must keep the existing honest "role-model-only" fallback framing, not invent a fake dial.

## Existing decisions

- Keep existing role names/structure (Request Evaluator, Controller, Planner, Lead Reviewer, Worker pool) and the existing dispatch-gate/handoff/escalation skeleton; V3.1 is a refinement, not a replacement.
- Fix a pre-existing, unrelated-but-adjacent bug found during investigation: `agent-topology.md` and `execution-router.md` both instruct running `prepare-dispatch` / `validate-dispatch`, but `scripts/agent_workflow.py` has no such subcommands (only `route, escalate, validate-packet, validate-handoff, fingerprint, freshness, finalize, resume-finalize, events`). Replace with an honest manual-reread + `route` framing.

## Decisions needed

- None - scope and design resolved by the Controller (this session) during investigation; see tracker TCK001 for the capability-vector registry values and role->model resolution table.

## Acceptance criteria

- AC-01: `agent-topology.md` documents capability-vector model selection (axes, registry pointer, cheapest-sufficient-match algorithm, effort-snap) without breaking any existing cross-references (section anchors used by other rule files stay valid).
- AC-02: `agent-models.json` is valid JSON holding a Claude-only capability registry (real model IDs) plus per-role floors and a precomputed resolved mapping consistent with the floors.
- AC-03: The 5 agent role `.md` files' `model:` frontmatter matches the registry's resolved mapping.
- AC-04: New policy additions present: measurable escalation predicates, hysteresis/limit defaults, Budget section, binding review invariants (reviewer capability >= worker's), enriched Handoff contract (established facts / attempted-and-failed), model-change-request contract.
- AC-05: The fabricated `prepare-dispatch`/`validate-dispatch` references are corrected to match real tooling.
- AC-06: `python3 scripts/validate_agent_governance.py`, `python3 -m unittest discover -s tests -v`, and `python3 scripts/agent_queue.py validate` all pass after the change.

## Impact checklist

```text
Workspace/path boundary: None
Permission/approval: None
Tool schema/runtime/error contract: None - no code reads agent-models.json; Lean contracts.py untouched
Process execution: None
Data/persistence: None
Git/release: None requested yet - implementation only, publication is a separate authorized step
Documentation/testing: Primary surface of this change; governance validation script + unittest suite are the safety net
```

## Dependencies and risks

Dependencies:

- None (first tracker/queue item in this repo)

Risks:

- Renaming/restructuring agent-topology.md sections could break a cross-reference from CLAUDE.md, execution-router.md, queue-claim.md, or the agent role files. Mitigation: keep existing heading text stable; run the governance link validator.
- Introducing a Budget policy concept with no enforcing code could read as vaporware. Mitigation: scope it as policy/reporting discipline only, explicitly note no automated enforcement exists yet.

## Tracking

Tracker: `docs/tracking/TCK001-agent-topology-v3-1.md`
Queue items: Q0001
