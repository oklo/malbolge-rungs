"""Extract finite-map targets from MAL-51 raw match artifacts.

The extractor is intentionally conservative. It records where each pair came
from and marks raw-input gaps as uncertainties instead of inventing data.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


PAIR_STATUS_PASS = "pass"
PAIR_STATUS_FAIL = "fail"
PAIR_STATUS_UNKNOWN = "unknown"


@dataclass(frozen=True)
class ExtractedPair:
    input_hex: str
    expected_hex: str
    first_input_byte: str = ""
    actual_hex: str | None = None
    status: str = PAIR_STATUS_UNKNOWN
    source_path: str = ""
    turn_id: str = ""
    report_type: str = ""
    block_index: int | None = None
    seed_index: int | None = None
    confidence: str = "uncertain"
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.first_input_byte and self.input_hex:
            object.__setattr__(self, "first_input_byte", self.input_hex[:2])

    def key(self) -> tuple[str, str, str | None, str]:
        return (self.input_hex, self.expected_hex, self.actual_hex, self.status)


@dataclass
class ExtractedMap:
    rung_id: str
    match_id: str
    source_turns: list[str] = field(default_factory=list)
    passed_pairs: list[ExtractedPair] = field(default_factory=list)
    failed_pairs: list[ExtractedPair] = field(default_factory=list)
    visible_pair: ExtractedPair | None = None
    holdout_pairs: list[ExtractedPair] = field(default_factory=list)
    blocks3_pairs: list[ExtractedPair] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "rung_id": self.rung_id,
            "match_id": self.match_id,
            "source_turns": sorted(set(self.source_turns)),
            "visible_pair": None if self.visible_pair is None else asdict(self.visible_pair),
            "passed_pairs": [asdict(pair) for pair in sorted(self.passed_pairs, key=_pair_sort_key)],
            "failed_pairs": [asdict(pair) for pair in sorted(self.failed_pairs, key=_failed_pair_sort_key)],
            "holdout_pairs": [asdict(pair) for pair in sorted(self.holdout_pairs, key=_pair_sort_key)],
            "blocks3_pairs": [asdict(pair) for pair in sorted(self.blocks3_pairs, key=_pair_sort_key)],
            "uncertainties": sorted(set(self.uncertainties)),
        }


def extract_pairs_from_report_json(path: str | Path) -> list[ExtractedPair]:
    """Extract pairs from known HeLL-Lite/MAL-51 JSON report shapes."""

    path = Path(path)
    data = json.loads(path.read_text())
    pairs: list[ExtractedPair] = []
    _walk_report_json(data, path, pairs)
    if not pairs and _looks_like_mal51_report(data):
        pairs.append(
            ExtractedPair(
                input_hex="",
                expected_hex="",
                status=PAIR_STATUS_UNKNOWN,
                source_path=str(path),
                report_type="mal51_report_without_raw_inputs",
                notes="Report contains evaluator outcome but no raw challenge input bytes.",
            )
        )
    return _dedupe_pairs(pair for pair in pairs if pair.input_hex or pair.notes)


def extract_pairs_from_notes(path: str | Path) -> list[ExtractedPair]:
    """Extract byte relations from human notes without treating prose as proof."""

    path = Path(path)
    text = Path(path).read_text()
    pairs: list[ExtractedPair] = []
    for match in _EXPECTED_GOT_RE.finditer(text):
        input_hex = _compact_hex(match.group("input"))
        expected = _compact_hex(match.group("expected"))
        actual = _compact_hex(match.group("actual"))
        pairs.append(
            ExtractedPair(
                input_hex=input_hex,
                expected_hex=expected,
                actual_hex=actual,
                status=PAIR_STATUS_FAIL if actual != expected else PAIR_STATUS_PASS,
                source_path=str(path),
                report_type="notes",
                confidence="notes_only",
                notes=_line_for_match(text, match.start()),
            )
        )
    for match in _ARROW_STATUS_RE.finditer(text):
        input_hex = _compact_hex(match.group("input"))
        expected = _compact_hex(match.group("expected"))
        status_word = (match.group("status") or "").lower()
        status = PAIR_STATUS_PASS if status_word == "pass" else PAIR_STATUS_UNKNOWN
        pairs.append(
            ExtractedPair(
                input_hex=input_hex,
                expected_hex=expected,
                status=status,
                source_path=str(path),
                report_type="notes",
                confidence="notes_only",
                notes=_line_for_match(text, match.start()),
            )
        )
    for match in _ARROW_SIMPLE_RE.finditer(text):
        input_hex = _compact_hex(match.group("input"))
        expected = _compact_hex(match.group("expected"))
        pairs.append(
            ExtractedPair(
                input_hex=input_hex,
                expected_hex=expected,
                status=PAIR_STATUS_UNKNOWN,
                source_path=str(path),
                report_type="notes",
                confidence="notes_only",
                notes=_line_for_match(text, match.start()),
            )
        )
    return _dedupe_pairs(pairs)


def extract_pairs_from_holdout_summary(path: str | Path) -> list[ExtractedPair]:
    """Extract note-level pairs from a holdout summary markdown file."""

    pairs = []
    for pair in extract_pairs_from_notes(path):
        pairs.append(
            ExtractedPair(
                input_hex=pair.input_hex,
                expected_hex=pair.expected_hex,
                first_input_byte=pair.first_input_byte,
                actual_hex=pair.actual_hex,
                status=pair.status,
                source_path=pair.source_path,
                turn_id=pair.turn_id,
                report_type="holdout_summary",
                block_index=pair.block_index,
                seed_index=pair.seed_index,
                confidence="notes_only",
                notes=pair.notes,
            )
        )
    return pairs


def extract_codex012_map(match_dir: str | Path, rung: str = "L2.R0d.xor-1-len4096") -> ExtractedMap:
    match_dir = Path(match_dir)
    match_id = match_dir.name
    rung_dir = match_dir / "rungs" / rung
    turn_id = "012-codex"
    turn_dir = rung_dir / "turns" / turn_id
    out = ExtractedMap(rung_id=rung, match_id=match_id, source_turns=[turn_id])

    expected_paths = [
        turn_dir / "report.json",
        turn_dir / "notes.md",
        turn_dir / "diagnostics" / "final-candidate-full-input-score.json",
        turn_dir / "diagnostics" / "patched-candidate-full-input-score.json",
        turn_dir / "diagnostics" / "derived-holdout-012-blocks3-cases.json",
        turn_dir / "trampoline-search" / "c012-add-02" / "report.json",
        rung_dir / "holdout-codex-012" / "holdout-summary.md",
        rung_dir / "holdout-codex-012" / "holdout-sweep-blocks3.json",
    ]
    for path in expected_paths:
        if not path.exists():
            out.uncertainties.append(f"missing expected artifact: {path}")
            continue
        if path.suffix == ".json":
            _add_pairs_to_map(out, extract_pairs_from_report_json(path))
        elif path.suffix == ".md" and "holdout-summary" in path.name:
            _add_pairs_to_map(out, extract_pairs_from_holdout_summary(path))
        elif path.suffix == ".md":
            _add_pairs_to_map(out, extract_pairs_from_notes(path))

    if out.visible_pair is None:
        visible = ExtractedPair(
            input_hex="82",
            expected_hex="d3",
            status=PAIR_STATUS_UNKNOWN,
            source_path=str(turn_dir / "notes.md"),
            turn_id=turn_id,
            report_type="fallback_visible",
            notes="Visible pair was inferred from Codex 012 notes, but no structured row was found.",
        )
        out.visible_pair = visible
        out.uncertainties.append("visible pair used fallback note-derived value 82 -> d3")

    out.passed_pairs = _promote_prefixes(out.passed_pairs, out.blocks3_pairs, status=PAIR_STATUS_PASS)
    out.failed_pairs = _promote_prefixes(out.failed_pairs, out.blocks3_pairs, status=PAIR_STATUS_FAIL)
    out.passed_pairs = _dedupe_pairs(out.passed_pairs)
    out.failed_pairs = _dedupe_pairs(out.failed_pairs)
    out.holdout_pairs = _dedupe_pairs(out.holdout_pairs)
    out.blocks3_pairs = _dedupe_pairs(out.blocks3_pairs)
    return out


def _promote_prefixes(
    pairs: list[ExtractedPair],
    full_candidates: list[ExtractedPair],
    status: str,
) -> list[ExtractedPair]:
    promoted: list[ExtractedPair] = []
    for pair in pairs:
        if len(pair.input_hex) >= 8:
            promoted.append(pair)
            continue
        full = next(
            (
                candidate
                for candidate in full_candidates
                if candidate.status == PAIR_STATUS_UNKNOWN
                and candidate.input_hex.startswith(pair.input_hex)
                and candidate.expected_hex == pair.expected_hex
                and len(candidate.input_hex) > len(pair.input_hex)
            ),
            None,
        )
        if full is None:
            promoted.append(pair)
            continue
        promoted.append(
            ExtractedPair(
                input_hex=full.input_hex,
                expected_hex=pair.expected_hex,
            actual_hex=pair.actual_hex,
            status=status,
            source_path=pair.source_path,
            turn_id=pair.turn_id,
            report_type=pair.report_type,
            block_index=full.block_index if pair.block_index is None else pair.block_index,
            seed_index=full.seed_index if pair.seed_index is None else pair.seed_index,
            confidence="file_backed" if full.confidence == "file_backed" else pair.confidence,
            notes=f"{pair.notes}; full input from {full.source_path}",
        )
        )
    return promoted


def write_extracted_map_json(extracted: ExtractedMap, out_path: str | Path) -> None:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(extracted.to_dict(), indent=2, sort_keys=True) + "\n")


def write_extracted_map_markdown(extracted: ExtractedMap, out_path: str | Path) -> None:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Extracted Map: {extracted.rung_id}",
        "",
        f"Match: `{extracted.match_id}`",
        "",
        "This is a file-backed HeLL-Lite extraction. It is not an official evaluator report.",
        "",
    ]
    if extracted.visible_pair:
        lines.extend(["## Visible", "", _pair_line(extracted.visible_pair), ""])
    lines.extend(["## Passed Pairs", ""])
    lines.extend(_pair_line(pair) for pair in sorted(extracted.passed_pairs, key=_pair_sort_key))
    lines.extend(["", "## Failed Pairs", ""])
    lines.extend(_pair_line(pair) for pair in sorted(extracted.failed_pairs, key=_failed_pair_sort_key))
    lines.extend(["", "## Uncertainties", ""])
    if extracted.uncertainties:
        lines.extend(f"- {item}" for item in sorted(set(extracted.uncertainties)))
    else:
        lines.append("- none recorded")
    path.write_text("\n".join(lines) + "\n")


def write_extracted_outputs(extracted: ExtractedMap, out_dir: str | Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_extracted_map_json(extracted, out / "extracted-map.json")
    write_extracted_map_markdown(extracted, out / "extracted-map.md")


def _walk_report_json(data: Any, path: Path, pairs: list[ExtractedPair], seed_index: int | None = None) -> None:
    if isinstance(data, dict):
        current_seed = seed_index
        if isinstance(data.get("seed"), int):
            current_seed = int(data["seed"])
        if {"input_prefix", "expected"}.issubset(data):
            input_hex = _compact_hex(str(data["input_prefix"]))
            expected = _compact_hex(str(data["expected"]))
            actual = None if data.get("got") is None else _compact_hex(str(data.get("got")))
            correct = data.get("correct")
            status = PAIR_STATUS_PASS if correct is True else PAIR_STATUS_FAIL if correct is False else PAIR_STATUS_UNKNOWN
            pairs.append(
                ExtractedPair(
                    input_hex=input_hex,
                    expected_hex=expected,
                    actual_hex=actual,
                    status=status,
                    source_path=str(path),
                    turn_id=_turn_id_from_path(path),
                    report_type=_report_type_from_path(path, data),
                    seed_index=current_seed,
                    confidence="file_backed",
                    notes=str(data.get("name", "")),
                )
            )
        elif {"input", "expected"}.issubset(data) and _is_hex_string(data.get("input")):
            pairs.append(
                ExtractedPair(
                    input_hex=_compact_hex(str(data["input"])),
                    expected_hex=_compact_hex(str(data["expected"])),
                    status=PAIR_STATUS_UNKNOWN,
                    source_path=str(path),
                    turn_id=_turn_id_from_path(path),
                    report_type=_report_type_from_path(path, data),
                    block_index=int(data["block"]) if isinstance(data.get("block"), int) else None,
                    seed_index=current_seed,
                    confidence="file_backed",
                    notes=f"block={data.get('block', 'unknown')}",
                )
            )
        for value in data.values():
            _walk_report_json(value, path, pairs, current_seed)
    elif isinstance(data, list):
        for item in data:
            _walk_report_json(item, path, pairs, seed_index)


def _add_pairs_to_map(extracted: ExtractedMap, pairs: list[ExtractedPair]) -> None:
    for pair in pairs:
        pair = _with_turn(pair)
        if not pair.input_hex:
            extracted.uncertainties.append(f"{pair.source_path}: {pair.notes}")
            continue
        if pair.input_hex == "82" and pair.expected_hex == "d3":
            if extracted.visible_pair is None or pair.status == PAIR_STATUS_PASS:
                extracted.visible_pair = pair
        if pair.status == PAIR_STATUS_PASS:
            extracted.passed_pairs.append(pair)
        elif pair.status == PAIR_STATUS_FAIL:
            extracted.failed_pairs.append(pair)
        else:
            extracted.uncertainties.append(
                f"{pair.input_hex} -> {pair.expected_hex} has unknown status from {pair.source_path}"
            )
        if "blocks1" in pair.report_type or "b1-" in pair.notes or pair.input_hex in {"c0", "c5", "6f", "4a", "87"}:
            extracted.holdout_pairs.append(pair)
        if "blocks3" in pair.report_type or "b3-" in pair.notes or pair.input_hex in {"1c", "f6", "a7", "b9", "b4", "f05d", "2dca"}:
            extracted.blocks3_pairs.append(pair)


def _with_turn(pair: ExtractedPair) -> ExtractedPair:
    if pair.turn_id:
        return pair
    return ExtractedPair(
        input_hex=pair.input_hex,
        expected_hex=pair.expected_hex,
        first_input_byte=pair.first_input_byte,
        actual_hex=pair.actual_hex,
        status=pair.status,
        source_path=pair.source_path,
        turn_id=_turn_id_from_path(Path(pair.source_path)),
        report_type=pair.report_type,
        block_index=pair.block_index,
        seed_index=pair.seed_index,
        confidence=pair.confidence,
        notes=pair.notes,
    )


def _dedupe_pairs(pairs: list[ExtractedPair] | Any) -> list[ExtractedPair]:
    out_by_key: dict[tuple[str, str, str], ExtractedPair] = {}
    for pair in pairs:
        key = (pair.input_hex, pair.expected_hex, pair.status)
        existing = out_by_key.get(key)
        if existing is None:
            out_by_key[key] = pair
            continue
        if existing.actual_hex is None and pair.actual_hex is not None:
            out_by_key[key] = pair
        elif len(pair.input_hex) > len(existing.input_hex):
            out_by_key[key] = pair
    return sorted(out_by_key.values(), key=_pair_sort_key)


def _pair_sort_key(pair: ExtractedPair) -> tuple[str, str, str, str]:
    return (pair.input_hex, pair.expected_hex, pair.status, pair.source_path)


def _failed_pair_sort_key(pair: ExtractedPair) -> tuple[int, str, str, str, str]:
    # Keep the current Codex 012 repair target first for --target-index 0 demos,
    # then fall back to deterministic lexical order.
    priority = 0 if pair.input_hex.startswith("f05d") and pair.expected_hex == "a1" else 1
    return (priority, pair.input_hex, pair.expected_hex, pair.status, pair.source_path)


def _pair_line(pair: ExtractedPair) -> str:
    actual = "" if pair.actual_hex is None else f", actual `{pair.actual_hex}`"
    block = "" if pair.block_index is None else f", block `{pair.block_index}`"
    seed = "" if pair.seed_index is None else f", seed `{pair.seed_index}`"
    return (
        f"- `{pair.input_hex}` -> `{pair.expected_hex}`: `{pair.status}`{actual}{block}{seed}, "
        f"confidence `{pair.confidence}` ({pair.report_type}, `{pair.source_path}`)"
    )


def _compact_hex(text: str) -> str:
    text = text.lower().replace("0x", "")
    text = re.sub(r"[^0-9a-f]", "", text)
    if len(text) % 2 == 1:
        text = "0" + text
    return text


def _is_hex_string(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"(0x)?[0-9a-fA-F]{2,}", value.strip()))


def _turn_id_from_path(path: Path) -> str:
    parts = path.parts
    if "turns" in parts:
        index = parts.index("turns")
        if index + 1 < len(parts):
            return parts[index + 1]
    return ""


def _report_type_from_path(path: Path, row: dict[str, Any]) -> str:
    if "blocks3" in path.name or "blocks3" in str(path):
        return "blocks3"
    if "full-input-score" in path.name:
        return "full_input_score"
    if "holdout" in str(path):
        return "holdout"
    name = str(row.get("name", ""))
    if name.startswith("b3-"):
        return "blocks3_full_input_score"
    if name.startswith("b1-"):
        return "holdout_full_input_score"
    if name == "visible":
        return "visible_full_input_score"
    return path.stem


def _looks_like_mal51_report(data: Any) -> bool:
    return isinstance(data, dict) and (
        "report" in data or "task_package_hash" in data or "calibration_outcome" in data
    )


def _line_for_match(text: str, offset: int) -> str:
    start = text.rfind("\n", 0, offset) + 1
    end = text.find("\n", offset)
    if end < 0:
        end = len(text)
    return text[start:end].strip()


_HEX_TOKEN = r"(?:0x)?[0-9a-fA-F]{2}"
_INPUT_PATTERN = rf"(?P<input>{_HEX_TOKEN}(?:\s+{_HEX_TOKEN})?)\s*(?:\.\.\.)?"
_EXPECTED_GOT_RE = re.compile(
    rf"{_INPUT_PATTERN}\s*->\s*expected\s+(?P<expected>{_HEX_TOKEN}),\s*got\s+(?P<actual>{_HEX_TOKEN})",
    re.IGNORECASE,
)
_ARROW_STATUS_RE = re.compile(
    rf"{_INPUT_PATTERN}\s*->\s*(?P<expected>{_HEX_TOKEN})\s+(?P<status>pass|fail)\b",
    re.IGNORECASE,
)
_ARROW_SIMPLE_RE = re.compile(
    rf"(?<!expected\s){_INPUT_PATTERN}\s*->\s*(?P<expected>{_HEX_TOKEN})(?!\s*(?:pass|fail|,|not))",
    re.IGNORECASE,
)
