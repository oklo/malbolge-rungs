"""Trace-guided route diagnosis for finite MAL-51 candidates.

This module uses the local Python diagnostic VM. It is for construction work,
not native evidence.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from . import init, ops, source


@dataclass(frozen=True)
class TracePoint:
    step: int
    c: int
    d: int
    a: int
    op_name: str
    mem_c_before: int
    mem_d_before: int
    output_so_far: str
    jump_target: int | None = None
    movd_target: int | None = None
    wrote_d: int | None = None


@dataclass(frozen=True)
class TraceSummary:
    input_hex: str
    expected_hex: str
    actual_hex: str | None
    correct: bool
    steps: int
    halted: bool
    first_output_step: int | None
    final_a: int
    final_c: int
    final_d: int
    trace_points: list[dict[str, object]]


def route_surgeon(
    candidate: str | Path,
    map_path: str | Path,
    target: str | None = None,
    target_index: int | None = None,
    max_ops: int = 80,
    out_dir: str | Path | None = None,
) -> dict[str, object]:
    program = source.canonical_source_bytes(Path(candidate).read_bytes())
    source_ok, source_reason = source.validate_source(program, max_len=4096)
    extracted = json.loads(Path(map_path).read_text())
    preserve_pairs = _pairs_from_map(extracted, "passed_pairs")
    failure_pair = _select_target(extracted, target, target_index)
    selected_successes = _select_successes(preserve_pairs, failure_pair, limit=6)
    pair_rows = selected_successes + [failure_pair]
    summaries = [_trace_summary(program, pair, max_ops=max_ops) for pair in pair_rows] if source_ok else []
    success_summaries = [item for item in summaries if item.correct]
    failure_summaries = [item for item in summaries if item.input_hex == failure_pair["input_hex"]]
    failure_summary = failure_summaries[0] if failure_summaries else None
    comparison = _compare_routes(str(candidate), success_summaries, failure_summary, program)
    report = {
        "candidate_path": str(candidate),
        "map_path": str(map_path),
        "max_ops": max_ops,
        "source_valid": source_ok,
        "source_valid_reason": source_reason,
        "target": failure_pair,
        "success_inputs": [item.input_hex for item in success_summaries],
        "failure_inputs": [failure_pair["input_hex"]],
        "traces": [asdict(item) for item in summaries],
        "comparison": comparison,
        "warning": "Python diagnostic VM only; the native evaluator (malbolge-rungs verify) is the only ground truth.",
    }
    if out_dir is not None:
        write_route_surgeon_outputs(report, out_dir)
    return report


def write_route_surgeon_outputs(report: dict[str, object], out_dir: str | Path) -> None:
    out = Path(out_dir)
    traces_dir = out / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)
    (out / "route-surgeon-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (out / "route-surgeon-report.md").write_text(_markdown(report))
    for trace in report.get("traces", []):
        if not isinstance(trace, dict):
            continue
        name = str(trace.get("input_hex", "input"))[:16]
        (traces_dir / f"{name}.json").write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n")


def _trace_summary(program: bytes, pair: dict[str, str], max_ops: int) -> TraceSummary:
    memory = init.initialize_memory(source.assert_valid_source(program))
    a = 0
    c = 0
    d = 0
    input_bytes = bytes.fromhex(pair["input_hex"])
    input_index = 0
    output: list[int] = []
    trace: list[TracePoint] = []
    first_output_step = None
    steps = 0
    status = "timeout"
    for step in range(1, 2049):
        steps = step
        fetched = memory[c]
        if not ops.is_printable_byte(fetched):
            status = f"invalid_runtime:{fetched}@{c}"
            break
        op = ops.decode_op(fetched, c)
        mem_d_before = memory[d]
        jump_target = memory[d] if op == ops.JUMP else None
        movd_target = memory[d] if op == ops.MOVD else None
        wrote_d = d if op in {ops.ROT, ops.CRAZY} else None
        if len(trace) < max_ops:
            trace.append(
                TracePoint(
                    step=step,
                    c=c,
                    d=d,
                    a=a,
                    op_name=ops.op_name(op),
                    mem_c_before=fetched,
                    mem_d_before=mem_d_before,
                    output_so_far=bytes(output).hex(),
                    jump_target=jump_target,
                    movd_target=movd_target,
                    wrote_d=wrote_d,
                )
            )
        if op == ops.JUMP:
            c = memory[d]
        elif op == ops.OUT:
            if first_output_step is None:
                first_output_step = step
            output.append(a % 256)
            if len(output) >= 64:
                status = "output_limit"
                break
        elif op == ops.IN:
            if input_index < len(input_bytes):
                a = input_bytes[input_index]
                input_index += 1
            else:
                a = ops.WORD_MAX
        elif op == ops.ROT:
            value = ops.rotate_right_word(memory[d])
            memory[d] = value
            a = value
        elif op == ops.MOVD:
            d = memory[d]
        elif op == ops.CRAZY:
            value = ops.crazy_word(a, memory[d])
            memory[d] = value
            a = value
        elif op == ops.HALT:
            status = "halt"
            break
        if op != ops.HALT:
            if not ops.is_printable_byte(memory[c]):
                status = f"encipher_invalid:{memory[c]}@{c}"
                break
            memory[c] = ops.encipher_word(memory[c])
            c = (c + 1) % ops.MEMORY_CELLS
            d = (d + 1) % ops.MEMORY_CELLS
    actual = None if not output else f"{output[0]:02x}"
    return TraceSummary(
        input_hex=pair["input_hex"],
        expected_hex=pair["expected_hex"],
        actual_hex=actual,
        correct=actual == pair["expected_hex"],
        steps=steps,
        halted=status == "halt",
        first_output_step=first_output_step,
        final_a=a,
        final_c=c,
        final_d=d,
        trace_points=[asdict(item) for item in trace],
    )


def _compare_routes(
    candidate_path: str,
    successes: list[TraceSummary],
    failure: TraceSummary | None,
    program: bytes,
) -> dict[str, object]:
    success_points = [item.trace_points for item in successes]
    failure_points = [] if failure is None else failure.trace_points
    all_points = [point for trace in success_points + ([failure_points] if failure_points else []) for point in trace]
    common_prefix = _common_prefix_steps(success_points + ([failure_points] if failure_points else []))
    first_divergence = {}
    if failure is not None:
        for success in successes:
            first_divergence[success.input_hex] = _first_divergence(success.trace_points, failure.trace_points)
    success_c = _lane_counts(point["c"] for trace in success_points for point in trace)
    failure_c = {point["c"] for point in failure_points}
    success_d = _lane_counts(point["d"] for trace in success_points for point in trace)
    failure_d = {point["d"] for point in failure_points}
    shared_c = sorted(address for address in failure_c if address in success_c)
    shared_d = sorted(address for address in failure_d if address in success_d)
    jump_targets = sorted({point["jump_target"] for point in all_points if point.get("jump_target") is not None})
    movd_targets = sorted({point["movd_target"] for point in all_points if point.get("movd_target") is not None})
    patchable = _patchable_cells(program, failure_points, shared_c)
    dangerous = _dangerous_cells(program, success_points, shared_c, shared_d)
    return {
        "candidate_path": candidate_path,
        "common_prefix_steps": common_prefix,
        "first_divergence_by_pair": first_divergence,
        "shared_c_lanes": shared_c,
        "shared_d_lanes": shared_d,
        "jump_targets": jump_targets,
        "movd_targets": movd_targets,
        "suspected_collision_cells": sorted(set(shared_c) | set(shared_d)),
        "poisoned_lanes": [
            point
            for point in failure_points
            if str(point.get("op_name")) == "HALT" and point.get("c") not in shared_c
        ],
        "patchable_cells": patchable,
        "dangerous_cells": dangerous,
        "notes": [
            "Patchable means source-valid alternatives exist at an executed failure-path source address.",
            "Dangerous cells are touched by preserved successes or shared lanes.",
            "Source-tail data cells are tracked separately from executed C-path cells.",
        ],
    }


def _patchable_cells(program: bytes, failure_points: list[dict[str, object]], shared_c: list[int]) -> list[dict[str, object]]:
    out = []
    seen = set()
    for point in failure_points:
        address = int(point["c"])
        if address in seen or address >= len(program):
            continue
        seen.add(address)
        allowed = [byte for byte in ops.source_valid_bytes(address) if byte != program[address]]
        if not allowed:
            continue
        out.append(
            {
                "address": address,
                "current_byte": program[address],
                "current_char": chr(program[address]),
                "allowed_bytes": allowed,
                "allowed_chars": "".join(chr(byte) for byte in allowed),
                "role": "executed_code",
                "risk_level": "high" if address in shared_c else "medium",
                "reason_selected": f"failure trace executes {point['op_name']} at C={address}",
            }
        )
    return out


def _dangerous_cells(
    program: bytes,
    success_points: list[list[dict[str, object]]],
    shared_c: list[int],
    shared_d: list[int],
) -> list[dict[str, object]]:
    executed_success = {int(point["c"]) for trace in success_points for point in trace if int(point["c"]) < len(program)}
    out = []
    for address in sorted(executed_success | set(shared_c)):
        out.append({"address": address, "role": "executed_code", "risk_level": "high", "reason": "used by success trace"})
    for address in sorted(address for address in shared_d if address < len(program) and address not in executed_success):
        out.append({"address": address, "role": "source_tail_data", "risk_level": "high", "reason": "shared D lane"})
    return out


def _common_prefix_steps(traces: list[list[dict[str, object]]]) -> int:
    if not traces:
        return 0
    count = 0
    for items in zip(*traces):
        signature = {(item["c"], item["d"], item["op_name"]) for item in items}
        if len(signature) != 1:
            break
        count += 1
    return count


def _first_divergence(left: list[dict[str, object]], right: list[dict[str, object]]) -> dict[str, object]:
    for index, (a, b) in enumerate(zip(left, right)):
        if (a["c"], a["d"], a["op_name"]) != (b["c"], b["d"], b["op_name"]):
            return {"step_index": index, "success": a, "failure": b}
    return {"step_index": min(len(left), len(right)), "success": None, "failure": None}


def _lane_counts(values: Any) -> dict[int, int]:
    out: dict[int, int] = {}
    for value in values:
        out[int(value)] = out.get(int(value), 0) + 1
    return out


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


def _select_successes(preserve_pairs: list[dict[str, str]], target_pair: dict[str, str], limit: int) -> list[dict[str, str]]:
    target_first = target_pair["input_hex"][:2]
    nearby = [pair for pair in preserve_pairs if pair["input_hex"][:2] == target_first]
    visible = [pair for pair in preserve_pairs if pair["input_hex"] == "82"]
    rest = [pair for pair in preserve_pairs if pair not in nearby and pair not in visible]
    return (nearby + visible + rest)[:limit]


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
    comparison = report.get("comparison", {})
    target = report.get("target", {})
    lines = [
        "# Route Surgeon Report",
        "",
        "Diagnostic Python VM only; not native evidence.",
        "",
        f"- candidate: `{report.get('candidate_path')}`",
        f"- target: `{target.get('input_hex')}` -> `{target.get('expected_hex')}`",
        f"- common prefix steps: `{comparison.get('common_prefix_steps')}`",
        f"- patchable cells: `{len(comparison.get('patchable_cells', []))}`",
        f"- dangerous cells: `{len(comparison.get('dangerous_cells', []))}`",
        "",
        "## Notes",
        "",
    ]
    lines.extend(f"- {item}" for item in comparison.get("notes", []))
    return "\n".join(lines) + "\n"
