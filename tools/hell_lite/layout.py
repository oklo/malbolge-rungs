"""Tiny label/layout IR for HeLL-Lite Phase 2."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import ops, score, source

VALID_SECTIONS = {"CODE", "DATA", "TAIL", "NOTES", "META"}


@dataclass(frozen=True)
class CycleSpec:
    ops: list[str]
    visits: int
    verified_address: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CycleSpec":
        return cls(
            ops=[str(item).upper() for item in data.get("ops", [])],
            visits=int(data.get("visits", len(data.get("ops", [])))),
            verified_address=data.get("verified_address"),
        )


@dataclass(frozen=True)
class Label:
    name: str
    section: str


@dataclass(frozen=True)
class LabelRef:
    from_label: str
    to_label: str
    purpose: str = "reference"


@dataclass(frozen=True)
class Constraint:
    kind: str
    label: str | None = None
    refers_to: str | None = None
    comment: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Constraint":
        return cls(
            kind=str(data.get("kind", "")),
            label=data.get("label"),
            refers_to=data.get("refers_to"),
            comment=data.get("comment"),
        )


@dataclass(frozen=True)
class CodeCell:
    label: str
    op: str
    cycle: CycleSpec | None = None
    address_hint: int | None = None
    comment: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CodeCell":
        return cls(
            label=str(data["label"]),
            op=str(data["op"]).upper(),
            cycle=CycleSpec.from_dict(data["cycle"]) if data.get("cycle") else None,
            address_hint=data.get("address_hint"),
            comment=data.get("comment"),
        )


@dataclass(frozen=True)
class DataCell:
    label: str
    value: int | str
    source_valid_required: bool = False
    address_hint: int | None = None
    comment: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DataCell":
        return cls(
            label=str(data["label"]),
            value=data["value"],
            source_valid_required=bool(data.get("source_valid_required", False)),
            address_hint=data.get("address_hint"),
            comment=data.get("comment"),
        )


@dataclass(frozen=True)
class Section:
    name: str
    kind: str
    code: list[CodeCell] = field(default_factory=list)
    data: list[DataCell] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Section":
        return cls(
            name=str(data["name"]),
            kind=str(data["kind"]).upper(),
            code=[CodeCell.from_dict(item) for item in data.get("code", [])],
            data=[DataCell.from_dict(item) for item in data.get("data", [])],
            notes=[str(item) for item in data.get("notes", [])],
        )


@dataclass(frozen=True)
class LayoutSketch:
    name: str
    sections: list[Section]
    target: dict[str, Any] | None = None
    constraints: list[Constraint] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LayoutSketch":
        return cls(
            name=str(data["name"]),
            sections=[Section.from_dict(item) for item in data.get("sections", [])],
            target=data.get("target"),
            constraints=[Constraint.from_dict(item) for item in data.get("constraints", [])],
            notes=[str(item) for item in data.get("notes", [])],
        )


@dataclass(frozen=True)
class LayoutReport:
    valid: bool
    errors: list[str]
    warnings: list[str]
    labels: list[str]
    unsupported_features: list[str]
    source: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def load_layout(path: str | Path) -> LayoutSketch:
    return LayoutSketch.from_dict(json.loads(Path(path).read_text()))


def layout_to_dict(sketch: LayoutSketch) -> dict[str, object]:
    return asdict(sketch)


def canonical_json(sketch: LayoutSketch) -> str:
    return json.dumps(layout_to_dict(sketch), indent=2, sort_keys=True) + "\n"


def save_layout(sketch: LayoutSketch, path: str | Path) -> None:
    Path(path).write_text(canonical_json(sketch))


def validate_layout(sketch: LayoutSketch) -> LayoutReport:
    errors: list[str] = []
    warnings: list[str] = []
    unsupported: list[str] = []
    labels: dict[str, str] = {}

    for section in sketch.sections:
        if section.kind not in VALID_SECTIONS:
            errors.append(f"invalid section kind {section.kind!r} in {section.name!r}")
        for cell in section.code:
            _register_label(labels, cell.label, section.kind, errors)
            _validate_address_hint(cell.address_hint, f"code cell {cell.label}", errors)
            try:
                ops.parse_op_name(cell.op)
            except ValueError as exc:
                errors.append(str(exc))
            if cell.cycle is not None:
                unsupported.append(f"cycle compilation for {cell.label} is not implemented in Phase 2")
                if cell.cycle.visits < 1:
                    errors.append(f"cycle visits for {cell.label} must be positive")
                for op_name in cell.cycle.ops:
                    try:
                        ops.parse_op_name(op_name)
                    except ValueError as exc:
                        errors.append(str(exc))
        for cell in section.data:
            _register_label(labels, cell.label, section.kind, errors)
            _validate_address_hint(cell.address_hint, f"data cell {cell.label}", errors)
            if isinstance(cell.value, int) and not 0 <= cell.value <= ops.WORD_MAX:
                errors.append(f"data cell {cell.label} value out of range: {cell.value}")
            if isinstance(cell.value, str) and cell.value.startswith("@"):
                ref = cell.value[1:]
                if ref not in labels:
                    warnings.append(f"data cell {cell.label} references unresolved label {ref!r}")

    for constraint in sketch.constraints:
        if constraint.label is not None and constraint.label not in labels:
            errors.append(f"constraint {constraint.kind!r} references unknown label {constraint.label!r}")
        if constraint.refers_to is not None and constraint.refers_to not in labels:
            errors.append(f"constraint {constraint.kind!r} refers to unknown label {constraint.refers_to!r}")

    return LayoutReport(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        labels=sorted(labels),
        unsupported_features=sorted(set(unsupported)),
    )


def compile_linear_layout(sketch: LayoutSketch) -> bytes:
    report = validate_layout(sketch)
    if not report.valid:
        raise ValueError("; ".join(report.errors))
    code_sections = [section for section in sketch.sections if section.kind == "CODE" and section.code]
    nonempty_data = [section for section in sketch.sections if section.data]
    if len(code_sections) != 1:
        raise NotImplementedError("Phase 2 compile-layout supports exactly one non-empty CODE section")
    if nonempty_data:
        raise NotImplementedError("Phase 2 compile-layout does not place DATA cells yet")
    code = code_sections[0].code
    if any(cell.cycle is not None for cell in code):
        raise NotImplementedError("Phase 2 compile-layout does not compile cycle specs yet")
    for address, cell in enumerate(code):
        if cell.address_hint is not None and cell.address_hint != address:
            raise NotImplementedError(
                f"Phase 2 linear compile cannot honor non-linear address hint "
                f"{cell.address_hint} on {cell.label}; expected {address}"
            )
    return source.compile_ops([ops.parse_op_name(cell.op) for cell in code])


def compile_layout_report(sketch: LayoutSketch) -> LayoutReport:
    report = validate_layout(sketch)
    if not report.valid:
        return report
    try:
        program = compile_linear_layout(sketch)
    except NotImplementedError as exc:
        return LayoutReport(
            valid=False,
            errors=[],
            warnings=report.warnings,
            labels=report.labels,
            unsupported_features=report.unsupported_features + [str(exc)],
        )
    return LayoutReport(
        valid=True,
        errors=[],
        warnings=report.warnings,
        labels=report.labels,
        unsupported_features=report.unsupported_features,
        source=source.source_text(program),
    )


def score_compiled_layout(sketch: LayoutSketch, target: str = "echo1", inputs: list[int] | None = None) -> score.ScoreResult:
    program = compile_linear_layout(sketch)
    return score.score_candidate(program, target, inputs or [0x61, 0xFF])


def _register_label(labels: dict[str, str], label: str, section_kind: str, errors: list[str]) -> None:
    if not label:
        errors.append("empty label is invalid")
    elif label in labels:
        errors.append(f"duplicate label {label!r}")
    else:
        labels[label] = section_kind


def _validate_address_hint(address: int | None, label: str, errors: list[str]) -> None:
    if address is None:
        return
    if not isinstance(address, int):
        errors.append(f"{label} address hint must be an integer")
    elif not 0 <= address < ops.MEMORY_CELLS:
        errors.append(f"{label} address hint out of range: {address}")
