# Lean Agent Workflow runtime guide

The Lean workflow groups the development lifecycle into:

```text
ROUTE -> PREPARE -> EXECUTE -> RECOVER? -> VERIFY -> FINALIZE
```

This is additive orchestration. `scripts/agent_queue.py` and `agent_queue_core.QueueStore` remain the source of truth for item ownership, leases, dependencies, capabilities and exclusive scopes.

## What Lean removes

Lean tooling handles deterministic coordination without repeated agent reasoning:

- work-shape routing from explicit semantic-risk flags
- adaptive worker-count, review-mode and logical-effort recommendations
- temporary escalation decisions from explicit failure class
- Work Packet / handoff completeness checks
- bounded context/tool-budget metadata
- Git dirty-state evidence freshness
- complete-once finalize reconciliation
- queue/finalize event snapshots and deltas after reconnect

Does **not** remove Planner/Reviewer gates when risk requires them, nor add commit/push/deploy authority.

## CLI

Route a declared work shape:

```bash
python3 scripts/agent_workflow.py route --input route.json
```

Route output includes:

```text
classification
plannerRequired
reviewerRequired
recommendedWorkers
reviewMode
effortPolicy
reasonCodes
```

Evaluate failed attempt before retrying:

```bash
python3 scripts/agent_workflow.py escalate --input failure.json
```

Example input:

```json
{
  "version": "1.0.0",
  "item": "Q0123",
  "role": "worker",
  "currentLevel": "standard",
  "failureClass": "implementation",
  "escalationCount": 0,
  "maxEscalations": 1,
  "contextExpansionUsed": false
}
```

Possible actions are `REMEDIATE_SAME_LEVEL`, `BLOCK_FOR_AUTHORITY`, `EXPAND_CONTEXT`, `ESCALATE_ONE_LEVEL`, or `REPLAN`. Escalation is always temporary/item-scoped with `resetAfterItem` true.

Validate Work Packet or completed handoff:

```bash
python3 scripts/agent_workflow.py validate-packet --input packet.json
python3 scripts/agent_workflow.py validate-handoff --input handoff.json
```

Capture evidence after checks that justify completion:

```bash
python3 scripts/agent_workflow.py fingerprint --output /tmp/evidence.json
python3 scripts/agent_workflow.py freshness --input /tmp/evidence.json
```

Evidence record stores HEAD, hashes of staged/unstaged/untracked inputs, untracked count and bounded toolchain facts. Does not store raw diff/content or untracked file names. Changed input returns `STALE`.

Finalize currently owned item:

```bash
export AGENT_CLAIM_TOKEN='<session-local claim token>'
python3 scripts/agent_workflow.py finalize --input finalize.json
```

Finalize writes token-free ignored record under `.agent-runtime/finalize/`, then completes item through existing QueueStore. Completion evidence includes idempotency marker. Crash reconciles without replaying `complete`:

```bash
python3 scripts/agent_workflow.py resume-finalize --item QNNNN
```

After Controller has synchronized declared tracker markers:

```bash
python3 scripts/agent_workflow.py resume-finalize --item QNNNN --ack-sync
```

`--ack-sync` is check-only. Never rewrites requirement decisions or acceptance prose. Missing markers keep record `RECONCILIATION_REQUIRED`; later tracker drift changes prior `SYNCED` record back to reconciliation-required.

## Event-driven coordination

Get authority snapshot:

```bash
python3 scripts/agent_workflow.py events > /tmp/events.json
```

After completion/blocker/reconnect or meaningful event, request delta:

```bash
python3 scripts/agent_workflow.py events --previous /tmp/events.json
```

Snapshots expose queue durable/derived state, token-free claim metadata and finalize state. Coordination optimization only. Heartbeat/lease state in QueueStore remains liveness authority; events never permit editing.

## Route contract

`READ_ONLY` and low-risk reversible single-step `SMALL` changes avoid tracker/queue overhead. Unknown risk flags fail closed. Permission, approval, security, migration, release, workspace-isolation, destructive, public-contract and cross-area work always route `LARGE`. Meaningful bounded flags such as tool-schema/process-execution route at least `MEDIUM`.

Parallelism adaptive by default:

```text
1 independent item    -> 1 worker
2-3                   -> 2 workers
4-5                   -> 3 workers
6+                    -> 4 workers
explicit burst        -> up to 6
high semantic risk    -> cap at 3
```

Parallel work alone does not force Planner turn when task boundaries already independently executable. Recommendation cannot override dependency or exclusive-scope conflicts in QueueStore.

Review similarly bounded: `SELF`, `LEAD`, or `LEAD_PLUS_SPECIALIST`. No generic multi-reviewer fan-out by default.

## Logical effort and provider mapping

Workflow stores logical effort only:

```text
light -> standard -> high -> max
```

Provider names are deployment configuration, not durable queue semantics. Canonical mappings and provider-specific dispatch contracts live in [agent topology](../../.claude/rules/agent-topology.md#provider-agnostic-effort-ladder). Do not duplicate mapping: Codex and Claude expose different selection and effort controls.

Before delegation, resolve logical role/effort into provider's explicit model selection. Follow [Codex contract](../../.claude/rules/agent-topology.md#codex-runtime-dispatch-contract) or [Claude contract](../../.claude/rules/agent-topology.md#claude-runtime-dispatch-contract), and distinguish requested model from runtime-verified selection.

Provider mapping changes must not alter authorization, queue ownership, validation, approval, or publication behavior.

## Failure classification and temporary escalation

Do not retry blindly.

```text
environment/tooling
  -> repair and retry same level

authority
  -> block/request authority; same level

missing-context
  -> bounded context expansion first
  -> stronger model only after expansion is used and capability remains problem

reasoning/implementation/planning
  -> temporary +1 logical level
  -> one escalation by default
  -> reset after item
  -> max/exhausted -> REPLAN
```

Stronger attempt receives escalation capsule with only item, objective, failing AC, touched scope/diff summary, validation failure, fixed decisions, failure class, and do-not-touch constraints. Do not replay chat history.

## Context/tool budgets

Each delegated Lean Work Packet includes:

```json
{
  "contextBudget": {
    "maxBytes": 65536,
    "maxFiles": 16,
    "maxToolCalls": 24,
    "allowExpansion": true
  }
}
```

Budget exhaustion is not permission error. If required context is missing and `allowExpansion` is true, role may deliberately expand within contract maximum and record why. Tool visibility and context budget never grant workspace/path/provider access.

## Compact handoff/evidence

Handoffs stay small: changed files/behavior, concise validation result pairs, AC coverage, risks, follow-up, claim state, evidence fingerprint, and optional `artifactRefs`.

Detailed browser walkthroughs, long investigation narratives, or review transcripts belong in referenced evidence artifacts when useful. Queue completion evidence indexes detail rather than duplicating it.

## Validation waterfall

Workers run focused validation for owned slice. Integration checkpoint runs combined targeted checks and full suite/build once when required. Repeat identical full-suite validation only for observed flakiness/nondeterminism or explicit release certification.

## Failure and recovery rules

- `STALE` evidence -> rerun affected validation; do not finalize
- environment/tool/authority failure -> do not buy more model capability
- missing context -> expand bounded context before model escalation
- capability failure -> at most +1 temporary level by default, then re-plan
- PREPARED finalize + queue still TODO -> original live claim token required and evidence rechecked before completion
- PREPARED finalize + queue DONE with matching idempotency marker -> reconcile without completing again
- queue DONE with different marker -> conflict; do not claim historical success
- missing tracker marker -> `RECONCILIATION_REQUIRED`
- event loss/duplicate/out-of-order -> take new authority snapshot; do not infer ownership from event stream

## Rollout and rollback

Rollout order:

1. deterministic route/packet validation
2. adaptive effort/review/worker-count routing
3. failure classification and temporary escalation
4. evidence freshness for tracked development work
5. finalize/reconciliation for opted-in items
6. event snapshot/delta to replace routine status polling
7. expand to multi-agent worksets only after provider/worktree gates accepted

Rollback simple: stop invoking `agent_workflow.py` and continue with `agent_queue.py`. Queue definitions and claims require no migration. `.agent-runtime/finalize/` is ignored coordination metadata not needed to interpret queue ownership.

## Measurement

Do not claim token/cost savings without provider telemetry. Measure at least: prompt/input tokens per completed queue item, retries per item, escalation rate, Planner turns, reviewer fan-out, context files/bytes loaded, full-suite executions, and wall-clock completion. Safety acceptance requires high-risk routing remain heavy and authority boundaries never weaken.
