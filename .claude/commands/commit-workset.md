# Commit active workset

Use only when user or approved runbook explicitly authorizes **commit**. Commit authority does not imply push, merge, release, tag, deployment, or publication.

1. Confirm explicit workspace/repository, current branch, working-tree status. Refuse detached HEAD.
2. Read active requirement/tracker/queue state, combined diff, `.claude/rules/git-workflow.md`, latest review result.
3. Confirm before committing:
   - owned workset complete or at intended checkpoint;
   - queue/tracker synchronized;
   - required tests and governance checks passing;
   - review has no unresolved blocker;
   - validation evidence fresh for exact staged/unstaged/untracked inputs.
4. Inspect every path. Separate intended workset from unrelated changes, generated output, secrets, credentials, claim tokens, `.agent-runtime/`, runtime state.
5. Stage **only exact intended paths**. Do not use whole-repository staging to avoid selection.
6. Inspect staged status/diff. If staged set contains unrelated/unsafe content, stop and correct without resetting, cleaning, stashing, or discarding user work.
7. Create one coherent commit naming the outcome. Use host/gateway's bounded capability and exact-operation approval when available.
8. Read back resulting commit/HEAD and report:
   - commit SHA;
   - branch;
   - committed workset/scope;
   - validations/review used;
   - remaining uncommitted changes.
9. Do **not** push, tag, merge, release, or deploy unless separately authorized.

Do not create bookkeeping commit only to record the SHA unless project policy explicitly requires it and separately authorized.
