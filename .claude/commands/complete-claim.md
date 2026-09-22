# Complete a claim

1. Confirm item objective and every acceptance criterion satisfied.
2. Run all required validation and diff-triggered checks.
3. Inspect changed files. Ensure no out-of-scope or secret/runtime state included.
4. Complete with concrete evidence:

   ```bash
   python3 scripts/agent_queue.py complete \
     --id <Q-id> \
     --token "$AGENT_CLAIM_TOKEN" \
     --evidence "<command/scenario>: PASS" \
     --evidence "<additional evidence>: PASS"
   ```

5. Synchronize owning tracker task, execution snapshot, indexes immediately.
6. Return structured Worker handoff from `.claude/rules/agent-topology.md`.

Do not complete without validation evidence.
