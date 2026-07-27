"""Classic-Malbolge-51 v0 operation helpers."""

from __future__ import annotations

from dataclasses import dataclass

MEMORY_CELLS = 59049
WORD_TRITS = 10
WORD_MAX = 59048
ROTATE_TRIT_FACTOR = 19683
PRINTABLE_MIN = 33
PRINTABLE_MAX = 126

JUMP = 4
OUT = 5
IN = 23
ROT = 39
MOVD = 40
CRAZY = 62
NOP = 68
HALT = 81

VALID_OPS = (JUMP, OUT, IN, ROT, MOVD, CRAZY, NOP, HALT)
OP_NAMES = {
    JUMP: "JUMP",
    OUT: "OUT",
    IN: "IN",
    ROT: "ROT",
    MOVD: "MOVD",
    CRAZY: "CRAZY",
    NOP: "NOP",
    HALT: "HALT",
}
NAME_TO_OP = {name: op for op, name in OP_NAMES.items()}
NAME_TO_OP["JMP"] = JUMP

ENCIPHER_TABLE = (
    b"5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|"
    b"jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@"
)

# Indexed as CRAZY_TABLE[d_trit][a_trit], matching Classic-Malbolge-51 v0.
CRAZY_TABLE = (
    (1, 0, 0),
    (1, 0, 2),
    (2, 2, 1),
)


def is_printable_byte(value: int) -> bool:
    return PRINTABLE_MIN <= value <= PRINTABLE_MAX


def op_name(op: int) -> str:
    return OP_NAMES.get(op, f"NOPish({op})")


def parse_op_name(name: str) -> int:
    key = name.strip().upper()
    if key not in NAME_TO_OP:
        raise ValueError(f"unknown Malbolge op {name!r}")
    return NAME_TO_OP[key]


def decode_op(source_byte: int, address: int) -> int:
    return (source_byte + address) % 94


def source_byte_for_op(op: int, address: int) -> int:
    """Return the printable byte that first decodes to op at address."""

    if op not in VALID_OPS:
        raise ValueError(f"invalid source op code {op}")
    residue = (op - address) % 94
    if residue < PRINTABLE_MIN:
        residue += 94
    if not is_printable_byte(residue):
        raise AssertionError("printable ASCII representative was not found")
    if decode_op(residue, address) != op:
        raise AssertionError("compiled byte does not decode to requested op")
    return residue


def source_valid_bytes(address: int) -> list[int]:
    return sorted({source_byte_for_op(op, address) for op in VALID_OPS})


def encipher_word(word: int) -> int:
    if not is_printable_byte(word):
        raise ValueError(f"cannot encipher non-printable word {word}")
    return ENCIPHER_TABLE[word - PRINTABLE_MIN]


def to_trits(value: int, width: int = WORD_TRITS) -> list[int]:
    if not 0 <= value <= WORD_MAX:
        raise ValueError(f"classic word out of range: {value}")
    trits = []
    for _ in range(width):
        trits.append(value % 3)
        value //= 3
    return trits


def from_trits(trits: list[int] | tuple[int, ...]) -> int:
    if len(trits) > WORD_TRITS:
        raise ValueError("too many trits for classic word")
    result = 0
    mul = 1
    for trit in trits:
        if trit not in (0, 1, 2):
            raise ValueError(f"invalid trit {trit}")
        result += trit * mul
        mul *= 3
    if result > WORD_MAX:
        raise ValueError(f"classic word out of range: {result}")
    return result


def crazy_word(a: int, d: int) -> int:
    out = 0
    mul = 1
    av = a
    dv = d
    for _ in range(WORD_TRITS):
        out += CRAZY_TABLE[dv % 3][av % 3] * mul
        av //= 3
        dv //= 3
        mul *= 3
    return out


def rotate_right_word(word: int) -> int:
    if not 0 <= word <= WORD_MAX:
        raise ValueError(f"classic word out of range: {word}")
    return word // 3 + (word % 3) * ROTATE_TRIT_FACTOR


@dataclass(frozen=True)
class CycleEntry:
    visit: int
    address: int
    byte: int
    op: int
    op_name: str


def instruction_cycle(address: int, start_byte: int, visits: int) -> list[CycleEntry]:
    if visits < 0:
        raise ValueError("visits must be non-negative")
    if not is_printable_byte(start_byte):
        raise ValueError("cycle start byte must be printable")
    byte = start_byte
    entries = []
    for visit in range(visits):
        op = decode_op(byte, address)
        entries.append(CycleEntry(visit, address, byte, op, op_name(op)))
        byte = encipher_word(byte)
    return entries
