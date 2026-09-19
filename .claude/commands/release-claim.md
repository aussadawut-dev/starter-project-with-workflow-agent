# Release or block a claim

Use when the Worker will not complete its currently owned item.

Release uncompleted, safely returnable work:

```bash
python3 scripts/agent_queue.py release \
  --id <Q-id> \
  --token "$AGENT_CLAIM_TOKEN" \
  --reason "<truthful handoff reason>"
```

Block when a decision, authority, dependency, or environment prevents progress:

```bash
python3 scripts/agent_queue.py block \
  --id <Q-id> \
  --token "$AGENT_CLAIM_TOKEN" \
  --reason "<specific blocker and required action>"
```

Before either action, preserve safe changes and record a concise handoff in the tracker. Never delete the runtime claim directory manually.
