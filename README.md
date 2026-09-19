# Workflow Agent Starter Project

Portable starter repository for a bounded multi-agent software-development workflow.

The workflow keeps **requirements, tracking, queue ownership, runtime claims, verification, and publication authority** separate so multiple agents can work concurrently without treating chat history as the source of truth.

## Included

- `CLAUDE.md` — root governance entry point.
- `.claude/rules/` — routing, topology, queue, tracking, Git, testing, and Definition of Done.
- `.claude/skills/` and `.claude/commands/` — executable agent procedures.
- `.agents/skills/` — compatibility adapters that point back to the canonical Claude skills.
- `.agents/queue/schema/` — durable queue-item schema.
- `scripts/agent_queue*.py` — dependency/capability/scope-aware queue and lease ownership.
- `scripts/agent_workflow*.py` — lean routing, escalation, evidence freshness, events, and resumable finalize.
- `tests/test_agent_*.py` — governance, queue, and workflow tests.
- `docs/` — architecture, runtime guide, queue examples, requirement and tracker templates.

Historical queue items from the source project are intentionally **not included**. A new project starts with a clean queue.

## Requirements

- Python 3
- Git
- An agent runtime that can read repository instructions (Claude Code, Codex-compatible tooling, or another runtime wired to the same files)

The Python workflow tooling uses the standard library only.

## Validate

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_agent_governance.py
python3 scripts/agent_queue.py validate
```

## Start a work item

For Medium/Large work:

1. Capture the requirement from `docs/waiting-implement/TEMPLATE.md`.
2. Create a tracker from `docs/tracking/TEMPLATE.md`.
3. Create queue-ready work packets under `.agents/queue/items/`.
4. Claim before editing, validate the owned scope, then complete/block/release truthfully.
5. Review the combined workset before any separately authorized commit, push, release, or deploy.

Queue CLI help:

```bash
python3 scripts/agent_queue.py --help
python3 scripts/agent_workflow.py --help
```

See `docs/architecture/agent-workflow.md` and `docs/runtime/lean-agent-workflow.md` for the full model.
