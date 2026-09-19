from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from agent_queue import QueueError, QueueStore, to_iso  # noqa: E402
from agent_workflow_contracts import (  # noqa: E402
    WORKFLOW_CONTRACT_VERSION,
    WorkflowContractError,
    route_work,
    validate_work_packet,
)
from agent_workflow_evidence import make_evidence_record  # noqa: E402
from agent_workflow_finalize import (  # noqa: E402
    FinalizeError,
    event_snapshot,
    finalize_item,
    resume_finalize,
)


def item(item_id: str, scope: str) -> dict:
    now = to_iso()
    return {
        "$schema": "../schema/queue-item.schema.json",
        "id": item_id,
        "title": item_id,
        "status": "TODO",
        "priority": 10,
        "workset": "TCK999",
        "task": f"TASK-{item_id[1:]}",
        "objective": "Lean pilot",
        "dependencies": [],
        "requiredCapabilities": ["python"],
        "exclusiveScopes": [scope],
        "acceptanceCriteria": ["AC-01"],
        "relevantRules": [],
        "primaryFiles": ["tracked.txt"],
        "doNotTouch": [],
        "requiredValidation": ["pilot: PASS"],
        "createdAt": now,
        "updatedAt": now,
    }


def route(**overrides):
    value = {
        "version": WORKFLOW_CONTRACT_VERSION,
        "objective": "Pilot route",
        "persistentChange": True,
        "reversible": True,
        "unresolvedDecision": False,
        "materialSteps": 1,
        "independentWorkItems": 1,
        "riskFlags": [],
    }
    value.update(overrides)
    return route_work(value)


class LeanPilotRoutingTest(unittest.TestCase):
    def test_fast_path_and_high_risk_keep_different_topologies(self) -> None:
        small = route()
        self.assertEqual(small.classification, "SMALL")
        self.assertFalse(small.planner_required)
        self.assertFalse(small.queue_required)
        self.assertEqual(small.phases, ("ROUTE", "EXECUTE", "VERIFY"))

        medium = route(riskFlags=["tool-schema"])
        self.assertEqual(medium.classification, "MEDIUM")
        self.assertTrue(medium.queue_required)

        large = route(riskFlags=["security"], independentWorkItems=12)
        self.assertEqual(large.classification, "LARGE")
        self.assertTrue(large.planner_required)
        self.assertTrue(large.reviewer_required)
        # A high-risk flag caps fan-out at 3 workers: 4 is the normal maximum
        # and 5-6 need an explicit burstParallelism, which the cap still wins over.
        self.assertEqual(large.recommended_workers, 3)

        read_only = route(persistentChange=False)
        self.assertEqual(read_only.classification, "READ_ONLY")

    def test_context_budget_is_bounded_and_expansion_is_explicit(self) -> None:
        packet = {
            "version": WORKFLOW_CONTRACT_VERSION,
            "item": "Q9999",
            "workset": "TCK999",
            "task": "TASK-001",
            "objective": "Budget fixture",
            "dependencies": [],
            "decisions": [],
            "acceptanceCriteria": ["AC-01"],
            "requiredCapabilities": ["python"],
            "exclusiveScopes": ["pilot:budget"],
            "relevantRules": [],
            "primaryFiles": ["tracked.txt"],
            "doNotTouch": [],
            "requiredValidation": ["pilot: PASS"],
            "riskFlags": [],
            "contextBudget": {
                "maxBytes": 65536,
                "maxFiles": 8,
                "maxToolCalls": 12,
                "allowExpansion": False,
            },
        }
        normalized = validate_work_packet(packet)
        self.assertFalse(normalized["contextBudget"]["allowExpansion"])
        packet["contextBudget"] = {**packet["contextBudget"], "maxFiles": 999}
        with self.assertRaisesRegex(WorkflowContractError, "maxFiles"):
            validate_work_packet(packet)


class LeanPilotRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name).resolve()
        subprocess.run(["/usr/bin/git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["/usr/bin/git", "config", "user.email", "pilot@example.invalid"], cwd=self.root, check=True)
        subprocess.run(["/usr/bin/git", "config", "user.name", "Pilot"], cwd=self.root, check=True)
        (self.root / ".gitignore").write_text(".agent-runtime/\n", encoding="utf-8")
        (self.root / "tracked.txt").write_text("baseline\n", encoding="utf-8")
        (self.root / "tracker.md").write_text("Q9001 TODO\n", encoding="utf-8")
        self.store = QueueStore(self.root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def commit_queue(self) -> None:
        subprocess.run(["/usr/bin/git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["/usr/bin/git", "commit", "-qm", "pilot"], cwd=self.root, check=True)

    def finalize_request(self, item_id: str, evidence: dict) -> dict:
        return {
            "version": WORKFLOW_CONTRACT_VERSION,
            "item": item_id,
            "handoff": {
                "version": WORKFLOW_CONTRACT_VERSION,
                "item": item_id,
                "outcome": "DONE",
                "changed": ["tracked.txt"],
                "validation": [{"check": "pilot", "result": "PASS"}],
                "acCoverage": ["AC-01"],
                "risks": [],
                "followUp": None,
                "claimState": "completed",
                "evidenceFingerprint": evidence["fingerprint"],
            },
            "evidence": evidence,
            "syncPlan": [{"path": "tracker.md", "mustContain": [f"{item_id} DONE"]}],
        }

    def test_legacy_queue_rollback_path_keeps_scope_conflict_and_completion(self) -> None:
        self.store.enqueue(item("Q9001", "shared:scope"))
        self.store.enqueue(item("Q9002", "shared:scope"))
        first = self.store.claim("Q9001", agent_id="legacy-a", capabilities=["python"])
        with self.assertRaisesRegex(QueueError, "Exclusive scope conflict"):
            self.store.claim("Q9002", agent_id="legacy-b", capabilities=["python"], allow_multiple=True)
        completed = self.store.complete("Q9001", token=first.claim["token"], evidence=["legacy pilot: PASS"])
        self.assertEqual(completed["status"], "DONE")
        self.assertFalse((self.root / ".agent-runtime" / "finalize" / "Q9001.json").exists())

    def test_stale_evidence_blocks_pilot_finalize(self) -> None:
        self.store.enqueue(item("Q9001", "pilot:stale"))
        self.commit_queue()
        claim = self.store.claim("Q9001", agent_id="lean-a", capabilities=["python"])
        evidence = make_evidence_record(self.root)
        (self.root / "tracked.txt").write_text("changed after validation\n", encoding="utf-8")
        with self.assertRaisesRegex(FinalizeError, "STALE"):
            finalize_item(self.root, self.finalize_request("Q9001", evidence), token=claim.claim["token"])
        self.assertEqual(self.store.load_item("Q9001")["status"], "TODO")

    def test_interrupted_finalize_reconnects_from_authority_without_replay(self) -> None:
        self.store.enqueue(item("Q9001", "pilot:resume"))
        self.commit_queue()
        claim = self.store.claim("Q9001", agent_id="lean-a", capabilities=["python"])
        evidence = make_evidence_record(self.root)
        request = self.finalize_request("Q9001", evidence)
        with self.assertRaisesRegex(RuntimeError, "pilot-crash"):
            finalize_item(
                self.root,
                request,
                token=claim.claim["token"],
                after_complete=lambda: (_ for _ in ()).throw(RuntimeError("pilot-crash")),
            )
        self.assertEqual(self.store.load_item("Q9001")["status"], "DONE")
        recovered = resume_finalize(self.root, "Q9001")
        self.assertEqual(recovered["state"], "RECONCILIATION_REQUIRED")
        snapshot = event_snapshot(self.root)
        self.assertIn("Q9001", snapshot["reconciliationRequired"])
        self.assertTrue(snapshot["reconciledFromAuthority"])
        self.assertEqual(sum(value.startswith("lean-finalize:") for value in self.store.load_item("Q9001")["completion"]["evidence"]), 1)


if __name__ == "__main__":
    unittest.main()
