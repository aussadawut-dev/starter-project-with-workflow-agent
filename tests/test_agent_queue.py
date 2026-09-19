from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from agent_queue import QueueError, QueueStore, to_iso, utc_now  # noqa: E402


def make_item(
    item_id: str,
    *,
    title: str | None = None,
    dependencies: list[str] | None = None,
    capabilities: list[str] | None = None,
    scopes: list[str] | None = None,
    priority: int = 100,
) -> dict:
    now = to_iso()
    return {
        "$schema": "../schema/queue-item.schema.json",
        "id": item_id,
        "title": title or item_id,
        "status": "TODO",
        "priority": priority,
        "workset": "TCK001",
        "task": f"TASK-{item_id[1:]}",
        "objective": f"Complete {item_id}",
        "dependencies": dependencies or [],
        "requiredCapabilities": capabilities or [],
        "exclusiveScopes": scopes or [],
        "acceptanceCriteria": ["AC-01"],
        "relevantRules": [".claude/rules/queue-claim.md"],
        "primaryFiles": [],
        "doNotTouch": [],
        "requiredValidation": ["python3 -m unittest"],
        "createdAt": now,
        "updatedAt": now,
    }


class QueueStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.store = QueueStore(self.root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_enqueue_validate_and_list_ready(self) -> None:
        self.store.enqueue(make_item("Q0001"))
        result = self.store.validate_all()
        self.assertTrue(result["valid"])
        self.assertEqual(result["itemCount"], 1)
        rows = self.store.list_rows()
        self.assertEqual(rows[0]["derivedStatus"], "READY")

    def test_claim_is_exclusive_and_token_protected(self) -> None:
        self.store.enqueue(make_item("Q0001", capabilities=["python"]))
        first = self.store.claim(
            "Q0001", agent_id="worker-a", capabilities=["python"]
        )
        self.assertEqual(first.claim["agentId"], "worker-a")

        with self.assertRaisesRegex(QueueError, "already has an active claim"):
            self.store.claim(
                "Q0001",
                agent_id="worker-b",
                capabilities=["python"],
                allow_multiple=True,
            )

        with self.assertRaisesRegex(QueueError, "does not own"):
            self.store.heartbeat("Q0001", token="wrong-token")

        renewed = self.store.heartbeat("Q0001", token=first.claim["token"])
        self.assertEqual(renewed["itemId"], "Q0001")

    def test_worker_has_one_claim_by_default(self) -> None:
        self.store.enqueue(make_item("Q0001"))
        self.store.enqueue(make_item("Q0002"))
        first = self.store.claim_next(agent_id="worker-a")
        self.assertEqual(first.item["id"], "Q0001")

        with self.assertRaisesRegex(QueueError, "already owns active claim"):
            self.store.claim_next(agent_id="worker-a")

        second = self.store.claim_next(
            agent_id="worker-a", allow_multiple=True
        )
        self.assertEqual(second.item["id"], "Q0002")

    def test_claim_next_respects_priority_dependencies_and_capabilities(self) -> None:
        self.store.enqueue(
            make_item("Q0001", priority=10, capabilities=["go"])
        )
        self.store.enqueue(
            make_item("Q0002", priority=20, capabilities=["python"])
        )
        self.store.enqueue(
            make_item("Q0003", priority=1, dependencies=["Q0002"])
        )

        claimed = self.store.claim_next(
            agent_id="worker-a", capabilities=["python"]
        )
        self.assertEqual(claimed.item["id"], "Q0002")

        completed = self.store.complete(
            "Q0002",
            token=claimed.claim["token"],
            evidence=["unit tests passed"],
        )
        self.assertEqual(completed["status"], "DONE")

        next_claim = self.store.claim_next(
            agent_id="worker-b", capabilities=[]
        )
        self.assertEqual(next_claim.item["id"], "Q0003")

    def test_exclusive_scope_blocks_parallel_claim(self) -> None:
        self.store.enqueue(make_item("Q0001", scopes=["contract:tool-schema"]))
        self.store.enqueue(make_item("Q0002", scopes=["contract:tool-schema"]))
        self.store.enqueue(make_item("Q0003", scopes=["docs:readme"]))

        first = self.store.claim("Q0001", agent_id="worker-a")
        with self.assertRaisesRegex(QueueError, "Exclusive scope conflict"):
            self.store.claim(
                "Q0002", agent_id="worker-b", allow_multiple=True
            )

        third = self.store.claim(
            "Q0003", agent_id="worker-b", allow_multiple=True
        )
        self.assertEqual(third.item["id"], "Q0003")
        self.store.release(
            "Q0001", token=first.claim["token"], reason="handoff"
        )

    def test_complete_requires_evidence_and_updates_item(self) -> None:
        self.store.enqueue(make_item("Q0001"))
        claimed = self.store.claim("Q0001", agent_id="worker-a")

        with self.assertRaisesRegex(QueueError, "evidence"):
            self.store.complete(
                "Q0001", token=claimed.claim["token"], evidence=[]
            )

        completed = self.store.complete(
            "Q0001",
            token=claimed.claim["token"],
            evidence=["python3 -m unittest: PASS"],
        )
        self.assertEqual(completed["status"], "DONE")
        self.assertEqual(completed["completion"]["agentId"], "worker-a")
        self.assertIsNone(self.store._load_claim("Q0001"))

    def test_block_and_unblock(self) -> None:
        self.store.enqueue(make_item("Q0001"))
        claimed = self.store.claim("Q0001", agent_id="worker-a")
        blocked = self.store.block(
            "Q0001",
            token=claimed.claim["token"],
            reason="Needs architecture decision",
        )
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertEqual(self.store.list_rows()[0]["derivedStatus"], "BLOCKED")

        unblocked = self.store.unblock(
            "Q0001", reason="ADR accepted"
        )
        self.assertEqual(unblocked["status"], "TODO")
        self.assertEqual(self.store.list_rows()[0]["derivedStatus"], "READY")

    def test_stale_claim_is_recovered_and_reclaimable(self) -> None:
        self.store.enqueue(make_item("Q0001"))
        first = self.store.claim("Q0001", agent_id="worker-a", lease_seconds=60)
        claim_path = self.store._claim_path("Q0001")
        claim = json.loads(claim_path.read_text(encoding="utf-8"))
        claim["heartbeatAt"] = to_iso(utc_now() - timedelta(seconds=61))
        claim_path.write_text(json.dumps(claim), encoding="utf-8")

        recovered = self.store.recover_stale()
        self.assertEqual(recovered[0]["event"], "stale-recovered")

        second = self.store.claim("Q0001", agent_id="worker-b")
        self.assertNotEqual(first.claim["token"], second.claim["token"])

    def test_session_generation_recovery_releases_active_claim_without_token(self) -> None:
        self.store.enqueue(make_item("Q0001"))
        owner_hash = "a" * 64
        first = self.store.claim(
            "Q0001",
            agent_id="worker-a",
            owner_session_hash=owner_hash,
            owner_generation=7,
        )
        self.assertEqual(first.claim["ownerSessionHash"], owner_hash)
        self.assertEqual(first.claim["ownerGeneration"], 7)

        with self.assertRaisesRegex(QueueError, "does not require recovery"):
            self.store.recover_generation(
                "Q0001",
                agent_id="worker-a",
                owner_session_hash=owner_hash,
                owner_generation=7,
                reason="same generation",
            )
        with self.assertRaisesRegex(QueueError, "does not require recovery"):
            self.store.recover_generation(
                "Q0001",
                agent_id="worker-a",
                owner_session_hash="b" * 64,
                owner_generation=8,
                reason="foreign session",
            )

        recovered = self.store.recover_generation(
            "Q0001",
            agent_id="worker-a",
            owner_session_hash=owner_hash,
            owner_generation=8,
            reason="session reload invalidated handle",
        )
        self.assertEqual(recovered["event"], "session-generation-recovered")
        second = self.store.claim("Q0001", agent_id="worker-b")
        self.assertNotEqual(first.claim["token"], second.claim["token"])

    def test_legacy_claim_has_explicit_recovery_path(self) -> None:
        self.store.enqueue(make_item("Q0001"))
        self.store.claim("Q0001", agent_id="worker-a")
        recovered = self.store.recover_generation(
            "Q0001",
            agent_id="worker-a",
            owner_session_hash="a" * 64,
            owner_generation=2,
            reason="migrate legacy claim after reload",
        )
        self.assertEqual(recovered["event"], "legacy-claim-recovered")

    def test_dependency_cycle_is_rejected(self) -> None:
        self.store.enqueue(make_item("Q0001"))
        with self.assertRaisesRegex(QueueError, "missing item Q9999"):
            self.store.enqueue(
                make_item("Q0002", dependencies=["Q9999"])
            )

        # Simulate malformed externally edited queue to verify cycle detection.
        item_two = make_item("Q0002", dependencies=["Q0001"])
        self.store._item_path("Q0002").parent.mkdir(parents=True, exist_ok=True)
        self.store._item_path("Q0002").write_text(
            json.dumps(item_two), encoding="utf-8"
        )
        item_one = self.store.load_item("Q0001")
        item_one["dependencies"] = ["Q0002"]
        self.store._item_path("Q0001").write_text(
            json.dumps(item_one), encoding="utf-8"
        )
        result = self.store.validate_all()
        self.assertFalse(result["valid"])
        self.assertTrue(any("Dependency cycle" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
