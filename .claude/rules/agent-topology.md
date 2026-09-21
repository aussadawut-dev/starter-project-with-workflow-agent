# Agent Topology

Use the smallest topology and lowest provider-agnostic effort that safely completes the active workset. Roles are responsibilities, not permanent people or model names.

## Intake evaluator and Controller start

A new request may enter through one fixed, bounded **Request Evaluator** before any Controller exists. This bootstrap role has exactly one responsibility: choose the lowest sufficient logical Controller level (`light|standard|high|max`) and give a short reason. It does not classify the workset, decompose tasks, choose Planner/Reviewer/Workers, choose parallelism, create or claim queue items, dispatch agents, run mutations/processes, review results, or publish.

```text
User request
  -> fixed Request Evaluator
  -> { version, controllerLevel, reason }
  -> fresh Controller start with explicit supported runtime model/effort
  -> ROUTE / PREPARE / DISPATCH / EXECUTE / VERIFY / FINALIZE
```

The evaluator's runtime profile is configuration, not queue authority. Its output must contain only `version`, `controllerLevel`, and `reason`; extra orchestration fields fail closed. Once the fresh Controller starts, the evaluator is finished. The Controller receives the original request plus the validated selection and owns every downstream routing and orchestration decision.

For Claude, bind the named `request-evaluator` role/model and exact `effort` only when the live Agent tool exposes that parameter; otherwise the receipt is model-only and explicitly reports numerical reasoning effort as unverified. Claude Controller startup follows the same rule: exact model + effort when supported, otherwise exact model only. Never reinterpret bootstrap effort as Controller effort, invent an unsupported Claude effort, or silently reuse an already-running Controller with different settings.

## Mandatory fresh-read dispatch gate — every runtime

Before **every** assignment (new agent, follow-up, reassignment, resumed task, correction or effort escalation), the Controller must freshly read this entire file and the selected role file. This overrides ordinary read-once/context-cache guidance. A prior read, summary, role name or logical-effort label is not dispatch evidence.

1. Reread this topology, select the role from the route and actual work, and load its role file. Planner remains conditional.
2. Read the runtime mapping and actual agent-tool capabilities. Run `prepare-dispatch` and read its returned `sources`, including the entire topology. Keep requests/receipts in ignored runtime state or temporary files, never queue authority.
3. Run `validate-dispatch` immediately before the tool call with the receipt and exact proposed parameters. It rereads sources and rejects stale receipts, unsupported combinations and omitted/changed parameters. A failed gate means no dispatch until the mapping is resolved visibly.
4. For a new agent, pass the exact concrete spawn parameters to the runtime. Claude invokes the named role with `subagent_type` and an explicit model. Pass numerical effort only if its current tool supports that parameter; otherwise report `role-model-only`, never claim that prose changed reasoning settings.
5. For follow-ups, repeat the gate and verify the existing agent's recorded role and requested runtime settings. Validate its recorded spawn parameters; do not send unsupported model arguments to a follow-up tool. Follow-up text cannot change model/effort. If settings differ or are unknown, release old ownership and spawn a correctly configured agent. Carry fresh relevant role instructions in the bounded Work Packet.
6. Before every assignment tool call, explain the model and effort selection to the user using the assignment rationale below.
7. Record assignment, role, logical effort, concrete requested settings, model/effort rationale, source fingerprint and returned agent identity in session-local evidence. Requested settings prove the request, not an unreported backend model. Never assert hidden runtime state.

The helper validates workflow compliance; it cannot intercept arbitrary external agent-tool calls. Bypassing it is a workflow violation.

### Required user-visible assignment rationale

Every dispatch must include a concise explanation before the tool call; a hidden receipt or a final summary alone is insufficient. This includes new agents, follow-ups, corrections, reassignment, resume and escalation, even when settings are unchanged. State:

- **Task and role:** the bounded outcome being delegated.
- **Model and reason:** the concrete requested model from the supported runtime mapping, why its capabilities fit this task, and any availability constraint that affected the choice. Do not invent model capabilities.
- **Effort and reason:** both logical effort and the actual requested runtime effort when supported; connect the choice to concrete complexity, uncertainty, risk, or validation needs. Explain why this is the lowest sufficient level. A role label or "per mapping" alone is not a rationale.
- **Follow-up or escalation:** explain why existing settings remain suitable or why a change is justified. For escalation, name the observed failure class and evidence, and the item-scoped reset to baseline.

Use the user's language. A compact format is: "Assigning <task> to <role>, model <model>, because <task-specific capability reason>; effort <logical>/<runtime>, because <complexity/risk reason>." For `role-model-only`, explicitly say runtime effort cannot be set instead of implying it was configured. Never assert hidden backend settings. Keep concrete model names and dispatch rationale in session-local evidence, not durable queue authority.

This block is the machine-readable source of role baselines. Provider models remain runtime configuration, not role policy or queue authority.

<!-- dispatch-roles -->
```json
{
  "controller": { "effort": "light", "file": null },
  "planner": { "effort": "high", "file": ".claude/agents/planner.md" },
  "lead-reviewer": { "effort": "standard", "file": ".claude/agents/lead-reviewer.md" },
  "worker": { "effort": "standard", "file": ".claude/agents/worker.md" },
  "simple-worker": { "effort": "light", "file": ".claude/agents/simple-worker.md" }
}
```

For dispatch policy, the Controller is the active orchestrating session and is not a dispatchable worker role. An already-running Controller cannot change its actual model/effort through prompt or policy text; report that limitation instead of claiming a change. A fresh Controller may instead be started only through the validated intake-selection/startup path above. A user stop/pause stops affected agents/commands, releases claims and leaves that work paused until explicit user resumption. Workflow repair never implicitly resumes paused work.

## Accountable owner and token efficiency

At work start name one accountable owner (normally the current Controller) to the user and record it in the tracker snapshot. Every dispatch request carries that identity as `owner`; the assigned role remains responsible only for its bounded outcome. A reviewer is not automatically the work owner.

Optimize total task tokens while preserving sufficient correctness and required checks:

- Use the smallest sufficient model, effort, team and context. Do not invoke a Planner for already-resolved work or a reviewer without a review trigger.
- Delegate only when a bounded independent outcome justifies dispatch/context overhead. Avoid duplicate investigations, repeated handoffs and role layers without a concrete purpose.
- Send objective, owned files, fixed decisions, exclusions, validation and evidence references; never whole conversation dumps.
- Return compact findings/results and artifact references. Reuse fresh validated evidence; repeat checks only when changed inputs, failures or required gates justify them.
- Read topology afresh for every assignment as required; token savings must not bypass dispatch, ownership, safety or acceptance checks.
- Explain why the selected model/effort and delegation are sufficient and economical before dispatch. Do not invent token savings or hidden runtime settings.

## Controller

Owns orchestration only:

- classify the request and establish the workset;
- locate/resume requirements and tracking;
- resolve or route material decisions;
- build the dependency graph;
- create queue items and assign priorities/capabilities/scopes;
- monitor claims, blockers, and stale leases from queue authority, using Lean event snapshot/delta on reconnect or meaningful state changes instead of routine LLM polling;
- resolve ownership conflicts and integration order;
- select workset-level review and publication actions;
- synchronize root state and issue the final completion report.

The Controller does not perform routine implementation or routine line-by-line review. It may execute a Small task directly or perform a narrowly bounded integration fix when delegation would add more risk than value; record the exception.

Controller **startup** model/effort is selected before ROUTE by the Request Evaluator and validated against live runtime capabilities. The `light` value in the role baseline below is only the post-start logical orchestration baseline when no stronger intake selection applies to the current Controller; ROUTE must echo the intake-selected `controllerLevel` and must not upgrade or downgrade the Controller.

## Planner (on demand)

Invoke only when:

- a Large/Complex requirement needs initial decomposition;
- architecture or a public contract is unresolved;
- dependencies cannot be ordered safely;
- a failed checkpoint invalidates the current plan;
- multiple Workers would otherwise overlap because task boundaries are not actually independent.

Independent parallel items alone do **not** require a Planner turn when the accepted tracker and deterministic route already define safe boundaries.

The Planner returns decisions, dependency order, queue-ready task boundaries, risks, and validation strategy. It does not stay in the execution loop and does not claim implementation items. Default Planner effort is **high** and it is absent from the normal execution loop.

## Lead Reviewer

Reviews:

- Work Packet compliance;
- combined diff and integration behavior;
- validation evidence;
- security/approval/workspace boundaries;
- compatibility and rollback risk;
- tracking/queue synchronization.

Routine findings return to the owning Worker as a bounded correction. Escalate architecture, workspace isolation, permission, approval, destructive-operation, migration, public contract, or cross-area integration concerns to the Controller.

Review fan-out is risk based:

- **NONE** — read-only work; no change review.
- **SELF** — low-risk Small work or tracked Medium work with no risk flags when the deterministic route selects it; implementer verifies its bounded change.
- **LEAD** — Medium work with meaningful risk flags or ordinary Large integration; one Lead review.
- **LEAD_PLUS_SPECIALIST** — security, workspace isolation, permission/approval, destructive operation, migration, public contract, secrets, or cross-area contract risk; add only the specialist angle required by that risk.
- Multiple parallel reviewers are never the default and need distinct non-overlapping review questions.

The Reviewer must not silently rewrite broad implementation because it disagrees with style choices. It distinguishes blocking defects from non-blocking recommendations.

## Worker pool

A Worker:

- claims one ready item;
- reads only the Work Packet and referenced context;
- edits only the owned scope;
- maintains heartbeat;
- implements, tests, and documents the result;
- records compact evidence and a fresh Lean evidence fingerprint when the item will be finalized through the Lean path;
- completes, blocks, or releases the item;
- returns a structured handoff.

Normal parallelism is intentionally below the hard cap:

| Independent READY items | Normal workers |
|---:|---:|
| 1 | 1 |
| 2-3 | 2 |
| 4-5 | 3 |
| 6+ | 4 |

Use 5-6 Workers only as an explicit **burst** when isolation is strong, the machine/provider budget permits it, and the extra fan-out is expected to reduce end-to-end work rather than duplicate context loading. High-risk/shared-state work should use a lower cap.

A Worker must not:

- globally replan architecture;
- recursively spawn subagents merely because the provider supports it;
- claim work merely to reserve it;
- edit another Worker's exclusive scope;
- bypass approval or publication policy;
- mark another Worker's item complete.

## Provider-agnostic effort ladder

Queue items and governance store logical effort, not provider/model names:

```text
light -> standard -> high -> max
```

Baseline:

```text
Controller       light post-start baseline; fresh startup level comes from the intake evaluator
Planner          high, only when invoked
Lead Reviewer    standard; high for specialist/high-risk review
Worker           standard
Simple Worker    light when the task is repetitive/local and directly verifiable
```

Absent Planner, Reviewer, or Worker roles have effort `off`; effort labels do not create extra agents.

Provider/model mappings belong in supported runtime configuration, not queue history. Shared mapping lives in [agent-models.json](../runtime/agent-models.json). Resolve logical effort only to settings available in the current runtime. An unavailable mapping blocks dispatch until the Controller explicitly resolves the supported mapping and reruns the gate. Silent fallback/inheritance is forbidden.

### Concrete runtime effort

Logical `light/standard/high/max` tiers route roles and model defaults; they are not the runtime's exhaustive effort choices. Keep model selection unchanged when tuning effort. Dispatch may specify `runtimeEffort` with any value supported by the selected model in the current tool's `capabilities.models`. Defaults in `reasoningEfforts` are recommendations, not an allowlist. Any departure requires a task-specific `effortReason`, including why the selected value is the lowest sufficient choice; increases need concrete complexity or observed failure evidence, not habit. Decreases are allowed when sufficient.

Claude uses only its own live effort controls; without one, reject explicit effort requests rather than inventing support. The one-level logical escalation rule remains separate from concrete effort selection. Effort tuning never authorizes model escalation. A follow-up requires the existing agent's actual requested effort to match; otherwise replace it safely.

### Economical model selection

Choose both the model tier and reasoning effort for the bounded task. Lowering effort on the strongest model is not a substitute for choosing a smaller sufficient model.

- Repetitive/local edits, known assertion/mock alignment, and directly verifiable mechanical work use Simple Worker/light.
- Ordinary implementation, bounded debugging and routine Lead review use Worker or Lead Reviewer/standard.
- High is reserved for a Planner with one of the concrete triggers above, a route-required specialist review, or an item-scoped escalation supported by failure evidence. Workset size, many files, a required test run, or the model's availability alone does not justify high.
- Environment, stale fixtures, imports, packaging and tool failures first receive bounded diagnosis/remediation at the current tier; they do not by themselves justify a stronger model.
- Max remains a one-level, evidence-backed escalation from high, never a routine default. Reset to the role baseline after the item.

## Claude runtime dispatch contract

This section explicitly authorizes tier-based Claude model selection. Use the logical role baselines above: Controller/simple Worker = light, ordinary Worker/Lead Reviewer = standard, Planner/specialist Reviewer = high; max is temporary escalation only. Resolve to the concrete model IDs in [agent-models.json](../runtime/agent-models.json); verify the resolved model rather than promising a specific version.

Before each Claude Agent invocation:

1. Inspect the available tool schema and effective model configuration. Check `CLAUDE_CODE_SUBAGENT_MODEL`, `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`, provider alias mappings and model allowlists without exposing credentials. A forced single-model setting defeats tier routing: report the conflict and do not claim tier routing succeeded. Do not change managed settings or globally force all subagents onto one model to fix an individual dispatch.
2. Pass the resolved `model` explicitly in the invocation when supported. If the tool lacks a model parameter, select a custom agent with an explicit matching `model` frontmatter and verify that definition. Never use omitted model, `inherit`, a role label, or prompt wording as the tier selector. If neither mechanism is available, report the dispatch limitation instead of silently inheriting.
3. Model tier and reasoning effort are separate. The model ladder selects concrete IDs from agent-models.json. Where supported and needed, use Claude's `effort` frontmatter in a custom agent definition; validate its value against the selected model/runtime first. Record inherited/default effort honestly if no explicit supported effort is configured.
4. Send only the bounded Work Packet and necessary references. Do not use a full-conversation fork for tier selection: Claude forks use the parent model. Preserve queue ownership and all existing permission boundaries.
5. Check the actual selected model in `/tasks` or available runtime metadata after dispatch. Claude may substitute a model because of an allowlist or provider restriction. Report any mismatch as a tooling/configuration failure; if metadata is unavailable, mark the model as requested, not verified. Keep this evidence in transient dispatch state, not durable queue authority.
6. Recheck the selection on resume/follow-up and after temporary escalation. Preserve work and claims before replacing an agent; never overlap two implementations of the same item. Changes to these rules do not retarget agents already running.

For the Claude Code runtime, model binding is the `model:` frontmatter in `.claude/agents/planner.md`, `.claude/agents/worker.md`, `.claude/agents/simple-worker.md`, and `.claude/agents/lead-reviewer.md` (Controller stays the orchestrating session itself and is not a dispatchable subagent file). Without a role-specific file, an `Agent` call inherits the caller's session model regardless of stated effort — check these files before assuming an effort label changed the actual model.

Model precedence and supported controls are version-dependent: consult the installed runtime when they change. Current documented precedence is per-invocation model, definition model, subagent-model environment default, then parent model; the FORCE setting overrides tier selection.

## Temporary escalation

Escalation is **item-scoped**, at most one logical level at a time, and resets to the role baseline after the affected queue item/decision.

Classify the failure before escalating:

```text
ENVIRONMENT / TOOLING
  -> repair environment/tool state; same effort

AUTHORITY
  -> block/request authority; same effort

MISSING_CONTEXT
  -> add bounded missing context first; same effort
  -> if bounded expansion was already used and the task still fails for capability reasons, +1 level

REASONING / IMPLEMENTATION / PLANNING
  -> +1 level temporarily
  -> if already at max or escalation budget is exhausted, re-plan instead of repeated expensive retries
```

Never escalate merely because a command failed. The cause, not the symptom, controls escalation.

An escalation capsule contains only:

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

Do not replay the whole conversation or broad repository history to the stronger model.

## Adaptive topology

```text
Read-only   One light agent; inspect and answer.
Small       Controller executes directly at light/standard effort.
Medium      Controller + only needed Workers + risk-based review.
Large       Controller + Planner only when needed + adaptive Workers + risk-based review.
```

Do not impose `Controller -> Planner -> Lead -> Worker` when a layer adds no value. When the versioned Lean route input is complete, use its deterministic Planner/Reviewer/worker recommendation; unknown risk metadata fails closed rather than being guessed into a lighter topology.

## Escalation protocol

A Worker escalation is concise:

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

Block or release only the affected item. Independent items may continue.

## Handoff contract

A completed Worker handoff stays compact:

```text
ITEM              QNNNN
OUTCOME           DONE | BLOCKED | RELEASED
CHANGED           files and behavior
VALIDATION        concise check/result pairs
AC COVERAGE       mapped AC identifiers
ARTIFACT REFS     detailed evidence when needed
RISKS             remaining risk or None
FOLLOW-UP         required next queue item or None
CLAIM STATE       completed/blocked/released
```

The Controller accepts a handoff only when queue state, tracker state, and evidence agree.
