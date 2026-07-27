"""Source-tail CRAZY-chain search helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from . import ops, score, source

DEFAULT_XOR_DIAGNOSTIC_INPUTS = [
    0x02,
    0x03,
    0x06,
    0x07,
    0x09,
    0x0C,
    0x1C,
    0x1F,
    0x23,
    0x28,
    0x2B,
    0x30,
    0x43,
    0x44,
    0x62,
    0x64,
    0x82,
    0x9D,
    0xB5,
    0xE3,
    0xE8,
    0xEC,
    0xF8,
]

CODEX005_TAIL_OPERANDS = [123, 80, 79]
CODEX005_CRAZY_START = 12
CLAUDE006_TAIL_OPERANDS = [115, 114, 112]
CLAUDE006_CRAZY_START = 38
MAX_DEFAULT_CRAZY = 4
DEFAULT_MAX_CANDIDATES = 50000
_BYTE_DOMAIN = tuple(range(256))
_PREFIX_OUTPUT_CACHE: dict[tuple[int, ...], tuple[int, ...]] = {(): _BYTE_DOMAIN}


@dataclass(frozen=True)
class TailCrazyResult:
    operands: list[int]
    crazy_start: int
    source: str
    source_length: int
    selected_correct: int
    selected_inputs: int
    all_correct: int
    visible_pass: bool
    contains_in: bool
    hits: list[int]


@dataclass(frozen=True)
class KnownSpecimen:
    id: str
    match_id: str
    turn_id: str
    official_or_unofficial: str
    label: str
    result: TailCrazyResult
    notes: str


def apply_operands(input_byte: int, operands: list[int] | tuple[int, ...]) -> int:
    value = input_byte
    for operand in operands:
        value = ops.crazy_word(value, operand)
    return value % 256


def output_table_for_operands(operands: list[int] | tuple[int, ...]) -> tuple[int, ...]:
    """Return full-word outputs for byte inputs 0..255 after an operand chain."""

    key = tuple(operands)
    cached = _PREFIX_OUTPUT_CACHE.get(key)
    if cached is not None:
        return cached
    prefix = output_table_for_operands(key[:-1])
    output = tuple(ops.crazy_word(value, key[-1]) for value in prefix)
    # Prefixes are reused heavily by k=3 analysis; full longer chains are not.
    if len(key) <= 2:
        _PREFIX_OUTPUT_CACHE[key] = output
    return output


def visible_pass_for_operands(target: str, operands: list[int] | tuple[int, ...]) -> bool:
    if target != "xor1":
        raise ValueError("tail CRAZY visible check currently supports xor1 only")
    return apply_operands(0x82, operands) == score.expected_output(target, 0x82)


def plantable_sequences(k: int) -> dict[tuple[int, ...], int]:
    return dict(iter_plantable_sequences(k))


def iter_plantable_sequences(k: int):
    seen: set[tuple[int, ...]] = set()
    for start in range(2, 96):
        choices = [ops.source_valid_bytes(start + 40 + i) for i in range(k)]
        for operands in _walk_sequences(choices, ()):
            if operands in seen:
                continue
            seen.add(operands)
            yield operands, start


def _walk_sequences(
    choices: list[list[int]],
    prefix: tuple[int, ...],
):
    if len(prefix) == len(choices):
        yield prefix
        return
    for byte in choices[len(prefix)]:
        yield from _walk_sequences(choices, prefix + (byte,))


def search_tail_crazy(
    target: str = "xor1",
    max_crazy: int = 3,
    max_results: int = 10,
    inputs: list[int] | None = None,
    max_candidates: int | None = None,
    allow_large_search: bool = False,
) -> list[TailCrazyResult]:
    if target != "xor1":
        raise ValueError("tail CRAZY search currently supports xor1 only")
    validate_max_crazy(max_crazy, allow_large_search)
    if max_candidates is not None and max_candidates < 1:
        raise ValueError("max_candidates must be positive when supplied")
    inputs = inputs or DEFAULT_XOR_DIAGNOSTIC_INPUTS
    ranked = []
    candidates_tested = 0
    for k in range(1, max_crazy + 1):
        for operands_tuple, start in iter_plantable_sequences(k):
            if max_candidates is not None and candidates_tested >= max_candidates:
                break
            candidates_tested += 1
            operands = list(operands_tuple)
            hits = [x for x in inputs if apply_operands(x, operands) == score.expected_output(target, x)]
            visible_pass = visible_pass_for_operands(target, operands)
            if not hits and not visible_pass:
                continue
            candidate = source.build_tail_crazy_source(operands, crazy_start=start)
            result = TailCrazyResult(
                operands=operands,
                crazy_start=start,
                source=source.source_text(candidate),
                source_length=len(candidate),
                selected_correct=len(hits),
                selected_inputs=len(inputs),
                all_correct=0,
                visible_pass=visible_pass,
                contains_in=ops.IN in source.decode_ops(candidate),
                hits=hits,
            )
            rank = (
                1 if result.visible_pass else 0,
                result.selected_correct,
                -result.source_length,
            )
            ranked.append((rank, result))
        if max_candidates is not None and candidates_tested >= max_candidates:
            break
    ranked.sort(reverse=True, key=lambda item: item[0])
    results = [result for _, result in ranked[:max_results]]
    return [_with_all_correct(result, target) for result in results]


def validate_max_crazy(max_crazy: int, allow_large_search: bool = False) -> None:
    if max_crazy < 1:
        raise ValueError("max_crazy must be at least 1")
    if max_crazy > MAX_DEFAULT_CRAZY and not allow_large_search:
        raise ValueError(
            f"max_crazy={max_crazy} is combinatorial; pass --allow-large-search "
            "for exploratory runs above 4"
        )


def result_for_operands(
    operands: list[int],
    crazy_start: int,
    target: str = "xor1",
    inputs: list[int] | None = None,
) -> TailCrazyResult:
    inputs = inputs or DEFAULT_XOR_DIAGNOSTIC_INPUTS
    candidate = source.build_tail_crazy_source(operands, crazy_start=crazy_start)
    hits = [byte for byte in inputs if apply_operands(byte, operands) == score.expected_output(target, byte)]
    return _with_all_correct(
        TailCrazyResult(
            operands=operands,
            crazy_start=crazy_start,
            source=source.source_text(candidate),
            source_length=len(candidate),
            selected_correct=len(hits),
            selected_inputs=len(inputs),
            all_correct=0,
            visible_pass=visible_pass_for_operands(target, operands),
            contains_in=True,
            hits=hits,
        ),
        target,
    )


def known_specimens(
    target: str = "xor1",
    inputs: list[int] | None = None,
) -> list[KnownSpecimen]:
    if target != "xor1":
        return []
    return [
        KnownSpecimen(
            id="codex-005-source-tail-crazy",
            match_id="mal51-internal-xor4096-20260430-133753",
            turn_id="005-codex",
            official_or_unofficial="official_diagnostic",
            label="Codex 005 source-tail CRAZY diagnostic",
            result=result_for_operands(
                CODEX005_TAIL_OPERANDS,
                CODEX005_CRAZY_START,
                target,
                inputs,
            ),
            notes="55-byte input-reading diagnostic artifact; visible failed; 3/256 all-byte hits.",
        ),
        KnownSpecimen(
            id="claude-006-source-tail-crazy",
            match_id="mal51-internal-xor4096-20260430-133753",
            turn_id="006-claude",
            official_or_unofficial="official_diagnostic",
            label="Claude 006 source-tail CRAZY diagnostic",
            result=result_for_operands(
                CLAUDE006_TAIL_OPERANDS,
                CLAUDE006_CRAZY_START,
                target,
                inputs,
            ),
            notes="81-byte input-reading diagnostic artifact; visible failed; 11/256 all-byte hits.",
        ),
    ]


def analyze_tail_crazy(
    target: str = "xor1",
    max_crazy: int = 3,
    max_candidates: int | None = DEFAULT_MAX_CANDIDATES,
    include_known_specimens: bool = False,
    allow_large_search: bool = False,
    exhaustive: bool = False,
) -> dict[str, object]:
    if target != "xor1":
        raise ValueError("tail CRAZY analysis currently supports xor1 only")
    validate_max_crazy(max_crazy, allow_large_search)
    if exhaustive and not allow_large_search:
        raise ValueError("exhaustive analysis requires allow_large_search")
    if exhaustive:
        max_candidates = None
    if max_candidates is None and not allow_large_search:
        raise ValueError("unbounded analysis requires allow_large_search")
    if max_candidates is not None and max_candidates < 1:
        raise ValueError("max_candidates must be positive when supplied")
    by_k = []
    candidates_tested = 0
    truncated = False
    for k in range(1, max_crazy + 1):
        best: TailCrazyResult | None = None
        visible_possible = False
        best_by_start: dict[int, TailCrazyResult] = {}
        by_k_tested = 0
        by_k_truncated = False
        for operands_tuple, start in iter_plantable_sequences(k):
            if max_candidates is not None and candidates_tested >= max_candidates:
                truncated = True
                by_k_truncated = True
                break
            candidates_tested += 1
            by_k_tested += 1
            operands = list(operands_tuple)
            visible = visible_pass_for_operands(target, operands)
            visible_possible = visible_possible or visible
            output_table = output_table_for_operands(operands)
            all_correct = sum(
                1
                for byte, output in enumerate(output_table)
                if output % 256 == score.expected_output(target, byte)
            )
            if all_correct == 0 and not visible:
                continue
            hits = [
                byte
                for byte in DEFAULT_XOR_DIAGNOSTIC_INPUTS
                if output_table[byte] % 256 == score.expected_output(target, byte)
            ]
            candidate = source.build_tail_crazy_source(operands, crazy_start=start)
            result = TailCrazyResult(
                operands=operands,
                crazy_start=start,
                source=source.source_text(candidate),
                source_length=len(candidate),
                selected_correct=len(hits),
                selected_inputs=len(DEFAULT_XOR_DIAGNOSTIC_INPUTS),
                all_correct=all_correct,
                visible_pass=visible,
                contains_in=ops.IN in source.decode_ops(candidate),
                hits=hits,
            )
            if best is None or (result.all_correct, result.selected_correct) > (
                best.all_correct,
                best.selected_correct,
            ):
                best = result
            previous = best_by_start.get(start)
            if previous is None or result.all_correct > previous.all_correct:
                best_by_start[start] = result
        by_k.append(
            {
                "k": k,
                "candidates_tested": by_k_tested,
                "truncated": by_k_truncated,
                "visible_possible": visible_possible,
                "best_found_in_bounded_search": None if best is None else asdict(best),
                "best": None if best is None else asdict(best),
                "best_by_start": {
                    str(start): {
                        "all_correct": result.all_correct,
                        "selected_correct": result.selected_correct,
                        "operands": result.operands,
                        "visible_pass": result.visible_pass,
                    }
                    for start, result in sorted(best_by_start.items())
                },
            }
        )
        if truncated:
            break
    return {
        "target": target,
        "max_crazy": max_crazy,
        "max_candidates": max_candidates,
        "candidates_tested": candidates_tested,
        "truncated": truncated,
        "exhaustive": exhaustive,
        "analysis_scope": "bounded valid source-tail CRAZY operands over plantable source bytes",
        "warning": "analysis truncated; best values are best found in bounded search"
        if truncated
        else None,
        "by_k": by_k,
        "known_specimens": [
            asdict(item) for item in known_specimens(target)
        ]
        if include_known_specimens
        else [],
    }


def _with_all_correct(result: TailCrazyResult, target: str) -> TailCrazyResult:
    output_table = output_table_for_operands(result.operands)
    all_correct = sum(
        1
        for byte, output in enumerate(output_table)
        if output % 256 == score.expected_output(target, byte)
    )
    return TailCrazyResult(
        operands=result.operands,
        crazy_start=result.crazy_start,
        source=result.source,
        source_length=result.source_length,
        selected_correct=result.selected_correct,
        selected_inputs=result.selected_inputs,
        all_correct=all_correct,
        visible_pass=result.visible_pass,
        contains_in=result.contains_in,
        hits=result.hits,
    )


def write_results(results: list[TailCrazyResult], out_dir: str | Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(
        json.dumps([asdict(result) for result in results], indent=2, sort_keys=True)
    )
    for index, result in enumerate(results):
        (out / f"candidate-{index:03d}.mal").write_text(result.source)


def write_known_specimens(specimens: list[KnownSpecimen], out_dir: str | Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "known-specimens.json").write_text(
        json.dumps([asdict(specimen) for specimen in specimens], indent=2, sort_keys=True)
    )
    for specimen in specimens:
        (out / f"known-{specimen.id}.mal").write_text(specimen.result.source)
