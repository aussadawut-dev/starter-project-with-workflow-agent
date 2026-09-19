from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from agent_queue import QueueStore, to_iso  # noqa: E402
from agent_workflow_contracts import WORKFLOW_CONTRACT_VERSION  # noqa: E402
from agent_workflow_evidence import make_evidence_record  # noqa: E402
from agent_workflow_finalize import (  # noqa: E402
    FinalizeError,
    FinalizeJournal,
    event_delta,
    event_snapshot,
    finalize_item,
    resume_finalize,
)


def queue_item(item_id: str) -> dict:
    now = to_iso()
    return {
        "$schema": "../schema/queue-item.schema.json",
        "id": item_id,
        "title": item_id,
        "status": "TODO",
        "priority": 10,
        "workset": "TCK900",
        "task": "TASK-001",
        "objective": "Synthetic finalize fixture",
        "dependencies": [],
        "requiredCapabilities": ["python"],
        "exclusiveScopes": [f"fixture:{item_id}"],
        "acceptanceCriteria": ["AC-01"],
        "relevantRules": [".claude/rules/testing-dod.md"],
        "primaryFiles": ["tracked.txt"],
        "doNotTouch": [],
        "requiredValidation": ["synthetic: PASS"],
        "createdAt": now,
        "updatedAt": now,
    }


class LeanFinalizeFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name).resolve()
        subprocess.run(["/usr/bin/git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["/usr/bin/git", "config", "user.email", "test@example.invalid"], cwd=self.root, check=True)
        subprocess.run(["/usr/bin/git", "config", "user.name", "Test"], cwd=self.root, check=True)
        (self.root / ".gitignore").write_text(".agent-runtime/\n", encoding="utf-8")
        (self.root / "tracked.txt").write_text("baseline\n", encoding="utf-8")
        (self.root / "docs" / "tracking").mkdir(parents=True)
        self.tracker = self.root / "docs" / "tracking" / "TCK900.md"
        self.tracker.write_text("# TCK900\nQ9001 TODO\n", encoding="utf-8")
        self.store = QueueStore(self.root)
        self.store.enqueue(queue_item("Q9001"))
        subprocess.run(["/usr/bin/git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["/usr/bin/git", "commit", "-qm", "fixture"], cwd=self.root, check=True)
        self.claim = self.store.claim("Q9001", agent_id="worker-a", capabilities=["python"])

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def request(self, evidence: dict | None = None) -> dict:
        record = evidence or make_evidence_record(self.root)
        return {
            "version": WORKFLOW_CONTRACT_VERSION,
            "item": "Q9001",
            "handoff": {
                "version": WORKFLOW_CONTRACT_VERSION,
                "item": "Q9001",
                "outcome": "DONE",
                "changed": ["tracked.txt"],
                "validation": [{"check": "synthetic", "result": "PASS"}],
                "acCoverage": ["AC-01"],
                "risks": [],
                "followUp": None,
                "claimState": "completed",
                "evidenceFingerprint": record["fingerprint"],
            },
            "evidence": record,
            "syncPlan": [
                {
                    "path": "docs/tracking/TCK900.md",
                    "mustContain": ["Q9001 DONE"],
                }
            ],
        }


class LeanFinalizeTest(LeanFinalizeFixture):
    def test_finalize_completes_once_and_sync_ack_is_check_only(self) -> None:
        request = self.request()
        token = self.claim.claim["token"]
        result = finalize_item(self.root, request, token=token)
        self.assertEqual(result["state"], "RECONCILIATION_REQUIRED")
        self.assertFalse(result["reconciliation"]["complete"])
        self.assertEqual(self.store.load_item("Q9001")["status"], "DONE")

        persisted = FinalizeJournal(self.root).path("Q9001").read_text(encoding="utf-8")
        self.assertNotIn(token, persisted)
        self.assertNotIn('"token"', persisted.lower())

        # A repeated finalize returns durable state before checking the now-consumed token.
        repeated = finalize_item(self.root, request, token="definitely-not-the-old-token")
        self.assertEqual(repeated["idempotencyKey"], result["idempotencyKey"])
        self.assertEqual(self.store.load_item("Q9001")["completion"], self.store.load_item("Q9001")["completion"])

        with self.assertRaisesRegex(FinalizeError, "markers are still missing"):
            resume_finalize(self.root, "Q9001", acknowledge_sync=True)
        self.tracker.write_text("# TCK900\nQ9001 DONE\n", encoding="utf-8")
        synced = resume_finalize(self.root, "Q9001", acknowledge_sync=True)
        self.assertEqual(synced["state"], "SYNCED")

        # Later tracker drift is visible instead of silently retaining SYNCED.
        self.tracker.write_text("# TCK900\nQ9001 TODO\n", encoding="utf-8")
        drifted = resume_finalize(self.root, "Q9001")
        self.assertEqual(drifted["state"], "RECONCILIATION_REQUIRED")

    def test_prepared_resume_rechecks_freshness_before_completion(self) -> None:
        request = self.request()
        with self.assertRaisesRegex(RuntimeError, "prepared-crash"):
            finalize_item(
                self.root,
                request,
                token=self.claim.claim["token"],
                after_prepare=lambda: (_ for _ in ()).throw(RuntimeError("prepared-crash")),
            )
        self.assertEqual(self.store.load_item("Q9001")["status"], "TODO")
        self.assertEqual(FinalizeJournal(self.root).load("Q9001")["state"], "PREPARED")
        (self.root / "tracked.txt").write_text("changed-before-resume\n", encoding="utf-8")
        with self.assertRaisesRegex(FinalizeError, "became STALE"):
            resume_finalize(self.root, "Q9001", token=self.claim.claim["token"])
        self.assertEqual(self.store.load_item("Q9001")["status"], "TODO")

    def test_crash_after_queue_completion_recovers_without_replay(self) -> None:
        request = self.request()
        with self.assertRaisesRegex(RuntimeError, "simulated-crash"):
            finalize_item(
                self.root,
                request,
                token=self.claim.claim["token"],
                after_complete=lambda: (_ for _ in ()).throw(RuntimeError("simulated-crash")),
            )
        self.assertEqual(self.store.load_item("Q9001")["status"], "DONE")
        journal = FinalizeJournal(self.root)
        self.assertEqual(journal.load("Q9001")["state"], "PREPARED")
        recovered = resume_finalize(self.root, "Q9001")
        self.assertEqual(recovered["state"], "RECONCILIATION_REQUIRED")
        evidence = self.store.load_item("Q9001")["completion"]["evidence"]
        self.assertEqual(sum(value.startswith("lean-finalize:") for value in evidence), 1)

    def test_stale_evidence_refuses_before_queue_completion(self) -> None:
        evidence = make_evidence_record(self.root)
        (self.root / "tracked.txt").write_text("changed-after-test\n", encoding="utf-8")
        with self.assertRaisesRegex(FinalizeError, "STALE"):
            finalize_item(self.root, self.request(evidence), token=self.claim.claim["token"])
        self.assertEqual(self.store.load_item("Q9001")["status"], "TODO")
        self.assertIsNone(FinalizeJournal(self.root).load("Q9001"))

    def test_different_idempotency_request_conflicts(self) -> None:
        request = self.request()
        finalize_item(self.root, request, token=self.claim.claim["token"])
        altered = json.loads(json.dumps(request))
        altered["syncPlan"][0]["mustContain"] = ["different marker"]
        with self.assertRaisesRegex(FinalizeError, "conflict"):
            finalize_item(self.root, altered, token="unused")


class LeanEventSnapshotTest(LeanFinalizeFixture):
    def test_event_delta_reconciles_claim_state_without_token(self) -> None:
        # setUp already claimed; release first so the baseline is READY.
        token = self.claim.claim["token"]
        self.store.release("Q9001", token=token, reason="event-baseline")
        baseline = event_snapshot(self.root)
        self.assertEqual(baseline["items"]["Q9001"]["derivedStatus"], "READY")
        next_claim = self.store.claim("Q9001", agent_id="worker-b", capabilities=["python"])
        delta = event_delta(self.root, baseline)
        self.assertEqual(delta["changed"]["Q9001"]["derivedStatus"], "CLAIMED")
        serialized = json.dumps(delta, sort_keys=True)
        self.assertNotIn(next_claim.claim["token"], serialized)
        self.assertTrue(delta["reconciledFromAuthority"])


if __name__ == "__main__":
    unittest.main()
