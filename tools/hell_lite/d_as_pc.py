"""D-as-PC planning sketches for HeLL-Lite Phase 3."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class PcCell:
    label: str
    role: str
    required_value: str | None = None
    comment: str = ""


@dataclass(frozen=True)
class PcTransition:
    from_label: str
    to_label: str
    via: str
    d_points_to: str
    c_jumps_to: str
    notes: str = ""


@dataclass(frozen=True)
class DAsPcProgram:
    name: str
    cells: list[PcCell]
    transitions: list[PcTransition]
    required_data_cells: list[str]
    target_minus_one_refs: list[str]
    stable_cycle_cells: list[str]
    restore_fixup_cells: list[str]
    compile_status: str
    missing_pieces: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DAsPcReport:
    kind: str
    program: DAsPcProgram
    notes: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def d_as_pc_sketch(kind: str) -> DAsPcReport:
    if kind == "input-output-stop":
        program = DAsPcProgram(
            name="input-output-stop",
            cells=[
                PcCell("input", "CODE", "IN", "Read first byte into A."),
                PcCell("output", "CODE", "OUT", "Emit A mod 256."),
                PcCell("stop", "CODE", "HALT", "Terminate."),
            ],
            transitions=[
                PcTransition("input", "output", "linear", "next code cell", "output"),
                PcTransition("output", "stop", "linear", "next code cell", "stop"),
            ],
            required_data_cells=[],
            target_minus_one_refs=[],
            stable_cycle_cells=[],
            restore_fixup_cells=[],
            compile_status="partially_compilable",
            missing_pieces=["Only straight-line first-use source is compiled today."],
        )
    elif kind == "two-value-branch":
        program = DAsPcProgram(
            name="two-value-branch",
            cells=[
                PcCell("input", "CODE", "IN"),
                PcCell("route", "CODE", "JUMP", "D must point to a target-minus-one cell."),
                PcCell("arm_a_output", "CODE", "OUT"),
                PcCell("arm_b_output", "CODE", "OUT"),
                PcCell("stop", "CODE", "HALT"),
                PcCell("arm_a_ref", "DATA", "arm_a_output - 1"),
                PcCell("arm_b_ref", "DATA", "arm_b_output - 1"),
            ],
            transitions=[
                PcTransition("input", "route", "computed", "route_ref_by_input", "route"),
                PcTransition("route", "arm_a_output", "JUMP", "arm_a_ref", "arm_a_output"),
                PcTransition("route", "arm_b_output", "JUMP", "arm_b_ref", "arm_b_output"),
                PcTransition("arm_a_output", "stop", "linear", "next code cell", "stop"),
                PcTransition("arm_b_output", "stop", "linear", "next code cell", "stop"),
            ],
            required_data_cells=["route_ref_by_input", "arm_a_ref", "arm_b_ref"],
            target_minus_one_refs=["arm_a_ref", "arm_b_ref"],
            stable_cycle_cells=["route"],
            restore_fixup_cells=["route", "arm_a_output", "arm_b_output"],
            compile_status="planning_only",
            missing_pieces=[
                "No compiler for input-conditioned route_ref_by_input yet.",
                "No restore/fixup placement for reusable JUMP/output cells yet.",
            ],
        )
    elif kind == "finite-map-sketch":
        program = DAsPcProgram(
            name="finite-map-sketch",
            cells=[
                PcCell("input", "CODE", "IN"),
                PcCell("route", "CODE", "JUMP"),
                PcCell("output_table", "DATA/CODE", "N output arms"),
                PcCell("stop", "CODE", "HALT"),
            ],
            transitions=[
                PcTransition("input", "route", "computed", "map[input]", "route"),
                PcTransition("route", "output_table", "JUMP", "target_minus_one_for_input", "selected output arm"),
            ],
            required_data_cells=["map[input]", "target_minus_one_for_each_arm"],
            target_minus_one_refs=["target_minus_one_for_each_arm"],
            stable_cycle_cells=["route", "output arms"],
            restore_fixup_cells=["route", "output arms", "map cells"],
            compile_status="planning_only",
            missing_pieces=[
                "No source-valid table allocator.",
                "No branch-on-read generator.",
                "No restore-jump compiler.",
            ],
        )
    else:
        raise ValueError(f"unknown D-as-PC sketch kind {kind!r}")
    return DAsPcReport(
        kind=kind,
        program=program,
        notes=[
            "D-as-PC sketches are planning artifacts unless compile_status says otherwise.",
            "Official MAL-51 evidence still requires Rust runner/sweep reports.",
        ],
    )


def write_report(report: DAsPcReport, path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True))
