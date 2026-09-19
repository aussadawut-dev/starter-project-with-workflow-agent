# Git Workflow

Git history is evidence and publication, not a substitute for queue ownership or validation.

## Before editing

- Confirm the explicit workspace and repository.
- Inspect branch and working-tree status.
- Identify existing user changes.
- Do not work from detached HEAD.
- Do not reset, clean, stash, discard, or overwrite unrelated changes.
- For Medium/Large work, confirm tracker and queue ownership.

## During implementation

- Keep edits within the claimed Work Packet.
- Do not stage files before their scope and validation are understood.
- Avoid generated artifacts outside canonical ignored locations.
- Keep commits coherent by workset; do not mix unrelated queue items.
- Resolve conflicts by preserving both accepted intent and current user work, not by taking the easiest side.

## Commit authority

A request to edit does not automatically authorize commit. A request to commit does not automatically authorize push, merge, release, or deployment.

Before commit:

1. queue/tracker state is synchronized;
2. required tests and governance validation pass;
3. review has no unresolved blocking finding;
4. staged paths are inspected and limited to intended files;
5. commit message names the outcome, not merely “updates”.

## Push and publication

Push requires the gateway's required permission and exact-operation approval. Use the configured remote/upstream explicitly. Never force-push unless a separately defined destructive contract and exact approval exist.

After publication, record commit/remote/branch evidence in the tracker and reevaluate closure.

## Forbidden

- `git reset --hard`, `git clean`, destructive checkout, history rewrite, or force push as routine recovery.
- Staging the entire repository to avoid selecting paths.
- Committing claim tokens or `.agent-runtime/`.
- Marking work `DONE` merely because a commit exists.
- Updating queue/tracking in a later unrelated commit.
