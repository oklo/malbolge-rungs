"""Unit tests for HeLL-Lite v0."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from . import (
    branch_alloc,
    compare_map,
    cycles,
    d_as_pc,
    finite_map_compile,
    layout,
    loop_sketch,
    ops,
    patch_enum,
    routing,
    route_surgeon,
    score,
    sketches,
    source,
    specimens,
    tail_crazy,
    targets,
    trace_compare,
    unit_search,
    units,
)

EXAMPLES = Path(__file__).parent / "examples"


class HellLiteTests(unittest.TestCase):
    def test_compile_echo1_ops_to_ubo(self) -> None:
        self.assertEqual(source.compile_ops([ops.IN, ops.OUT, ops.HALT]), b"ubO")

    def test_source_byte_calculation_printable(self) -> None:
        for address in range(200):
            for op in ops.VALID_OPS:
                byte = ops.source_byte_for_op(op, address)
                self.assertTrue(ops.is_printable_byte(byte))
                self.assertEqual(ops.decode_op(byte, address), op)

    def test_source_valid_bytes_decode_to_valid_ops(self) -> None:
        for address in range(200):
            for byte in ops.source_valid_bytes(address):
                self.assertIn(ops.decode_op(byte, address), ops.VALID_OPS)

    def test_crazy_trit_table_and_word_helpers(self) -> None:
        self.assertEqual(ops.CRAZY_TABLE[0][0], 1)
        self.assertEqual(ops.CRAZY_TABLE[0][1], 0)
        self.assertEqual(ops.CRAZY_TABLE[1][2], 2)
        self.assertEqual(ops.crazy_word(0, 0), 29524)
        self.assertNotEqual(ops.crazy_word(0, 1), ops.crazy_word(1, 0))

    def test_rot_helper(self) -> None:
        self.assertEqual(ops.rotate_right_word(0), 0)
        self.assertEqual(ops.rotate_right_word(1), 19683)
        self.assertEqual(ops.rotate_right_word(3), 1)
        self.assertEqual(ops.rotate_right_word(59048), 59048)

    def test_cycle_generation(self) -> None:
        entries = cycles.cycle(0, visits=8)
        self.assertEqual(len(entries), 8)
        self.assertIn("op_name", entries[0].__dataclass_fields__)

    def test_straight_line_echo1_sketch(self) -> None:
        sketch = sketches.Sketch(name="echo1", ops=["IN", "OUT", "HALT"])
        self.assertEqual(sketches.compile_sketch(sketch), b"ubO")

    def test_layout_echo1_load_validate_and_compile(self) -> None:
        sketch = layout.load_layout(EXAMPLES / "layout_echo1.json")
        report = layout.validate_layout(sketch)
        self.assertTrue(report.valid, report.errors)
        self.assertEqual(report.labels, ["emit_byte", "halt", "read_byte"])
        self.assertEqual(layout.compile_linear_layout(sketch), b"ubO")

    def test_layout_deterministic_serialization_round_trip(self) -> None:
        sketch = layout.load_layout(EXAMPLES / "layout_echo1.json")
        canonical = layout.canonical_json(sketch)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "layout.json"
            layout.save_layout(sketch, path)
            loaded = layout.load_layout(path)
        self.assertEqual(canonical, layout.canonical_json(loaded))

    def test_layout_compiled_echo1_scores(self) -> None:
        sketch = layout.load_layout(EXAMPLES / "layout_echo1.json")
        result = layout.score_compiled_layout(sketch, "echo1", [0x61, 0xFF])
        self.assertEqual(result.total_correct, 2)
        self.assertTrue(result.contains_in)

    def test_layout_invalid_and_unsupported_fail_clearly(self) -> None:
        bad = layout.LayoutSketch(
            name="bad",
            sections=[
                layout.Section(
                    name="main",
                    kind="CODE",
                    code=[
                        layout.CodeCell(label="x", op="IN"),
                        layout.CodeCell(label="x", op="OUT"),
                    ],
                )
            ],
        )
        self.assertFalse(layout.validate_layout(bad).valid)
        unsupported = layout.LayoutSketch(
            name="unsupported",
            sections=[
                layout.Section(
                    name="main",
                    kind="CODE",
                    code=[
                        layout.CodeCell(
                            label="x",
                            op="NOP",
                            cycle=layout.CycleSpec(ops=["NOP", "MOVD"], visits=2),
                        )
                    ],
                )
            ],
        )
        with self.assertRaises(NotImplementedError):
            layout.compile_linear_layout(unsupported)

    def test_cycle_find_is_deterministic(self) -> None:
        expected = [ops.NOP, ops.MOVD]
        first = cycles.find_cycle(expected, 0, 500, max_results=5)
        second = cycles.find_cycle(expected, 0, 500, max_results=5)
        self.assertEqual(first, second)
        for item in first:
            self.assertEqual(item["expected_ops"], ["NOP", "MOVD"])
            self.assertTrue(item["matches"])

    def test_target_helpers_and_finite_map_parser(self) -> None:
        self.assertEqual(targets.parse_finite_map_pairs("09:58,30:61"), {0x09: 0x58, 0x30: 0x61})
        info = targets.target_info("xor1", "09,30,82")
        self.assertEqual(info["outputs"]["09"], "58")
        self.assertEqual(info["outputs"]["30"], "61")
        self.assertEqual(info["outputs"]["82"], "d3")

    def test_finite_map_scoring_and_varying_output_detection(self) -> None:
        pairs = targets.parse_finite_map_pairs("61:61,ff:ff")
        result = score.score_candidate(b"ubO", "finite-map", [0x61, 0xFF], pairs)
        self.assertEqual(result.total_correct, 2)
        self.assertTrue(result.output_varies)
        self.assertIn("per_input_results", result.to_json())

    def test_routing_reports_are_structured(self) -> None:
        report = routing.search_routing(
            "finite-map",
            pairs="09:58,30:61",
            template="source-tail-crazy",
            max_results=5,
        )
        self.assertEqual(report.target["name"], "finite-map")
        self.assertEqual(report.template_family, "source-tail-crazy")
        self.assertGreater(report.candidates_tested, 0)
        self.assertIn("not a native result", " ".join(report.notes))

        placeholder = routing.search_routing("xor1", inputs=[0x09, 0x30], template="route-sketch")
        self.assertIsNone(placeholder.best_candidate)
        self.assertIn("not implemented", " ".join(placeholder.limitations))

    def test_loop_sketch_report_is_planning_only(self) -> None:
        report = loop_sketch.loop_sketch("input-output-loop")
        self.assertEqual(report.compile_status, "not_implemented")
        self.assertIn("read_input", report.intended_labels)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "loop.json"
            loop_sketch.write_loop_sketch(report, path)
            self.assertTrue(path.exists())

    def test_unit_catalog_validation_and_serialization(self) -> None:
        catalog = units.built_in_catalog()
        validation = catalog.validate()
        self.assertTrue(validation["valid"], validation["errors"])
        self.assertIn("linear_input_unit", catalog.list_units())
        self.assertIn("branch_placeholder_unit", catalog.canonical_json())

        bad = units.UnitCatalog(
            [
                units.OperationUnit(
                    name="bad",
                    intended_op="NO_SUCH_OP",
                    cells=[units.UnitCell(label="x", required_first_use_op="IN")],
                    entry_label="x",
                    exit_label="x",
                )
            ]
        )
        self.assertFalse(bad.validate()["valid"])

    def test_find_unit_cells_is_deterministic(self) -> None:
        first = unit_search.find_unit_cells("NOP,MOVD", 0, 500, max_results=3)
        second = unit_search.find_unit_cells("NOP,MOVD", 0, 500, max_results=3)
        self.assertEqual(first, second)
        self.assertTrue(first)
        self.assertEqual(first[0]["expected_ops"], ["NOP", "MOVD"])
        self.assertIn("source_byte", first[0])
        with self.assertRaises(ValueError):
            unit_search.find_unit_cells("NOT_AN_OP", 0, 10)

    def test_d_as_pc_two_value_branch_is_planning_only(self) -> None:
        report = d_as_pc.d_as_pc_sketch("two-value-branch")
        data = report.to_dict()
        self.assertEqual(data["program"]["compile_status"], "planning_only")
        self.assertIn("route", [cell["label"] for cell in data["program"]["cells"]])
        self.assertIn("arm_a_output", [cell["label"] for cell in data["program"]["cells"]])
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "d-as-pc.json"
            d_as_pc.write_report(report, path)
            self.assertTrue(path.exists())

    def test_finite_map_compile_reports_status(self) -> None:
        two = finite_map_compile.compile_finite_map("02:53,06:57")
        self.assertEqual(two["compile_status"], "executable_candidate")
        self.assertEqual(two["candidate_score"]["total_correct"], 2)  # type: ignore[index]
        self.assertEqual(two["target_pairs"]["02"], "53")  # type: ignore[index]

        three = finite_map_compile.compile_finite_map("02:53,06:57,82:d3")
        self.assertIn(three["compile_status"], {"planning_only", "diagnostic_candidate_only"})
        self.assertEqual(three["target_pairs"]["82"], "d3")  # type: ignore[index]
        self.assertIsNone(three["candidate_source"])

    def test_specimen_listing_metadata(self) -> None:
        ids = [item.id for item in specimens.known_specimens()]
        self.assertIn("codex-007-two-input-jump-branch", ids)
        self.assertIn("codex-008-visible-holdout-routed", ids)
        self.assertIn("0x02 -> 0x53", next(item for item in specimens.known_specimens() if item.id == "codex-007-two-input-jump-branch").finite_map_hits)

    def test_compare_map_reports_hits_and_variation(self) -> None:
        with TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "echo.mal"
            candidate.write_text("ubO\n")
            report = compare_map.compare_map(candidate, "61:61,ff:ff", trace_ops=2)
        self.assertEqual(report["total_correct"], 2)
        self.assertTrue(report["output_varies"])
        self.assertIn("initial_ops", report["per_input_results"][0])  # type: ignore[index]

    def test_branch_allocator_planning_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "echo.mal"
            candidate.write_text("ubO\n")
            extracted = {
                "passed_pairs": [
                    {"input_hex": "61", "expected_hex": "61", "status": "pass", "source_path": "fixture"}
                ],
                "failed_pairs": [
                    {"input_hex": "62", "expected_hex": "33", "status": "fail", "source_path": "fixture"}
                ],
                "blocks3_pairs": [],
            }
            map_path = root / "map.json"
            map_path.write_text(json.dumps(extracted))
            report = branch_alloc.allocate_branch(map_path, candidate, "62:33", max_candidates=10)
        self.assertEqual(report["compile_status"], "planning_only")
        self.assertEqual(report["preserved_count"], 1)
        self.assertIn("collision_report", report)

    def test_branch_allocator_diagnostic_candidate_when_seed_already_adds_target(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "echo.mal"
            candidate.write_text("ubO\n")
            extracted = {
                "passed_pairs": [
                    {"input_hex": "61", "expected_hex": "61", "status": "pass", "source_path": "fixture"}
                ],
                "failed_pairs": [
                    {"input_hex": "62", "expected_hex": "62", "status": "fail", "source_path": "fixture"}
                ],
                "blocks3_pairs": [],
            }
            map_path = root / "map.json"
            map_path.write_text(json.dumps(extracted))
            report = branch_alloc.allocate_branch(map_path, candidate, "62:62", max_candidates=10)
        self.assertEqual(report["compile_status"], "diagnostic_candidate")
        self.assertIsNotNone(report["candidate_source"])

    def test_compare_trace_echo1_is_deterministic_and_bounded(self) -> None:
        with TemporaryDirectory() as tmp:
            candidate = Path(tmp) / "echo.mal"
            candidate.write_text("ubO\n")
            report = trace_compare.compare_trace(candidate, "61:61,ff:ff", max_ops=2)
            again = trace_compare.compare_trace(candidate, "61:61,ff:ff", max_ops=2)
        self.assertEqual(report, again)
        self.assertEqual(report["total_correct"], 2)
        self.assertLessEqual(len(report["rows"][0]["trace"]), 2)  # type: ignore[index]
        self.assertIn("divergence_summary", report)
        self.assertIn("diagnostic VM", report["warning"])

    def test_route_surgeon_reports_divergence_and_patch_cells(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "echo.mal"
            candidate.write_text("ubO\n")
            extracted = {
                "passed_pairs": [{"input_hex": "61", "expected_hex": "61"}],
                "failed_pairs": [{"input_hex": "62", "expected_hex": "33"}],
                "blocks3_pairs": [],
            }
            map_path = root / "map.json"
            map_path.write_text(json.dumps(extracted))
            out = root / "route"
            report = route_surgeon.route_surgeon(candidate, map_path, target_index=0, max_ops=2, out_dir=out)
            self.assertTrue((out / "route-surgeon-report.json").exists())
        self.assertEqual(report["failure_inputs"], ["62"])
        self.assertEqual(report["success_inputs"], ["61"])
        self.assertLessEqual(len(report["traces"][0]["trace_points"]), 2)  # type: ignore[index]
        comparison = report["comparison"]  # type: ignore[assignment]
        self.assertIn("patchable_cells", comparison)

    def test_patch_enum_filters_invalid_bytes_and_respects_max_candidates(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "echo.mal"
            candidate.write_text("ubO\n")
            extracted = {
                "passed_pairs": [{"input_hex": "61", "expected_hex": "61"}],
                "failed_pairs": [{"input_hex": "62", "expected_hex": "33"}],
                "blocks3_pairs": [],
            }
            map_path = root / "map.json"
            map_path.write_text(json.dumps(extracted))
            valid = ops.source_valid_bytes(2)[0]
            route_report = {
                "comparison": {
                    "patchable_cells": [
                        {
                            "address": 2,
                            "current_byte": ord("O"),
                            "allowed_bytes": [1, valid],
                            "role": "executed_code",
                            "reason_selected": "fixture",
                            "risk_level": "medium",
                        }
                    ]
                }
            }
            route_path = root / "route.json"
            route_path.write_text(json.dumps(route_report))
            report = patch_enum.patch_enum(
                candidate,
                map_path,
                route_path,
                target_index=0,
                max_candidates=1,
            )
        self.assertEqual(report["candidates_tested"], 1)
        self.assertEqual(len(report["sites_considered"][0]["allowed_bytes"]), 1)  # type: ignore[index]

    def test_patch_enum_preserves_constraints_in_small_case(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "echo.mal"
            candidate.write_text("ubO\n")
            extracted = {
                "passed_pairs": [{"input_hex": "61", "expected_hex": "61"}],
                "failed_pairs": [{"input_hex": "62", "expected_hex": "62"}],
                "blocks3_pairs": [],
            }
            map_path = root / "map.json"
            map_path.write_text(json.dumps(extracted))
            route_report = {"comparison": {"patchable_cells": []}}
            route_path = root / "route.json"
            route_path.write_text(json.dumps(route_report))
            report = patch_enum.patch_enum(candidate, map_path, route_path, target_index=0)
        self.assertEqual(report["compile_status"], "diagnostic_candidate")

    def test_repair_branch_report_shape(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidate = root / "echo.mal"
            candidate.write_text("ubO\n")
            extracted = {
                "passed_pairs": [{"input_hex": "61", "expected_hex": "61"}],
                "failed_pairs": [{"input_hex": "62", "expected_hex": "33"}],
                "blocks3_pairs": [],
            }
            map_path = root / "map.json"
            map_path.write_text(json.dumps(extracted))
            report = branch_alloc.repair_branch(
                map_path,
                candidate,
                target_index=0,
                out_dir=root / "repair",
                max_candidates=2,
                max_sites=1,
                max_edits=1,
            )
            self.assertTrue((root / "repair" / "branch-repair-report.json").exists())
        self.assertIn("route_diagnosis", report)
        self.assertIn("patch_search_summary", report)

    def test_tail_template_generation_is_source_valid(self) -> None:
        program = source.build_tail_crazy_source([123, 80, 79], crazy_start=12)
        ok, reason = source.validate_source(program)
        self.assertTrue(ok, reason)
        info = source.recognize_tail_crazy_source(program)
        self.assertIsNotNone(info)
        self.assertEqual(info["operands"], [123, 80, 79])

    def test_scorer_detects_constant_output_and_in(self) -> None:
        constant = b"(CB$@?!!<5YF"
        constant_score = score.score_candidate(constant, "xor1", [0x82, 0x09])
        self.assertTrue(constant_score.likely_constant_output)
        self.assertFalse(constant_score.contains_in)

        echo = b"ubO"
        echo_score = score.score_candidate(echo, "echo1", [0x61, 0xFF])
        self.assertTrue(echo_score.contains_in)
        self.assertEqual(echo_score.total_correct, 2)

    def test_tail_search_recognizes_codex005_pattern(self) -> None:
        program = source.build_tail_crazy_source([123, 80, 79], crazy_start=12)
        codex005 = b"(tBA@?>=<;:9210TA3210/.-,+*)('&%$#\"!~}|{zyxwvutsrqpo{PO"
        self.assertEqual(program, codex005)
        specimens = tail_crazy.known_specimens()
        self.assertTrue(any(item.id == "codex-005-source-tail-crazy" for item in specimens))

    def test_tail_search_does_not_displace_ranked_results_with_known_specimens(self) -> None:
        results = tail_crazy.search_tail_crazy(max_crazy=3, max_results=5, max_candidates=1000)
        self.assertEqual(len(results), 5)
        self.assertFalse(any(result.operands == [123, 80, 79] for result in results))
        self.assertTrue(any(item.result.operands == [123, 80, 79] for item in tail_crazy.known_specimens()))

    def test_tail_search_visible_pass_ignores_selected_inputs(self) -> None:
        results = tail_crazy.search_tail_crazy(max_crazy=1, max_results=3, inputs=[0x00])
        for result in results:
            self.assertEqual(
                result.visible_pass,
                tail_crazy.visible_pass_for_operands("xor1", result.operands),
            )

    def test_max_crazy_guard(self) -> None:
        tail_crazy.validate_max_crazy(3)
        with self.assertRaises(ValueError):
            tail_crazy.validate_max_crazy(5)
        tail_crazy.validate_max_crazy(5, allow_large_search=True)
        with self.assertRaises(ValueError):
            tail_crazy.search_tail_crazy(max_candidates=0)
        with self.assertRaises(ValueError):
            routing.search_routing("xor1", template="source-tail-crazy", max_candidates=0)

    def test_tail_analysis_is_bounded_and_reports_truncation(self) -> None:
        truncated = tail_crazy.analyze_tail_crazy(max_crazy=3, max_candidates=10)
        self.assertEqual(truncated["candidates_tested"], 10)
        self.assertTrue(truncated["truncated"])
        self.assertIsNotNone(truncated["warning"])
        self.assertIn("candidates_tested", truncated["by_k"][0])

        complete = tail_crazy.analyze_tail_crazy(max_crazy=1, max_candidates=1000)
        self.assertFalse(complete["truncated"])
        self.assertGreater(complete["candidates_tested"], 0)

        with self.assertRaises(ValueError):
            tail_crazy.analyze_tail_crazy(max_candidates=0)
        with self.assertRaises(ValueError):
            tail_crazy.analyze_tail_crazy(max_candidates=None)
        tail_crazy.analyze_tail_crazy(
            max_crazy=1,
            max_candidates=None,
            exhaustive=True,
            allow_large_search=True,
        )

    def test_claude006_known_specimen(self) -> None:
        program = source.build_tail_crazy_source([115, 114, 112], crazy_start=38)
        claude006 = b"(tBA@?>=<;:9876543210/.-,+*)('&%$#\"!~}vut:'wvutsrqponmlkjihgfedcba`_^]\\[ZYXWVUsrp"
        self.assertEqual(program, claude006)
        specimen = next(item for item in tail_crazy.known_specimens() if item.id == "claude-006-source-tail-crazy")
        self.assertEqual(specimen.result.all_correct, 11)
        self.assertFalse(specimen.result.visible_pass)


if __name__ == "__main__":
    unittest.main()
