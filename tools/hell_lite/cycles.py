"""Instruction cycle catalogue helpers."""

from __future__ import annotations

from . import ops


def cycle(address: int, start_byte: int | None = None, visits: int = 8) -> list[ops.CycleEntry]:
    if start_byte is None:
        start_byte = ops.source_valid_bytes(address)[0]
    return ops.instruction_cycle(address, start_byte, visits)


def classify_cycle(entries: list[ops.CycleEntry]) -> dict[str, object]:
    names = [entry.op_name for entry in entries]
    useful = [name for name in names if name != "NOP" and not name.startswith("NOPish")]
    alternates_with_nop = len(entries) >= 2 and all(
        (entries[i].op_name == "NOP") != (entries[i + 1].op_name == "NOP")
        for i in range(len(entries) - 1)
    )
    return {
        "useful_ops": sorted(set(useful)),
        "alternates_with_nop": alternates_with_nop,
        "has_jump": "JUMP" in useful,
        "has_io": "IN" in useful or "OUT" in useful,
        "has_data_motion": "MOVD" in useful or "CRAZY" in useful or "ROT" in useful,
    }


def evaluate_cycle(
    address: int,
    start_byte: int,
    expected_ops: list[int],
) -> dict[str, object]:
    entries = cycle(address, start_byte, len(expected_ops))
    actual_ops = [entry.op for entry in entries]
    return {
        "address": address,
        "source_byte": start_byte,
        "source_char": chr(start_byte),
        "expected_ops": [ops.op_name(op) for op in expected_ops],
        "actual_ops": [entry.op_name for entry in entries],
        "matches": actual_ops == expected_ops,
        "entries": [
            {
                "visit": entry.visit,
                "byte": entry.byte,
                "char": chr(entry.byte),
                "op": entry.op,
                "op_name": entry.op_name,
            }
            for entry in entries
        ],
    }


def find_cycle(
    expected_ops: list[int],
    address_start: int,
    address_end: int,
    max_results: int = 20,
) -> list[dict[str, object]]:
    if not expected_ops:
        raise ValueError("cycle must include at least one op")
    if address_start < 0 or address_end < address_start:
        raise ValueError("invalid address range")
    results = []
    for address in range(address_start, address_end + 1):
        for byte in ops.source_valid_bytes(address):
            report = evaluate_cycle(address, byte, expected_ops)
            if report["matches"]:
                results.append(report)
                if len(results) >= max_results:
                    return results
    return results


def format_cycle(entries: list[ops.CycleEntry]) -> str:
    lines = ["visit address byte char op_code op_name"]
    for entry in entries:
        char = chr(entry.byte)
        lines.append(
            f"{entry.visit:>5} {entry.address:>7} {entry.byte:>4} {char!r:>6} "
            f"{entry.op:>7} {entry.op_name}"
        )
    cls = classify_cycle(entries)
    lines.append(f"classification: {cls}")
    return "\n".join(lines)
