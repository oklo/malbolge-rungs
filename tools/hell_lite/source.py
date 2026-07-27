"""Source construction helpers for HeLL-Lite."""

from __future__ import annotations

import string

from . import ops

ASCII_WHITESPACE = set(ord(ch) for ch in string.whitespace)


def canonical_source_bytes(program: bytes) -> bytes:
    return bytes(byte for byte in program if byte not in ASCII_WHITESPACE)


def parse_ops_csv(text: str) -> list[int]:
    if not text.strip():
        return []
    return [ops.parse_op_name(part) for part in text.split(",")]


def compile_ops(op_codes: list[int] | tuple[int, ...]) -> bytes:
    return bytes(ops.source_byte_for_op(op, address) for address, op in enumerate(op_codes))


def decode_ops(source: bytes) -> list[int]:
    source = canonical_source_bytes(source)
    return [ops.decode_op(byte, address) for address, byte in enumerate(source)]


def validate_source(source: bytes, min_len: int = 2, max_len: int = 4096) -> tuple[bool, str]:
    source = canonical_source_bytes(source)
    if len(source) < min_len:
        return False, f"source length {len(source)} below minimum {min_len}"
    if len(source) > max_len:
        return False, f"source length {len(source)} exceeds maximum {max_len}"
    for address, byte in enumerate(source):
        if not ops.is_printable_byte(byte):
            return False, f"byte {byte} at address {address} is not printable"
        if ops.decode_op(byte, address) not in ops.VALID_OPS:
            return False, f"byte {byte} at address {address} is not source-valid"
    return True, "ok"


def assert_valid_source(source: bytes, min_len: int = 2, max_len: int = 4096) -> bytes:
    source = canonical_source_bytes(source)
    ok, reason = validate_source(source, min_len=min_len, max_len=max_len)
    if not ok:
        raise ValueError(reason)
    return source


def source_text(source: bytes) -> str:
    return source.decode("latin1")


def build_tail_crazy_source(
    operands: list[int] | tuple[int, ...],
    crazy_start: int | None = None,
    max_len: int = 4096,
) -> bytes:
    """Build MOVD, IN, NOP..., CRAZY^k, OUT, HALT with planted tail operands."""

    operands = tuple(operands)
    if not operands:
        raise ValueError("at least one CRAZY operand is required")

    starts = range(2, 96) if crazy_start is None else (crazy_start,)
    for start in starts:
        tail_start = start + 40
        length = tail_start + len(operands)
        if length > max_len:
            continue
        if any(byte not in ops.source_valid_bytes(tail_start + i) for i, byte in enumerate(operands)):
            continue

        op_codes = [ops.MOVD, ops.IN]
        op_codes.extend([ops.NOP] * (start - 2))
        op_codes.extend([ops.CRAZY] * len(operands))
        op_codes.extend([ops.OUT, ops.HALT])
        source = bytearray(compile_ops(op_codes))
        while len(source) < length:
            source.append(ops.source_byte_for_op(ops.NOP, len(source)))
        for i, byte in enumerate(operands):
            source[tail_start + i] = byte
        return assert_valid_source(bytes(source), max_len=max_len)

    raise ValueError("operands cannot be planted as source-valid tail bytes")


def recognize_tail_crazy_source(source: bytes) -> dict[str, object] | None:
    """Recognize the simple MOVD/IN/NOP*/CRAZY*/OUT/HALT/tail pattern."""

    source = canonical_source_bytes(source)
    decoded = decode_ops(source)
    if len(decoded) < 6 or decoded[:2] != [ops.MOVD, ops.IN]:
        return None

    index = 2
    while index < len(decoded) and decoded[index] == ops.NOP:
        index += 1
    crazy_start = index
    while index < len(decoded) and decoded[index] == ops.CRAZY:
        index += 1
    crazy_count = index - crazy_start
    if crazy_count < 1:
        return None
    if index + 1 >= len(decoded) or decoded[index : index + 2] != [ops.OUT, ops.HALT]:
        return None
    tail_start = crazy_start + 40
    if tail_start + crazy_count > len(source):
        return None
    operands = list(source[tail_start : tail_start + crazy_count])
    return {
        "kind": "tail_crazy",
        "crazy_start": crazy_start,
        "tail_start": tail_start,
        "crazy_count": crazy_count,
        "operands": operands,
    }
