# Claim next queue item

1. Read `CLAUDE.md`, `.claude/rules/execution-router.md`, and `.claude/rules/queue-claim.md`.
2. Set a stable Worker ID and declare only real capabilities.
3. Inspect the queue:

   ```bash
   python3 scripts/agent_queue.py validate
   python3 scripts/agent_queue.py list
   ```

4. Claim atomically:

   ```bash
   python3 scripts/agent_queue.py claim-next \
     --agent <worker-id> \
     --capability <capability>
   ```

5. Preserve the returned token in `AGENT_CLAIM_TOKEN`; do not commit or share it.
6. Read only the claimed Work Packet references.
7. Confirm dependencies, exclusive scopes, primary files, exclusions, ACs, and validation before editing.
8. Heartbeat during long work.
