# Execution Router

Every agent uses this routing overlay before reading broadly or making changes.

```text
INTAKE -> CONTROLLER START -> ROUTE -> PREPARE -> DISPATCH GATE -> EXECUTE -> RECOVER? -> VERIFY -> FINALIZE

INTAKE           = fixed Request Evaluator chooses only Controller logical level + reason
CONTROLLER START = validate that selection and start a fresh Controller with explicit supported model/effort
ROUTE            = Controller CLASSIFY + LOCATE + downstream effort/review/parallelism choice
PREPARE          = Controller DECIDE + PLAN only when needed + QUEUE
DISPATCH         = fresh topology/role read + explicit runtime parameter validation
EXECUTE          = CLAIM + bounded implementation
RECOVER          = classify failure before retry/escalation
VERIFY           = targeted evidence + risk-triggered review
FINALIZE         = complete-once + SYNC + PUBLISH/CLOSE when authorized
```

Intake/startup pair is bootstrap, not delegated work phase. Request Evaluator ends after emitting validated Controller selection; only Controller enters ROUTE and makes downstream orchestration decisions. Grouped Lean phases reduce handoff/polling overhead but do not remove detailed lifecycle below. Tracking, queue, gateway, Git, approval, validation rules remain authoritative. `scripts/agent_workflow.py` may validate intake/startup, deterministically route, evaluate escalation, validate packets/handoffs, fingerprint evidence, reconcile events, finalize claimed items; `agent_queue_core.QueueStore` remains ownership source of truth.

## Lean helper discipline

See the [Lean runtime guide](../../docs/runtime/lean-agent-workflow.md) for CLI contracts, failure recovery and rollback.

- Before ROUTE, use fixed intake/startup gates when launching new Controller. Intake evaluator may choose only `controllerLevel` + reason; must not choose workers, Planner/Reviewer roles, parallelism, queue actions, execution steps.
- Pass validated `controllerLevel` into ROUTE. ROUTE echoes that level and may choose only downstream topology; never reconfigures Controller.
- Use deterministic route/packet validation for delegated work; do not spend Planner turn reproducing decision table tool can resolve.
- Use route's provider-agnostic effort policy; provider/model mapping is configuration, never queue authority.
- Context budget is economy limit, never authorization boundary. Expand only when evidence shows missing context; keep bounded.
- Classify failure before retrying. Environment, tooling, authority failures do not justify more expensive model.
- Capture evidence fingerprint after validations justify completion. Any changed HEAD/staged/unstaged/untracked/toolchain input makes evidence `STALE`.
- Prefer `events` snapshot/delta on reconnect or meaningful queue events over repeated LLM status polling. Lease heartbeat remains authoritative for liveness.
- For tracked work, Lean `finalize` may complete already-owned queue item once and record reconciliation state. Tracker/requirement prose synchronized by exact Controller-owned edits, then `resume-finalize --ack-sync` verifies declared markers.
- Legacy `agent_queue.py` path remains valid and is rollback path; Lean tooling never grants commit, push, release, deployment authority.

## CLASSIFY

CLASSIFY is Controller-owned. Intake selection ended before this point; Request Evaluator must not pre-classify work or pre-select downstream roles.

| Class | Criteria | Route |
|---|---|---|
| Read-only | Explanation, status, inspection, or diagnosis with no persistent change | Inspect narrowly and answer directly |
| Small | Localized, reversible, directly verifiable, no approval/security/contract/dependency impact | Execute directly, verify, no tracker or queue |
| Medium | Multiple material steps or one meaningful contract/runtime behavior change | Track, plan only if needed, queue, claim, execute, risk-based review |
| Large | Cross-area, architecture, security, approval model, data migration, release, or broad refactor; or a real multi-item workset | Controller + Planner only when needed + adaptive parallel Workers + risk-based review |

Treat uncertain work as Medium. Single-file change is not Small when it affects workspace isolation, permissions, approval, tool schemas, process execution, destructive actions, or public compatibility.

## LOCATE: lazy context loading

Read only the current role's layer.

```text
Controller
  Root CLAUDE.md
  Active requirement/tracker
  Queue summary and dependency state
  Only rules needed to classify or resolve decisions

Planner
  Accepted requirement/tracker
  Relevant architecture/rules and source boundaries
  No unrelated implementation history

Worker
  Repository CLAUDE.md
  Claimed queue item / Work Packet
  Only named rules, primary files, and required tests

Reviewer
  Acceptance criteria
  Work Packet(s)
  Combined diff and validation evidence
  Applicable risk/gate rules
```

Role may load one additional document when evidence shows it is needed; must not respond by reading entire policy or repository tree. If expansion is insufficient, record missing-context reason before loading another bounded slice.

## DECIDE

The Controller owns the decision delta.

- Reuse decisions already recorded in requirements, ADRs, trackers, root rules.
- Resolve architecture, security, approval, compatibility, destructive-operation, data-ownership ambiguity before queueing dependent work.
- Record assumptions only when reversible and low risk.
- Worker encountering material conflict stops only affected item, records `BLOCKED`, escalates concise decision request. Does not silently redesign system.
- Never spend Planner turn only to restate deterministic route or already accepted decision.

## PLAN: Work Packet

Every delegated queue item must be independently executable and contain:

```text
QUEUE ITEM          QNNNN
WORKSET             TCKNNN or accepted requirement reference
TASK                TASK-NNN
OBJECTIVE           One verifiable outcome
DEPENDENCIES        Queue IDs that must be DONE first
DECISIONS           Accepted decisions by reference
ACCEPTANCE CRITERIA Testable AC identifiers
REQUIRED CAPABILITY Worker skill tags (e.g. `typescript`, `docs`) - not the model capability-vector axes in agent-topology.md's Capability Model, a distinct concept
EXCLUSIVE SCOPES    Opaque conflict keys
RELEVANT RULES      Only rules required for this item
PRIMARY FILES       Expected edit surface
DO NOT TOUCH        Explicit exclusions
REQUIRED VALIDATION Commands/scenarios that must pass
CONTEXT BUDGET      bounded files/bytes/tool calls
HANDOFF             compact result + artifact refs when detail is needed
```

Do not put provider/model names in queue history. Route selects logical effort (`light|standard|high|max`); runtime/provider configuration maps that to actual model.

Do not create queue item that still requires broad discovery, architecture design, or unresolved decision. Route that to Planner or Controller first.

## QUEUE

The Controller converts dependency-safe tracker tasks into `.agents/queue/items/QNNNN.json`.

- Queue IDs are repository-local and stable.
- Dependencies form directed acyclic graph.
- Priority chooses among ready items but never overrides dependencies, capabilities, exclusive scopes.
- Use coarse explicit conflict keys: `contract:tool-schema`, `runtime:process-policy`, `file:scripts/agent_queue.py`.
- Do not queue two items that intentionally edit same coherent change unless one depends on other.
- Do not spawn six Workers for six items. Use adaptive recommendation: normally 1/2/3/4 Workers, 5-6 reserved for explicit burst. Clamp dispatch to actual available runtime slots including other active roles; recommendation never creates capacity.

## CLAIM

A Worker must claim before editing. Claim operations are atomic and lease based.

- One active item per Worker by default.
- Claim token proves ownership.
- Heartbeat before lease expires and before/after long-running execution.
- Release when handing back uncompleted work.
- Block when external decision/dependency prevents progress.
- Complete only after required validation evidence exists.
- Never manually delete or edit runtime claim files.

See [queue claim](queue-claim.md).

## DISPATCH GATE

Before assignment tool call, give user task/role, concrete requested model/effort, task-specific reason for each selection as required by [assignment rationale](agent-topology.md#required-user-visible-assignment-rationale). Applies to every assignment including follow-ups with unchanged settings. Record rationale in session-local dispatch evidence.

Before every spawn or follow-up (including correction, reassignment, escalation, resume), read [agent topology](agent-topology.md) in full and selected role file, then resolve role's required capability vector against [agent-models.json](../runtime/agent-models.json) (agent-topology.md's Capability Model and Mandatory fresh-read dispatch gate sections). No `prepare-dispatch`/`validate-dispatch` CLI — manual reread-and-resolve, optionally cross-checked with `python3 scripts/agent_workflow.py route`. Required, overrides cached-context/read-once advice. Unknown capability, stale resolution, unavailable model/effort, mismatched existing agent means no dispatch. Prompt-only role labels do not configure runtime. See topology for provider mapping, follow-up reuse, stop/resume rules.

## EXECUTE

- Work only inside claimed scope.
- Preserve unrelated user changes.
- Implement smallest dependency-safe slice.
- Start at route's baseline effort; do not select max preemptively.
- Apply topology's economical model selection before dispatch: mechanical work uses simple tier, ordinary implementation/review uses standard tier, high requires concrete planning/specialist/escalation trigger. Lower reasoning on strongest model does not satisfy economical selection. Name accountable owner, resolve tier in runtime configuration, fail closed if unavailable. No role defaults to frontier model; stronger-model request separately requires evidence of failed same-assignment attempt at baseline ceiling. Minimize total context and delegation overhead.
- Do not broaden scope merely because adjacent cleanup is convenient.
- Do not recursively delegate/subagent unless separate independent work item is queue-ready and ownership-safe.
- When needed change falls outside Work Packet, stop that portion and ask Controller to amend or create queue item.
- Keep heartbeat current during long work.

## RECOVER: classify before retry

Use `scripts/agent_workflow.py escalate --input failure.json` or the equivalent deterministic policy.

```text
environment/tooling
  -> remediate; retry at the same effort

authority
  -> block/request authority; same effort

missing-context
  -> bounded context expansion at the same effort
  -> only after expansion is used may a genuine capability failure escalate

reasoning/implementation/planning
  -> temporarily +1 effort level
  -> max one escalation by default
  -> success or terminal handoff resets to baseline
  -> exhausted/max -> re-plan; do not loop expensive retries
```

The stronger attempt receives an escalation capsule, not a conversation dump:

```text
item + objective + failing AC + touched scope + diff summary +
validation failure + fixed decisions + failure class + do-not-touch
```

## VERIFY

Use a validation waterfall:

1. Worker runs only focused tests/checks required by item plus checks triggered by actual diff.
2. Integration checkpoint runs combined targeted checks.
3. Run full suite/build once when combined workset warrants it.
4. Rerun required full-suite/build checks when subsequent code or relevant input changes invalidate evidence; also repeat for observed flakiness/nondeterminism or explicit release-certification. Do not repeat unchanged green checks without reason.

Review mode is risk based:

- `NONE` for read-only work.
- `SELF` for low-risk Small work or tracked Medium work with no risk flags when selected by the deterministic route.
- `LEAD` for Medium work with meaningful risk flags or ordinary Large integration.
- `LEAD_PLUS_SPECIALIST` only for the concrete specialist risks defined in agent-topology.

Evidence must name what ran and its result. “Looks good” is not evidence. Keep queue completion evidence compact; detailed browser traces, investigation narratives, or long command logs belong in a referenced evidence artifact, not repeatedly inside every queue JSON.

## SYNC

Synchronize in this order:

```text
queue item -> owning tracker task -> tracker status/snapshot -> requirement/index
```

After completion, blocked state, scope change, or material validation result, update durable records immediately. Do not defer to end of session.

## PUBLISH/CLOSE

Commit, push, merge, release, deployment, external publication require explicit authority. Without it, finish at truthful local state, commonly `REVIEW`.

Close only when all in-scope queue items terminal, AC have evidence, review has no unresolved blocker, requested publication complete.

## Forbidden

- Reading every rule, skill, tracker, source file by default.
- Delegating conversation transcript instead of Work Packet or escalation capsule.
- Preemptively using max effort for routine work.
- Escalating model effort for environment/tool/authority failures.
- Keeping escalated model as new baseline after one item succeeds.
- Spawning recursive subagents without independent queue-ready work.
- Running multiple generic review angles with overlapping questions.
- Editing before claim acquisition.
- Sharing or reusing another Worker's claim token.
- Claiming multiple items to reserve future work.
- Treating stale claim as permission to edit without reclaiming via queue tool.
- Marking `DONE` without evidence.
- Letting queue state and tracker state disagree.
