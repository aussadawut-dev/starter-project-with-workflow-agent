# TCK001 - Merge MCP V3.1 capability-vector topology

Started 2026-09-22 from `docs/waiting-implement/in-breakdown/imp-agent-topology-v3-1.md`.

## Requirement

Outcome: `.claude/rules/agent-topology.md` (+ registry config + role frontmatter) reflects the V3.1 capability-vector design: model selection by required-capability-vector match against a registry, measurable escalation predicates, hysteresis limits, Budget authority, binding review invariants, richer Handoff/model-change-request contracts - without breaking existing cross-references or the (untouched) Lean helper scripts.
Primary actor/consumer: Any Claude Code session (Controller/Planner/Worker/Lead Reviewer roles) reading this repo's governance.
Readiness: READY

### Acceptance criteria

- AC-01: Capability-vector model selection documented (axes, registry pointer, cheapest-sufficient-match, effort-snap); all existing section anchors referenced from CLAUDE.md/execution-router.md/queue-claim.md/agent role files remain valid.
- AC-02: `agent-models.json` valid JSON, Claude-only registry (real IDs), per-role floors, resolved mapping consistent with those floors.
- AC-03: 5 role `.md` files' `model:` frontmatter matches the resolved mapping.
- AC-04: New policy present: escalation predicates, hysteresis/limits, Budget section, review invariants, enriched Handoff, model-change-request contract, idempotency note.
- AC-05: `prepare-dispatch`/`validate-dispatch` fictional references corrected to real tooling (`route`, manual reread).
- AC-06: `validate_agent_governance.py`, `unittest discover`, `agent_queue.py validate` all PASS after the change.

## Scope

```text
IN   .claude/rules/agent-topology.md
IN   .claude/runtime/agent-models.json
IN   .claude/agents/{request-evaluator,planner,worker,simple-worker,lead-reviewer}.md
IN   docs/tracking/TEMPLATE.md, .claude/rules/tracking.md (Budget line only)
OUT  scripts/*.py, tests/*.py, execution-router.md structural changes, any rename of existing role/section names
```

## Decisions and assumptions

Confirmed decisions:

- No code or test reads `agent-models.json` or hardcodes these model IDs (verified via repo-wide grep) - restructuring it is safe.
- Registry stays Claude-only (fable-5-1, opus-5, sonnet-5, haiku-4-5-20251001), legacy sonnet-4-6/opus-4-6 kept as `deprecated: true` entries per Appendix-A-style maintenance rule (never delete, never reuse).
- Resolved role -> model (cheapest registry entry meeting the role's capability floor; ties broken by lowest cost_weight):
  - Request Evaluator: floor {reasoning>=5} -> `claude-haiku-4-5-20251001`
  - Simple Worker: floor {coding>=6} -> `claude-haiku-4-5-20251001`
  - Worker: floor {coding>=7} -> `claude-sonnet-5`
  - Lead Reviewer: floor {reasoning>=7, coding>=7} -> `claude-sonnet-5` (escalates to `claude-opus-5` when the specialist/high-risk floor raises reasoning>=9)
  - Planner: floor {reasoning>=7, coding>=6, longctx>=6, synthesis>=6} -> `claude-sonnet-5` (escalates to `claude-opus-5` on genuine architecture/contract ambiguity)
  - Controller: floor {reasoning>=8} -> `claude-opus-5` (session-level; cannot swap mid-session, per existing rule)
  - `claude-fable-5-1` kept in registry, not a default for any role; called out for items whose Planner/Worker-level required floor explicitly raises longctx/synthesis (large-document research/synthesis), consistent with "required_caps always wins" over role defaults.
- Budget is policy/reporting discipline only in this pass (task-level token ceiling set at intake, Controller cannot raise it, exhaustion -> stop/report/ask); no enforcing code is added since none currently reads/enforces it, matching the existing precedent that provider/model config here is advisory, not machine-enforced.
- `prepare-dispatch`/`validate-dispatch` do not exist as CLI subcommands (`scripts/agent_workflow.py --help` confirmed: route, escalate, validate-packet, validate-handoff, fingerprint, freshness, finalize, resume-finalize, events). Rule text corrected to stop asserting a tool that isn't there.

Safe assumptions:

- Capability axis scores (reasoning/coding/longctx/synthesis) and cost_weight are project-defined routing judgement (per the source doc's own disclaimer), reused directly from the user-supplied spec for opus-5/sonnet-5/fable-5-1/opus-4-6/sonnet-4-6; haiku-4-5 scores are newly assigned by this session (not in the source doc) since Haiku isn't scored there.

Open issues:

- None

## Impact

```text
Workspace/path boundary: None
Permission/approval: None
Tool schema/runtime/error contract: None - config/docs only, no code path reads these files
Process execution: None
Git/publication: None requested yet - stays at REVIEW until the user authorizes commit
Observability/audit: Decision-log framing added to Handoff contract section (session-local, not a new durable file)
Backward compatibility: Old model IDs kept as `deprecated: true`, not deleted
```

Risks and mitigations:

- Section-anchor breakage -> keep existing heading text stable; run link validator.
- Budget concept reading as unimplemented vaporware -> explicitly scope it as policy/reporting only.

## Dependency order

```text
TASK-001 -> TASK-002 (review) -> TASK-003 (sync/close)
```

## Tasks and queue mapping

```text
[x] TASK-001 | Rewrite agent-topology.md + registry + role frontmatter | Q0001 | DONE
[x] TASK-002 | Lead Reviewer pass (direct Agent dispatch) + fix its 1 blocking + 2 non-blocking findings | Q0002 | DONE
[x] TASK-003 | Sync tracker/IMP to closure, report REVIEW to user | None | DONE
```

## Queue items

| Item | Objective | Dependencies | Exclusive scopes | Status |
|---|---|---|---|---|
| Q0001 | Merge V3.1 capability-vector concepts into agent-topology.md + agent-models.json + role frontmatter | None | `docs:agent-governance` | DONE |
| Q0002 | Fix Lead Review findings on Q0001 (effort-vocabulary contradiction + 2 clarity notes) | Q0001 | `docs:agent-governance` | DONE |

## Validation plan and evidence

| AC / invariant | Evidence | Result |
|---|---|---|
| AC-01 | manual link/anchor check + `validate_agent_governance.py` link validator | PASS |
| AC-02 | `validate_agent_governance.py` JSON check + manual floor/resolution check (see Decisions) | PASS |
| AC-03 | manual diff of 5 `.md` frontmatter vs resolved mapping | PASS |
| AC-04 | manual section presence check (Capability Model, Budget, escalation predicates, hysteresis, review invariants, model-change-request, enriched Handoff, Decision log, idempotency note) | PASS |
| AC-05 | grep for `prepare-dispatch`/`validate-dispatch` - only the corrected explanatory text remains, no live instruction to run them | PASS |
| AC-06 | `validate_agent_governance.py` PASS; `unittest discover -s tests -v` 54/54 PASS; `agent_queue.py validate` PASS (0 errors) | PASS |

## Execution snapshot

```text
Status: REVIEW
Current item: None - all queue items DONE
Next ready item: None
Blocked by: None
Dependencies: None
Accepted decisions: see Decisions and assumptions above
Active exclusive scopes: None (docs:agent-governance released with Q0002 completion)
Required review/gates: LEAD - completed; 1 blocking finding (BLK-01) + 2 non-blocking (NB-01, NB-02), all fixed via Q0002 and self-verified (mechanical, low-risk correction - SELF tier per agent-topology.md review fan-out)
Last validation: 2026-09-22 - validate_agent_governance.py PASS, unittest 54/54 PASS, agent_queue.py validate PASS (post-fix rerun)
Budget: Not set by intake (no Requester/session budget ceiling was given for this task); tracked qualitatively only
Publication: DONE - commit f172635 on main, pushed to origin (6141e67..f172635), tag v1.1.0 (annotated, MINOR bump from v1.0.0) pushed to origin
```

## Handoff and completion

```text
Overall status: DONE
Completed: Implementation (Q0001), Lead review + fix of all findings (Q0002), full validation suite green, tracker/IMP synced, committed + pushed + tagged
Remaining: None. (Note: an unrelated, separately-requested caveman-compress pass over 32 governance files landed in the same commit/tag - see commit f172635 body; not tracked as its own queue item, Small/reversible/no-policy-change exception)
Blocked: None
Not run: None - all 3 required validations ran twice (pre- and post-fix), both green
Publication: commit f172635, pushed to origin/main (6141e67..f172635), tag v1.1.0 pushed to origin
Rollback/operations: Pure doc/config change (no application code, no scripts/tests touched); revert via git if needed (git revert f172635, git push --delete origin v1.1.0 + local tag delete if the tag itself must come back too)
```
