"""Compare a candidate against explicit byte pairs with the Python VM."""

from __future__ import annotations

from pathlib import Path

from . import ops, score, source, targets


def compare_map(candidate: str | Path, pairs: str, trace_ops: int = 0) -> dict[str, object]:
    program = source.canonical_source_bytes(Path(candidate).read_bytes())
    mapping = targets.parse_finite_map_pairs(pairs)
    result = score.score_candidate(program, "finite-map", sorted(mapping), mapping)
    rows = []
    decoded_names = [ops.op_name(op) for op in source.decode_ops(program)] if trace_ops else []
    for row in result.per_input_results:
        item = dict(row)
        if trace_ops:
            item["initial_ops"] = decoded_names[:trace_ops]
        rows.append(item)
    return {
        "candidate": str(candidate),
        "source_length": result.source_length,
        "pairs": {f"{key:02x}": f"{value:02x}" for key, value in sorted(mapping.items())},
        "total_correct": result.total_correct,
        "total_inputs": result.total_inputs,
        "contains_in": result.contains_in,
        "output_varies": result.output_varies,
        "likely_constant_output": result.likely_constant_output,
        "per_input_results": rows,
        "status_counts": result.status_counts,
        "note": "Python diagnostic VM only; claims need the native evaluator (malbolge-rungs verify).",
    }
