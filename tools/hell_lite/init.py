"""Classic Malbolge memory initialization helper."""

from __future__ import annotations

from . import ops
from .source import assert_valid_source


def initialize_memory(source: bytes, memory_cells: int = ops.MEMORY_CELLS) -> list[int]:
    source = assert_valid_source(source, max_len=memory_cells)
    if len(source) > memory_cells:
        raise ValueError("source longer than memory")
    memory = [0] * memory_cells
    for index, byte in enumerate(source):
        memory[index] = byte
    for index in range(len(source), memory_cells):
        memory[index] = ops.crazy_word(memory[index - 1], memory[index - 2])
    return memory
