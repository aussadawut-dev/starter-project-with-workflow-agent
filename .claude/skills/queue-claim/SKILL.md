---
name: queue-claim
description: Enqueue, atomically claim, heartbeat, release, block, recover, and complete concurrent agent work while enforcing dependencies, capabilities, exclusive scopes, lease ownership, and validation evidence.
---

# Queue Claim

Read [the queue-claim rule](../../rules/queue-claim.md) before mutating queue or claim state.

## Controller path

```bash
python3 scripts/agent_queue.py validate
python3 scripts/agent_queue.py list
python3 scripts/agent_queue.py enqueue ...
```

Queue only queue-ready Work Packets with known decisions, dependencies, capabilities, exclusive scopes, files, exclusions, ACs, and validation.

## Worker path

```bash
python3 scripts/agent_queue.py claim-next --agent <id> [--capability <cap> ...]
```

After claim:

1. keep the returned token session-local;
2. read only the Work Packet references;
3. edit only the claimed scope;
4. heartbeat at least once per one-third of the lease;
5. validate and collect evidence;
6. call exactly one of `complete`, `block`, or `release`.

Never edit `.agent-runtime/claims/` manually.

## Reviewer path

Check queue/tracker agreement, ownership, scope conflicts, evidence, stale claims, and terminal state before accepting the workset.
