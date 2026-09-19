---
name: review-workset
description: Review a completed workset from Work Packets, combined diff, tests, queue/tracker state, MCP security/approval contracts, and publication risk; return blocking findings or an evidence-based gate result.
---

# Review Workset

Read [testing and DoD](../../rules/testing-dod.md), plus only the domain rules selected by the semantic diff.

## Inputs

- accepted requirement and ACs;
- active tracker and execution snapshot;
- completed/blocked queue items;
- combined diff;
- Worker validation evidence;
- requested publication authority.

## Review order

1. Requirement and scope compliance.
2. Queue ownership and exclusive-scope integrity.
3. Workspace, path, secret, permission, and approval safety.
4. Tool schema/runtime/error/audit compatibility.
5. Correctness and failure paths.
6. Tests and evidence.
7. Tracking/documentation synchronization.
8. Git/publication state.

Classify each finding as `BLOCKING`, `NON_BLOCKING`, or `ESCALATE`. Return routine fixes to the owning Worker as a bounded correction. Escalate architecture, destructive behavior, workspace boundary, approval model, or public contract findings to the Controller.

Result: `PASS`, `FIXED`, `BLOCKED`, or `FAIL`.
