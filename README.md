# Workflow Agent Starter Project

Portable starter repository for a bounded multi-agent software-development workflow.

The workflow keeps **requirements, tracking, queue ownership, runtime claims, verification, and publication authority** separate so multiple agents can work concurrently without treating chat history as the source of truth.

## How it works

Every request funnels through one routing pipeline, whether it's answered in a single turn or split across several parallel Workers:

```text
INTAKE -> CONTROLLER START -> CLASSIFY -> LOCATE -> DECIDE -> PLAN (if needed)
   -> QUEUE -> DISPATCH GATE -> CLAIM -> EXECUTE -> RECOVER (if needed)
   -> VERIFY -> SYNC -> PUBLISH/CLOSE
```

A small, fixed **Request Evaluator** looks at the incoming request just long enough to pick a starting effort level for the Controller, then stops. From there, one **Controller** owns classification, decomposition, and integration for the whole request — it does not do the routine typing itself unless the task is genuinely small.

```text
                         USER
                          |
                 REQUEST EVALUATOR   (bootstrap: picks Controller level, then stops)
                          |
                      CONTROLLER      (classify, plan, queue, integrate, publish)
                     /     |     \
               PLANNER  WORKER POOL  LEAD REVIEWER
              (on demand) (1-4 normal,  (risk-based:
                           5-6 burst)    NONE / SELF / LEAD / LEAD_PLUS_SPECIALIST)
```

Work that's genuinely small — a one-line fix, a localized reversible edit — never touches the queue: the Controller just makes the change and verifies it. Work that's Medium or Large gets a **tracker** (`docs/tracking/TCKNNN-*.md`) recording decisions and acceptance criteria, broken into **queue items** (`.agents/queue/items/QNNNN.json`) that Workers atomically claim, execute, and complete with evidence attached.

## Why this shape

- **No ceremony on small work.** Read-only questions get answered directly; small reversible edits get made directly. The queue/tracker machinery only activates for work that's actually multi-step, risky, or needs more than one owner.
- **Concurrency without collisions.** A Worker claims an item with an atomic lease before touching it; `exclusiveScopes` stop two Workers from editing the same file or behavior at once. No claim, no edit.
- **Nothing is "DONE" on vibes.** A queue item can't close without evidence attached — a command that ran, a test that passed. A tracker can't close with an unresolved blocking review finding or a stale claim left behind.
- **Cheapest sufficient model, every time.** The same kind of task doesn't default to the most expensive available model just because it's there — see below.
- **Publication is a separate decision from editing.** Commit, push, merge, tag, and deploy each need their own explicit go-ahead; finishing the work never silently authorizes shipping it.
- **Portable.** `CLAUDE.md` + `.claude/` is canonical for any agent runtime that reads it; `AGENTS.md` + `.agents/skills/` are thin pointers for other tools, so there is never a second copy of the policy to keep in sync.

## Project structure

```text
.
├── CLAUDE.md                       entry point every agent reads first
├── AGENTS.md                       thin adapter -> points to CLAUDE.md
├── README.md
├── .claude/                        canonical policy + Claude-runtime binding
│   ├── rules/                      the actual policy
│   │   ├── agent-topology.md       roles, capability-vector model selection, escalation
│   │   ├── execution-router.md     routing pipeline (CLASSIFY/LOCATE/.../PUBLISH)
│   │   ├── queue-claim.md          atomic claim/lease/exclusive-scope protocol
│   │   ├── tracking.md             requirement -> tracker -> queue -> closure lifecycle
│   │   ├── git-workflow.md         commit/push/release authority boundaries
│   │   └── testing-dod.md         validation waterfall + Definition of Done
│   ├── agents/                     one file per dispatchable role (model pinned per role)
│   │   ├── request-evaluator.md
│   │   ├── planner.md
│   │   ├── worker.md
│   │   ├── simple-worker.md
│   │   └── lead-reviewer.md
│   ├── skills/                     executable procedures (canonical)
│   │   ├── execution-router/SKILL.md
│   │   ├── queue-claim/SKILL.md
│   │   ├── review-workset/SKILL.md
│   │   └── work-tracking/SKILL.md
│   ├── commands/                   slash-command wrappers around the skills above
│   │   ├── claim-next.md
│   │   ├── commit-workset.md
│   │   ├── complete-claim.md
│   │   ├── publish-workset.md
│   │   └── release-claim.md, review-workset.md
│   └── runtime/agent-models.json   capability-vector model registry (see below)
├── .agents/                        non-Claude-runtime side
│   ├── skills/                     thin adapters -> point back to .claude/skills/
│   │   └── {execution-router,queue-claim,review-workset,work-tracking}/SKILL.md
│   └── queue/
│       ├── schema/queue-item.schema.json
│       └── items/                  durable queue items (QNNNN.json)
├── docs/
│   ├── architecture/agent-workflow.md
│   ├── runtime/lean-agent-workflow.md
│   ├── queue/README.md + examples/
│   ├── tracking/                   trackers (TCKNNN-*.md) - the durable execution record
│   │   ├── README.md, TEMPLATE.md, evidence/README.md
│   │   └── TCK001-agent-topology-v3-1.md
│   └── waiting-implement/          requirements: intake -> in-breakdown -> implemented
│       ├── README.md, TEMPLATE.md
│       ├── in-breakdown/README.md
│       └── implemented/README.md + imp-agent-topology-v3-1.md
├── scripts/
│   ├── agent_queue.py              CLI: enqueue/claim/heartbeat/complete/...
│   ├── agent_queue_{core,store,claims,common}.py   atomic claim/lease/scope-conflict engine
│   ├── agent_workflow.py           CLI: route/escalate/validate-packet/finalize/...
│   ├── agent_workflow_{contracts,evidence,finalize}.py
│   └── validate_agent_governance.py   repo-wide required-paths/JSON/link/skill checker
└── tests/test_agent_*.py           governance, queue, and workflow tests

Not tracked (local/ephemeral, see .gitignore): .agent-runtime/ (claim leases), __pycache__/, *.pyc
```

`scripts/*.py` use the standard library only - no third-party dependency to install. Historical queue items from the source project are intentionally **not included**; a new project starts with a clean queue.

## Choosing model + effort

A role (Controller, Planner, Worker, Lead Reviewer, ...) is a fixed responsibility. The model and effort behind it are not fixed — both are resolved per task from a small capability registry (`.claude/runtime/agent-models.json`).

Each candidate model is scored 1-10 on four axes, plus a relative cost weight:

```text
reasoning   multi-step logic, architecture, novel problems
coding      implementation, refactoring, debugging
longctx     holding and navigating large context accurately
synthesis   writing, summarizing, research
```

A role (or a specific work item that needs more) declares a **floor** on those axes. Selection: filter every non-deprecated model that clears every axis of that floor, then take the cheapest one left. Nothing climbs to a stronger model just because it's available, and nothing gets assigned a model that doesn't actually clear the floor — an empty result means re-scope the item, not lower the bar.

Right now that resolves to three real tiers: `claude-haiku-4-5` for cheap, mechanical work (the bootstrap Request Evaluator, Simple Worker), `claude-sonnet-5` for ordinary implementation/planning/review (Worker, Planner, Lead Reviewer), and `claude-opus-5` for the Controller's sustained, cross-cutting reasoning. A fourth model, `claude-fable-5-1`, stays in the registry as a long-context/synthesis specialist for the rare item that genuinely needs it — it is nobody's default.

Effort (`light -> standard -> high -> max`) is a separate, lighter dial on top of whichever model gets picked — how much depth to ask for, not which model to use. It can rise mid-task on real evidence of trouble (repeated tool errors, repeated test failures), but only steps back down at a clean phase boundary, never mid-item, so it doesn't thrash. Changing the *model* (rather than just the effort) needs the Controller's sign-off and only happens for a genuine capability gap; every escalation is charged against a per-task budget and capped, so a struggling task gets re-planned instead of endlessly climbing to a bigger model.

Full mechanics: [`.claude/rules/agent-topology.md`](.claude/rules/agent-topology.md).

## Requirements

- Python 3
- Git
- An agent runtime that can read repository instructions (Claude Code, Codex-compatible tooling, or another runtime wired to the same files)

The Python workflow tooling uses the standard library only.

## Validate

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_agent_governance.py
python3 scripts/agent_queue.py validate
```

## Start a work item

For Medium/Large work:

1. Capture the requirement from `docs/waiting-implement/TEMPLATE.md`.
2. Create a tracker from `docs/tracking/TEMPLATE.md`.
3. Create queue-ready work packets under `.agents/queue/items/`.
4. Claim before editing, validate the owned scope, then complete/block/release truthfully.
5. Review the combined workset before any separately authorized commit, push, release, or deploy.

Queue CLI help:

```bash
python3 scripts/agent_queue.py --help
python3 scripts/agent_workflow.py --help
```

See `docs/architecture/agent-workflow.md` and `docs/runtime/lean-agent-workflow.md` for the full model.
