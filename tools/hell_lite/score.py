"""Diagnostic scoring for HeLL-Lite candidates.

The Python VM here is a construction aid. Official MAL-51 results must still be
produced by the Rust CLI.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from . import init, ops, source, targets


@dataclass(frozen=True)
class ExecutionResult:
    output: list[int]
    steps: int
    status: str


@dataclass(frozen=True)
class TraceExecutionResult:
    output: list[int]
    steps: int
    status: str
    final_a: int
    final_c: int
    final_d: int
    trace: list[dict[str, int | str]]


@dataclass(frozen=True)
class ScoreResult:
    target: str
    source_length: int
    contains_in: bool
    output_varies: bool
    likely_constant_output: bool
    total_inputs: int
    total_correct: int
    per_input_results: list[dict[str, int | str | bool]]
    status_counts: dict[str, int]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def execute_python(
    program: bytes,
    input_bytes: bytes,
    max_steps: int = 2048,
    max_output_len: int = 64,
) -> ExecutionResult:
    program = source.assert_valid_source(program)
    memory = init.initialize_memory(program)
    a = 0
    c = 0
    d = 0
    input_index = 0
    output: list[int] = []

    for step in range(1, max_steps + 1):
        fetched = memory[c]
        if not ops.is_printable_byte(fetched):
            return ExecutionResult(output, step, f"invalid_runtime:{fetched}@{c}")
        op = ops.decode_op(fetched, c)

        if op == ops.JUMP:
            c = memory[d]
        elif op == ops.OUT:
            if len(output) >= max_output_len:
                return ExecutionResult(output, step, "output_limit")
            output.append(a % 256)
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
            return ExecutionResult(output, step, "halt")

        if not ops.is_printable_byte(memory[c]):
            return ExecutionResult(output, step, f"encipher_invalid:{memory[c]}@{c}")
        memory[c] = ops.encipher_word(memory[c])
        c = (c + 1) % ops.MEMORY_CELLS
        d = (d + 1) % ops.MEMORY_CELLS

    return ExecutionResult(output, max_steps, "timeout")


def execute_python_trace(
    program: bytes,
    input_bytes: bytes,
    max_steps: int = 2048,
    max_output_len: int = 64,
    max_ops: int = 40,
) -> TraceExecutionResult:
    """Run the diagnostic Python VM and retain a compact first-N trace."""

    program = source.assert_valid_source(program)
    memory = init.initialize_memory(program)
    a = 0
    c = 0
    d = 0
    input_index = 0
    output: list[int] = []
    trace: list[dict[str, int | str]] = []

    for step in range(1, max_steps + 1):
        fetched = memory[c]
        if not ops.is_printable_byte(fetched):
            return TraceExecutionResult(output, step, f"invalid_runtime:{fetched}@{c}", a, c, d, trace)
        op = ops.decode_op(fetched, c)
        if len(trace) < max_ops:
            trace.append(
                {
                    "step": step,
                    "a": a,
                    "c": c,
                    "d": d,
                    "fetched": fetched,
                    "mem_d": memory[d],
                    "op": ops.op_name(op),
                    "output": bytes(output).hex(),
                    "jump_target": memory[d] if op == ops.JUMP else "",
                    "movd_target": memory[d] if op == ops.MOVD else "",
                }
            )

        if op == ops.JUMP:
            c = memory[d]
        elif op == ops.OUT:
            if len(output) >= max_output_len:
                return TraceExecutionResult(output, step, "output_limit", a, c, d, trace)
            output.append(a % 256)
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
            return TraceExecutionResult(output, step, "halt", a, c, d, trace)

        if not ops.is_printable_byte(memory[c]):
            return TraceExecutionResult(output, step, f"encipher_invalid:{memory[c]}@{c}", a, c, d, trace)
        memory[c] = ops.encipher_word(memory[c])
        c = (c + 1) % ops.MEMORY_CELLS
        d = (d + 1) % ops.MEMORY_CELLS

    return TraceExecutionResult(output, max_steps, "timeout", a, c, d, trace)


def expected_output(
    target: str,
    input_byte: int,
    finite_map: dict[int, int] | None = None,
) -> int:
    return targets.expected_output(target, input_byte, finite_map)


def parse_inputs(text: str) -> list[int]:
    return targets.parse_inputs(text)


def score_candidate(
    program: bytes,
    target: str,
    inputs: list[int],
    finite_map: dict[int, int] | None = None,
) -> ScoreResult:
    program = source.assert_valid_source(program)
    decoded = source.decode_ops(program)
    contains_in = ops.IN in decoded
    per_input_results = []
    status_counts: dict[str, int] = {}
    outputs = []
    for input_byte in inputs:
        result = execute_python(program, bytes([input_byte]), max_output_len=1)
        got = result.output[0] if result.output else None
        outputs.append(got)
        expected = expected_output(target, input_byte, finite_map)
        correct = got == expected
        status_counts[result.status] = status_counts.get(result.status, 0) + 1
        per_input_results.append(
            {
                "input": input_byte,
                "expected": expected,
                "got": "none" if got is None else got,
                "correct": correct,
                "steps": result.steps,
                "status": result.status,
            }
        )
    unique_outputs = {value for value in outputs if value is not None}
    return ScoreResult(
        target=target,
        source_length=len(program),
        contains_in=contains_in,
        output_varies=len(unique_outputs) > 1,
        likely_constant_output=len(unique_outputs) <= 1,
        total_inputs=len(inputs),
        total_correct=sum(1 for item in per_input_results if item["correct"]),
        per_input_results=per_input_results,
        status_counts=status_counts,
    )


def official_classic_execute(repo_root: str | Path, candidate: str | Path, input_hex: str) -> dict:
    """Run the Rust CLI for an important candidate and return parsed JSON."""

    command = [
        "cargo",
        "run",
        "-q",
        "-p",
        "harness",
        "--",
        "execute",
        "--program",
        str(candidate),
        "--input-hex",
        input_hex,
    ]
    completed = subprocess.run(
        command,
        cwd=repo_root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    start = completed.stdout.find("{")
    if start < 0:
        raise RuntimeError("Rust CLI did not emit JSON")
    return json.loads(completed.stdout[start:])
