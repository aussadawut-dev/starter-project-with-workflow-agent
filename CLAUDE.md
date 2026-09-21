# Workflow Agent Starter Project

This file is the root governance entry point. Keep it concise. Detailed policy belongs in `.claude/rules/`; executable procedures belong in `.claude/skills/` and `.claude/commands/`.

## Shared agent source of truth

`CLAUDE.md` and `.claude/` are canonical for every agent runtime. `AGENTS.md` and `.agents/skills/` are thin compatibility adapters only. Never maintain a second policy copy for another agent product.

Every request enters through the `execution-router` skill and follows:

```text
INTAKE -> CONTROLLER START -> CLASSIFY -> LOCATE -> DECIDE -> PLAN when needed -> QUEUE -> DISPATCH GATE -> CLAIM -> EXECUTE -> RECOVER if needed -> VERIFY -> SYNC -> PUBLISH/CLOSE
```

Queue/claim extends the delivery lifecycle; it does not replace requirement tracking or review. Before every agent assignment, including follow-ups and resumed tasks, freshly read [agent topology](.claude/rules/agent-topology.md) and pass its mandatory dispatch gate. Cached context is not a substitute.

## Team topology

Name one accountable work owner at intake. Token efficiency governs model, effort, context and delegation choices without weakening required checks. Follow the canonical topology for evidence-backed escalation and role-specific economical defaults.

- **Request Evaluator (bootstrap)** — runs once before the Controller exists; chooses only the lowest sufficient Controller logical level and stops. Never plans, decomposes, dispatches, or executes work.
- **Controller** — owns classification, queue, dependency ordering, ownership, dispatch, conflict resolution, integration decisions, and workset state. Default effort is light; it does not perform routine implementation or review.
- **Planner (on demand)** — decomposes Large/Complex or unresolved work initially or replans after a failed checkpoint. Parallelism alone does not require a Planner turn.
- **Lead Reviewer** — performs risk-based combined review. The deterministic route selects self-review for low-risk work and one Lead for meaningful integration risk; specialist review is added only for the concrete high-risk boundary that needs it.
- **Worker pool x N** — one Worker per independent executable queue item. Normal adaptive parallelism is 1/2/3/4 Workers; 5-6 is explicit burst mode only, subject to actual available runtime slots across all active roles.

Roles use provider-agnostic logical effort `light -> standard -> high -> max`. A capability failure may temporarily raise one level for the affected item; environment/tool/authority failures do not. Escalation always resets after the item.

Full role policy: [agent topology](.claude/rules/agent-topology.md).

## Routing and context discipline

- Read-only/status/explanation work: answer directly.
- Small, localized, reversible work with no contract or dependency impact: execute directly and verify; no tracker or queue item is required.
- Medium/Large, multi-step, risky, security-sensitive, approval-sensitive, contract-changing, or cross-area work: locate/create tracking before implementation and dispatch executable tasks through the queue.
- Load only the current role's context. Expand context only after a concrete missing-context signal and keep the expansion bounded.
- Delegate with a bounded Work Packet, never with a conversation dump.
- Before spawning, apply the [Claude runtime dispatch contract](.claude/rules/agent-topology.md#claude-runtime-dispatch-contract): explicitly select the mapped model from [agent-models.json](.claude/runtime/agent-models.json) and supported effort controls; never silently inherit the Controller's model.
- Use the lowest logical effort likely to finish safely; do not select max effort preemptively.
- On failure, classify `environment|tooling|authority|missing-context|reasoning|implementation|planning` before retry/escalation.
- Provider/model mappings are runtime configuration and must not be stored as durable queue authority.

Full policy: [execution router](.claude/rules/execution-router.md).

## Queue and claim invariant

Tracked queue definitions live in `.agents/queue/items/`. Runtime claim leases live in `.agent-runtime/claims/` and are intentionally ignored by Git.

A Worker must atomically claim an item before editing its scope. At most one active claim may own an item, and overlapping exclusive scopes must not run concurrently. Claims use a lease and heartbeat; stale leases may be reclaimed only through the queue tool. Completion requires validation evidence before the item becomes `DONE`.

Use:

```bash
python3 scripts/agent_queue.py list
python3 scripts/agent_queue.py claim-next --agent <agent-id>
python3 scripts/agent_queue.py heartbeat --id <Q-id> --token <claim-token>
python3 scripts/agent_queue.py complete --id <Q-id> --token <claim-token> \
  --evidence "<validation>"
```

Full policy: [queue claim](.claude/rules/queue-claim.md).

## Persistent work tracking

For Medium/Large work:

1. Capture or locate the requirement under `docs/waiting-implement/`.
2. Resolve material decisions once and record them.
3. Move selected work to `docs/waiting-implement/in-breakdown/`.
4. Create or resume a tracker under `docs/tracking/`.
5. Decompose only dependency-safe executable tasks into queue items.
6. Claim, implement, validate, and synchronize each item immediately.
7. Review the combined workset before publication or closure.

The tracker is the durable execution record. The queue is the concurrency and ownership mechanism. Neither may silently override the other.

Full policy: [tracking](.claude/rules/tracking.md).

## Git and publication safety

Commit, push, merge, release, and deployment are separate actions. Perform only the actions explicitly authorized by the user or an approved runbook. Never work from detached HEAD. Never rewrite or discard user work to make a task easier.

Full policy: [Git workflow](.claude/rules/git-workflow.md).

## Definition of Done

A workset is complete only when all acceptance criteria map to evidence, required targeted/integration checks pass, queue items and tracking are synchronized, required review has no unresolved blocking finding, documentation reflects the actual behavior, and any requested publication action succeeds. Otherwise report `REVIEW`, `BLOCKED`, or `PARTIAL` truthfully.

Full policy: [testing and DoD](.claude/rules/testing-dod.md).

## Rule precedence

```text
Root CLAUDE.md
  -> .claude/rules/
  -> accepted requirement / tracker decisions
  -> claimed Work Packet
  -> .claude/skills/ and .claude/commands/
  -> source-level conventions and runtime evidence
```

A lower layer may add detail but may not weaken workspace isolation, approval, security, data-integrity, queue ownership, or publication rules.

## Project-specific rules

None yet. When this project needs domain-specific engineering rules (e.g. API contracts, data-integrity invariants), add them under `.claude/rules/` and link them from this index; keep them separate from the generic workflow-agent rules above.

## Index

Rules: [execution router](.claude/rules/execution-router.md) · [agent topology](.claude/rules/agent-topology.md) · [queue claim](.claude/rules/queue-claim.md) · [tracking](.claude/rules/tracking.md) · [Git workflow](.claude/rules/git-workflow.md) · [testing and DoD](.claude/rules/testing-dod.md)

Agents: [request-evaluator](.claude/agents/request-evaluator.md) · [worker](.claude/agents/worker.md) · [simple-worker](.claude/agents/simple-worker.md) · [lead-reviewer](.claude/agents/lead-reviewer.md) · [planner](.claude/agents/planner.md) · [model config](.claude/runtime/agent-models.json)

Skills: [execution router](.claude/skills/execution-router/SKILL.md) · [work tracking](.claude/skills/work-tracking/SKILL.md) · [queue claim](.claude/skills/queue-claim/SKILL.md) · [review workset](.claude/skills/review-workset/SKILL.md)
