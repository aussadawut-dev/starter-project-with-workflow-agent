# Execution Router

Every agent uses this routing overlay before reading broadly or changing files.

```text
ROUTE -> PREPARE -> EXECUTE -> RECOVER? -> VERIFY -> FINALIZE

ROUTE     = CLASSIFY + LOCATE + effort/review/parallelism choice
PREPARE   = DECIDE + PLAN only when needed + QUEUE
EXECUTE   = CLAIM + bounded implementation
RECOVER   = classify failure before retry/escalation
VERIFY    = targeted evidence + risk-triggered review
FINALIZE  = complete-once + SYNC + PUBLISH/CLOSE when authorized
```

The grouped Lean phases reduce handoff/polling overhead; they do not remove the detailed lifecycle below. Tracking, queue, gateway, Git, approval and validation rules remain authoritative. `scripts/agent_workflow.py` may deterministically route, evaluate temporary escalation, validate packets/handoffs, fingerprint evidence, reconcile events and finalize a claimed item, but `agent_queue_core.QueueStore` remains the ownership source of truth.

## Lean helper discipline

See the [Lean runtime guide](../../docs/runtime/lean-agent-workflow.md) for CLI contracts, failure recovery and rollback.

- Use deterministic route/packet validation when work is being delegated; do not spend a Planner turn reproducing a decision table the tool can resolve.
- Use the route's provider-agnostic effort policy; provider/model mapping is configuration and never queue authority.
- A context budget is an economy limit, never an authorization boundary. Expand it only when evidence shows missing context and keep the expansion bounded.
- Classify a failure before retrying. Environment, tooling, and authority failures do not justify a more expensive model.
- Capture an evidence fingerprint after the validations that justify completion. Any changed HEAD/staged/unstaged/untracked/toolchain input makes that evidence `STALE`.
- Prefer `events` snapshot/delta on reconnect or meaningful queue events over repeated LLM status polling. Lease heartbeat remains authoritative for liveness.
- For tracked work, Lean `finalize` may complete the already-owned queue item once and record reconciliation state. Tracker/requirement prose is still synchronized by exact Controller-owned edits, then `resume-finalize --ack-sync` verifies the declared markers.
- The legacy `agent_queue.py` path remains valid and is the rollback path; Lean tooling never grants commit, push, release or deployment authority.

## CLASSIFY

| Class | Criteria | Route |
|---|---|---|
| Read-only | Explanation, status, inspection, or diagnosis with no persistent change | Inspect narrowly and answer directly |
| Small | Localized, reversible, directly verifiable, no approval/security/contract/dependency impact | Execute directly, verify, no tracker or queue |
| Medium | Multiple material steps or one meaningful contract/runtime behavior change | Track, plan only if needed, queue, claim, execute, risk-based review |
| Large | Cross-area, architecture, security, approval model, data migration, release, or broad refactor; or a real multi-item workset | Controller + Planner only when needed + adaptive parallel Workers + risk-based review |

Treat uncertain work as Medium. A single-file change is not Small when it affects workspace isolation, permissions, approval, tool schemas, process execution, destructive actions, or public compatibility.

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

A role may load one additional document when evidence shows it is needed; it must not respond by reading the entire policy or repository tree. If that expansion is insufficient, record the missing-context reason before loading another bounded slice.

## DECIDE

The Controller owns the decision delta.

- Reuse decisions already recorded in accepted requirements, ADRs, trackers, or root rules.
- Resolve architecture, security, approval, compatibility, destructive-operation, and data-ownership ambiguity before queueing dependent work.
- Record assumptions only when they are reversible and low risk.
- A Worker encountering a new material conflict stops only the affected item, records `BLOCKED`, and escalates a concise decision request. It does not silently redesign the system.
- Never spend a Planner turn only to restate a deterministic route or already accepted decision.

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
REQUIRED CAPABILITY Worker capabilities needed
EXCLUSIVE SCOPES    Opaque conflict keys
RELEVANT RULES      Only rules required for this item
PRIMARY FILES       Expected edit surface
DO NOT TOUCH        Explicit exclusions
REQUIRED VALIDATION Commands/scenarios that must pass
CONTEXT BUDGET      bounded files/bytes/tool calls
HANDOFF             compact result + artifact refs when detail is needed
```

Do not put provider/model names into queue history. The route selects logical effort (`light|standard|high|max`); runtime/provider configuration maps that effort to an actual model.

Do not create a queue item that still requires broad discovery, architecture design, or an unresolved decision. Route that work to the Planner or Controller first.

## QUEUE

The Controller converts dependency-safe tracker tasks into `.agents/queue/items/QNNNN.json`.

- Queue IDs are repository-local and stable.
- Dependencies form a directed acyclic graph.
- Priority chooses among ready items but never overrides dependencies, capabilities, or exclusive scopes.
- Use coarse explicit conflict keys such as `contract:tool-schema`, `runtime:process-policy`, or `file:scripts/agent_queue.py`.
- Do not queue two items that intentionally edit the same coherent change unless one depends on the other.
- Do not materialize six Workers because six items exist. Use the adaptive recommendation: normally 1/2/3/4 Workers, with 5-6 reserved for explicit burst mode.

## CLAIM

A Worker must claim before editing. Claim operations are atomic and lease based.

- One active item per Worker by default.
- The claim token proves ownership.
- Heartbeat before the lease expires and before/after long-running execution.
- Release when handing back uncompleted work.
- Block when an external decision/dependency prevents progress.
- Complete only after required validation evidence exists.
- Never manually delete or edit runtime claim files.

See [queue claim](queue-claim.md).

## EXECUTE

- Work only inside the claimed scope.
- Preserve unrelated user changes.
- Implement the smallest dependency-safe slice.
- Start at the route's baseline effort; do not preemptively select max effort.
- Do not broaden scope merely because adjacent cleanup is convenient.
- Do not recursively delegate/subagent unless a separate independent work item is queue-ready and ownership-safe.
- When a needed change falls outside the Work Packet, stop that portion and ask the Controller to amend or create a queue item.
- Keep the heartbeat current during long work.

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

1. Worker runs only focused tests/checks required by its item plus checks triggered by the actual diff.
2. Integration checkpoint runs combined targeted checks.
3. Run the full suite/build once when the combined workset warrants it.
4. Repeat a full suite only for observed flakiness/nondeterminism or explicit release-certification policy.

Review mode is risk based:

- `SELF` for low-risk Small work.
- `LEAD` for ordinary Medium/Large integration.
- `LEAD_PLUS_SPECIALIST` only for the concrete specialist risks defined in agent-topology.

Evidence must name what ran and its result. “Looks good” is not evidence. Keep queue completion evidence compact; detailed browser traces, investigation narratives, or long command logs belong in a referenced evidence artifact, not repeatedly inside every queue JSON.

## SYNC

Synchronize in this order:

```text
queue item -> owning tracker task -> tracker status/snapshot -> requirement/index
```

After completion, blocked state, scope change, or material validation result, update the durable records immediately. Do not defer synchronization to the end of the session.

## PUBLISH/CLOSE

Commit, push, merge, release, deployment, and external publication require explicit authority. Without it, finish at the truthful local state, commonly `REVIEW`.

Close only when all in-scope queue items are terminal, acceptance criteria have evidence, review has no unresolved blocker, and requested publication is complete.

## Forbidden

- Reading every rule, skill, tracker, or source file by default.
- Delegating a conversation transcript instead of a Work Packet or escalation capsule.
- Preemptively using max effort for routine work.
- Escalating model effort for environment/tool/authority failures.
- Keeping an escalated model as the new baseline after one item succeeds.
- Spawning recursive subagents without independent queue-ready work.
- Running multiple generic review angles with overlapping questions.
- Editing before claim acquisition.
- Sharing or reusing another Worker's claim token.
- Claiming multiple items to reserve future work.
- Treating a stale claim as permission to edit without reclaiming it through the queue tool.
- Marking `DONE` without evidence.
- Letting queue state and tracker state disagree.
