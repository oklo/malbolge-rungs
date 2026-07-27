"""Known internal MAL-51 construction specimens."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass


CODEX007_JUMP_BRANCH_SOURCE = '(tBA@?>=65|W876543210)M:,%I6(\'&%$#"!~}|{zyxwvutsU10onmlkjihgfedcba`_^]\\[ZYXWVUTSRQPONMLKJIHGFEDCBA@?>=<;:9876543210/.-,+*)(\'&%$#"!~>+'

CODEX008_ROUTED_SOURCE = '(tBA@?>=65|W876543210/.\'&%I6(\'&%$#"!~}|{zyrq7$ts220B{gle*)(:s_GpbD`}X|i[ZYXWVUNMq^nONMLKJIHGFEDCBA@?>=<;kj2h0/.-,+*)M:,+*)YED%${z@-}|{zyxwvutsrqponmlkjihgfedcba`_^]\\[ZYXWVUTSRQPONMLKJIHGFEDCBA@?>=<;:987wTA3210/.-,+*)(\'&%'


@dataclass(frozen=True)
class Specimen:
    id: str
    match_id: str
    turn_id: str
    classification: str
    source: str | None
    source_length: int
    visible_result: str
    holdout_result: str | None
    all_byte_score: str | None
    finite_map_hits: list[str]
    notes: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def known_specimens() -> list[Specimen]:
    return [
        Specimen(
            id="codex-005-source-tail-crazy",
            match_id="mal51-internal-xor4096-20260430-133753",
            turn_id="005-codex",
            classification="source_tail_crazy_diagnostic",
            source=None,
            source_length=55,
            visible_result="failed",
            holdout_result="not_run",
            all_byte_score="3/256",
            finite_map_hits=["0x09 -> 0x58", "0x30 -> 0x61"],
            notes="Input-dependent diagnostic artifact; not a solution.",
        ),
        Specimen(
            id="claude-006-source-tail-crazy",
            match_id="mal51-internal-xor4096-20260430-133753",
            turn_id="006-claude",
            classification="source_tail_crazy_diagnostic",
            source=None,
            source_length=81,
            visible_result="failed",
            holdout_result="not_run",
            all_byte_score="11/256",
            finite_map_hits=[],
            notes="Reported source-tail CRAZY ceiling marker for k<=3 diagnostics.",
        ),
        Specimen(
            id="codex-007-two-input-jump-branch",
            match_id="mal51-internal-xor4096-20260430-133753",
            turn_id="007-codex",
            classification="jump_routing_diagnostic",
            source=CODEX007_JUMP_BRANCH_SOURCE,
            source_length=len(CODEX007_JUMP_BRANCH_SOURCE),
            visible_result="failed",
            holdout_result="not_run",
            all_byte_score=None,
            finite_map_hits=["0x02 -> 0x53", "0x06 -> 0x57"],
            notes="First executable input-dependent JUMP/routing branch specimen.",
        ),
        Specimen(
            id="codex-008-visible-holdout-routed",
            match_id="mal51-internal-xor4096-20260430-133753",
            turn_id="008-codex",
            classification="finite_routed_official_progress",
            source=CODEX008_ROUTED_SOURCE,
            source_length=len(CODEX008_ROUTED_SOURCE),
            visible_result="passed",
            holdout_result="blocks1 5/5; blocks3 0/5",
            all_byte_score="6/256",
            finite_map_hits=[
                "0x82 -> 0xd3",
                "0xc0 0x2f... -> 0x91",
                "0xc5 0xae... -> 0x94",
                "0x6f 0x43... -> 0x3e",
                "0x4a 0x4e... -> 0x1b",
                "0x87 0x58... -> 0xd6",
            ],
            notes="First visible plus 5/5 one-block holdout routed construction; not full xor1.",
        ),
    ]


def specimens_json() -> str:
    return json.dumps([item.to_dict() for item in known_specimens()], indent=2, sort_keys=True)
