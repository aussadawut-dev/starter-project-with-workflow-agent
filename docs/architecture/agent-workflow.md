# Agent Workflow Architecture

## Purpose

This workflow allows multiple coding agents to work in one repository without duplicate execution, context explosion, hidden ownership, or unsafe concurrent edits.

The design separates four concerns:

```text
Requirement  What must be achieved and why
Tracking     Durable decisions, plan, evidence, and closure
Queue        Executable dependency graph and priority
Claim        Atomic runtime ownership and lease
```

No layer silently replaces another.

## End-to-end flow

The canonical workflow is grouped into five Lean phases while preserving every existing queue/claim/security boundary:

```text
User request
    |
    v
ROUTE  = CLASSIFY + LOCATE
    |------ read-only ------> inspect narrowly -> answer
    |------ Small ----------> direct bounded edit -> VERIFY -> report
    |------ Medium/Large
    v
PREPARE = DECIDE + PLAN + QUEUE
    |
    v
EXECUTE = CLAIM + owned implementation
    |           |           |
 Worker A    Worker B    Worker C     (only independent READY items, cap 6)
    |           |           |
    +------ heartbeat -------+
    v
VERIFY = required/risk-triggered checks + fresh evidence fingerprint + review
    |
    v
FINALIZE = complete-once -> reconciliation -> tracker/requirement sync
    |
    v
PUBLISH / CLOSE only with separate authority
```

Detailed CLASSIFY/LOCATE/DECIDE/PLAN/QUEUE/CLAIM/SYNC semantics remain the same; the grouping removes repeated agent handoffs rather than removing controls. `scripts/agent_workflow.py` provides deterministic routing, packet/handoff validation, evidence freshness, event snapshot/delta and resumable finalize. `scripts/agent_queue.py` remains the ownership/lease source of truth and the rollback-compatible execution path.

## Roles

### Controller

The Controller is the sole orchestration owner. It classifies, locates, resolves decision deltas, creates the dependency graph, enqueues items, monitors ownership, integrates results, and synchronizes workset state.

It does not routinely implement or review. This prevents the highest-context agent from consuming tokens on work a bounded Worker can perform.

### Planner

The Planner is on demand. It appears only for initial Large/Complex decomposition or re-planning caused by a real dependency, architecture, or validation change.

It returns queue-ready boundaries and leaves the loop.

### Lead Reviewer

The Reviewer receives the accepted ACs, Work Packets, combined diff, evidence, and selected risk rules. It does not reread the whole repository by default.

Routine findings return to the owning Worker. Architecture, security, workspace, approval, destructive-operation, migration, and public-contract findings escalate.

### Worker pool

The pool size equals genuinely independent ready items, normally capped at six. Each Worker claims one item and reads only its Work Packet references.

A Worker may not claim future work merely to reserve it.

## Context routing

The system reduces token use through hierarchical routing:

```text
Root entry point
  -> one applicable rule
     -> one applicable skill/runbook
        -> one tracker/queue item
           -> named source files and tests
```

Agents do not preload every rule, historical tracker, or source directory.

The Controller passes references and exact boundaries instead of copying requirements, architecture prose, or conversation history into every Worker prompt. Lean Work Packets additionally carry explicit `maxBytes`, `maxFiles`, `maxToolCalls`, and `allowExpansion` context-budget metadata. These values control economy only; they never expand workspace, path, provider, process, or approval authority.

## Work Packet boundary

A queue item is ready only when it answers:

- What exact outcome is required?
- Which durable workset/task owns it?
- Which decisions are already accepted?
- Which dependencies must be DONE?
- Which capabilities are required?
- Which exclusive conflict keys apply?
- Which files are expected?
- Which areas are prohibited?
- Which ACs and validations prove completion?
- What handoff must be returned?

Discovery or architecture work without these answers belongs to the Controller/Planner, not the Worker queue.

## Queue state model

Durable queue item:

```text
TODO -> BLOCKED -> TODO
  \-> DONE
  \-> CANCELLED
```

Derived runtime state:

```text
WAITING  dependency incomplete
READY    eligible and unclaimed
CLAIMED  active lease
STALE    heartbeat expired
```

The active claim is the sole source of truth for in-progress ownership.

## Atomicity and concurrency

Claim-next is serialized by an atomic global coordination directory. Item ownership is represented by an atomic per-item claim directory. New queue definitions use exclusive file creation. State updates use atomic file replacement.

Exclusive scopes are opaque keys rather than guessed path overlap. The Controller assigns the same key to tasks that must not run concurrently.

Examples:

```text
contract:api-schema
runtime:process-policy
security:auth-boundary
docs:agent-governance
```

## Lease model

A lease prevents abandoned ownership from blocking the queue permanently.

- Default: 30 minutes.
- Heartbeat: at least every 10 minutes and around long operations.
- Expired lease: archived and removed by recovery.
- Lost lease: Worker stops editing and reclaims before continuing.
- Blocked work: durable `BLOCKED`, claim released.
- Unfinished handoff: claim released with reason.
- Completion: evidence persisted, item `DONE`, claim archived and removed.

## Tracker synchronization

Queue completion is not the end of the workflow.

```text
Q item state
  -> owning TASK state/evidence
     -> tracker snapshot/status
        -> requirement/index state
```

This synchronization happens immediately after each material state change, not at session end. Lean finalize records a token-free PREPARED/reconciliation state before completing the existing queue item and checks declared tracker markers afterward. A crash after queue completion is recovered from the queue's idempotency evidence; completion is never replayed. The finalize journal is ignored coordination metadata, not another ownership source of truth.

## Publication boundary

Editing, commit, push, merge, release, and deployment are distinct authorities. Queue ownership grants none of them automatically.

When implementation and review are complete but publication is not authorized, the truthful workset state is `REVIEW`.

## Operational example

```bash
# Controller
python3 scripts/agent_queue.py enqueue   --id Q0007   --title "Add rate limiting to the signup endpoint"   --workset TCK003   --task TASK-004   --objective "Reject excessive signup attempts from one source"   --capability typescript   --scope contract:api-schema   --validation "npm test -- signup"

# Worker
python3 scripts/agent_queue.py claim-next   --agent worker-ts-01   --capability typescript

export AGENT_CLAIM_TOKEN='<returned token>'

python3 scripts/agent_queue.py heartbeat --id Q0007

# after implementation and validation
python3 scripts/agent_queue.py complete   --id Q0007   --evidence "npm test -- signup: PASS"   --evidence "manual rate-limit scenarios: PASS"
```

## Design constraints

- Local runtime claim state assumes coordinating agents share one workspace filesystem.
- Claims are not distributed locks across unrelated clones or machines.
- Git branches do not replace claims.
- Queue JSON is human-reviewable and implementation-neutral.
- The Python queue utility has no third-party dependency.
