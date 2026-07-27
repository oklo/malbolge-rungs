"""Tiny finite-map compiler attempts for HeLL-Lite Phase 3."""

from __future__ import annotations

import json
from pathlib import Path

from . import compare_map, routing, source, specimens, targets


def compile_finite_map(
    pairs: str,
    out_dir: str | Path | None = None,
    max_source_length: int = 4096,
    seed_candidate: str | Path | None = None,
    preserve_candidate: str | Path | None = None,
) -> dict[str, object]:
    mapping = targets.parse_finite_map_pairs(pairs)
    sorted_pairs = ",".join(f"{key:02x}:{value:02x}" for key, value in sorted(mapping.items()))
    report: dict[str, object] = {
        "target_pairs": {f"{key:02x}": f"{value:02x}" for key, value in sorted(mapping.items())},
        "max_source_length": max_source_length,
        "seed_candidate": None if seed_candidate is None else str(seed_candidate),
        "preserve_candidate": None if preserve_candidate is None else str(preserve_candidate),
        "compile_status": "planning_only",
        "candidate_source": None,
        "candidate_score": None,
        "plan": {
            "strategy": "specimen_or_routing_scaffold",
            "constraints": [
                "source-valid classic Malbolge",
                "one output byte per input",
                "Python score is diagnostic only",
            ],
            "missing_pieces": [],
        },
    }

    candidate_text: str | None = None
    if set(mapping.items()).issubset({(0x02, 0x53), (0x06, 0x57)}):
        candidate_text = specimens.CODEX007_JUMP_BRANCH_SOURCE
        report["compile_status"] = "executable_candidate"
        report["plan"]["strategy"] = "reuse codex-007 two-input JUMP/routing specimen"  # type: ignore[index]
    elif seed_candidate is not None:
        candidate_text = source.source_text(source.assert_valid_source(Path(seed_candidate).read_bytes()))
        report["compile_status"] = "diagnostic_candidate_only"
        report["plan"]["strategy"] = "score supplied seed candidate"  # type: ignore[index]
    else:
        route_report = routing.search_routing(
            target_name="finite-map",
            pairs=sorted_pairs,
            template="source-tail-crazy",
            max_results=5,
            max_candidates=10000,
        )
        report["routing_scaffold"] = route_report.to_dict()
        report["compile_status"] = "planning_only"
        report["plan"]["missing_pieces"] = [  # type: ignore[index]
            "No Phase 3 compiler could synthesize an executable candidate for all pairs.",
            "Use D-as-PC route planning or a protected trampoline allocator next.",
        ]

    if candidate_text is not None:
        candidate = source.assert_valid_source(candidate_text.encode("latin1"), max_len=max_source_length)
        report["candidate_source"] = source.source_text(candidate)
        with _optional_temp_candidate(candidate, out_dir) as candidate_path:
            report["candidate_score"] = compare_map.compare_map(candidate_path, sorted_pairs)
    if out_dir is not None:
        write_compile_outputs(report, out_dir)
    return report


class _optional_temp_candidate:
    def __init__(self, candidate: bytes, out_dir: str | Path | None):
        self.candidate = candidate
        self.out_dir = Path(out_dir) if out_dir is not None else None
        self.path: Path | None = None

    def __enter__(self) -> Path:
        if self.out_dir is None:
            from tempfile import NamedTemporaryFile

            self._tmp = NamedTemporaryFile(delete=False, suffix=".mal")  # type: ignore[attr-defined]
            self._tmp.write(self.candidate)  # type: ignore[attr-defined]
            self._tmp.close()  # type: ignore[attr-defined]
            self.path = Path(self._tmp.name)  # type: ignore[attr-defined]
        else:
            self.out_dir.mkdir(parents=True, exist_ok=True)
            self.path = self.out_dir / "candidate.mal"
            self.path.write_text(source.source_text(self.candidate) + "\n")
        return self.path

    def __exit__(self, *_args: object) -> None:
        if self.out_dir is None and self.path is not None:
            self.path.unlink(missing_ok=True)


def write_compile_outputs(report: dict[str, object], out_dir: str | Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    (out / "plan.json").write_text(json.dumps(report["plan"], indent=2, sort_keys=True))
    candidate = report.get("candidate_source")
    if isinstance(candidate, str):
        (out / "candidate.mal").write_text(candidate + "\n")
