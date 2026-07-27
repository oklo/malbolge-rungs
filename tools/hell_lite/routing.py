"""Experimental finite-map routing search scaffolds for HeLL-Lite."""

from __future__ import annotations

import itertools
from dataclasses import asdict, dataclass

from . import ops, score, source, tail_crazy, targets


@dataclass(frozen=True)
class RouteSearchReport:
    target: dict[str, object]
    template_family: str
    inputs_tested: list[int]
    candidates_tested: int
    best_candidate: str | None
    best_score: int
    visible_pass: bool
    contains_in: bool
    output_varies: bool
    notes: list[str]
    limitations: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def search_routing(
    target_name: str,
    pairs: str | None = None,
    inputs: str | list[int] | None = None,
    template: str = "source-tail-crazy",
    max_results: int = 10,
    max_candidates: int = 10000,
) -> RouteSearchReport:
    if max_candidates < 1:
        raise ValueError("max_candidates must be positive")
    target = targets.target_spec(target_name, pairs)
    selected_inputs = targets.target_inputs(target, inputs)
    if template == "source-tail-crazy":
        return _search_source_tail(target, selected_inputs, max_results, max_candidates)
    if template == "linear-op":
        return _search_linear_ops(target, selected_inputs, max_candidates)
    if template == "route-sketch":
        return RouteSearchReport(
            target=target.to_dict(),
            template_family=template,
            inputs_tested=selected_inputs,
            candidates_tested=0,
            best_candidate=None,
            best_score=0,
            visible_pass=False,
            contains_in=False,
            output_varies=False,
            notes=["Route sketch accepted as a planning target only."],
            limitations=[
                "Route-sketch compilation is not implemented in HeLL-Lite Phase 2.",
                "Phase 2 does not compile branch-on-read or JUMP routing layouts.",
                "Use layout and loop-sketch reports to make constraints explicit first.",
            ],
        )
    raise ValueError(f"unknown routing template {template!r}")


def _search_source_tail(
    target: targets.TargetSpec,
    selected_inputs: list[int],
    max_results: int,
    max_candidates: int,
) -> RouteSearchReport:
    ranked: list[tuple[tuple[int, int], tuple[int, ...], int, int, bool]] = []
    candidates_tested = 0
    for k in range(1, 4):
        for operands, start in tail_crazy.plantable_sequences(k).items():
            if candidates_tested >= max_candidates:
                break
            candidates_tested += 1
            outputs = [tail_crazy.apply_operands(input_byte, operands) for input_byte in selected_inputs]
            correct = sum(
                1
                for input_byte, got in zip(selected_inputs, outputs)
                if got == targets.expected_output(target, input_byte)
            )
            length = start + 40 + len(operands)
            output_varies = len(set(outputs)) > 1
            ranked.append(((correct, int(output_varies), -length), operands, start, correct, output_varies))
        if candidates_tested >= max_candidates:
            break
    ranked.sort(reverse=True, key=lambda item: item[0])
    best_operands = ranked[0][1] if ranked else None
    best_start = ranked[0][2] if ranked else 0
    best_correct = ranked[0][3] if ranked else 0
    best_varies = ranked[0][4] if ranked else False
    best_program = (
        None
        if best_operands is None
        else source.build_tail_crazy_source(list(best_operands), crazy_start=best_start)
    )
    return RouteSearchReport(
        target=target.to_dict(),
        template_family="source-tail-crazy",
        inputs_tested=selected_inputs,
        candidates_tested=candidates_tested,
        best_candidate=None if best_program is None else source.source_text(best_program),
        best_score=best_correct,
        visible_pass=_tail_visible_pass(target, best_operands),
        contains_in=best_program is not None,
        output_varies=best_varies,
        notes=[
            f"Ranked bounded search results; max_results={max_results}, max_candidates={max_candidates}.",
            "Source-tail CRAZY is diagnostic scaffolding, not a solution claim.",
            "This report is not an official MAL-51 result.",
        ],
        limitations=[
            "Only fixed source-tail CRAZY chains with plantable source bytes are searched.",
            "No JUMP, restore-cell, or branch-on-read layout is generated.",
        ],
    )


def _search_linear_ops(target: targets.TargetSpec, selected_inputs: list[int], max_candidates: int) -> RouteSearchReport:
    op_pool = [ops.IN, ops.ROT, ops.CRAZY, ops.MOVD, ops.OUT, ops.HALT, ops.NOP]
    best_program: bytes | None = None
    best_score: score.ScoreResult | None = None
    tested = 0
    for length in range(3, 8):
        for sequence in itertools.product(op_pool, repeat=length):
            if tested >= max_candidates:
                break
            if sequence[-1] != ops.HALT or ops.OUT not in sequence:
                continue
            tested += 1
            program = source.compile_ops(sequence)
            result = score.score_candidate(program, target.name, selected_inputs, target.finite_map)
            if best_score is None or (result.total_correct, result.output_varies) > (
                best_score.total_correct,
                best_score.output_varies,
            ):
                best_program = program
                best_score = result
        if tested >= max_candidates:
            break
    return RouteSearchReport(
        target=target.to_dict(),
        template_family="linear-op",
        inputs_tested=selected_inputs,
        candidates_tested=tested,
        best_candidate=None if best_program is None else source.source_text(best_program),
        best_score=0 if best_score is None else best_score.total_correct,
        visible_pass=_visible_pass(best_score),
        contains_in=False if best_score is None else best_score.contains_in,
        output_varies=False if best_score is None else best_score.output_varies,
        notes=["Short linear op search completed deterministically."],
        limitations=[
            "No source-tail operands, branch-on-read, JUMP layout, or restore-cell planning.",
            "This template is a scaffold for scoring, not a serious compiler.",
        ],
    )


def _visible_pass(result: score.ScoreResult | None) -> bool:
    if result is None:
        return False
    for item in result.per_input_results:
        if item["input"] == 0x82:
            return bool(item["correct"])
    return False


def _tail_visible_pass(target: targets.TargetSpec, operands: tuple[int, ...] | None) -> bool:
    if operands is None or target.name != "xor1":
        return False
    return tail_crazy.apply_operands(0x82, operands) == targets.expected_output(target, 0x82)
