"""Bounded source-valid local patch enumeration.

This is a surgical diagnostic tool. It scores local byte edits against an
extracted finite map with the Python VM and never edits match artifacts.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from . import ops, score, source

DIAGNOSTIC_SCORE_BUDGET = 100


@dataclass(frozen=True)
class PatchSite:
    address: int
    current_byte: int
    allowed_bytes: list[int]
    role: str
    reason_selected: str
    risk_level: str


@dataclass(frozen=True)
class PatchCandidate:
    edits: list[dict[str, int | str]]
    source_text: str
    preserves_count: int
    add_count: int
    visible_pass: bool
    notes: list[str]


def patch_enum(
    candidate: str | Path,
    map_path: str | Path,
    route_report: str | Path,
    target: str | None = None,
    target_index: int | None = None,
    out_dir: str | Path | None = None,
    max_sites: int = 12,
    max_edits: int = 2,
    max_candidates: int = 50000,
    allow_regression: bool = False,
    write_top: int = 3,
) -> dict[str, object]:
    if max_sites < 1:
        raise ValueError("max_sites must be positive")
    if max_edits < 1:
        raise ValueError("max_edits must be positive")
    if max_candidates < 1:
        raise ValueError("max_candidates must be positive")
    program = source.canonical_source_bytes(Path(candidate).read_bytes())
    source_ok, source_reason = source.validate_source(program, max_len=4096)
    extracted = json.loads(Path(map_path).read_text())
    route = json.loads(Path(route_report).read_text())
    preserve_pairs = _pairs_from_map(extracted, "passed_pairs")
    add_pairs = [_select_target(extracted, target, target_index)]
    sites = _sites_from_route(route, program, max_sites=max_sites)
    warnings = [
        "Python diagnostic VM only; official MAL-51 evidence requires Rust runner/sweep reports.",
        "Patch enumeration is bounded and local; no local patch may exist.",
    ]
    effective_budget = min(max_candidates, DIAGNOSTIC_SCORE_BUDGET)
    if effective_budget < max_candidates:
        warnings.append(
            f"diagnostic score budget limited this run to {effective_budget} scored candidates "
            f"inside the user cap of {max_candidates}"
        )
    candidates_tested = 0
    best: list[dict[str, object]] = []
    failure_reason = ""
    seed_score = _score_program(program, preserve_pairs, add_pairs) if source_ok else None
    if not source_ok:
        compile_status = "failed_constraints"
        failure_reason = source_reason
    elif seed_score and seed_score["preserves_count"] == len(preserve_pairs) and seed_score["add_count"] == len(add_pairs):
        compile_status = "diagnostic_candidate"
        best.append(
            {
                "edits": [],
                "preserves_count": seed_score["preserves_count"],
                "add_count": seed_score["add_count"],
                "visible_pass": seed_score["visible_pass"],
                "source_text": source.source_text(program),
                "notes": ["seed candidate already satisfies preserve and add constraints"],
            }
        )
    elif not sites:
        compile_status = "planning_only"
        failure_reason = "route report did not provide patchable source-valid sites"
        if seed_score is not None:
            best.append(
                {
                    "edits": [],
                    "preserves_count": seed_score["preserves_count"],
                    "add_count": seed_score["add_count"],
                    "visible_pass": seed_score["visible_pass"],
                    "source_text": source.source_text(program),
                    "notes": ["seed candidate baseline; no patchable sites"],
                }
            )
    else:
        compile_status = "planning_only"
        if seed_score is not None:
            best.append(
                {
                    "edits": [],
                    "preserves_count": seed_score["preserves_count"],
                    "add_count": seed_score["add_count"],
                    "visible_pass": seed_score["visible_pass"],
                    "source_text": source.source_text(program),
                    "notes": ["seed candidate baseline"],
                }
            )
        for edit_count in range(1, max_edits + 1):
            for site_group in itertools.combinations(sites, edit_count):
                for replacement_group in itertools.product(*(site.allowed_bytes for site in site_group)):
                    if candidates_tested >= effective_budget:
                        failure_reason = "diagnostic_score_budget reached"
                        break
                    candidates_tested += 1
                    patched = bytearray(program)
                    edits = []
                    for site, new_byte in zip(site_group, replacement_group):
                        patched[site.address] = new_byte
                        edits.append(
                            {
                                "address": site.address,
                                "old_byte": site.current_byte,
                                "new_byte": new_byte,
                                "old_char": chr(site.current_byte),
                                "new_char": chr(new_byte),
                            }
                        )
                    patched_bytes = bytes(patched)
                    ok, reason = source.validate_source(patched_bytes, max_len=4096)
                    if not ok:
                        continue
                    add_rows = _score_pairs(patched_bytes, add_pairs)
                    add_count = sum(1 for row in add_rows if row["correct"])
                    if add_count < len(add_pairs):
                        continue
                    candidate_score = _score_program(patched_bytes, preserve_pairs, add_pairs)
                    if not allow_regression and candidate_score["preserves_count"] < len(preserve_pairs):
                        continue
                    item = {
                        "edits": edits,
                        "preserves_count": candidate_score["preserves_count"],
                        "add_count": candidate_score["add_count"],
                        "visible_pass": candidate_score["visible_pass"],
                        "source_text": source.source_text(patched_bytes),
                        "notes": [reason],
                    }
                    best.append(item)
                    best.sort(key=lambda row: (-int(row["add_count"]), -int(row["preserves_count"]), len(row["edits"])))
                    best = best[: max(write_top, 1)]
                    if candidate_score["preserves_count"] == len(preserve_pairs) and candidate_score["add_count"] == len(add_pairs):
                        compile_status = "diagnostic_candidate"
                if failure_reason:
                    break
            if failure_reason:
                break
    report = {
        "seed_candidate": str(candidate),
        "preserve_pairs": preserve_pairs,
        "add_pairs": add_pairs,
        "sites_considered": [asdict(site) for site in sites],
        "candidates_tested": candidates_tested,
        "best_candidates": best,
        "compile_status": compile_status,
        "failure_reason": failure_reason,
        "warnings": warnings,
        "allow_regression": allow_regression,
        "max_candidates": max_candidates,
        "effective_candidate_budget": effective_budget,
    }
    if out_dir is not None:
        write_patch_outputs(report, out_dir)
    return report


def write_patch_outputs(report: dict[str, object], out_dir: str | Path) -> None:
    out = Path(out_dir)
    candidates_dir = out / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    (out / "patch-search-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (out / "patch-search-report.md").write_text(_markdown(report))
    best = report.get("best_candidates", [])
    if isinstance(best, list) and best:
        preserve = max(best, key=lambda row: int(row.get("preserves_count", 0)))
        add = max(best, key=lambda row: int(row.get("add_count", 0)))
        overall = max(best, key=lambda row: (int(row.get("add_count", 0)), int(row.get("preserves_count", 0))))
        _write_candidate(candidates_dir / "best-preserve.mal", preserve)
        _write_candidate(candidates_dir / "best-add-target.mal", add)
        _write_candidate(candidates_dir / "best-overall.mal", overall)


def _write_candidate(path: Path, row: object) -> None:
    if isinstance(row, dict) and isinstance(row.get("source_text"), str):
        path.write_text(str(row["source_text"]) + "\n")


def _sites_from_route(route: dict[str, Any], program: bytes, max_sites: int) -> list[PatchSite]:
    comparison = route.get("comparison", {})
    raw_sites = comparison.get("patchable_cells", []) if isinstance(comparison, dict) else []
    sites = []
    for item in raw_sites:
        if not isinstance(item, dict):
            continue
        address = int(item.get("address", -1))
        if address < 0 or address >= len(program):
            continue
        current = int(item.get("current_byte", program[address]))
        allowed = [int(byte) for byte in item.get("allowed_bytes", []) if int(byte) != current]
        allowed = [byte for byte in allowed if byte in ops.source_valid_bytes(address)]
        if not allowed:
            continue
        sites.append(
            PatchSite(
                address=address,
                current_byte=current,
                allowed_bytes=allowed,
                role=str(item.get("role", "unknown")),
                reason_selected=str(item.get("reason_selected", "")),
                risk_level=str(item.get("risk_level", "unknown")),
            )
        )
    sites.sort(key=lambda site: (site.risk_level == "high", site.address))
    return sites[:max_sites]


def _score_program(program: bytes, preserve_pairs: list[dict[str, str]], add_pairs: list[dict[str, str]]) -> dict[str, object]:
    preserve_rows = _score_pairs(program, preserve_pairs)
    add_rows = _score_pairs(program, add_pairs)
    visible_rows = [row for row in preserve_rows if row["input_hex"] == "82"]
    return {
        "preserves_count": sum(1 for row in preserve_rows if row["correct"]),
        "add_count": sum(1 for row in add_rows if row["correct"]),
        "visible_pass": bool(visible_rows and visible_rows[0]["correct"]),
    }


def _score_pairs(program: bytes, pairs: list[dict[str, str]]) -> list[dict[str, object]]:
    rows = []
    for pair in pairs:
        result = score.execute_python(program, bytes.fromhex(pair["input_hex"]), max_output_len=1)
        actual = None if not result.output else f"{result.output[0]:02x}"
        rows.append(
            {
                "input_hex": pair["input_hex"],
                "expected_hex": pair["expected_hex"],
                "actual_hex": actual,
                "correct": actual == pair["expected_hex"],
                "steps": result.steps,
                "status": result.status,
            }
        )
    return rows


def _pairs_from_map(extracted: dict[str, Any], key: str) -> list[dict[str, str]]:
    rows = []
    for item in extracted.get(key, []):
        if item.get("input_hex") and item.get("expected_hex"):
            rows.append({"input_hex": str(item["input_hex"]), "expected_hex": str(item["expected_hex"])})
    return rows


def _select_target(extracted: dict[str, Any], target: str | None, target_index: int | None) -> dict[str, str]:
    failed = _pairs_from_map(extracted, "failed_pairs")
    if target_index is not None:
        if target_index < 0 or target_index >= len(failed):
            raise ValueError(f"target index {target_index} out of range for {len(failed)} failed pairs")
        return failed[target_index]
    if target:
        prefix, expected = _parse_target(target)
        for pair in failed + _pairs_from_map(extracted, "blocks3_pairs"):
            if pair["input_hex"].startswith(prefix) and pair["expected_hex"] == expected:
                return pair
        return {"input_hex": prefix, "expected_hex": expected}
    if not failed:
        raise ValueError("extracted map has no failed pairs; provide --target")
    return failed[0]


def _parse_target(text: str) -> tuple[str, str]:
    if ":" not in text:
        raise ValueError("target must be input_hex:expected_hex")
    left, right = text.split(":", 1)
    return (_normalize_hex(left), _normalize_hex(right))


def _normalize_hex(text: str) -> str:
    text = text.strip().lower().removeprefix("0x")
    if len(text) % 2 == 1:
        text = "0" + text
    bytes.fromhex(text)
    return text


def _markdown(report: dict[str, object]) -> str:
    lines = [
        "# Patch Search Report",
        "",
        "Diagnostic Python VM only; this is not official MAL-51 evidence.",
        "",
        f"- compile_status: `{report.get('compile_status')}`",
        f"- candidates tested: `{report.get('candidates_tested')}`",
        f"- sites considered: `{len(report.get('sites_considered', []))}`",
        f"- best candidates: `{len(report.get('best_candidates', []))}`",
        f"- failure reason: `{report.get('failure_reason')}`",
        "",
        "## Warnings",
        "",
    ]
    lines.extend(f"- {item}" for item in report.get("warnings", []))
    return "\n".join(lines) + "\n"
