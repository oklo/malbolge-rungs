"""Tiny JSON sketch representation for HeLL-Lite."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import source


@dataclass(frozen=True)
class Sketch:
    name: str
    ops: list[str] | None = None
    kind: str = "linear"
    tail_operands: list[int] | None = None
    crazy_start: int | None = None
    diagnostic_target: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Sketch":
        return cls(
            name=str(data["name"]),
            ops=data.get("ops"),
            kind=data.get("kind", "linear"),
            tail_operands=data.get("tail_operands"),
            crazy_start=data.get("crazy_start"),
            diagnostic_target=data.get("diagnostic_target"),
        )


def load_sketch(path: str | Path) -> Sketch:
    return Sketch.from_dict(json.loads(Path(path).read_text()))


def compile_sketch(sketch: Sketch) -> bytes:
    if sketch.kind == "linear":
        if sketch.ops is None:
            raise ValueError("linear sketch requires ops")
        return source.compile_ops(source.parse_ops_csv(",".join(sketch.ops)))
    if sketch.kind == "tail_crazy":
        if sketch.tail_operands is None:
            raise ValueError("tail_crazy sketch requires tail_operands")
        return source.build_tail_crazy_source(sketch.tail_operands, sketch.crazy_start)
    raise ValueError(f"unsupported sketch kind {sketch.kind!r}")
