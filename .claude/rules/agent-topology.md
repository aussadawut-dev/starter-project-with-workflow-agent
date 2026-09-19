# Agent Topology

Use the smallest topology and lowest provider-agnostic effort that safely completes the active workset. Roles are responsibilities, not permanent people or model names.

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

Default Controller effort is **light**. Raise it only for a concrete orchestration/decision failure, then return to light after that decision or queue item.

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

- **SELF** — low-risk Small work; implementer verifies its own bounded change.
- **LEAD** — ordinary Medium/Large integration or meaningful risk; one Lead review.
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
Controller       light
Planner          high, only when invoked
Lead Reviewer    standard; high for specialist/high-risk review
Worker           standard
Simple Worker    light when the task is repetitive/local and directly verifiable
```

Provider mappings are deployment configuration and may change without rewriting queue history. Current intended mappings are:

```text
OpenAI / Codex
  logical role.effort       model ID          reasoning_effort
  controller.light      -> gpt-6-astra        low
  controller.standard   -> gpt-6-astra        medium
  controller.high       -> gpt-6-astra        high
  controller.max        -> gpt-6-astra        max
  planner.high          -> gpt-5.6-terra      high
  planner.max           -> gpt-5.6-terra      max
  reviewer.standard     -> gpt-5.6-terra      medium
  reviewer.high         -> gpt-5.6-terra      high
  reviewer.max          -> gpt-5.6-terra      max
  worker.light          -> gpt-5.6-luna       medium
  worker.standard       -> gpt-5.6-luna       high
  worker.high/max       -> gpt-5.6-luna       max (temporary escalation)

Claude
  light                 -> haiku (intended family: Haiku)
  standard              -> sonnet (intended family: Sonnet)
  high                  -> opus (intended family: Opus)
  max                   -> fable (intended family: Fable)
```

These names are mappings, not authority. A provider/model change must not alter queue ownership, permissions, approval, validation, or publication semantics.

## Codex runtime dispatch contract

This section explicitly authorizes the Controller to select the mapped model and reasoning effort for delegated roles. The mapping above is runtime configuration, not a queue field. A role name or an effort instruction inside a prompt does not select a model.

Before every `collaboration.spawn_agent` call:

1. Resolve the role and logical effort from the route and any item-scoped escalation, then resolve both runtime values from the mapping above. Logical `standard` is not a runtime reasoning-effort value.
2. Check that the current tool advertises the selected model and supports its reasoning effort. If unavailable or unmapped, report the dispatch limitation; do not silently fall back to the Controller's model or claim that the requested tier was used.
3. Pass **both** `model` and `reasoning_effort` explicitly as tool arguments. Use `fork_turns: "none"` and include the bounded Work Packet in `message`. Full-history forks (`fork_turns: "all"` or omitted) inherit the parent settings and do not accept overrides; do not use them for tier-routed dispatch.
4. Before sending, verify that the actual tool arguments match the resolved pair. Do not rely on role labels, prompt wording, or `fork_turns: "none"` alone to override inherited settings.
5. Record the requested pair in the transient dispatch summary. Verify the actual model/effort when runtime metadata is available; otherwise mark it as requested, not verified. Keep provider names out of durable queue authority. A mismatch is a tooling/configuration failure, not a reason to escalate effort.

Example for a standard Worker (replace the message with the actual bounded Work Packet):

```json
{
  "task_name": "worker",
  "fork_turns": "none",
  "model": "gpt-5.6-luna",
  "reasoning_effort": "high",
  "message": "Bounded Work Packet"
}
```

Changing these rules does not change the current Controller or agents already running. `send_message` and `followup_task` do not expose model overrides in this runtime. If an existing agent uses the wrong pair, preserve its work and claim state, stop it at a safe checkpoint, and dispatch a replacement using the explicit pair; never start overlapping implementation to correct a tier mismatch.

## Claude runtime dispatch contract

This section explicitly authorizes tier-based Claude model selection. Use the logical role baselines above: Controller/simple Worker = light, ordinary Worker/Lead Reviewer = standard, Planner/specialist Reviewer = high; max is temporary escalation only. Resolve to the Claude aliases above, not the Codex model IDs. Aliases track the provider's configured version; verify the resolved model rather than promising a specific version.

Before each Claude Agent invocation (or Task on older runtimes):

1. Inspect the available tool schema and effective model configuration. Check `CLAUDE_CODE_SUBAGENT_MODEL`, `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`, provider alias mappings and model allowlists without exposing credentials. A forced single-model setting defeats tier routing: report the conflict and do not claim tier routing succeeded. Do not change managed settings or globally force all subagents onto one model to fix an individual dispatch.
2. Pass the resolved `model` explicitly in the invocation when supported. If the tool lacks a model parameter, select a custom agent with an explicit matching `model` frontmatter and verify that definition. Never use omitted model, `inherit`, a role label, or prompt wording as the tier selector. If neither mechanism is available, report the dispatch limitation instead of silently inheriting.
3. Model tier and reasoning effort are separate. The Claude ladder above selects model families. Where supported and needed, use Claude's `effort` frontmatter in a custom agent definition; validate its value against the selected model/runtime first. Do not copy Codex's `reasoning_effort` or `fork_turns` fields into Claude calls. Do not assume Haiku supports an effort control or equate logical `max` with runtime `effort: max`. Record inherited/default effort honestly if no explicit supported effort is configured.
4. Send only the bounded Work Packet and necessary references. Do not use a full-conversation fork for tier selection: Claude forks use the parent model. Preserve queue ownership and all existing permission boundaries.
5. Check the actual selected model in `/tasks` or available runtime metadata after dispatch. Claude may substitute a model because of an allowlist or provider restriction. Report any mismatch as a tooling/configuration failure; if metadata is unavailable, mark the model as requested, not verified. Keep this evidence in transient dispatch state, not durable queue authority.
6. Recheck the selection on resume/follow-up and after temporary escalation. Preserve work and claims before replacing an agent; never overlap two implementations of the same item. Changes to these rules do not retarget agents already running.

For example, an ordinary Worker requests `model: "sonnet"`; a Planner requests `model: "opus"`. Set the actual tool's required task/prompt fields as advertised. A standard custom Worker can use `model: sonnet` in `.claude/agents/<name>.md`; it must still receive its role, bounded Work Packet, and canonical rules. A model field alone does not grant permissions.

Verified against local Claude Code 2.1.277 and [Claude Code subagent documentation](https://code.claude.com/docs/en/sub-agents) on 2026-09-19. Model precedence and supported controls are version-dependent: consult the installed runtime when they change. Current documented precedence is per-invocation model, definition model, subagent-model environment default, then parent model; the FORCE setting overrides tier selection.

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
