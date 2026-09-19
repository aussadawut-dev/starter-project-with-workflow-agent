from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from agent_workflow_contracts import (  # noqa: E402
    WORKFLOW_CONTRACT_VERSION,
    WorkflowContractError,
    evaluate_escalation,
    route_work,
    validate_handoff,
    validate_work_packet,
)
from agent_workflow_evidence import (  # noqa: E402
    evidence_freshness,
    make_evidence_record,
)


def route_payload(**overrides):
    payload = {
        "version": WORKFLOW_CONTRACT_VERSION,
        "objective": "Do a bounded change",
        "persistentChange": True,
        "reversible": True,
        "unresolvedDecision": False,
        "materialSteps": 1,
        "independentWorkItems": 1,
        "riskFlags": [],
    }
    payload.update(overrides)
    return payload


def escalation_payload(**overrides):
    payload = {
        "version": WORKFLOW_CONTRACT_VERSION,
        "item": "Q9001",
        "role": "worker",
        "currentLevel": "standard",
        "failureClass": "implementation",
        "escalationCount": 0,
        "maxEscalations": 1,
        "contextExpansionUsed": False,
    }
    payload.update(overrides)
    return payload


def packet_payload(**overrides):
    payload = {
        "version": WORKFLOW_CONTRACT_VERSION,
        "item": "Q9001",
        "workset": "TCK900",
        "task": "TASK-001",
        "objective": "Implement one thing",
        "dependencies": [],
        "decisions": ["ADR-0001"],
        "acceptanceCriteria": ["AC-01"],
        "requiredCapabilities": ["python"],
        "exclusiveScopes": ["workflow:test"],
        "relevantRules": [".claude/rules/testing-dod.md"],
        "primaryFiles": ["scripts/example.py"],
        "doNotTouch": ["product runtime"],
        "requiredValidation": ["python3 -m unittest"],
        "riskFlags": [],
        "contextBudget": {
            "maxBytes": 65536,
            "maxFiles": 16,
            "maxToolCalls": 24,
            "allowExpansion": True,
        },
    }
    payload.update(overrides)
    return payload


class LeanRoutingContractTest(unittest.TestCase):
    def test_read_only_and_small_fast_paths(self) -> None:
        read_only = route_work(route_payload(persistentChange=False))
        self.assertEqual(read_only.classification, "READ_ONLY")
        self.assertFalse(read_only.queue_required)
        self.assertEqual(read_only.as_dict()["effortPolicy"]["controller"], "light")

        small = route_work(route_payload())
        self.assertEqual(small.classification, "SMALL")
        self.assertFalse(small.tracker_required)
        self.assertEqual(small.phases, ("ROUTE", "EXECUTE", "VERIFY"))
        self.assertEqual(small.review_mode, "SELF")

    def test_high_risk_cannot_be_small_even_when_single_step(self) -> None:
        for flag in (
            "permission",
            "approval",
            "migration",
            "release",
            "security",
            "workspace-isolation",
        ):
            decision = route_work(route_payload(riskFlags=[flag]))
            self.assertEqual(decision.classification, "LARGE", flag)
            self.assertTrue(decision.planner_required)
            self.assertTrue(decision.reviewer_required)

        schema = route_work(route_payload(riskFlags=["tool-schema"]))
        self.assertEqual(schema.classification, "MEDIUM")
        self.assertNotEqual(schema.classification, "SMALL")

    def test_parallelism_is_adaptive_and_burst_is_explicit(self) -> None:
        normal = route_work(route_payload(independentWorkItems=64))
        self.assertEqual(normal.classification, "LARGE")
        self.assertEqual(normal.recommended_workers, 4)
        self.assertFalse(normal.planner_required)
        self.assertIn("ADAPTIVE_PARALLELISM", normal.reason_codes)

        burst = route_work(route_payload(independentWorkItems=64, burstParallelism=True))
        self.assertEqual(burst.recommended_workers, 6)
        self.assertIn("EXPLICIT_BURST", burst.reason_codes)

        risky = route_work(
            route_payload(
                independentWorkItems=64,
                burstParallelism=True,
                riskFlags=["security"],
            )
        )
        self.assertEqual(risky.recommended_workers, 3)
        self.assertEqual(risky.review_mode, "LEAD_PLUS_SPECIALIST")

    def test_parallel_work_does_not_force_planner_without_ambiguity(self) -> None:
        decision = route_work(route_payload(independentWorkItems=3))
        self.assertEqual(decision.classification, "LARGE")
        self.assertFalse(decision.planner_required)
        self.assertEqual(decision.planner_effort, "off")
        self.assertEqual(decision.review_mode, "LEAD")

        ambiguous = route_work(
            route_payload(independentWorkItems=3, unresolvedDecision=True)
        )
        self.assertTrue(ambiguous.planner_required)
        self.assertEqual(ambiguous.planner_effort, "high")

    def test_route_exposes_provider_agnostic_effort_policy(self) -> None:
        decision = route_work(route_payload(riskFlags=["security"])).as_dict()
        self.assertEqual(decision["effortPolicy"]["controller"], "light")
        self.assertEqual(decision["effortPolicy"]["planner"], "high")
        self.assertEqual(decision["effortPolicy"]["reviewer"], "high")
        self.assertEqual(decision["effortPolicy"]["worker"], "standard")
        self.assertEqual(
            decision["effortPolicy"]["temporaryEscalation"],
            {"mode": "PLUS_ONE", "maxEscalations": 1, "resetAfterItem": True},
        )

    def test_unknown_risk_flag_fails_closed(self) -> None:
        with self.assertRaisesRegex(WorkflowContractError, "Unknown riskFlags"):
            route_work(route_payload(riskFlags=["make-it-fast"]))

    def test_packet_requires_scope_acceptance_validation_and_budget(self) -> None:
        normalized = validate_work_packet(packet_payload())
        self.assertEqual(normalized["contextBudget"]["maxFiles"], 16)
        for field in ("acceptanceCriteria", "exclusiveScopes", "requiredValidation"):
            payload = packet_payload()
            payload[field] = []
            with self.assertRaisesRegex(WorkflowContractError, field):
                validate_work_packet(payload)
        payload = packet_payload()
        payload.pop("contextBudget")
        with self.assertRaisesRegex(WorkflowContractError, "contextBudget"):
            validate_work_packet(payload)

    def test_done_handoff_rejects_missing_or_failed_evidence_and_keeps_artifact_refs(self) -> None:
        base = {
            "version": WORKFLOW_CONTRACT_VERSION,
            "item": "Q9001",
            "outcome": "DONE",
            "changed": ["scripts/example.py"],
            "validation": [{"check": "unit", "result": "PASS"}],
            "acCoverage": ["AC-01"],
            "artifactRefs": ["docs/tracking/evidence/TCK900-Q9001.md"],
            "risks": [],
            "followUp": None,
            "claimState": "completed",
            "evidenceFingerprint": "a" * 64,
        }
        normalized = validate_handoff(base)
        self.assertEqual(normalized["outcome"], "DONE")
        self.assertEqual(normalized["artifactRefs"], base["artifactRefs"])
        failed = {**base, "validation": [{"check": "unit", "result": "FAIL"}]}
        with self.assertRaisesRegex(WorkflowContractError, "DONE handoff"):
            validate_handoff(failed)


class EscalationPolicyTest(unittest.TestCase):
    def test_non_capability_failure_never_buys_more_model(self) -> None:
        for failure in ("environment", "tooling"):
            decision = evaluate_escalation(escalation_payload(failureClass=failure))
            self.assertEqual(decision.action, "REMEDIATE_SAME_LEVEL")
            self.assertEqual(decision.next_level, "standard")

        authority = evaluate_escalation(escalation_payload(failureClass="authority"))
        self.assertEqual(authority.action, "BLOCK_FOR_AUTHORITY")
        self.assertEqual(authority.next_level, "standard")

    def test_missing_context_expands_before_escalating(self) -> None:
        first = evaluate_escalation(escalation_payload(failureClass="missing-context"))
        self.assertEqual(first.action, "EXPAND_CONTEXT")
        self.assertEqual(first.next_level, "standard")

        after_expansion = evaluate_escalation(
            escalation_payload(failureClass="missing-context", contextExpansionUsed=True)
        )
        self.assertEqual(after_expansion.action, "ESCALATE_ONE_LEVEL")
        self.assertEqual(after_expansion.next_level, "high")

    def test_capability_failure_escalates_once_and_then_replans(self) -> None:
        first = evaluate_escalation(escalation_payload())
        self.assertEqual(first.action, "ESCALATE_ONE_LEVEL")
        self.assertEqual(first.next_level, "high")
        self.assertTrue(first.reset_after_item)

        exhausted = evaluate_escalation(
            escalation_payload(currentLevel="high", escalationCount=1)
        )
        self.assertEqual(exhausted.action, "REPLAN")
        self.assertEqual(exhausted.next_level, "high")

        maximum = evaluate_escalation(escalation_payload(currentLevel="max"))
        self.assertEqual(maximum.action, "REPLAN")

    def test_invalid_failure_class_fails_closed(self) -> None:
        with self.assertRaisesRegex(WorkflowContractError, "failureClass"):
            evaluate_escalation(escalation_payload(failureClass="just-try-harder"))


class LeanEvidenceFingerprintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name).resolve()
        subprocess.run(["/usr/bin/git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["/usr/bin/git", "config", "user.email", "test@example.invalid"], cwd=self.root, check=True)
        subprocess.run(["/usr/bin/git", "config", "user.name", "Test"], cwd=self.root, check=True)
        (self.root / "tracked.txt").write_text("one\n", encoding="utf-8")
        subprocess.run(["/usr/bin/git", "add", "tracked.txt"], cwd=self.root, check=True)
        subprocess.run(["/usr/bin/git", "commit", "-qm", "initial"], cwd=self.root, check=True)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_clean_record_is_fresh_and_tracked_change_is_stale(self) -> None:
        record = make_evidence_record(self.root)
        self.assertEqual(evidence_freshness(record, self.root)["status"], "FRESH")
        (self.root / "tracked.txt").write_text("two\n", encoding="utf-8")
        stale = evidence_freshness(record, self.root)
        self.assertEqual(stale["status"], "STALE")
        self.assertIn("unstagedSha256", stale["changedInputs"])

    def test_untracked_inputs_invalidate_without_leaking_name_or_content(self) -> None:
        record = make_evidence_record(self.root)
        secret_name = "private-secret-name.txt"
        secret_value = "do-not-persist-this-value"
        (self.root / secret_name).write_text(secret_value, encoding="utf-8")
        stale = evidence_freshness(record, self.root)
        self.assertEqual(stale["status"], "STALE")
        serialized = json.dumps(make_evidence_record(self.root), sort_keys=True)
        self.assertNotIn(secret_name, serialized)
        self.assertNotIn(secret_value, serialized)


if __name__ == "__main__":
    unittest.main()
