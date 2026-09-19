# Review active workset

1. Read only the accepted requirement, active tracker, queue state, combined diff, and applicable rules.
2. Run:

   ```bash
   python3 scripts/agent_queue.py validate
   python3 scripts/agent_queue.py list
   python3 scripts/validate_agent_governance.py
   ```

3. Verify Work Packet scope, ownership, exclusive scopes, acceptance criteria, tests, MCP contracts, security/approval behavior, and documentation synchronization.
4. Return findings as `BLOCKING`, `NON_BLOCKING`, or `ESCALATE`.
5. Return routine corrections to the owning Worker. Escalate architecture/security/approval/public-contract findings to the Controller.
6. Record the overall result as `PASS`, `FIXED`, `BLOCKED`, or `FAIL`.
7. Do not commit, push, merge, release, or deploy unless separately authorized.
