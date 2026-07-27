"""Structured non-executable JUMP/loop planning reports."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class LoopSketchReport:
    kind: str
    compile_status: str
    intended_labels: list[str]
    intended_c_path: list[str]
    intended_d_path: list[str]
    target_minus_one_cells: list[str]
    enciphered_cells: list[str]
    restore_fixup_needed: list[str]
    unsupported_phase2_pieces: list[str]
    notes: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def loop_sketch(kind: str) -> LoopSketchReport:
    if kind == "input-output-loop":
        return LoopSketchReport(
            kind=kind,
            compile_status="not_implemented",
            intended_labels=["entry", "read_input", "write_output", "restore_jump", "halt"],
            intended_c_path=["entry", "read_input", "write_output", "restore_jump"],
            intended_d_path=["input_cell", "output_cell", "jump_target_cell"],
            target_minus_one_cells=["jump_target_cell"],
            enciphered_cells=["read_input", "write_output", "restore_jump"],
            restore_fixup_needed=["read_input", "write_output"],
            unsupported_phase2_pieces=[
                "cycle-aware address placement",
                "restore-cell synthesis",
                "D-pointer schedule solver",
                "jump target materialization",
            ],
            notes=["Planning artifact only; no runnable Malbolge is emitted."],
        )
    if kind == "two-value-branch-sketch":
        return LoopSketchReport(
            kind=kind,
            compile_status="not_implemented",
            intended_labels=["entry", "read_input", "test_case_a", "emit_a", "emit_b", "halt"],
            intended_c_path=["entry", "read_input", "test_case_a", "emit_a_or_b"],
            intended_d_path=["input_cell", "flag_cell", "target_a_minus_one", "target_b_minus_one"],
            target_minus_one_cells=["target_a_minus_one", "target_b_minus_one"],
            enciphered_cells=["read_input", "test_case_a", "emit_a", "emit_b"],
            restore_fixup_needed=["test_case_a", "emit_a", "emit_b"],
            unsupported_phase2_pieces=[
                "branch-on-read predicate synthesis",
                "flag-cell construction",
                "restore jumps after branch arms",
            ],
            notes=["Use this to enumerate constraints for a later layout solver."],
        )
    raise ValueError(f"unknown loop sketch kind {kind!r}")


def write_loop_sketch(report: LoopSketchReport, out: str | Path) -> None:
    Path(out).write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n")
