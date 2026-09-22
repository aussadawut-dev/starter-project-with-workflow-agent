# Queue Claim Protocol

Queue coordinates ownership and concurrency. Not a substitute for requirements, architecture decisions, tracking, review, or Git history.

## Sources of truth

```text
Requirement / decisions  docs/waiting-implement/ and accepted ADRs
Durable execution record docs/tracking/
Tracked queue definitions .agents/queue/items/QNNNN.json
Ephemeral claim leases    .agent-runtime/claims/QNNNN.claim/claim.json
Ephemeral claim history   .agent-runtime/history/
```

`.agent-runtime/` ignored by Git because claims coordinate agents sharing one active workspace, not branches or releases.

## Queue item contract

Each item is bounded Work Packet. Required fields defined by `.agents/queue/schema/queue-item.schema.json`.

Important fields:

- `id`: stable repository-local `QNNNN`;
- `status`: durable `TODO`, `BLOCKED`, `DONE`, or `CANCELLED`;
- `priority`: lower number selected first among otherwise eligible items;
- `workset` and `task`: durable tracker relationship;
- `dependencies`: queue IDs that must be `DONE`;
- `requiredCapabilities`: capabilities Worker must advertise;
- `exclusiveScopes`: opaque conflict keys; equal keys may not be claimed concurrently;
- `acceptanceCriteria`, `primaryFiles`, `doNotTouch`, `requiredValidation`: execution boundaries;
- `completion.evidence`: mandatory for `DONE`.

Runtime states are derived:

```text
READY        status TODO, dependencies DONE, no claim
WAITING      status TODO, dependency not DONE
CLAIMED      active non-stale claim exists
STALE_CLAIM  lease expired; must be recovered
BLOCKED      durable blocker recorded
DONE         completion evidence recorded
CANCELLED    intentionally removed from execution
```

Do not persist `IN_PROGRESS` in item. Active claim is authoritative in-progress state.

## Atomic claim behavior

`scripts/agent_queue.py` uses:

1. one atomic global coordination directory for claim/release/complete selection;
2. one atomic claim directory per item;
3. exclusive file creation for new queue definitions;
4. atomic replace for JSON state updates.

Prevents two Workers from successfully claiming same item and serializes cross-item exclusive-scope checks.

Never implement claims as “read status, then write my name” without atomic acquisition.

## Eligibility

An item is claimable only when:

- durable status is `TODO`;
- every dependency is `DONE`;
- no active claim owns item;
- Worker capabilities cover every required capability;
- no active claim holds equal exclusive-scope key;
- same Worker does not already hold another item, unless Controller explicitly permits multiple claims.

Priority never bypasses conditions.

## Lease and heartbeat

Default lease: 1,800 seconds.

- Heartbeat at least once per one-third of lease during active work.
- Heartbeat immediately before and after long-running tests, builds, approved processes.
- Lease protects ownership, not correctness.
- Expired lease must be recovered via `recover` or new atomic claim operation.
- Worker that loses lease stops editing until it owns new claim.
- Do not extend lease indefinitely for idle or blocked Worker.

## Claim token

Token returned by `claim` or `claim-next` required for heartbeat, release, block, completion.

- Keep in process/session-local state, e.g. `AGENT_CLAIM_TOKEN`.
- Do not commit.
- Do not share between Workers.
- Token possession does not authorize out-of-scope edits, destructive actions, publication.

## Exclusive scopes

Scopes are explicit opaque keys, not inferred path globs:

```text
contract:tool-schema
runtime:process-policy
security:path-boundary
file:scripts/agent_queue.py
docs:agent-governance
```

Use same key for work that cannot safely run concurrently. Use no key when tasks truly independent.

Prefer one coherent owner over multiple fine-grained queue items that edit same behavior.

## Commands

Validate and inspect:

```bash
python3 scripts/agent_queue.py validate
python3 scripts/agent_queue.py list
python3 scripts/agent_queue.py show --id Q0001
```

Enqueue:

```bash
python3 scripts/agent_queue.py enqueue \
  --id Q0001 \
  --title "Synchronize tool schemas" \
  --workset TCK001 \
  --task TASK-002 \
  --objective "Expose the same validated arguments in schema and runtime" \
  --priority 20 \
  --capability typescript \
  --scope contract:tool-schema \
  --primary-file src/tools/schema.ts \
  --validation "npm test -- tool-schema"
```

Claim:

```bash
python3 scripts/agent_queue.py claim-next \
  --agent worker-01 \
  --capability typescript

python3 scripts/agent_queue.py claim \
  --id Q0001 \
  --agent worker-01 \
  --capability typescript
```

Maintain or leave a claim:

```bash
python3 scripts/agent_queue.py heartbeat --id Q0001 --token "$TOKEN"

python3 scripts/agent_queue.py release \
  --id Q0001 --token "$TOKEN" --reason "Returning unstarted work"

python3 scripts/agent_queue.py block \
  --id Q0001 --token "$TOKEN" --reason "Needs approval model decision"
```

Complete only with evidence:

```bash
python3 scripts/agent_queue.py complete \
  --id Q0001 \
  --token "$TOKEN" \
  --evidence "npm test -- tool-schema: PASS" \
  --evidence "manual schema/runtime parity check: PASS"
```

Controller recovery:

```bash
python3 scripts/agent_queue.py recover
python3 scripts/agent_queue.py unblock \
  --id Q0001 --reason "ADR-0003 accepted"
```

## Controller responsibilities

- enqueue only queue-ready work;
- validate dependencies and cycle freedom;
- allocate conflict scopes consistently;
- monitor claims without taking ownership from healthy Worker;
- recover only stale/terminal claims;
- amend queue items before Worker claims them, or coordinate release first;
- synchronize queue completion into tracker.

## Worker responsibilities

- claim before editing;
- confirm Work Packet boundaries;
- maintain heartbeat;
- stop on lease loss or scope conflict;
- collect required evidence;
- use `complete`, `block`, or `release` truthfully;
- never manually modify another Worker's claim.

## Reviewer responsibilities

Reviewer checks:

- every changed implementation area had owning item or justified Small-work exception;
- no overlapping exclusive scopes ran concurrently;
- completed items include evidence;
- durable tracker and queue states agree;
- stale claims were recovered rather than ignored;
- blocked findings remain non-DONE.

## Failure and recovery

- **Worker crash:** lease expires; `recover` archives and removes stale claim; item returns to derived `READY`.
- **Terminal item with residual claim:** recovery archives claim as terminal cleanup.
- **Invalid queue JSON or dependency cycle:** queue validation fails; no `claim-next` proceeds.
- **Wrong token:** operation fails without changing state.
- **Claim acquired but no work started:** release with reason.
- **New material dependency:** block/release, amend tracker and queue graph, then reclaim.
- **Runtime directory deleted:** active ownership lost; Workers stop and reclaim. Durable queue items remain intact.

## Forbidden

- Manually editing or deleting `.agent-runtime/claims/`.
- Treating Git branch ownership as queue ownership.
- Claiming several items to reserve future work.
- Completing without validation evidence.
- Using broad scope key on every item, which serializes entire pool.
- Omitting scope key when two items modify one public contract.
- Reopening DONE item by editing JSON; create new corrective queue item.
