# Agent Topology

Use smallest topology and lowest provider-agnostic effort that safely completes active workset. Roles are responsibilities, not permanent people or model names: role is fixed, model and effort are runtime resources resolved per item from capability-vector registry (see Capability Model), never linear rank.

## Intake evaluator and Controller start

A new request may enter through one fixed, bounded **Request Evaluator** before any Controller exists. This bootstrap role has exactly one responsibility: choose lowest sufficient logical Controller level (`light|standard|high|max`) and give short reason. It does not classify workset, decompose tasks, choose Planner/Reviewer/Workers, choose parallelism, create/claim queue items, dispatch agents, run mutations/processes, review results, or publish.

```text
User request
  -> fixed Request Evaluator
  -> { version, controllerLevel, reason }
  -> fresh Controller start with explicit supported runtime model/effort
  -> ROUTE / PREPARE / DISPATCH / EXECUTE / VERIFY / FINALIZE
```

Evaluator's runtime profile is configuration, not queue authority. Output must contain only `version`, `controllerLevel`, and `reason`; extra orchestration fields fail closed. Once fresh Controller starts, evaluator is finished. Controller receives original request plus validated selection and owns every downstream routing and orchestration decision.

For Claude, bind named `request-evaluator` role/model and exact `effort` only when live Agent tool exposes that parameter; otherwise receipt is model-only and explicitly reports numerical reasoning effort as unverified. Claude Controller startup follows same rule: exact model + effort when supported, otherwise exact model only. Never reinterpret bootstrap effort as Controller effort, invent unsupported Claude effort, or silently reuse already-running Controller with different settings.

## Mandatory fresh-read dispatch gate — every runtime

Before **every** assignment (new agent, follow-up, reassignment, resumed task, correction or effort escalation), Controller must freshly read this entire file and selected role file. This overrides ordinary read-once/context-cache guidance. Prior read, summary, role name or logical-effort label is not dispatch evidence.

1. Reread this topology, select role from route and actual work, and load its role file. Planner remains conditional.
2. Read runtime mapping in [agent-models.json](../runtime/agent-models.json) and live agent-tool capabilities. Resolve role's required capability vector (see Capability Model) against registry to get concrete model, and optionally run `python3 scripts/agent_workflow.py route` to cross-check classification driving this dispatch. No `prepare-dispatch`/`validate-dispatch` CLI helper — no such subcommands exist in `scripts/agent_workflow.py`; this step is manual reread-and-resolve, not automated gate. Keep resolution in ignored runtime state or temporary files, never queue authority.
3. Immediately before tool call, recheck resolved model/effort against exact proposed parameters: reject stale resolution, unsupported combination, or omitted/changed parameter. Failed check means no dispatch until mapping is resolved visibly.
4. For new agent, pass exact concrete spawn parameters to runtime. Claude invokes named role with `subagent_type` and explicit model. Pass numerical effort only if current tool supports that parameter; otherwise report `role-model-only`, never claim prose changed reasoning settings.
5. For follow-ups, repeat gate and verify existing agent's recorded role and requested runtime settings. Validate recorded spawn parameters; do not send unsupported model arguments to follow-up tool. Follow-up text cannot change model/effort. If settings differ or unknown, release old ownership and spawn correctly configured agent. Carry fresh relevant role instructions in bounded Work Packet.
6. Before every assignment tool call, explain model and effort selection to user using assignment rationale below.
7. Record assignment, role, logical effort, concrete requested settings, model/effort rationale, source fingerprint and returned agent identity in session-local evidence (see Decision log). Requested settings prove request, not unreported backend model. Never assert hidden runtime state.

This gate is manual discipline, not machine-enforced lock: no tool in this repo can intercept arbitrary external agent-tool call. Skipping reread is workflow violation regardless.

### Required user-visible assignment rationale

Every dispatch must include concise explanation before tool call; hidden receipt or final summary alone is insufficient. This includes new agents, follow-ups, corrections, reassignment, resume and escalation, even when settings are unchanged. State:

- **Task and role:** bounded outcome being delegated.
- **Model and reason:** concrete requested model from supported runtime mapping, why its capabilities fit this task, and any availability constraint that affected choice. Do not invent model capabilities.
- **Effort and reason:** both logical effort and actual requested runtime effort when supported; connect choice to concrete complexity, uncertainty, risk, or validation needs. Explain why this is lowest sufficient level. Role label or "per mapping" alone is not rationale.
- **Follow-up or escalation:** explain why existing settings remain suitable or why change is justified. For escalation, name observed failure class and evidence, and item-scoped reset to baseline.

Use user's language. Compact format: "Assigning <task> to <role>, model <model>, because <task-specific capability reason>; effort <logical>/<runtime>, because <complexity/risk reason>." For `role-model-only`, explicitly say runtime effort cannot be set instead of implying it was configured. Never assert hidden backend settings. Keep concrete model names and dispatch rationale in session-local evidence, not durable queue authority.

This block is machine-readable source of role baselines — sole authoritative logical `effort` per role; [agent-models.json](../runtime/agent-models.json) deliberately does not restate it, to avoid two sources drifting apart. `requiredCaps` is default capability-vector floor per role (see Capability Model); an item may raise it, never lower it. Provider models remain runtime configuration, not role policy or queue authority — concrete `model_id` for each floor is resolved from agent-models.json, never hardcoded here. `request-evaluator` is intentionally absent: it is pre-Controller bootstrap role Controller never dispatches through this gate (its capability floor and resolved model live in agent-models.json's `roleDefaults.requestEvaluator`).

<!-- dispatch-roles -->
```json
{
  "controller": { "effort": "light", "file": null, "requiredCaps": {"reasoning": 8, "coding": 6, "longctx": 6, "synthesis": 6} },
  "planner": { "effort": "high", "file": ".claude/agents/planner.md", "requiredCaps": {"reasoning": 7, "coding": 6, "longctx": 6, "synthesis": 6} },
  "lead-reviewer": { "effort": "standard", "file": ".claude/agents/lead-reviewer.md", "requiredCaps": {"reasoning": 7, "coding": 7, "longctx": 6, "synthesis": 5} },
  "worker": { "effort": "standard", "file": ".claude/agents/worker.md", "requiredCaps": {"reasoning": 6, "coding": 7, "longctx": 5, "synthesis": 4} },
  "simple-worker": { "effort": "light", "file": ".claude/agents/simple-worker.md", "requiredCaps": {"reasoning": 4, "coding": 6, "longctx": 3, "synthesis": 3} }
}
```

For dispatch policy, Controller is active orchestrating session and is not dispatchable worker role. Already-running Controller cannot change its actual model/effort through prompt or policy text; report that limitation instead of claiming change. Fresh Controller may instead be started only through validated intake-selection/startup path above. User stop/pause stops affected agents/commands, releases claims and leaves that work paused until explicit user resumption. Workflow repair never implicitly resumes paused work.

## Accountable owner and token efficiency

At work start name one accountable owner (normally current Controller) to user and record it in tracker snapshot. Every dispatch request carries that identity as `owner`; assigned role remains responsible only for its bounded outcome. Reviewer is not automatically work owner.

Optimize total task tokens while preserving sufficient correctness and required checks:

- Use smallest sufficient model, effort, team and context. Do not invoke Planner for already-resolved work or reviewer without review trigger.
- Delegate only when bounded independent outcome justifies dispatch/context overhead. Avoid duplicate investigations, repeated handoffs and role layers without concrete purpose.
- Send objective, owned files, fixed decisions, exclusions, validation and evidence references; never whole conversation dumps.
- Return compact findings/results and artifact references. Reuse fresh validated evidence; repeat checks only when changed inputs, failures or required gates justify them.
- Read topology afresh for every assignment as required; token savings must not bypass dispatch, ownership, safety or acceptance checks.
- Explain why selected model/effort and delegation are sufficient and economical before dispatch. Do not invent token savings or hidden runtime settings.

## Controller

Owns orchestration only:

- classify request and establish workset;
- locate/resume requirements and tracking;
- resolve or route material decisions;
- build dependency graph;
- create queue items and assign priorities/capabilities/scopes;
- monitor claims, blockers, and stale leases from queue authority, using Lean event snapshot/delta on reconnect or meaningful state changes instead of routine LLM polling;
- resolve ownership conflicts and integration order;
- select workset-level review and publication actions;
- spend against workset's token/cost budget and stop at its ceiling (see Budget); never raise that ceiling itself;
- synchronize root state and issue final completion report.

Controller does not perform routine implementation or routine line-by-line review. It may execute Small task directly or perform narrowly bounded integration fix when delegation would add more risk than value; record exception.

Controller **startup** model/effort is selected before ROUTE by Request Evaluator and validated against live runtime capabilities. `light` value in role baseline below is only post-start logical orchestration baseline when no stronger intake selection applies to current Controller; ROUTE must echo intake-selected `controllerLevel` and must not upgrade or downgrade Controller.

## Budget

Token/cost budget is set once, outside Controller, and Controller cannot raise it — spender is not control on itself.

```yaml
budget:
  unit: tokens                # or another normalised cost unit
  task_budget: <set at intake>
  reserve: 0.15                # held back for integration + review, not spent by early items
  per_node_cap: 0.4            # no single Worker/Planner/Reviewer turn consumes >40% of task_budget
```

- Set `task_budget` at intake (recorded in tracker's Execution snapshot `Budget:` line); it is ceiling, not target.
- Every role reports its spend on completion or handoff so running total stays visible.
- Model or effort escalation is charged to same budget, measured end-to-end (new model's tokens plus handoff generation), not by per-token price alone — see Temporary escalation.
- On exhaustion: stop dispatching new work, finish or safely abort in-flight items, report completed work plus current diff and what remains, and ask user whether to extend budget. Never silently degrade to weaker model to stay inside budget.
- This is policy/reporting discipline in this repo today: no script currently enforces `per_node_cap` or halts dispatch automatically on exhaustion. Track and report it honestly rather than implying automated enforcement that doesn't exist.

## Planner (on demand)

Invoke only when:

- Large/Complex requirement needs initial decomposition;
- architecture or public contract is unresolved;
- dependencies cannot be ordered safely;
- failed checkpoint invalidates current plan;
- multiple Workers would otherwise overlap because task boundaries are not actually independent.

Independent parallel items alone do **not** require Planner turn when accepted tracker and deterministic route already define safe boundaries.

Planner returns decisions, dependency order, queue-ready task boundaries, risks, and validation strategy, and assigns disjoint exclusive scopes so parallel Workers never overlap same file/resource (see [queue claim](queue-claim.md)) — overlap is decomposition error to fix by re-decomposing, not by merging afterward. It does not stay in execution loop and does not claim implementation items. Default Planner effort is **high** and it is absent from normal execution loop.

## Lead Reviewer

Reviews:

- Work Packet compliance;
- combined diff and integration behavior;
- validation evidence;
- security/approval/workspace boundaries;
- compatibility and rollback risk;
- tracking/queue synchronization.

Routine findings return to owning Worker as bounded correction. Escalate architecture, workspace isolation, permission, approval, destructive-operation, migration, public contract, or cross-area integration concerns to Controller.

Review fan-out is risk based:

- **NONE** — read-only work; no change review.
- **SELF** — low-risk Small work or tracked Medium work with no risk flags when deterministic route selects it; implementer verifies its bounded change.
- **LEAD** — Medium work with meaningful risk flags or ordinary Large integration; one Lead review.
- **LEAD_PLUS_SPECIALIST** — security, workspace isolation, permission/approval, destructive operation, migration, public contract, secrets, or cross-area contract risk; add only specialist angle required by that risk.
- Multiple parallel reviewers are never default and need distinct non-overlapping review questions.

Reviewer must not silently rewrite broad implementation because it disagrees with style choices. It distinguishes blocking defects from non-blocking recommendations.

Binding for `LEAD` and `LEAD_PLUS_SPECIALIST` review:

- Reviewer's resolved capability vector must meet or exceed Worker's on every axis item required — reviewer weaker than its worker on required axis is not independent check;
- prefer Reviewer whose `model_id` differs from Worker's for `LEAD_PLUS_SPECIALIST` risk (security, workspace isolation, permission/approval, destructive operation, migration, public contract, secrets, cross-area contract); same-model review is acceptable only when no distinct model in registry meets required floor;
- Reviewer receives acceptance criteria, Work Packet(s), and combined diff — not Worker's raw reasoning trace or full conversation history;
- critical/high-risk items may start with `LEAD_PLUS_SPECIALIST` immediately rather than escalating into it after failed `LEAD` pass.

## Worker pool

Worker:

- claims one ready item;
- reads only Work Packet and referenced context;
- edits only owned scope;
- maintains heartbeat;
- implements, tests, and documents result;
- records compact evidence and fresh Lean evidence fingerprint when item will be finalized through Lean path;
- completes, blocks, or releases item;
- returns structured handoff.

Normal parallelism is intentionally below hard cap:

| Independent READY items | Normal workers |
|---:|---:|
| 1 | 1 |
| 2-3 | 2 |
| 4-5 | 3 |
| 6+ | 4 |

Use 5-6 Workers only as explicit **burst** when isolation is strong, machine/provider budget permits it, and extra fan-out is expected to reduce end-to-end work rather than duplicate context loading. High-risk/shared-state work should use lower cap.

Worker must not:

- globally replan architecture;
- recursively spawn subagents merely because provider supports it;
- claim work merely to reserve it;
- edit another Worker's exclusive scope;
- bypass approval or publication policy;
- mark another Worker's item complete.

Work Packet that mutates external state (an API, third-party record, anything outside this repo's files) must declare whether it is `idempotent: true|false`. Non-idempotent item is never auto-retried on failure — Worker stops, records partial external state it observed, and routes to Controller instead of guessing whether retry would double-apply effect.

## Capability Model

Role selects **required capability vector**, not model name. Four project-defined axes, scored 1-10:

```text
reasoning   multi-step logic, architecture, novel problem solving
coding      implementation, refactoring, debugging, multi-file edits
longctx     holding and navigating large context accurately
synthesis   writing, summarising, document and research work
```

Each [agent-models.json](../runtime/agent-models.json) registry entry also carries `cost_weight` (relative expense, 1 = cheapest). Selection is match, never rank arithmetic — model that scores lower overall can still be right pick for axis-specific need.

Selection algorithm:

```text
candidates = registry.filter(entry =>
    not entry.deprecated
    AND every axis: entry.caps[axis] >= required_caps[axis])

if candidates is empty:
    -> re-scope item (Controller/Planner), NOT assign insufficient model

selected = candidates.sort_by(cost_weight).first
effort   = snap(desired_effort, selected.effort_levels)   # see Concrete runtime effort
```

Every role's default floor is `requiredCaps` object in dispatch-roles block above. Planner (or Controller, for Small task it executes directly) may raise — never lower — individual item's floor by recording explicit note under Work Packet's DECISIONS or RELEVANT RULES field when role default is insufficient for that specific item (for example, Worker item needing unusually deep cross-package reasoning). This is distinct concept from Work Packet's `REQUIRED CAPABILITY` field in [execution router](execution-router.md), which names Worker *skill* tags (e.g. `typescript`, `docs`); do not conflate two.

This repo's registry is Claude-only (prior revision explicitly removed cross-provider dispatch); entry's `provider` field is descriptive, not live multi-provider switch.

**Assigned capability must be verified, not assumed.** Model actually invoked can differ from one requested (allowlist substitution, provider rerouting). Read responding model identity back from tool/task metadata when available (see Claude runtime dispatch contract step 5) and treat mismatch as capability event to re-assess, not silent pass.

## Provider-agnostic effort ladder

Queue items and governance store logical effort, not provider/model names:

```text
light -> standard -> high -> max
```

Baseline:

```text
Controller       light post-start baseline; fresh startup level comes from intake evaluator
Planner          high, only when invoked
Lead Reviewer    standard; high for specialist/high-risk review
Worker           standard
Simple Worker    light when task is repetitive/local and directly verifiable
```

Absent Planner, Reviewer, or Worker roles have effort `off`; effort labels do not create extra agents.

Provider/model mappings belong in supported runtime configuration, not queue history. Shared mapping lives in [agent-models.json](../runtime/agent-models.json) and is resolved via Capability Model above, never guessed or hardcoded here. Resolve logical effort only to settings available in current runtime. Unavailable mapping blocks dispatch until Controller explicitly resolves supported mapping and reruns gate. Silent fallback/inheritance is forbidden.

### Concrete runtime effort

Logical `light/standard/high/max` tiers route roles and model defaults; they are not runtime's exhaustive effort choices. Keep model selection unchanged when tuning effort. Dispatch may specify `runtimeEffort` with any value supported by selected model in current tool's `capabilities.models`. Defaults in `reasoningEfforts` are recommendations, not allowlist. Any departure requires task-specific `effortReason`, including why selected value is lowest sufficient choice; increases need concrete complexity or observed failure evidence, not habit. Decreases are allowed when sufficient.

Claude uses only its own live effort controls; without one, reject explicit effort requests rather than inventing support. One-level logical escalation rule remains separate from concrete effort selection. Effort tuning never authorizes model escalation. Follow-up requires existing agent's actual requested effort to match; otherwise replace it safely.

### Economical model selection

Choose both model tier and reasoning effort for bounded task: `cheapest registry entry meeting required_caps` + `lowest effort sufficient within that model`. Lowering effort on strongest model is not substitute for choosing smaller sufficient model, and inverse holds too — do not default to stronger model out of habit when cheaper one already meets item's floor.

- Repetitive/local edits, known assertion/mock alignment, and directly verifiable mechanical work use Simple Worker/light — resolves to cheapest registry entry (currently Haiku-tier).
- Ordinary implementation, bounded debugging and routine Lead review use Worker or Lead Reviewer/standard — resolves to mid-tier entry that clears their `coding`/`reasoning` floor (currently Sonnet-tier).
- High is reserved for Planner with one of concrete triggers above, route-required specialist review, or item-scoped escalation supported by failure evidence. Workset size, many files, required test run, or model's availability alone does not justify high.
- Environment, stale fixtures, imports, packaging and tool failures first receive bounded diagnosis/remediation at current tier; they do not by themselves justify stronger model.
- Max remains one-level, evidence-backed escalation from high, never routine default. Reset to role baseline after item.
- Measure escalation cost end-to-end (new model's tokens plus handoff generation plus any discarded work), not by per-token price alone — decision log (see Decision log) is what tells you whether cheap model that escalated twice cost more than starting one tier up.

## Claude runtime dispatch contract

This section explicitly authorizes tier-based Claude model selection. Use logical role baselines above: Controller/simple Worker = light, ordinary Worker/Lead Reviewer = standard, Planner/specialist Reviewer = high; max is temporary escalation only. Resolve to concrete model IDs in [agent-models.json](../runtime/agent-models.json) via Capability Model match, not by habit; verify resolved model rather than promising specific version. Registry is Claude-only: current non-deprecated entries are `claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5-20251001`, and `claude-fable-5-1` (a longctx/synthesis specialist, not role default — used only when item's floor explicitly needs it); `claude-opus-4-6` and `claude-sonnet-4-6` are kept `deprecated: true` for continuity, not for new assignments.

Before each Claude Agent invocation:

1. Inspect available tool schema and effective model configuration. Check `CLAUDE_CODE_SUBAGENT_MODEL`, `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`, provider alias mappings and model allowlists without exposing credentials. Forced single-model setting defeats tier routing: report conflict and do not claim tier routing succeeded. Do not change managed settings or globally force all subagents onto one model to fix individual dispatch.
2. Pass resolved `model` explicitly in invocation when supported. If tool lacks model parameter, select custom agent with explicit matching `model` frontmatter and verify that definition. Never use omitted model, `inherit`, role label, or prompt wording as tier selector. If neither mechanism is available, report dispatch limitation instead of silently inheriting.
3. Model tier and reasoning effort are separate. Model ladder selects concrete IDs from agent-models.json. Where supported and needed, use Claude's `effort` frontmatter in custom agent definition; validate its value against selected model/runtime first. Record inherited/default effort honestly if no explicit supported effort is configured.
4. Send only bounded Work Packet and necessary references. Do not use full-conversation fork for tier selection: Claude forks use parent model. Preserve queue ownership and all existing permission boundaries.
5. Check actual selected model in `/tasks` or available runtime metadata after dispatch. Claude may substitute model because of allowlist or provider restriction. Report any mismatch as tooling/configuration failure; if metadata is unavailable, mark model as requested, not verified. Keep this evidence in transient dispatch state, not durable queue authority.
6. Recheck selection on resume/follow-up and after temporary escalation. Preserve work and claims before replacing agent; never overlap two implementations of same item. Changes to these rules do not retarget agents already running.

For Claude Code runtime, model binding is `model:` frontmatter in `.claude/agents/planner.md`, `.claude/agents/worker.md`, `.claude/agents/simple-worker.md`, and `.claude/agents/lead-reviewer.md` (Controller stays orchestrating session itself and is not dispatchable subagent file). Without role-specific file, `Agent` call inherits caller's session model regardless of stated effort — check these files before assuming effort label changed actual model.

Model precedence and supported controls are version-dependent: consult installed runtime when they change. Current documented precedence is per-invocation model, definition model, subagent-model environment default, then parent model; FORCE setting overrides tier selection.

## Temporary escalation

Escalation is **item-scoped**, at most one logical level at time, and resets to role baseline after affected queue item/decision.

Classify failure before escalating:

```text
ENVIRONMENT / TOOLING
  -> repair environment/tool state; same effort

AUTHORITY
  -> block/request authority; same effort

MISSING_CONTEXT
  -> add bounded missing context first; same effort
  -> if bounded expansion was already used and task still fails for capability reasons, +1 level

REASONING / IMPLEMENTATION / PLANNING
  -> +1 level temporarily
  -> if already at max or escalation budget is exhausted, re-plan instead of repeated expensive retries
```

Never escalate merely because command failed. Cause, not symptom, controls escalation.

### Default escalation predicates (tunable)

Default, parameterised triggers — tune them from Decision log, not from habit:

```yaml
raise_effort_if:
  - tool_error_rate > 0.3        # over the last 5 tool calls on this item
  - test_fail_count >= 2         # same target, after a fix attempt
  - retry_count == 1
  - phase in [architecture, security, auth, data_migration]

change_model_if:
  - retry_count >= 2 AND effort_ceiling_reached
  - reviewer_rejected >= 2       # same work item
  - required_caps not satisfied by current model   # jump straight to right model; do not climb effort first
  - task domain changed and new required_caps are not satisfied

controller_replan_if:
  - escalation_count >= max_escalations_per_task
  - effort_flips >= max_effort_flips
  - two different models failed same work item
  - budget_spent > 0.7 * task_budget AND work item is not converging
```

Role may self-report confidence as metadata; log it, never treat as trigger — it is not calibrated enough to drive decision.

### Hysteresis and limits

Without these, node oscillates and burns budget on routing instead of work:

```yaml
min_dwell: 1 work item          # no config change until at least one item is attempted
max_escalations_per_task: 3     # model changes, any role, across the whole tracked workset
max_effort_flips: 4             # direction changes per work item
cooldown_after_change: 1 work item
```

Effort may rise mid-item; it may only fall at phase boundary (clean stopping point between items or clearly-separated phases of one item), never inside unfinished work — that is how thrashing starts. Exceeding any limit above does not justify further escalation; it routes to Controller re-plan, on assumption decomposition is wrong, not that model is too small.

Escalation capsule contains only:

```text
ITEM
OBJECTIVE
AC STILL FAILING
FILES/SCOPES TOUCHED
CURRENT DIFF SUMMARY
VALIDATION FAILURE
DECISIONS ALREADY FIXED
BLOCKER/FAILURE CLASS
DO NOT TOUCH
```

Do not replay whole conversation or broad repository history to stronger model.

## Adaptive topology

```text
Read-only   One light agent; inspect and answer.
Small       Controller executes directly at light/standard effort.
Medium      Controller + only needed Workers + risk-based review.
Large       Controller + Planner only when needed + adaptive Workers + risk-based review.
```

Do not impose `Controller -> Planner -> Lead -> Worker` when layer adds no value. When versioned Lean route input is complete, use its deterministic Planner/Reviewer/worker recommendation; unknown risk metadata fails closed rather than being guessed into lighter topology.

## Escalation protocol

Worker escalation is concise:

```text
ITEM              QNNNN
TYPE              BLOCKER | ARCHITECTURE CONFLICT | SCOPE CONFLICT | VALIDATION FAILURE
FAILURE CLASS     ENVIRONMENT | TOOLING | AUTHORITY | MISSING_CONTEXT | REASONING | IMPLEMENTATION | PLANNING
OBSERVED          Concrete evidence
AFFECTED AC       AC identifiers
CURRENT CLAIM     active/stale/released
SAFE WORK DONE    completed portion, if any
CURRENT EFFORT    light/standard/high/max
DECISION NEEDED   exact choice or missing authority
RECOMMENDATION    preferred next action
```

Block or release only affected item. Independent items may continue.

### Model change request contract

Effort change (same model, more depth) is self-managed within limits above. **Model** change — current model no longer satisfies `required_caps`, or its effort ceiling is reached without convergence — requires Controller approval and names capability needed, not specific model:

```yaml
capability_change_request:
  item: QNNNN
  current: {model_id: ..., effort: ..., effort_ceiling_reached: true|false}
  evidence: {retry_count: N, test_fail_count: N, tool_error_rate: 0.0, failing_axis: reasoning|coding|longctx|synthesis, reason: <short>}
  requested_caps: {reasoning: N, coding: N, longctx: N, synthesis: N}
  budget_remaining: N
```

Worker (or Planner/Reviewer) requests capability; Controller runs Capability Model's selection algorithm and picks model. Request that names specific model instead of capability floor is advisory only.

## Handoff contract

Completed Worker handoff stays compact:

```text
ITEM                  QNNNN
OUTCOME               DONE | BLOCKED | RELEASED
CHANGED               files and behavior
ESTABLISHED FACTS     verified facts next owner should not have to re-derive
ATTEMPTED AND FAILED  approach -> outcome pairs (highest-value field on model/effort change:
                      it is what incoming owner cannot reconstruct on its own)
VALIDATION            concise check/result pairs
AC COVERAGE           mapped AC identifiers
ARTIFACT REFS         detailed evidence when needed
RISKS                 remaining risk or None
FOLLOW-UP             required next queue item or None
CLAIM STATE           completed/blocked/released
```

Never forward raw transcript or full reasoning trace when item changes owner (model change, reassignment, escalation) — outgoing owner writes this compact packet before releasing item; replaying long history into next model inverts token-efficiency goal in Accountable owner and token efficiency and carries failed reasoning trace into fresh attempt. `ESTABLISHED FACTS` and `ATTEMPTED AND FAILED` may be empty only for first-attempt `DONE`.

Controller accepts handoff only when queue state, tracker state, and evidence agree.

## Decision log

Every model/effort change decision from dispatch gate (step 7) and every escalation/de-escalation is session-local evidence, not durable queue authority. Record it compactly enough to tune predicates in Temporary escalation later:

```yaml
- ts: <ISO8601>
  item: QNNNN
  role: worker|planner|lead-reviewer|controller
  decision: effort_change | model_change | de_escalation
  from: {model_id: ..., effort: ...}
  to: {model_id: ..., effort: ...}
  trigger: <predicate that fired>
  assigned_vs_responding_match: true|false
  outcome: resolved | still_failing | replanned
```

Review it periodically for: escalations that didn't help (threshold too eager), repeated failures before escalation (too slow), and item types that always escalate (their `required_caps` were set too low at planning time). This does not create new durable file requirement — keep it in tracker's Execution snapshot or session evidence, whichever workset already uses.
