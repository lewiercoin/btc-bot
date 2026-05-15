from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HYPOTHESIS_CLASSES = {
    "entry_filter",
    "exit_filter",
    "timing_overlay",
    "multi_asset_transfer",
    "timeframe_feasibility",
    "regime_label",
    "diagnostic_only",
    "parameter_refinement",
}
HYPOTHESIS_STATUSES = {"DRAFT", "APPROVED", "ACTIVE", "CLOSED", "REJECTED"}
PROGRAM_STATUSES = {"ACTIVE", "PAUSED", "CLOSED"}
EXECUTABLE_FIELD_NAMES = {
    "python_code",
    "code",
    "module_path",
    "function_name",
    "import",
    "eval",
    "exec",
    "shell_command",
}


@dataclass(frozen=True)
class ResearchProgram:
    research_program_id: str
    title: str
    objective: str
    constraints: tuple[str, ...]
    allowed_data: tuple[str, ...]
    allowed_hypothesis_classes: tuple[str, ...]
    disallowed_actions: tuple[str, ...]
    baseline_reference: str
    validation_protocol: str
    owner: str
    builder: str
    auditor: str
    status: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ResearchProgram":
        required = {
            "research_program_id",
            "title",
            "objective",
            "constraints",
            "allowed_data",
            "allowed_hypothesis_classes",
            "disallowed_actions",
            "baseline_reference",
            "validation_protocol",
            "owner",
            "builder",
            "auditor",
            "status",
        }
        _ensure_required(payload, required)
        if payload["status"] not in PROGRAM_STATUSES:
            raise ValueError(f"Invalid research program status: {payload['status']}")
        invalid_classes = set(payload["allowed_hypothesis_classes"]) - HYPOTHESIS_CLASSES
        if invalid_classes:
            raise ValueError(f"Invalid allowed hypothesis classes: {sorted(invalid_classes)}")
        return cls(
            research_program_id=str(payload["research_program_id"]),
            title=str(payload["title"]),
            objective=str(payload["objective"]),
            constraints=tuple(str(v) for v in payload["constraints"]),
            allowed_data=tuple(str(v) for v in payload["allowed_data"]),
            allowed_hypothesis_classes=tuple(str(v) for v in payload["allowed_hypothesis_classes"]),
            disallowed_actions=tuple(str(v) for v in payload["disallowed_actions"]),
            baseline_reference=str(payload["baseline_reference"]),
            validation_protocol=str(payload["validation_protocol"]),
            owner=str(payload["owner"]),
            builder=str(payload["builder"]),
            auditor=str(payload["auditor"]),
            status=str(payload["status"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "research_program_id": self.research_program_id,
            "title": self.title,
            "objective": self.objective,
            "constraints": list(self.constraints),
            "allowed_data": list(self.allowed_data),
            "allowed_hypothesis_classes": list(self.allowed_hypothesis_classes),
            "disallowed_actions": list(self.disallowed_actions),
            "baseline_reference": self.baseline_reference,
            "validation_protocol": self.validation_protocol,
            "owner": self.owner,
            "builder": self.builder,
            "auditor": self.auditor,
            "status": self.status,
        }


@dataclass(frozen=True)
class HypothesisSpec:
    hypothesis_id: str
    name: str
    hypothesis_class: str
    edge_rationale: str
    counterparty_or_market_mechanism: str
    required_data: tuple[str, ...]
    timeframes: tuple[str, ...]
    baseline_reference: str
    variables: tuple[dict[str, Any], ...]
    frozen_assumptions: tuple[str, ...]
    expected_observation: str
    acceptance_criteria: dict[str, Any]
    kill_criteria: dict[str, Any]
    failure_modes: tuple[str, ...]
    out_of_scope: tuple[str, ...]
    author: str
    created_at: str
    status: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "HypothesisSpec":
        validate_hypothesis_spec(payload)
        return cls(
            hypothesis_id=str(payload["hypothesis_id"]),
            name=str(payload["name"]),
            hypothesis_class=str(payload["class"]),
            edge_rationale=str(payload["edge_rationale"]),
            counterparty_or_market_mechanism=str(payload["counterparty_or_market_mechanism"]),
            required_data=tuple(str(v) for v in payload["required_data"]),
            timeframes=tuple(str(v) for v in payload["timeframe"]),
            baseline_reference=str(payload["baseline_reference"]),
            variables=tuple(dict(v) for v in payload["variables"]),
            frozen_assumptions=tuple(str(v) for v in payload["frozen_assumptions"]),
            expected_observation=str(payload["expected_observation"]),
            acceptance_criteria=dict(payload["acceptance_criteria"]),
            kill_criteria=dict(payload["kill_criteria"]),
            failure_modes=tuple(str(v) for v in payload["failure_modes"]),
            out_of_scope=tuple(str(v) for v in payload["out_of_scope"]),
            author=str(payload["author"]),
            created_at=str(payload["created_at"]),
            status=str(payload["status"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "name": self.name,
            "class": self.hypothesis_class,
            "edge_rationale": self.edge_rationale,
            "counterparty_or_market_mechanism": self.counterparty_or_market_mechanism,
            "required_data": list(self.required_data),
            "timeframe": list(self.timeframes),
            "baseline_reference": self.baseline_reference,
            "variables": [dict(v) for v in self.variables],
            "frozen_assumptions": list(self.frozen_assumptions),
            "expected_observation": self.expected_observation,
            "acceptance_criteria": dict(self.acceptance_criteria),
            "kill_criteria": dict(self.kill_criteria),
            "failure_modes": list(self.failure_modes),
            "out_of_scope": list(self.out_of_scope),
            "author": self.author,
            "created_at": self.created_at,
            "status": self.status,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_hypothesis_spec(path: Path) -> HypothesisSpec:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return HypothesisSpec.from_dict(payload)


def validate_hypothesis_spec(payload: dict[str, Any]) -> None:
    required = {
        "hypothesis_id",
        "name",
        "class",
        "edge_rationale",
        "counterparty_or_market_mechanism",
        "required_data",
        "timeframe",
        "baseline_reference",
        "variables",
        "frozen_assumptions",
        "expected_observation",
        "acceptance_criteria",
        "kill_criteria",
        "failure_modes",
        "out_of_scope",
        "author",
        "created_at",
        "status",
    }
    _ensure_required(payload, required)
    _reject_executable_fields(payload)
    if payload["class"] not in HYPOTHESIS_CLASSES:
        raise ValueError(f"Invalid hypothesis class: {payload['class']}")
    if payload["status"] not in HYPOTHESIS_STATUSES:
        raise ValueError(f"Invalid hypothesis status: {payload['status']}")
    for field in ("required_data", "timeframe", "variables", "frozen_assumptions", "failure_modes", "out_of_scope"):
        if not isinstance(payload[field], list):
            raise ValueError(f"Field {field} must be a list")
    for field in ("acceptance_criteria", "kill_criteria"):
        if not isinstance(payload[field], dict):
            raise ValueError(f"Field {field} must be an object")


def _ensure_required(payload: dict[str, Any], required: set[str]) -> None:
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"Missing required fields: {missing}")


def _reject_executable_fields(value: Any, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).lower() in EXECUTABLE_FIELD_NAMES:
                raise ValueError(f"Executable field is not allowed at {path}.{key}")
            _reject_executable_fields(nested, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_executable_fields(nested, path=f"{path}[{index}]")
