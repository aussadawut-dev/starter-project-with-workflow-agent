# Publish active workset

Use this command only when the user or an approved runbook has explicitly authorized **push/publication**. A release tag is an additional authority and must be separately explicit.

1. Confirm the explicit workspace/repository, current attached branch, exact HEAD, configured remotes, and working-tree status. Refuse detached HEAD.
2. Read `.claude/rules/git-workflow.md`, the active tracker, and the commit/review evidence for the workset being published.
3. Confirm the intended workset is represented by the exact current HEAD. Dirty unrelated changes must not be discarded and must not be described as published.
4. Select an explicitly configured safe remote. An existing upstream may be used only as a remote-selection hint; upstream is not required.
5. Push only the **current attached local branch to the exact same-name remote branch** through the host/gateway's bounded Git capability and exact-operation approval.
   - Do not use arbitrary refspecs.
   - Do not rename the remote destination.
   - Do not set upstream implicitly.
   - Do not force-push or rewrite history.
6. Read back branch/HEAD/publication state and report the pushed commit and destination truthfully. If the push fails after the local commit exists, preserve and report that partial state; do not roll back or rewrite the commit.
7. If, and only if, a release tag was separately authorized:
   - accept only a SemVer release tag, optionally prefixed with `v`;
   - bind the annotated tag to the exact approved HEAD;
   - use exact-operation approval and the host/gateway's bounded release-tag capability;
   - push only that exact tag;
   - never overwrite, retarget, delete, or force-push an existing release tag.
8. Record publication evidence required by the active tracker: commit, remote, branch, and release tag when applicable. If recording that evidence creates new repository changes, do not silently commit or republish them without separate commit/push authority.
9. Reevaluate closure only after every requested publication action has succeeded and no blocking review finding remains.

Commit, push, release-tag, merge, and deployment permissions remain distinct throughout this command.
