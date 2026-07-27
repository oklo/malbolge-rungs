"""Diagnostic trace comparison for explicit finite-map pairs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from . import score, source


@dataclass(frozen=True)
class TracePair:
    input_hex: str
    expected_hex: str


def parse_trace_pairs(text: str) -> list[TracePair]:
    pairs: list[TracePair] = []
    if not text.strip():
        raise ValueError("pairs cannot be empty")
    for part in text.split(","):
        item = part.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(f"trace pair must be input_hex:expected_hex, got {item!r}")
        left, right = item.split(":", 1)
        input_hex = _normalize_hex(left)
        expected_hex = _normalize_hex(right)
        if len(expected_hex) != 2:
            raise ValueError(f"expected output must be one byte, got {right!r}")
        pairs.append(TracePair(input_hex=input_hex, expected_hex=expected_hex))
    if not pairs:
        raise ValueError("pairs cannot be empty")
    return pairs


def compare_trace(candidate: str | Path, pairs: str, max_ops: int = 40) -> dict[str, object]:
    program = source.canonical_source_bytes(Path(candidate).read_bytes())
    parsed_pairs = parse_trace_pairs(pairs)
    rows = []
    for pair in parsed_pairs:
        result = score.execute_python_trace(
            program,
            bytes.fromhex(pair.input_hex),
            max_output_len=1,
            max_ops=max_ops,
        )
        got = None if not result.output else f"{result.output[0]:02x}"
        rows.append(
            {
                "input_hex": pair.input_hex,
                "expected_hex": pair.expected_hex,
                "actual_hex": got,
                "correct": got == pair.expected_hex,
                "status": result.status,
                "steps": result.steps,
                "final_a": result.final_a,
                "final_c": result.final_c,
                "final_d": result.final_d,
                "trace": result.trace,
            }
        )
    return {
        "candidate": str(candidate),
        "source_length": len(program),
        "max_ops": max_ops,
        "pairs": [asdict(pair) for pair in parsed_pairs],
        "rows": rows,
        "divergence_summary": _divergence_summary(rows),
        "total_correct": sum(1 for row in rows if row["correct"]),
        "total_inputs": len(rows),
        "warning": "Python diagnostic VM only; Rust trace is not available through this helper.",
    }


def compare_trace_json(candidate: str | Path, pairs: str, max_ops: int = 40) -> str:
    return json.dumps(compare_trace(candidate, pairs, max_ops=max_ops), indent=2, sort_keys=True)


def _normalize_hex(text: str) -> str:
    text = text.strip().lower().removeprefix("0x")
    if not text:
        raise ValueError("hex value cannot be empty")
    if len(text) % 2 == 1:
        text = "0" + text
    bytes.fromhex(text)
    return text


def _divergence_summary(rows: list[dict[str, object]]) -> dict[str, object]:
    traces = [row["trace"] for row in rows if isinstance(row.get("trace"), list)]
    if len(traces) < 2:
        return {"common_prefix_steps": 0, "first_divergence": None}
    common = 0
    first = None
    for items in zip(*traces):
        signature = {(item.get("c"), item.get("d"), item.get("op")) for item in items if isinstance(item, dict)}
        if len(signature) != 1:
            first = [item for item in items if isinstance(item, dict)]
            break
        common += 1
    return {"common_prefix_steps": common, "first_divergence": first}
