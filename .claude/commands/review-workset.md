# Review active workset

1. Read accepted requirement, active tracker, queue state, combined diff, applicable rules.
2. Run:

   ```bash
   python3 scripts/agent_queue.py validate
   python3 scripts/agent_queue.py list
   python3 scripts/validate_agent_governance.py
   ```

3. Verify Work Packet scope, ownership, exclusive scopes, acceptance criteria, tests, MCP contracts, security/approval behavior, documentation sync.
4. Return findings as `BLOCKING`, `NON_BLOCKING`, or `ESCALATE`.
5. Return routine corrections to owning Worker. Escalate architecture/security/approval/public-contract findings to Controller.
6. Record overall result as `PASS`, `FIXED`, `BLOCKED`, or `FAIL`.
7. Do not commit, push, merge, release, or deploy unless separately authorized.
