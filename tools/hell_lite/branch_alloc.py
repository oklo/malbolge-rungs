"""Bounded branch-allocation planning for finite MAL-51 maps.

This module is deliberately modest. It can score a seed candidate against a
file-backed map, classify preservation/add-target failures, and emit cycle and
D-as-PC planning metadata. It does not yet synthesize restore/fixup layouts.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import d_as_pc, patch_enum, route_surgeon, score, source, unit_search


@dataclass(frozen=True)
class BranchAllocationProblem:
    preserve_pairs: list[dict[str, str]]
    add_pairs: list[dict[str, str]]
    seed_candidate_path: str
    max_source_len: int = 4096
    objective_weights: dict[str, int] = field(default_factory=lambda: {"preserve": 100, "add": 10})
    constraints: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class BranchAllocationResult:
    compile_status: str
    candidate_source: str | None
    preserved_count: int
    added_count: int
    failed_pairs: list[dict[str, object]]
    collision_report: dict[str, object]
    poisoned_lanes: list[dict[str, object]]
    cycle_cells_used: list[dict[str, object]]
    plan: dict[str, object]
    notes: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def allocate_branch(
    map_path: str | Path,
    seed_candidate: str | Path,
    add_target: str,
    out_dir: str | Path | None = None,
    max_candidates: int = 50000,
    max_edit_sites: int = 16,
    max_branch_bodies: int = 128,
    allow_large_search: bool = False,
) -> dict[str, object]:
    if max_candidates < 1:
        raise ValueError("max_candidates must be positive")
    if max_candidates > 100000 and not allow_large_search:
        raise ValueError("max_candidates above 100000 requires allow_large_search")
    extracted = json.loads(Path(map_path).read_text())
    seed_candidate = Path(seed_candidate)
    program = source.canonical_source_bytes(seed_candidate.read_bytes())
    source_ok, source_reason = source.validate_source(program, max_len=4096)

    preserve_pairs = _pairs_from_map(extracted, "passed_pairs")
    add_pairs = _resolve_add_target(extracted, add_target)
    problem = BranchAllocationProblem(
        preserve_pairs=preserve_pairs,
        add_pairs=add_pairs,
        seed_candidate_path=str(seed_candidate),
        constraints={
            "max_candidates": max_candidates,
            "max_edit_sites": max_edit_sites,
            "max_branch_bodies": max_branch_bodies,
            "source_valid": source_ok,
            "source_valid_reason": source_reason,
            "diagnostic_vm": True,
        },
    )

    rows = _score_pairs(program, preserve_pairs + add_pairs) if source_ok else []
    preserve_rows = rows[: len(preserve_pairs)]
    add_rows = rows[len(preserve_pairs) :]
    preserved_count = sum(1 for row in preserve_rows if row["correct"])
    added_count = sum(1 for row in add_rows if row["correct"])
    failed_pairs = [row for row in rows if not row["correct"]]
    poisoned_lanes = [
        row
        for row in rows
        if isinstance(row.get("status"), str)
        and ("invalid" in str(row["status"]) or "output_limit" in str(row["status"]))
    ]

    cycle_cells = unit_search.find_unit_cells("NOP,MOVD", 0, min(1000, max(120, len(program) + 120)), max_results=8)
    collision_report = _collision_report(preserve_pairs + add_pairs)
    daspc = d_as_pc.d_as_pc_sketch("finite-map-sketch").to_dict()

    if not source_ok:
        compile_status = "failed_constraints"
        candidate_source = None
    elif preserved_count == len(preserve_pairs) and added_count == len(add_pairs):
        compile_status = "diagnostic_candidate"
        candidate_source = source.source_text(program)
    else:
        compile_status = "planning_only"
        candidate_source = None

    result = BranchAllocationResult(
        compile_status=compile_status,
        candidate_source=candidate_source,
        preserved_count=preserved_count,
        added_count=added_count,
        failed_pairs=failed_pairs,
        collision_report=collision_report,
        poisoned_lanes=poisoned_lanes,
        cycle_cells_used=cycle_cells,
        plan={
            "strategy": "seed_score_plus_landing_pad_plan",
            "problem": asdict(problem),
            "attempted_candidates": 1 if source_ok else 0,
            "d_as_pc": daspc,
            "next_missing_pieces": [
                "source-valid landing-pad edit synthesis",
                "input-conditioned route_ref_by_input compiler",
                "restore/fixup compiler for reusable JUMP and output cells",
                "full official-input scorer integrated into allocation search",
            ],
        },
        notes=[
            "Allocator is bounded and diagnostic; it does not submit match candidates.",
            "Known successes are scored as hard preservation constraints.",
            "planning_only means no executable improvement was produced.",
            "The native evaluator (malbolge-rungs verify) is the only ground truth.",
        ],
    )
    report = result.to_dict()
    if out_dir is not None:
        write_allocation_outputs(report, out_dir)
    return report


def write_allocation_outputs(report: dict[str, object], out_dir: str | Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "allocation-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (out / "plan.json").write_text(json.dumps(report["plan"], indent=2, sort_keys=True) + "\n")
    candidate = report.get("candidate_source")
    if isinstance(candidate, str):
        (out / "candidate.mal").write_text(candidate + "\n")


def repair_branch(
    map_path: str | Path,
    seed_candidate: str | Path,
    target: str | None = None,
    target_index: int | None = None,
    out_dir: str | Path | None = None,
    max_candidates: int = 50000,
    max_sites: int = 12,
    max_edits: int = 2,
) -> dict[str, object]:
    """Orchestrate route diagnosis plus bounded patch enumeration."""

    out = Path(out_dir) if out_dir is not None else None
    route_out = None if out is None else out / "route-surgeon"
    patch_out = None if out is None else out / "patch-enum"
    route_report = route_surgeon.route_surgeon(
        seed_candidate,
        map_path,
        target=target,
        target_index=target_index,
        max_ops=80,
        out_dir=route_out,
    )
    route_report_path = None
    if route_out is not None:
        route_report_path = route_out / "route-surgeon-report.json"
    else:
        tmp = Path("/tmp/hell-lite-repair-route-report.json")
        tmp.write_text(json.dumps(route_report, indent=2, sort_keys=True) + "\n")
        route_report_path = tmp
    patch_report = patch_enum.patch_enum(
        seed_candidate,
        map_path,
        route_report_path,
        target=target,
        target_index=target_index,
        out_dir=patch_out,
        max_sites=max_sites,
        max_edits=max_edits,
        max_candidates=max_candidates,
    )
    best_candidates = patch_report.get("best_candidates", [])
    candidate_produced = bool(best_candidates) and patch_report.get("compile_status") == "diagnostic_candidate"
    current_known_successes = len(json.loads(Path(map_path).read_text()).get("passed_pairs", []))
    result = {
        "compile_status": patch_report.get("compile_status"),
        "current_known_successes": current_known_successes,
        "target_failure": route_report.get("target"),
        "route_diagnosis": {
            "common_prefix_steps": route_report.get("comparison", {}).get("common_prefix_steps"),
            "patchable_cells": route_report.get("comparison", {}).get("patchable_cells"),
            "dangerous_cells": route_report.get("comparison", {}).get("dangerous_cells"),
            "suspected_collision_cells": route_report.get("comparison", {}).get("suspected_collision_cells"),
        },
        "patch_search_summary": {
            "candidates_tested": patch_report.get("candidates_tested"),
            "sites_considered": patch_report.get("sites_considered"),
            "best_candidates": [
                {
                    "edits": item.get("edits"),
                    "preserves_count": item.get("preserves_count"),
                    "add_count": item.get("add_count"),
                    "visible_pass": item.get("visible_pass"),
                }
                for item in best_candidates
                if isinstance(item, dict)
            ],
            "failure_reason": patch_report.get("failure_reason"),
        },
        "candidate_produced": candidate_produced,
        "known_successes_preserved": any(
            isinstance(item, dict) and item.get("preserves_count") == current_known_successes
            for item in best_candidates
        ),
        "add_target_achieved": any(isinstance(item, dict) and item.get("add_count") == 1 for item in best_candidates),
        "next_suggested_task": _next_repair_task(route_report, patch_report),
        "warning": "Python diagnostic VM only; the native evaluator (malbolge-rungs verify) is the only ground truth.",
    }
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        (out / "branch-repair-report.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        (out / "branch-repair-report.md").write_text(_repair_markdown(result))
    return result


def _next_repair_task(route_report: dict[str, object], patch_report: dict[str, object]) -> str:
    if patch_report.get("compile_status") == "diagnostic_candidate":
        return "Cross-check best candidate with Rust runner/sweep before any match use."
    comparison = route_report.get("comparison", {})
    patchable = comparison.get("patchable_cells", []) if isinstance(comparison, dict) else []
    if patch_report.get("failure_reason") == "max_candidates reached":
        return "Increase bounds only if the route diagnosis is still promising."
    if patchable:
        first = patchable[0]
        if isinstance(first, dict):
            if first.get("risk_level") == "high":
                return "Local patch sites are high-risk shared code; design a restore/fixup-aware landing-pad split."
            return f"Inspect landing-pad cell {first.get('address')} and design a restore/fixup-aware branch body."
    return "Develop a broader D-as-PC/layout allocator; local source-valid patch sites were insufficient."


def _repair_markdown(report: dict[str, object]) -> str:
    target = report.get("target_failure", {})
    lines = [
        "# Branch Repair Report",
        "",
        "Diagnostic Python VM only; not native evidence.",
        "",
        f"- compile_status: `{report.get('compile_status')}`",
        f"- target: `{target.get('input_hex')}` -> `{target.get('expected_hex')}`",
        f"- candidate produced: `{report.get('candidate_produced')}`",
        f"- known successes preserved: `{report.get('known_successes_preserved')}`",
        f"- add target achieved: `{report.get('add_target_achieved')}`",
        f"- next task: {report.get('next_suggested_task')}",
        "",
    ]
    return "\n".join(lines)


def _pairs_from_map(extracted: dict[str, Any], key: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in extracted.get(key, []):
        if not item.get("input_hex") or not item.get("expected_hex"):
            continue
        out.append(
            {
                "input_hex": str(item["input_hex"]),
                "expected_hex": str(item["expected_hex"]),
                "source": str(item.get("source_path", "")),
                "status": str(item.get("status", "")),
            }
        )
    return _dedupe_pair_dicts(out)


def _resolve_add_target(extracted: dict[str, Any], add_target: str) -> list[dict[str, str]]:
    target_input, target_expected = _parse_target(add_target)
    candidates = []
    for item in extracted.get("failed_pairs", []) + extracted.get("blocks3_pairs", []):
        input_hex = str(item.get("input_hex", ""))
        expected = str(item.get("expected_hex", ""))
        if input_hex.startswith(target_input) and expected == target_expected:
            candidates.append(
                {
                    "input_hex": input_hex,
                    "expected_hex": expected,
                    "source": str(item.get("source_path", "")),
                    "status": str(item.get("status", "")),
                }
            )
    if candidates:
        ranked = _dedupe_pair_dicts(sorted(candidates, key=lambda item: (-len(item["input_hex"]), item["source"])))
        return ranked[:1]
    return [{"input_hex": target_input, "expected_hex": target_expected, "source": "cli", "status": "requested"}]


def _score_pairs(program: bytes, pairs: list[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for pair in pairs:
        result = score.execute_python(program, bytes.fromhex(pair["input_hex"]), max_output_len=1)
        got = None if not result.output else f"{result.output[0]:02x}"
        rows.append(
            {
                "input_hex": pair["input_hex"],
                "expected_hex": pair["expected_hex"],
                "actual_hex": got,
                "correct": got == pair["expected_hex"],
                "status": result.status,
                "steps": result.steps,
                "source": pair.get("source", ""),
            }
        )
    return rows


def _collision_report(pairs: list[dict[str, str]]) -> dict[str, object]:
    by_first: dict[str, list[dict[str, str]]] = {}
    by_two: dict[str, list[dict[str, str]]] = {}
    for pair in pairs:
        input_hex = pair["input_hex"]
        by_first.setdefault(input_hex[:2], []).append(pair)
        by_two.setdefault(input_hex[:4], []).append(pair)
    collisions = {
        key: value
        for key, value in sorted(by_first.items())
        if len({item["expected_hex"] for item in value}) > 1 or len(value) > 1
    }
    return {
        "group_by_first_byte": {key: len(value) for key, value in sorted(by_first.items())},
        "group_by_first_two_bytes": {key: len(value) for key, value in sorted(by_two.items())},
        "first_byte_collisions": collisions,
        "notes": [
            "Full MAL-51 inputs can share a first byte but diverge on later bytes.",
            "A real allocator must decide whether a lane is private, colliding, or poisoned before editing.",
        ],
    }


def _parse_target(text: str) -> tuple[str, str]:
    if ":" not in text:
        raise ValueError("add target must be input_hex:expected_hex")
    left, right = text.split(":", 1)
    return (_normalize_hex(left), _normalize_hex(right))


def _normalize_hex(text: str) -> str:
    text = text.strip().lower().removeprefix("0x")
    if len(text) % 2 == 1:
        text = "0" + text
    bytes.fromhex(text)
    return text


def _dedupe_pair_dicts(pairs: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, str]] = []
    for pair in pairs:
        key = (pair["input_hex"], pair["expected_hex"])
        if key in seen:
            continue
        seen.add(key)
        out.append(pair)
    return out
