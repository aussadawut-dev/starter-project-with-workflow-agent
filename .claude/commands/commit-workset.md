# Commit active workset

Use this command only when the user or an approved runbook has explicitly authorized a **commit**. Commit authority does not imply push, merge, release, tag, deployment, or other publication authority.

1. Confirm the explicit workspace/repository, current attached branch, and working-tree status. Refuse to operate from detached HEAD.
2. Read the active requirement/tracker/queue state, the combined diff, `.claude/rules/git-workflow.md`, and the latest review result.
3. Confirm before committing:
   - the owned workset is complete or truthfully at the intended checkpoint;
   - queue/tracker state is synchronized;
   - required tests and governance checks are current and passing;
   - review has no unresolved blocking finding;
   - validation evidence is still fresh for the exact staged/unstaged/untracked inputs that justify the commit.
4. Inspect every changed path. Separate intended workset files from unrelated user changes, generated output, secrets, credentials, claim tokens, `.agent-runtime/`, and other runtime state.
5. Stage **only the exact intended paths**. Do not use whole-repository staging merely to avoid path selection.
6. Inspect staged status/diff again. If the staged set contains unrelated or unsafe content, stop and correct the staged set without resetting, cleaning, stashing, or discarding user work.
7. Create one coherent commit whose message names the outcome. Use the host/gateway's bounded Git capability and exact-operation approval when available.
8. Read back the resulting commit/HEAD and report:
   - commit SHA;
   - branch;
   - committed workset/scope;
   - validations/review used;
   - any remaining uncommitted changes.
9. Do **not** push, tag, merge, release, or deploy unless separately authorized.

Do not create a second bookkeeping commit only to record the SHA of the commit that just happened unless the project's tracking policy explicitly requires it and that additional commit is separately authorized.
