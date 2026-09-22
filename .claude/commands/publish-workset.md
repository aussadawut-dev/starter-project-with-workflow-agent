# Publish active workset

Use only when user or approved runbook explicitly authorizes **push/publication**. Release tag requires separate explicit authority.

1. Confirm explicit workspace/repository, current branch, exact HEAD, configured remotes, working-tree status. Refuse detached HEAD.
2. Read `.claude/rules/git-workflow.md`, active tracker, commit/review evidence for published workset.
3. Confirm intended workset represented by exact current HEAD. Dirty unrelated changes must not be discarded or described as published.
4. Select explicitly configured safe remote. Existing upstream is only a hint; not required.
5. Push **current branch to exact same-name remote** through host/gateway's bounded capability and exact-operation approval:
   - No arbitrary refspecs.
   - No remote rename.
   - No implicit upstream.
   - No force-push or rewrite.
6. Read back branch/HEAD/publication state. Report pushed commit and destination truthfully. If push fails after local commit, preserve and report partial state; do not roll back.
7. Only if release tag separately authorized:
   - Accept SemVer tag, optionally prefixed `v`;
   - Bind annotated tag to exact approved HEAD;
   - Use exact-operation approval and host/gateway's bounded capability;
   - Push only exact tag;
   - Never overwrite, retarget, delete, or force-push release tags.
8. Record publication evidence for active tracker: commit, remote, branch, release tag. If recording creates new changes, do not silently commit/republish without separate authority.
9. Reevaluate closure only after every requested action succeeds and no blocking review finding remains.

Commit, push, release-tag, merge, deployment permissions remain distinct.
