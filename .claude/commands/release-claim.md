# Release or block a claim

Use when Worker will not complete its owned item.

Release uncompleted, safely returnable work:

```bash
python3 scripts/agent_queue.py release \
  --id <Q-id> \
  --token "$AGENT_CLAIM_TOKEN" \
  --reason "<truthful handoff reason>"
```

Block when decision, authority, dependency, or environment prevents progress:

```bash
python3 scripts/agent_queue.py block \
  --id <Q-id> \
  --token "$AGENT_CLAIM_TOKEN" \
  --reason "<specific blocker and required action>"
```

Before either action, preserve changes and record concise handoff in tracker. Never delete runtime claim directory manually.
