# Complete a claim

1. Confirm the item objective and every mapped acceptance criterion are satisfied.
2. Run all required validation and any additional checks triggered by the diff.
3. Inspect changed files and ensure no out-of-scope or secret/runtime state is included.
4. Complete with concrete evidence:

   ```bash
   python3 scripts/agent_queue.py complete \
     --id <Q-id> \
     --token "$AGENT_CLAIM_TOKEN" \
     --evidence "<command/scenario>: PASS" \
     --evidence "<additional evidence>: PASS"
   ```

5. Synchronize the owning tracker task, execution snapshot, and indexes immediately.
6. Return the structured Worker handoff from `.claude/rules/agent-topology.md`.

Do not complete merely because implementation exists; validation evidence is mandatory.
