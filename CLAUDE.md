# Workflow Agent Starter Project

Root governance entry point. Detailed policy in `.claude/rules/`; executable procedures in `.claude/skills/` and `.claude/commands/`.

## Shared agent source of truth

`CLAUDE.md` and `.claude/` canonical for every agent runtime. `AGENTS.md` and `.agents/skills/` thin compatibility adapters only. Never maintain a second policy copy.

Every request enters through the `execution-router` skill and follows:

```text
INTAKE -> CONTROLLER START -> CLASSIFY -> LOCATE -> DECIDE -> PLAN when needed -> QUEUE -> DISPATCH GATE -> CLAIM -> EXECUTE -> RECOVER if needed -> VERIFY -> SYNC -> PUBLISH/CLOSE
```

Queue/claim extends delivery lifecycle; does not replace requirement tracking or review. Before every agent assignment (including follow-ups and resumed tasks), read [agent topology](.claude/rules/agent-topology.md) and pass dispatch gate. Cached context is not sufficient.

## Team topology

Name accountable owner at intake. Token efficiency governs model, effort, context, delegation without weakening checks. Follow topology for evidence-backed escalation and role-specific economical defaults.

- **Request Evaluator (bootstrap)** — runs once before the Controller exists; chooses only the lowest sufficient Controller logical level and stops. Never plans, decomposes, dispatches, or executes work.
- **Controller** — owns classification, queue, dependency ordering, ownership, dispatch, conflict resolution, integration decisions, and workset state. Default effort is light; it does not perform routine implementation or review.
- **Planner (on demand)** — decomposes Large/Complex or unresolved work initially or replans after a failed checkpoint. Parallelism alone does not require a Planner turn.
- **Lead Reviewer** — performs risk-based combined review. The deterministic route selects self-review for low-risk work and one Lead for meaningful integration risk; specialist review is added only for the concrete high-risk boundary that needs it.
- **Worker pool x N** — one Worker per independent executable queue item. Normal adaptive parallelism is 1/2/3/4 Workers; 5-6 is explicit burst mode only, subject to actual available runtime slots across all active roles.

Roles use provider-agnostic logical effort `light -> standard -> high -> max`. A capability failure may temporarily raise one level for the affected item; environment/tool/authority failures do not. Escalation always resets after the item.

Full role policy: [agent topology](.claude/rules/agent-topology.md).

## Routing and context discipline

- Read-only/status/explanation work: answer directly.
- Small, localized, reversible work with no contract/dependency impact: execute directly and verify; no tracker or queue item needed.
- Medium/Large, multi-step, risky, security-sensitive, approval-sensitive, contract-changing, or cross-area work: track before implementation, dispatch via queue.
- Load only current role context. Expand only after missing-context signal; keep bounded.
- Delegate with bounded Work Packet, never conversation dump.
- Before spawning, apply [Claude runtime dispatch contract](.claude/rules/agent-topology.md#claude-runtime-dispatch-contract): explicitly select mapped model from [agent-models.json](.claude/runtime/agent-models.json) and supported effort controls; never silently inherit Controller model.
- Use lowest logical effort likely to finish safely; do not select max preemptively.
- On failure, classify `environment|tooling|authority|missing-context|reasoning|implementation|planning` before retry/escalation.
- Provider/model mappings are runtime configuration, never durable queue authority.

Full policy: [execution router](.claude/rules/execution-router.md).

## Queue and claim invariant

Queue definitions in `.agents/queue/items/`. Claim leases in `.agent-runtime/claims/`, intentionally ignored by Git.

Worker must atomically claim before editing. At most one active claim per item; overlapping exclusive scopes must not run concurrently. Claims use lease and heartbeat; stale leases reclaimed via queue tool. Completion requires validation evidence.

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

Tracker is durable execution record. Queue is concurrency and ownership mechanism. Neither may silently override.

Full policy: [tracking](.claude/rules/tracking.md).

## Git and publication safety

Commit, push, merge, release, deployment are separate actions. Perform only authorized actions. Never work from detached HEAD. Never rewrite or discard user work.

Full policy: [Git workflow](.claude/rules/git-workflow.md).

## Definition of Done

Workset complete only when: all AC map to evidence, checks pass, queue/tracking synchronized, review has no blocking finding, documentation matches behavior, requested publication succeeds. Otherwise report `REVIEW`, `BLOCKED`, or `PARTIAL` truthfully.

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

Lower layers may add detail but not weaken workspace isolation, approval, security, data-integrity, queue ownership, or publication rules.

## Project-specific rules

None yet. When domain-specific rules are needed (e.g. API contracts, data-integrity invariants), add under `.claude/rules/` and link here; keep separate from generic workflow-agent rules.

## Index

Rules: [execution router](.claude/rules/execution-router.md) · [agent topology](.claude/rules/agent-topology.md) · [queue claim](.claude/rules/queue-claim.md) · [tracking](.claude/rules/tracking.md) · [Git workflow](.claude/rules/git-workflow.md) · [testing and DoD](.claude/rules/testing-dod.md)

Agents: [request-evaluator](.claude/agents/request-evaluator.md) · [worker](.claude/agents/worker.md) · [simple-worker](.claude/agents/simple-worker.md) · [lead-reviewer](.claude/agents/lead-reviewer.md) · [planner](.claude/agents/planner.md) · [model config](.claude/runtime/agent-models.json)

Skills: [execution router](.claude/skills/execution-router/SKILL.md) · [work tracking](.claude/skills/work-tracking/SKILL.md) · [queue claim](.claude/skills/queue-claim/SKILL.md) · [review workset](.claude/skills/review-workset/SKILL.md)
