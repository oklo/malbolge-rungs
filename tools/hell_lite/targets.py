"""Finite byte-mapping target helpers for HeLL-Lite."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class TargetSpec:
    name: str
    finite_map: dict[int, int] | None = None

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        if self.finite_map is not None:
            data["finite_map"] = {
                f"{key:02x}": f"{value:02x}"
                for key, value in sorted(self.finite_map.items())
            }
        return data


def parse_byte(text: str) -> int:
    text = text.strip().lower()
    if text.startswith("0x"):
        value = int(text, 16)
    else:
        value = int(text, 16)
    if not 0 <= value <= 0xFF:
        raise ValueError(f"byte out of range: {text!r}")
    return value


def parse_inputs(text: str) -> list[int]:
    if text == "all":
        return list(range(256))
    out = []
    for part in text.split(","):
        part = part.strip()
        if part:
            out.append(parse_byte(part))
    return out


def parse_finite_map_pairs(text: str) -> dict[int, int]:
    mapping: dict[int, int] = {}
    if not text.strip():
        raise ValueError("finite-map pairs cannot be empty")
    for part in text.split(","):
        item = part.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(f"finite-map pair must be input:output, got {item!r}")
        left, right = item.split(":", 1)
        key = parse_byte(left)
        value = parse_byte(right)
        if key in mapping:
            raise ValueError(f"duplicate finite-map input {key:02x}")
        mapping[key] = value
    if not mapping:
        raise ValueError("finite-map pairs cannot be empty")
    return mapping


def target_spec(name: str, pairs: str | None = None) -> TargetSpec:
    if name == "finite-map":
        if pairs is None:
            raise ValueError("finite-map target requires --pairs")
        return TargetSpec(name=name, finite_map=parse_finite_map_pairs(pairs))
    if name in ("echo1", "xor1"):
        return TargetSpec(name=name)
    raise ValueError(f"unknown target {name!r}")


def expected_output(target: str | TargetSpec, input_byte: int, finite_map: dict[int, int] | None = None) -> int:
    if isinstance(target, TargetSpec):
        finite_map = target.finite_map
        target = target.name
    if target == "xor1":
        return input_byte ^ 0x51
    if target == "echo1":
        return input_byte
    if target == "finite-map":
        if finite_map is None:
            raise ValueError("finite-map target requires finite_map")
        if input_byte not in finite_map:
            raise ValueError(f"input {input_byte:02x} is not in finite map")
        return finite_map[input_byte]
    raise ValueError(f"unknown target {target!r}")


def target_inputs(target: TargetSpec, inputs: str | list[int] | None = None) -> list[int]:
    if target.name == "finite-map":
        return sorted((target.finite_map or {}).keys())
    if inputs is None:
        return list(range(256))
    if isinstance(inputs, list):
        return inputs
    return parse_inputs(inputs)


def target_info(name: str, inputs: str, pairs: str | None = None) -> dict[str, object]:
    spec = target_spec(name, pairs)
    selected = target_inputs(spec, inputs)
    outputs = {f"{value:02x}": f"{expected_output(spec, value):02x}" for value in selected}
    return {
        "target": spec.to_dict(),
        "inputs": [f"{value:02x}" for value in selected],
        "outputs": outputs,
        "expected_outputs": [
            {"input": f"{value:02x}", "expected": f"{expected_output(spec, value):02x}"}
            for value in selected
        ],
    }
