"""Operation-unit sketches for HeLL-Lite Phase 3.

These structures describe small Nagoya/LAL/HeLL-inspired construction units.
They are intentionally JSON-friendly and conservative: planning-only units are
marked as such, and no unit here is a full LMAO/Nagoya compiler primitive.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from . import ops


@dataclass(frozen=True)
class UnitCell:
    label: str
    address: int | None = None
    required_first_use_op: str = "NOP"
    required_cycle: list[str] | None = None
    source_byte: int | None = None
    comment: str = ""


@dataclass(frozen=True)
class RestorePlan:
    cells: list[str] = field(default_factory=list)
    restore_strategy: str = "none"
    fixup_labels: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass(frozen=True)
class OperationUnit:
    name: str
    intended_op: str
    required_instruction_cycle: list[str] | None = None
    code_labels: list[str] = field(default_factory=list)
    data_labels: list[str] = field(default_factory=list)
    entry_label: str = ""
    exit_label: str = ""
    cells: list[UnitCell] = field(default_factory=list)
    restore_plan: RestorePlan = field(default_factory=RestorePlan)
    executable_phase3: bool = False
    limitations: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class UnitCall:
    unit_name: str
    call_label: str
    input_labels: list[str] = field(default_factory=list)
    output_labels: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass(frozen=True)
class UnitSearchResult:
    unit_name: str
    address: int
    source_byte: int
    source_char: str
    expected_ops: list[str]
    actual_ops: list[str]
    matches: bool
    comments: list[str] = field(default_factory=list)


@dataclass
class UnitCatalog:
    units: list[OperationUnit] = field(default_factory=list)

    def add_unit(self, unit: OperationUnit) -> None:
        self.units.append(unit)

    def list_units(self) -> list[str]:
        return [unit.name for unit in self.units]

    def validate(self) -> dict[str, object]:
        errors: list[str] = []
        seen_names: set[str] = set()
        for unit in self.units:
            if unit.name in seen_names:
                errors.append(f"duplicate unit name {unit.name!r}")
            seen_names.add(unit.name)
            _validate_op_name(unit.intended_op, errors, f"{unit.name}.intended_op")
            if unit.required_instruction_cycle is not None:
                for name in unit.required_instruction_cycle:
                    _validate_op_name(name, errors, f"{unit.name}.required_instruction_cycle")
            cell_labels: set[str] = set()
            for cell in unit.cells:
                if cell.label in cell_labels:
                    errors.append(f"{unit.name}: duplicate cell label {cell.label!r}")
                cell_labels.add(cell.label)
                _validate_op_name(cell.required_first_use_op, errors, f"{unit.name}.{cell.label}")
                if cell.required_cycle is not None:
                    for name in cell.required_cycle:
                        _validate_op_name(name, errors, f"{unit.name}.{cell.label}.cycle")
                if cell.address is not None and not 0 <= cell.address < ops.MEMORY_CELLS:
                    errors.append(f"{unit.name}.{cell.label}: address out of range")
                if cell.source_byte is not None and not ops.is_printable_byte(cell.source_byte):
                    errors.append(f"{unit.name}.{cell.label}: source_byte is not printable")
            for label_name, value in (("entry_label", unit.entry_label), ("exit_label", unit.exit_label)):
                if value and value not in cell_labels:
                    errors.append(f"{unit.name}: {label_name} {value!r} is not a cell label")
        return {"valid": not errors, "errors": errors, "unit_count": len(self.units)}

    def to_dict(self) -> dict[str, object]:
        return {"units": [asdict(unit) for unit in self.units], "validation": self.validate()}

    def canonical_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def _validate_op_name(name: str, errors: list[str], context: str) -> None:
    try:
        ops.parse_op_name(name)
    except ValueError:
        # Phase 3 also uses a few high-level placeholders that are not classic
        # opcodes. Keep them explicit and non-executable.
        if name not in {
            "INPUT",
            "OUTPUT",
            "MOV",
            "BRANCH",
            "BRANCH_PLACEHOLDER",
            "ROUTE",
            "STOP",
        }:
            errors.append(f"{context}: invalid op name {name!r}")


def built_in_catalog() -> UnitCatalog:
    catalog = UnitCatalog()
    catalog.add_unit(
        OperationUnit(
            name="linear_input_unit",
            intended_op="IN",
            code_labels=["input_op"],
            entry_label="input_op",
            exit_label="input_op",
            cells=[UnitCell(label="input_op", required_first_use_op="IN")],
            executable_phase3=True,
            limitations=["Only first-use straight-line placement is supported."],
        )
    )
    catalog.add_unit(
        OperationUnit(
            name="linear_output_unit",
            intended_op="OUT",
            code_labels=["output_op"],
            entry_label="output_op",
            exit_label="output_op",
            cells=[UnitCell(label="output_op", required_first_use_op="OUT")],
            executable_phase3=True,
            limitations=["Does not synthesize the value in A."],
        )
    )
    catalog.add_unit(
        OperationUnit(
            name="linear_halt_unit",
            intended_op="HALT",
            code_labels=["halt_op"],
            entry_label="halt_op",
            exit_label="halt_op",
            cells=[UnitCell(label="halt_op", required_first_use_op="HALT")],
            executable_phase3=True,
            limitations=["Only terminates a straight-line sketch."],
        )
    )
    catalog.add_unit(
        OperationUnit(
            name="movd_probe_unit",
            intended_op="MOVD",
            required_instruction_cycle=["MOVD", "NOP"],
            code_labels=["movd_probe"],
            data_labels=["d_target"],
            entry_label="movd_probe",
            exit_label="movd_probe",
            cells=[UnitCell(label="movd_probe", required_first_use_op="MOVD", required_cycle=["MOVD", "NOP"])],
            restore_plan=RestorePlan(
                cells=["movd_probe"],
                restore_strategy="planning_required",
                notes="Repeated use needs cycle-compatible placement or restore/fixup.",
            ),
            executable_phase3=False,
            limitations=["Cycle placement is discoverable, but no restore jump is compiled yet."],
        )
    )
    catalog.add_unit(
        OperationUnit(
            name="jump_probe_unit",
            intended_op="JUMP",
            required_instruction_cycle=["JUMP", "NOP"],
            code_labels=["jump_op"],
            data_labels=["target_minus_one"],
            entry_label="jump_op",
            exit_label="target_minus_one",
            cells=[
                UnitCell(label="jump_op", required_first_use_op="JUMP", required_cycle=["JUMP", "NOP"]),
                UnitCell(
                    label="target_minus_one",
                    required_first_use_op="NOP",
                    comment="Planning cell expected to hold the jump destination minus one.",
                ),
            ],
            restore_plan=RestorePlan(
                cells=["jump_op", "target_minus_one"],
                restore_strategy="planning_required",
                notes="JUMP target cells and post-encipher restoration are not compiled in Phase 3.",
            ),
            executable_phase3=False,
            limitations=["Planning only; does not synthesize target-minus-one data cells."],
        )
    )
    catalog.add_unit(
        OperationUnit(
            name="branch_placeholder_unit",
            intended_op="BRANCH_PLACEHOLDER",
            code_labels=["route"],
            data_labels=["arm_a", "arm_b"],
            entry_label="route",
            exit_label="route",
            cells=[UnitCell(label="route", required_first_use_op="JUMP", comment="Conceptual route cell.")],
            restore_plan=RestorePlan(
                cells=["route"],
                restore_strategy="not_implemented",
                notes="Branch-on-read and table routing are still planning-only.",
            ),
            executable_phase3=False,
            limitations=["No branch-on-read compiler or table router yet."],
        )
    )
    return catalog
