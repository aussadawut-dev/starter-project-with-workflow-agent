# Agent Queue

Tracked, executable Work Packets with atomic lease-based runtime ownership.

## Layout

```text
.agents/queue/
  schema/queue-item.schema.json
  items/QNNNN.json

.agent-runtime/              # ignored by Git
  claims/QNNNN.claim/claim.json
  history/
  claim-global.lock/
```

Do not manually edit `.agent-runtime/`.

Runtime implementation is split by responsibility:

```text
scripts/agent_queue.py          CLI and compatibility exports
scripts/agent_queue_core.py     stable public facade
scripts/agent_queue_common.py   validation, atomic writes, repository lock
scripts/agent_queue_store.py    durable queue definitions and derived state
scripts/agent_queue_claims.py   claim, heartbeat, release, block and recovery
```

## Create an item

Queue IDs are stable and repository-local. Choose next unused `QNNNN` after inspecting `.agents/queue/items/`.

```bash
python3 scripts/agent_queue.py enqueue \
  --id Q0001 \
  --title "Add input validation to the signup endpoint" \
  --workset TCK001 \
  --task TASK-002 \
  --objective "Reject malformed or unsafe signup payloads" \
  --priority 20 \
  --capability typescript \
  --scope contract:api-schema \
  --acceptance-criterion "AC-02" \
  --rule ".claude/rules/testing-dod.md" \
  --primary-file "src/api/signup/schema.ts" \
  --do-not-touch "src/auth/" \
  --validation "npm test -- signup"
```

Repeat flags for multiple dependencies, capabilities, scopes, ACs, rules, files, exclusions, or validations.

## Inspect

```bash
python3 scripts/agent_queue.py validate
python3 scripts/agent_queue.py list
python3 scripts/agent_queue.py list --json
python3 scripts/agent_queue.py show --id Q0001
```

## Claim

```bash
python3 scripts/agent_queue.py claim-next \
  --agent worker-01 \
  --capability typescript
```

Or claim a specific item:

```bash
python3 scripts/agent_queue.py claim \
  --id Q0001 \
  --agent worker-01 \
  --capability typescript
```

The output includes a claim token. Keep it session-local:

```bash
export AGENT_ID=worker-01
export AGENT_CLAIM_TOKEN='<token>'
```

One Worker may hold one claim by default. `--allow-multiple` exists for an explicit Controller decision, not routine use.

## Heartbeat

```bash
python3 scripts/agent_queue.py heartbeat --id Q0001
```

When `AGENT_CLAIM_TOKEN` is not set, pass `--token`.

## Finish

Complete with evidence:

```bash
python3 scripts/agent_queue.py complete \
  --id Q0001 \
  --evidence "npm test -- signup: PASS" \
  --evidence "manual malformed-payload scenarios: PASS"
```

Return uncompleted work:

```bash
python3 scripts/agent_queue.py release \
  --id Q0001 \
  --reason "Worker reassigned before edits"
```

Record blocker:

```bash
python3 scripts/agent_queue.py block \
  --id Q0001 \
  --reason "Approval semantics require ADR"
```

Controller unblocks after resolution:

```bash
python3 scripts/agent_queue.py unblock \
  --id Q0001 \
  --reason "ADR-0004 accepted"
```

Recover expired/terminal claims:

```bash
python3 scripts/agent_queue.py recover
```

## Selection order

`claim-next` chooses lowest numeric priority, then lowest queue ID, among items that:

- are `TODO`
- have all dependencies `DONE`
- match Worker capabilities
- do not conflict with active exclusive scopes
- are not already claimed

## Scope keys

Use exact opaque keys compared for equality.

Good:

```text
contract:api-schema
security:auth-boundary
runtime:process-policy
file:scripts/agent_queue.py
```

Avoid one global key on every item; removes useful parallelism.

## Evidence

Evidence must be reproducible and bounded:

```text
python3 -m unittest discover -s tests -v: PASS (9 tests)
manual symlink escape scenario: PASS
schema/runtime fixture parity: PASS
```

Never use "done", "checked", or "looks good" as evidence.

## Example

See [`examples/Q0001-example.json`](examples/Q0001-example.json). Documentation only; do not copy into live item directory without assigning real tracker and validating scope.
