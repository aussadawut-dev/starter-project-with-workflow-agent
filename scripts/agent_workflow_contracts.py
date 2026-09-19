"""Versioned Lean Agent Workflow routing and handoff contracts.

This layer is deliberately pure: it owns no queue state, filesystem mutation,
process execution, provider selection, or publication authority. It turns
declared work shape into a deterministic route, evaluates bounded temporary
escalation, and validates compact packets/handoffs before another layer acts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

WORKFLOW_CONTRACT_VERSION = "1.0.0"
MAX_WORKERS = 6
NORMAL_MAX_WORKERS = 4
MAX_CONTEXT_BYTES = 2 * 1024 * 1024
MAX_CONTEXT_FILES = 128
MAX_TOOL_CALLS = 128

EFFORT_LEVELS = ("light", "standard", "high", "max")
FAILURE_CLASSES = frozenset(
    {
        "environment",
        "tooling",
        "authority",
        "missing-context",
        "reasoning",
        "implementation",
        "planning",
    }
)
RISK_FLAGS = frozenset(
    {
        "workspace-isolation",
        "path-safety",
        "secrets",
        "permission",
        "approval",
        "tool-schema",
        "public-contract",
        "process-execution",
        "destructive-action",
        "migration",
        "release",
        "cross-area",
        "security",
    }
)
LARGE_RISK_FLAGS = frozenset(
    {
        "workspace-isolation",
        "secrets",
        "permission",
        "approval",
        "public-contract",
        "destructive-action",
        "migration",
        "release",
        "cross-area",
        "security",
    }
)
SPECIALIST_REVIEW_FLAGS = frozenset(
    {
        "workspace-isolation",
        "secrets",
        "permission",
        "approval",
        "public-contract",
        "destructive-action",
        "migration",
        "cross-area",
        "security",
    }
)


class WorkflowContractError(ValueError):
    """A Lean workflow request/packet/handoff is malformed or unsafe."""


def _string(value: Any, field: str, *, max_length: int = 32768) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkflowContractError(f"{field} must be a non-empty string")
    if len(value) > max_length:
        raise WorkflowContractError(f"{field} exceeds {max_length} characters")
    return value.strip()


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise WorkflowContractError(f"{field} must be boolean")
    return value


def _optional_bool(payload: Mapping[str, Any], field: str, default: bool = False) -> bool:
    if field not in payload:
        return default
    return _bool(payload[field], field)


def _integer(value: Any, field: str, minimum: int, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise WorkflowContractError(f"{field} must be an integer in [{minimum}, {maximum}]")
    return value


def _optional_integer(
    payload: Mapping[str, Any],
    field: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    if field not in payload:
        return default
    return _integer(payload[field], field, minimum, maximum)


def _strings(value: Any, field: str, *, maximum: int = 256) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum:
        raise WorkflowContractError(f"{field} must be a list with at most {maximum} entries")
    result = [_string(item, field, max_length=4096) for item in value]
    if len(result) != len(set(result)):
        raise WorkflowContractError(f"{field} must not contain duplicates")
    return result


def _version(payload: Mapping[str, Any]) -> None:
    if payload.get("version") != WORKFLOW_CONTRACT_VERSION:
        raise WorkflowContractError(
            f"version must be {WORKFLOW_CONTRACT_VERSION!r}"
        )


def _adaptive_worker_count(independent: int, *, burst: bool, high_risk: bool) -> int:
    if independent <= 1:
        workers = 1
    elif burst:
        workers = min(MAX_WORKERS, independent)
    elif independent <= 3:
        workers = 2
    elif independent <= 5:
        workers = 3
    else:
        workers = NORMAL_MAX_WORKERS
    if high_risk:
        workers = min(workers, 3)
    return workers


@dataclass(frozen=True)
class RouteDecision:
    classification: str
    tracker_required: bool
    queue_required: bool
    planner_required: bool
    reviewer_required: bool
    recommended_workers: int
    review_mode: str
    controller_effort: str
    planner_effort: str
    reviewer_effort: str
    worker_effort: str
    phases: tuple[str, ...]
    reason_codes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": WORKFLOW_CONTRACT_VERSION,
            "classification": self.classification,
            "trackerRequired": self.tracker_required,
            "queueRequired": self.queue_required,
            "plannerRequired": self.planner_required,
            "reviewerRequired": self.reviewer_required,
            "recommendedWorkers": self.recommended_workers,
            "reviewMode": self.review_mode,
            "effortPolicy": {
                "controller": self.controller_effort,
                "planner": self.planner_effort,
                "reviewer": self.reviewer_effort,
                "worker": self.worker_effort,
                "temporaryEscalation": {
                    "mode": "PLUS_ONE",
                    "maxEscalations": 1,
                    "resetAfterItem": True,
                },
            },
            "phases": list(self.phases),
            "reasonCodes": list(self.reason_codes),
        }


@dataclass(frozen=True)
class EscalationDecision:
    item: str
    role: str
    failure_class: str
    current_level: str
    action: str
    next_level: str
    reset_after_item: bool
    reason_codes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": WORKFLOW_CONTRACT_VERSION,
            "item": self.item,
            "role": self.role,
            "failureClass": self.failure_class,
            "currentLevel": self.current_level,
            "action": self.action,
            "nextLevel": self.next_level,
            "resetAfterItem": self.reset_after_item,
            "reasonCodes": list(self.reason_codes),
        }


def route_work(payload: Mapping[str, Any]) -> RouteDecision:
    """Classify work from explicit shape/risk metadata.

    High-risk flags can only make the route heavier. Parallelism alone can
    create a Large workset without forcing a Planner turn when the work is
    already independently executable.
    """

    _version(payload)
    _string(payload.get("objective"), "objective")
    persistent = _bool(payload.get("persistentChange"), "persistentChange")
    reversible = _bool(payload.get("reversible"), "reversible")
    unresolved = _bool(payload.get("unresolvedDecision"), "unresolvedDecision")
    steps = _integer(payload.get("materialSteps"), "materialSteps", 0, 1000)
    independent = _integer(
        payload.get("independentWorkItems"), "independentWorkItems", 0, 64
    )
    burst = _optional_bool(payload, "burstParallelism", False)
    flags = frozenset(_strings(payload.get("riskFlags", []), "riskFlags", maximum=64))
    unknown = sorted(flags - RISK_FLAGS)
    if unknown:
        raise WorkflowContractError(f"Unknown riskFlags: {', '.join(unknown)}")

    if not persistent:
        return RouteDecision(
            "READ_ONLY", False, False, False, False, 1, "NONE",
            "light", "off", "off", "off", ("ROUTE",),
            ("NO_PERSISTENT_CHANGE",),
        )

    large_flags = flags & LARGE_RISK_FLAGS
    if large_flags or independent > 1:
        planner_required = bool(large_flags or unresolved)
        specialist = bool(flags & SPECIALIST_REVIEW_FLAGS)
        reasons = ["HIGH_SEMANTIC_RISK" if large_flags else "PARALLEL_WORKSET"]
        if unresolved:
            reasons.append("UNRESOLVED_DECISION")
        if independent > 1 and not burst:
            reasons.append("ADAPTIVE_PARALLELISM")
        if burst:
            reasons.append("EXPLICIT_BURST")
        return RouteDecision(
            "LARGE", True, True, planner_required, True,
            _adaptive_worker_count(independent, burst=burst, high_risk=bool(large_flags)),
            "LEAD_PLUS_SPECIALIST" if specialist else "LEAD",
            "light", "high" if planner_required else "off",
            "high" if specialist else "standard", "standard",
            ("ROUTE", "PREPARE", "EXECUTE", "VERIFY", "FINALIZE"),
            tuple(reasons),
        )

    if flags or unresolved or steps > 1 or not reversible:
        reasons: list[str] = []
        if flags:
            reasons.append("MEANINGFUL_RISK")
        if unresolved:
            reasons.append("UNRESOLVED_DECISION")
        if steps > 1:
            reasons.append("MULTI_STEP")
        if not reversible:
            reasons.append("NOT_REVERSIBLE")
        reviewer_required = bool(flags)
        specialist = bool(flags & SPECIALIST_REVIEW_FLAGS)
        return RouteDecision(
            "MEDIUM", True, True, unresolved, reviewer_required, 1,
            "LEAD_PLUS_SPECIALIST" if specialist else "LEAD" if reviewer_required else "SELF",
            "light", "high" if unresolved else "off",
            "high" if specialist else "standard" if reviewer_required else "off",
            "standard",
            ("ROUTE", "PREPARE", "EXECUTE", "VERIFY", "FINALIZE"),
            tuple(reasons or ["TRACKED_CHANGE"]),
        )

    return RouteDecision(
        "SMALL", False, False, False, False, 1, "SELF",
        "standard", "off", "off", "off",
        ("ROUTE", "EXECUTE", "VERIFY"),
        ("LOW_RISK_REVERSIBLE_SINGLE_STEP",),
    )


def evaluate_escalation(payload: Mapping[str, Any]) -> EscalationDecision:
    """Choose the cheapest truthful recovery action for one failed item."""

    _version(payload)
    item = _string(payload.get("item"), "item", max_length=128)
    role = _string(payload.get("role"), "role", max_length=32).lower()
    if role not in {"controller", "planner", "reviewer", "worker"}:
        raise WorkflowContractError("role must be controller, planner, reviewer, or worker")

    current = _string(payload.get("currentLevel"), "currentLevel", max_length=32).lower()
    if current not in EFFORT_LEVELS:
        raise WorkflowContractError(f"currentLevel must be one of {', '.join(EFFORT_LEVELS)}")

    failure_class = _string(payload.get("failureClass"), "failureClass", max_length=64).lower()
    if failure_class not in FAILURE_CLASSES:
        raise WorkflowContractError(
            f"failureClass must be one of {', '.join(sorted(FAILURE_CLASSES))}"
        )

    escalation_count = _optional_integer(payload, "escalationCount", 0, 0, 3)
    max_escalations = _optional_integer(payload, "maxEscalations", 1, 0, 3)
    context_expansion_used = _optional_bool(payload, "contextExpansionUsed", False)

    if failure_class in {"environment", "tooling"}:
        return EscalationDecision(
            item, role, failure_class, current, "REMEDIATE_SAME_LEVEL",
            current, True, ("NON_CAPABILITY_FAILURE",),
        )

    if failure_class == "authority":
        return EscalationDecision(
            item, role, failure_class, current, "BLOCK_FOR_AUTHORITY",
            current, True, ("AUTHORITY_IS_NOT_MODEL_CAPABILITY",),
        )

    if failure_class == "missing-context" and not context_expansion_used:
        return EscalationDecision(
            item, role, failure_class, current, "EXPAND_CONTEXT",
            current, True, ("BOUNDED_CONTEXT_FIRST",),
        )

    if current == EFFORT_LEVELS[-1] or escalation_count >= max_escalations:
        return EscalationDecision(
            item, role, failure_class, current, "REPLAN",
            current, True, ("ESCALATION_BUDGET_EXHAUSTED",),
        )

    next_level = EFFORT_LEVELS[EFFORT_LEVELS.index(current) + 1]
    return EscalationDecision(
        item, role, failure_class, current, "ESCALATE_ONE_LEVEL",
        next_level, True, ("CAPABILITY_FAILURE", "TEMPORARY_ITEM_SCOPE"),
    )


def validate_budget(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise WorkflowContractError("contextBudget must be an object")
    max_bytes = _integer(value.get("maxBytes"), "contextBudget.maxBytes", 1024, MAX_CONTEXT_BYTES)
    max_files = _integer(value.get("maxFiles"), "contextBudget.maxFiles", 1, MAX_CONTEXT_FILES)
    max_tools = _integer(value.get("maxToolCalls"), "contextBudget.maxToolCalls", 1, MAX_TOOL_CALLS)
    allow_expansion = _bool(value.get("allowExpansion"), "contextBudget.allowExpansion")
    return {
        "maxBytes": max_bytes,
        "maxFiles": max_files,
        "maxToolCalls": max_tools,
        "allowExpansion": allow_expansion,
    }


def validate_work_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    _version(payload)
    normalized: dict[str, Any] = {
        "version": WORKFLOW_CONTRACT_VERSION,
        "item": _string(payload.get("item"), "item", max_length=128),
        "workset": _string(payload.get("workset"), "workset", max_length=128),
        "task": _string(payload.get("task"), "task", max_length=128),
        "objective": _string(payload.get("objective"), "objective"),
        "dependencies": _strings(payload.get("dependencies"), "dependencies"),
        "decisions": _strings(payload.get("decisions"), "decisions"),
        "acceptanceCriteria": _strings(payload.get("acceptanceCriteria"), "acceptanceCriteria"),
        "requiredCapabilities": _strings(payload.get("requiredCapabilities"), "requiredCapabilities"),
        "exclusiveScopes": _strings(payload.get("exclusiveScopes"), "exclusiveScopes"),
        "relevantRules": _strings(payload.get("relevantRules"), "relevantRules"),
        "primaryFiles": _strings(payload.get("primaryFiles"), "primaryFiles"),
        "doNotTouch": _strings(payload.get("doNotTouch"), "doNotTouch"),
        "requiredValidation": _strings(payload.get("requiredValidation"), "requiredValidation"),
        "riskFlags": _strings(payload.get("riskFlags", []), "riskFlags", maximum=64),
        "contextBudget": validate_budget(payload.get("contextBudget")),
    }
    unknown = sorted(set(normalized["riskFlags"]) - RISK_FLAGS)
    if unknown:
        raise WorkflowContractError(f"Unknown riskFlags: {', '.join(unknown)}")
    for required_nonempty in ("acceptanceCriteria", "exclusiveScopes", "requiredValidation"):
        if not normalized[required_nonempty]:
            raise WorkflowContractError(f"{required_nonempty} must not be empty")
    return normalized


def validate_handoff(payload: Mapping[str, Any]) -> dict[str, Any]:
    _version(payload)
    outcome = _string(payload.get("outcome"), "outcome", max_length=32)
    if outcome not in {"DONE", "BLOCKED", "RELEASED"}:
        raise WorkflowContractError("outcome must be DONE, BLOCKED, or RELEASED")
    claim_state = _string(payload.get("claimState"), "claimState", max_length=32)
    expected_claim_state = {"DONE": "completed", "BLOCKED": "blocked", "RELEASED": "released"}[outcome]
    if claim_state != expected_claim_state:
        raise WorkflowContractError(
            f"claimState must be {expected_claim_state!r} for outcome {outcome}"
        )
    validation = payload.get("validation")
    if not isinstance(validation, list) or not validation:
        raise WorkflowContractError("validation must be a non-empty list")
    normalized_validation: list[dict[str, str]] = []
    for index, entry in enumerate(validation):
        if not isinstance(entry, Mapping):
            raise WorkflowContractError(f"validation[{index}] must be an object")
        result = _string(entry.get("result"), f"validation[{index}].result", max_length=32)
        if result not in {"PASS", "FIXED", "BLOCKED", "FAIL", "NOT_RUN"}:
            raise WorkflowContractError(f"validation[{index}].result is invalid")
        normalized_validation.append(
            {
                "check": _string(entry.get("check"), f"validation[{index}].check"),
                "result": result,
            }
        )
    if outcome == "DONE" and any(
        entry["result"] in {"BLOCKED", "FAIL", "NOT_RUN"}
        for entry in normalized_validation
    ):
        raise WorkflowContractError("DONE handoff cannot contain blocking validation results")
    fingerprint = _string(payload.get("evidenceFingerprint"), "evidenceFingerprint", max_length=128)
    if len(fingerprint) != 64 or any(ch not in "0123456789abcdef" for ch in fingerprint):
        raise WorkflowContractError("evidenceFingerprint must be lowercase SHA-256")
    return {
        "version": WORKFLOW_CONTRACT_VERSION,
        "item": _string(payload.get("item"), "item", max_length=128),
        "outcome": outcome,
        "changed": _strings(payload.get("changed"), "changed"),
        "validation": normalized_validation,
        "acCoverage": _strings(payload.get("acCoverage"), "acCoverage"),
        "artifactRefs": _strings(payload.get("artifactRefs", []), "artifactRefs", maximum=64),
        "risks": _strings(payload.get("risks", []), "risks"),
        "followUp": payload.get("followUp") if payload.get("followUp") is None else _string(payload.get("followUp"), "followUp"),
        "claimState": claim_state,
        "evidenceFingerprint": fingerprint,
    }
