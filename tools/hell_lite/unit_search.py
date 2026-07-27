"""Cycle-to-operation-unit search helpers."""

from __future__ import annotations

from . import cycles, source


def find_unit_cells(
    cycle_spec: str | list[int],
    address_start: int,
    address_end: int,
    max_results: int = 20,
) -> list[dict[str, object]]:
    expected_ops = source.parse_ops_csv(cycle_spec) if isinstance(cycle_spec, str) else cycle_spec
    reports = cycles.find_cycle(expected_ops, address_start, address_end, max_results=max_results)
    out: list[dict[str, object]] = []
    for report in reports:
        out.append(
            {
                "address": report["address"],
                "source_byte": report["source_byte"],
                "source_char": report["source_char"],
                "expected_ops": report["expected_ops"],
                "actual_ops": report["actual_ops"],
                "matches": report["matches"],
                "comments": [
                    "cycle match can be used as a candidate operation-unit cell",
                    "restore/fixup is still planning-only in Phase 3",
                ],
                "cycle_report": report,
            }
        )
    return out
