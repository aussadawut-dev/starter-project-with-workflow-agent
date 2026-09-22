# Git Workflow

Git history is evidence and publication, not a substitute for queue ownership or validation.

## Before editing

- Confirm explicit workspace and repository.
- Inspect branch and working-tree status.
- Identify existing user changes.
- Do not work from detached HEAD.
- Do not reset, clean, stash, discard, or overwrite unrelated changes.
- For Medium/Large work, confirm tracker and queue ownership.

## During implementation

- Keep edits within claimed Work Packet.
- Do not stage files before scope and validation understood.
- Avoid generated artifacts outside canonical ignored locations.
- Keep commits coherent by workset; do not mix unrelated queue items.
- Resolve conflicts by preserving both accepted intent and current user work, not easiest side.

## Commit authority

Request to edit does not automatically authorize commit. Request to commit does not automatically authorize push, merge, release, deployment.

Before commit:

1. queue/tracker state synchronized;
2. required tests and governance validation pass;
3. review has no unresolved blocking finding;
4. staged paths inspected and limited to intended files;
5. commit message names outcome, not merely “updates”.

## Push and publication

Push requires gateway permission and exact-operation approval. Use configured remote explicitly. Configured upstream may hint at remote-selection but is not prerequisite for publication. When execution environment provides bounded generic push, publish only current attached local branch to exact same-name remote. Do not use arbitrary refspecs, change destination branch, set upstream implicitly, or force-push unless separately defined destructive contract and exact approval exist.

Release tags are separate publication action. When execution environment supports bounded release tagging, use only SemVer release tags (optionally prefixed `v`), create annotated tags bound to exact approved commit/HEAD, require exact-operation approval. Never overwrite, retarget, delete, or force-push existing release tag as part of normal workflow.

These rules describe portable workflow policy only. MCP host or local execution gateway remains authoritative for capability availability, remote trust, exact-HEAD binding, credentials, approvals, runtime safety checks.

After publication, record commit/remote/branch and release-tag evidence in tracker and reevaluate closure.

## Forbidden

- `git reset --hard`, `git clean`, destructive checkout, history rewrite, force push as routine recovery.
- Staging entire repository to avoid selecting paths.
- Committing claim tokens or `.agent-runtime/`.
- Marking work `DONE` merely because commit exists.
- Updating queue/tracking in later unrelated commit.
