"""Command-line interface for HeLL-Lite construction helpers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

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
    source,
    specimens,
    tail_crazy,
    targets,
    trace_compare,
    unit_search,
    units,
)


def cmd_compile_linear(args: argparse.Namespace) -> None:
    op_codes = source.parse_ops_csv(args.ops)
    program = source.compile_ops(op_codes)
    print(source.source_text(program))
    print(f"hex={program.hex()}")


def cmd_cycles(args: argparse.Namespace) -> None:
    start_byte = int(args.byte, 0) if args.byte is not None else None
    entries = cycles.cycle(args.address, start_byte, args.visits)
    print(cycles.format_cycle(entries))


def cmd_score(args: argparse.Namespace) -> None:
    program = source.canonical_source_bytes(Path(args.candidate).read_bytes())
    spec = targets.target_spec(args.target, args.pairs)
    inputs = targets.target_inputs(spec, args.inputs)
    result = score.score_candidate(program, spec.name, inputs, spec.finite_map)
    print(result.to_json())


def cmd_search_tail_crazy(args: argparse.Namespace) -> None:
    inputs = None if args.inputs == "default" else score.parse_inputs(args.inputs)
    results = tail_crazy.search_tail_crazy(
        target=args.target,
        max_crazy=args.max_crazy,
        max_results=args.max_results,
        inputs=inputs,
        max_candidates=args.max_candidates,
        allow_large_search=args.allow_large_search,
    )
    tail_crazy.write_results(results, args.out)
    for index, result in enumerate(results):
        print(
            f"{index}: len={result.source_length} visible={result.visible_pass} "
            f"selected={result.selected_correct}/{result.selected_inputs} "
            f"all={result.all_correct}/256 operands={result.operands}"
        )
        print(result.source)
    if args.include_known_specimens:
        specimens = tail_crazy.known_specimens(args.target, inputs)
        tail_crazy.write_known_specimens(specimens, args.out)
        print("known specimens:")
        for specimen in specimens:
            result = specimen.result
            print(
                f"{specimen.id}: len={result.source_length} visible={result.visible_pass} "
                f"selected={result.selected_correct}/{result.selected_inputs} "
                f"all={result.all_correct}/256 operands={result.operands}"
            )


def cmd_analyze_tail_crazy(args: argparse.Namespace) -> None:
    analysis = tail_crazy.analyze_tail_crazy(
        target=args.target,
        max_crazy=args.max_crazy,
        max_candidates=args.max_candidates,
        include_known_specimens=args.include_known_specimens,
        allow_large_search=args.allow_large_search,
        exhaustive=args.exhaustive,
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "analysis.json").write_text(json.dumps(analysis, indent=2, sort_keys=True))
    for row in analysis["by_k"]:
        best = row["best"]
        if best is None:
            print(
                f"k={row['k']} tested={row['candidates_tested']} "
                f"truncated={row['truncated']} no nonzero candidates"
            )
        else:
            print(
                f"k={row['k']} tested={row['candidates_tested']} "
                f"truncated={row['truncated']} best_all={best['all_correct']}/256 "
                f"visible_possible={row['visible_possible']} "
                f"operands={best['operands']} crazy_start={best['crazy_start']}"
            )
    if analysis["truncated"]:
        print("warning: analysis truncated; best values are bounded-search results")


def cmd_verify_rust(args: argparse.Namespace) -> None:
    result = score.official_classic_execute(args.repo_root, args.candidate, args.input_hex)
    print(json.dumps(result, indent=2, sort_keys=True))


def cmd_validate_layout(args: argparse.Namespace) -> None:
    sketch = layout.load_layout(args.sketch)
    report = layout.validate_layout(sketch)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))


def cmd_compile_layout(args: argparse.Namespace) -> None:
    sketch = layout.load_layout(args.sketch)
    report = layout.compile_layout_report(sketch)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    if report.source is not None:
        print(report.source)


def cmd_find_cycle(args: argparse.Namespace) -> None:
    expected_ops = source.parse_ops_csv(args.cycle)
    reports = cycles.find_cycle(
        expected_ops,
        args.address_start,
        args.address_end,
        max_results=args.max_results,
    )
    print(json.dumps(reports, indent=2, sort_keys=True))


def cmd_find_unit_cells(args: argparse.Namespace) -> None:
    reports = unit_search.find_unit_cells(
        args.cycle,
        args.address_start,
        args.address_end,
        max_results=args.max_results,
    )
    print(json.dumps(reports, indent=2, sort_keys=True))


def cmd_target_info(args: argparse.Namespace) -> None:
    info = targets.target_info(args.target, args.inputs, args.pairs)
    print(json.dumps(info, indent=2, sort_keys=True))


def cmd_search_routing(args: argparse.Namespace) -> None:
    report = routing.search_routing(
        target_name=args.target,
        pairs=args.pairs,
        inputs=args.inputs,
        template=args.template,
        max_results=args.max_results,
        max_candidates=args.max_candidates,
    )
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))


def cmd_loop_sketch(args: argparse.Namespace) -> None:
    report = loop_sketch.loop_sketch(args.kind)
    if args.out:
        loop_sketch.write_loop_sketch(report, args.out)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))


def cmd_unit_catalog(args: argparse.Namespace) -> None:
    catalog = units.built_in_catalog()
    if args.names:
        print(json.dumps(catalog.list_units(), indent=2, sort_keys=True))
    else:
        print(catalog.canonical_json())


def cmd_d_as_pc_sketch(args: argparse.Namespace) -> None:
    report = d_as_pc.d_as_pc_sketch(args.kind)
    if args.out:
        d_as_pc.write_report(report, args.out)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))


def cmd_compile_finite_map(args: argparse.Namespace) -> None:
    report = finite_map_compile.compile_finite_map(
        args.pairs,
        out_dir=args.out,
        max_source_length=args.max_source_length,
        seed_candidate=args.seed_candidate,
        preserve_candidate=args.preserve_candidate,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


def cmd_list_specimens(args: argparse.Namespace) -> None:
    print(specimens.specimens_json())


def cmd_compare_map(args: argparse.Namespace) -> None:
    report = compare_map.compare_map(args.candidate, args.pairs, trace_ops=args.trace_ops)
    print(json.dumps(report, indent=2, sort_keys=True))


def cmd_allocate_branch(args: argparse.Namespace) -> None:
    report = branch_alloc.allocate_branch(
        args.map,
        args.seed_candidate,
        args.add_target,
        out_dir=args.out,
        max_candidates=args.max_candidates,
        max_edit_sites=args.max_edit_sites,
        max_branch_bodies=args.max_branch_bodies,
        allow_large_search=args.allow_large_search,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


def cmd_compare_trace(args: argparse.Namespace) -> None:
    print(trace_compare.compare_trace_json(args.candidate, args.pairs, max_ops=args.max_ops))


def cmd_route_surgeon(args: argparse.Namespace) -> None:
    report = route_surgeon.route_surgeon(
        args.candidate,
        args.map,
        target=args.target,
        target_index=args.target_index,
        max_ops=args.max_ops,
        out_dir=args.out,
    )
    print(json.dumps(_route_summary(report), indent=2, sort_keys=True))


def cmd_patch_enum(args: argparse.Namespace) -> None:
    report = patch_enum.patch_enum(
        args.candidate,
        args.map,
        args.route_report,
        target=args.target,
        target_index=args.target_index,
        out_dir=args.out,
        max_sites=args.max_sites,
        max_edits=args.max_edits,
        max_candidates=args.max_candidates,
        allow_regression=args.allow_regression,
    )
    print(json.dumps(_patch_summary(report), indent=2, sort_keys=True))


def cmd_repair_branch(args: argparse.Namespace) -> None:
    report = branch_alloc.repair_branch(
        args.map,
        args.seed_candidate,
        target=args.target,
        target_index=args.target_index,
        out_dir=args.out,
        max_candidates=args.max_candidates,
        max_sites=args.max_sites,
        max_edits=args.max_edits,
    )
    print(json.dumps(_repair_summary(report), indent=2, sort_keys=True))


def _route_summary(report: dict[str, object]) -> dict[str, object]:
    comparison = report.get("comparison", {})
    return {
        "out": report.get("out"),
        "target": report.get("target"),
        "success_inputs": report.get("success_inputs"),
        "failure_inputs": report.get("failure_inputs"),
        "common_prefix_steps": comparison.get("common_prefix_steps") if isinstance(comparison, dict) else None,
        "patchable_cells": len(comparison.get("patchable_cells", [])) if isinstance(comparison, dict) else 0,
        "dangerous_cells": len(comparison.get("dangerous_cells", [])) if isinstance(comparison, dict) else 0,
        "warning": report.get("warning"),
    }


def _patch_summary(report: dict[str, object]) -> dict[str, object]:
    return {
        "compile_status": report.get("compile_status"),
        "candidates_tested": report.get("candidates_tested"),
        "sites_considered": len(report.get("sites_considered", [])),
        "best_candidates": [
            {
                "edits": item.get("edits"),
                "preserves_count": item.get("preserves_count"),
                "add_count": item.get("add_count"),
                "visible_pass": item.get("visible_pass"),
            }
            for item in report.get("best_candidates", [])
            if isinstance(item, dict)
        ],
        "failure_reason": report.get("failure_reason"),
    }


def _repair_summary(report: dict[str, object]) -> dict[str, object]:
    patch_summary = report.get("patch_search_summary", {})
    route = report.get("route_diagnosis", {})
    return {
        "compile_status": report.get("compile_status"),
        "candidate_produced": report.get("candidate_produced"),
        "known_successes_preserved": report.get("known_successes_preserved"),
        "add_target_achieved": report.get("add_target_achieved"),
        "target_failure": report.get("target_failure"),
        "common_prefix_steps": route.get("common_prefix_steps") if isinstance(route, dict) else None,
        "patchable_cells": len(route.get("patchable_cells", [])) if isinstance(route, dict) else 0,
        "candidates_tested": patch_summary.get("candidates_tested") if isinstance(patch_summary, dict) else None,
        "failure_reason": patch_summary.get("failure_reason") if isinstance(patch_summary, dict) else None,
        "next_suggested_task": report.get("next_suggested_task"),
    }


def cmd_smoke(args: argparse.Namespace) -> None:
    checks: list[dict[str, object]] = []

    program = source.compile_ops([ops.IN, ops.OUT, ops.HALT])
    checks.append(
        {
            "name": "compile-linear IN,OUT,HALT",
            "ok": program == b"ubO",
            "source": "ubO",
        }
    )

    cycle_reports = cycles.find_cycle(
        [ops.NOP, ops.MOVD],
        0,
        120,
        max_results=1,
    )
    checks.append({"name": "find short NOP,MOVD cycle", "ok": bool(cycle_reports)})

    layout_path = Path("tools/hell_lite/examples/layout_echo1.json")
    if layout_path.exists():
        sketch = layout.load_layout(layout_path)
        report = layout.compile_layout_report(sketch)
        checks.append(
            {
                "name": "compile layout_echo1",
                "ok": report.source == "ubO",
                "source": report.source,
            }
        )

    echo_source = Path("fixtures/classic/echo_first_byte.mal").read_bytes()
    echo_result = score.score_candidate(
        source.canonical_source_bytes(echo_source),
        "echo1",
        [0x61, 0xFF],
    )
    checks.append({"name": "score echo fixture", "ok": echo_result.total_correct == 2})

    tail_results = tail_crazy.search_tail_crazy(
        target="xor1",
        max_crazy=1,
        max_results=2,
        inputs=[0x09, 0x30, 0x82],
        max_candidates=200,
    )
    checks.append({"name": "tiny tail-crazy search", "ok": isinstance(tail_results, list)})

    ok = all(bool(item["ok"]) for item in checks)
    print(json.dumps({"ok": ok, "checks": checks}, indent=2, sort_keys=True))
    if not ok:
        raise SystemExit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HeLL-Lite construction helpers")
    sub = parser.add_subparsers(required=True)

    compile_linear = sub.add_parser("compile-linear")
    compile_linear.add_argument("--ops", required=True, help="comma-separated op names")
    compile_linear.set_defaults(func=cmd_compile_linear)

    cycle_parser = sub.add_parser("cycles")
    cycle_parser.add_argument("--address", type=int, required=True)
    cycle_parser.add_argument("--byte", help="optional starting byte, decimal or 0xNN")
    cycle_parser.add_argument("--visits", type=int, default=8)
    cycle_parser.set_defaults(func=cmd_cycles)

    score_parser = sub.add_parser("score")
    score_parser.add_argument("--candidate", required=True)
    score_parser.add_argument("--target", choices=["xor1", "echo1", "finite-map"], required=True)
    score_parser.add_argument("--inputs", default="all")
    score_parser.add_argument("--pairs", help="finite-map byte pairs such as 09:58,30:61")
    score_parser.set_defaults(func=cmd_score)

    tail_parser = sub.add_parser("search-tail-crazy")
    tail_parser.add_argument("--target", choices=["xor1"], default="xor1")
    tail_parser.add_argument("--max-crazy", type=int, default=3)
    tail_parser.add_argument("--max-results", type=int, default=10)
    tail_parser.add_argument("--max-candidates", type=int, default=50000)
    tail_parser.add_argument("--inputs", default="default")
    tail_parser.add_argument("--out", required=True)
    tail_parser.add_argument("--include-known-specimens", action="store_true")
    tail_parser.add_argument("--allow-large-search", action="store_true")
    tail_parser.set_defaults(func=cmd_search_tail_crazy)

    analysis_parser = sub.add_parser("analyze-tail-crazy")
    analysis_parser.add_argument("--target", choices=["xor1"], default="xor1")
    analysis_parser.add_argument("--max-crazy", type=int, default=3)
    analysis_parser.add_argument("--max-candidates", type=int, default=50000)
    analysis_parser.add_argument("--out", required=True)
    analysis_parser.add_argument("--include-known-specimens", action="store_true")
    analysis_parser.add_argument("--allow-large-search", action="store_true")
    analysis_parser.add_argument("--exhaustive", action="store_true")
    analysis_parser.set_defaults(func=cmd_analyze_tail_crazy)

    rust_parser = sub.add_parser("verify-rust")
    rust_parser.add_argument("--candidate", required=True)
    rust_parser.add_argument("--input-hex", required=True)
    rust_parser.add_argument("--repo-root", default=".")
    rust_parser.set_defaults(func=cmd_verify_rust)

    validate_layout = sub.add_parser("validate-layout")
    validate_layout.add_argument("--sketch", required=True)
    validate_layout.set_defaults(func=cmd_validate_layout)

    compile_layout = sub.add_parser("compile-layout")
    compile_layout.add_argument("--sketch", required=True)
    compile_layout.set_defaults(func=cmd_compile_layout)

    find_cycle = sub.add_parser("find-cycle")
    find_cycle.add_argument("--cycle", required=True, help="comma-separated expected op names")
    find_cycle.add_argument("--address-start", type=int, required=True)
    find_cycle.add_argument("--address-end", type=int, required=True)
    find_cycle.add_argument("--max-results", type=int, default=20)
    find_cycle.set_defaults(func=cmd_find_cycle)

    find_unit_cells = sub.add_parser("find-unit-cells")
    find_unit_cells.add_argument("--cycle", required=True, help="comma-separated expected op names")
    find_unit_cells.add_argument("--address-start", type=int, required=True)
    find_unit_cells.add_argument("--address-end", type=int, required=True)
    find_unit_cells.add_argument("--max-results", type=int, default=20)
    find_unit_cells.set_defaults(func=cmd_find_unit_cells)

    target_info = sub.add_parser("target-info")
    target_info.add_argument("--target", choices=["xor1", "echo1", "finite-map"], required=True)
    target_info.add_argument("--inputs", default="all")
    target_info.add_argument("--pairs", help="finite-map byte pairs such as 09:58,30:61")
    target_info.set_defaults(func=cmd_target_info)

    search_routing = sub.add_parser("search-routing")
    search_routing.add_argument("--target", choices=["xor1", "echo1", "finite-map"], required=True)
    search_routing.add_argument("--pairs", help="finite-map byte pairs such as 09:58,30:61")
    search_routing.add_argument("--inputs", help="inputs such as 09,30,82 or all")
    search_routing.add_argument(
        "--template",
        choices=["source-tail-crazy", "linear-op", "route-sketch"],
        required=True,
    )
    search_routing.add_argument("--max-results", type=int, default=10)
    search_routing.add_argument("--max-candidates", type=int, default=10000)
    search_routing.set_defaults(func=cmd_search_routing)

    loop_parser = sub.add_parser("loop-sketch")
    loop_parser.add_argument("--kind", required=True)
    loop_parser.add_argument("--out")
    loop_parser.set_defaults(func=cmd_loop_sketch)

    catalog_parser = sub.add_parser("unit-catalog")
    catalog_parser.add_argument("--names", action="store_true", help="print only built-in unit names")
    catalog_parser.set_defaults(func=cmd_unit_catalog)

    daspc_parser = sub.add_parser("d-as-pc-sketch")
    daspc_parser.add_argument(
        "--kind",
        choices=["input-output-stop", "two-value-branch", "finite-map-sketch"],
        required=True,
    )
    daspc_parser.add_argument("--out")
    daspc_parser.set_defaults(func=cmd_d_as_pc_sketch)

    compile_map = sub.add_parser("compile-finite-map")
    compile_map.add_argument("--pairs", required=True, help="finite-map byte pairs such as 02:53,06:57")
    compile_map.add_argument("--out", required=True)
    compile_map.add_argument("--max-source-length", type=int, default=4096)
    compile_map.add_argument("--seed-candidate")
    compile_map.add_argument("--preserve-candidate")
    compile_map.set_defaults(func=cmd_compile_finite_map)

    list_specimens = sub.add_parser("list-specimens")
    list_specimens.set_defaults(func=cmd_list_specimens)

    compare = sub.add_parser("compare-map")
    compare.add_argument("--candidate", required=True)
    compare.add_argument("--pairs", required=True, help="finite-map byte pairs such as 02:53,06:57")
    compare.add_argument("--trace-ops", type=int, default=0)
    compare.set_defaults(func=cmd_compare_map)


    allocate = sub.add_parser("allocate-branch")
    allocate.add_argument("--map", required=True)
    allocate.add_argument("--seed-candidate", required=True)
    allocate.add_argument("--add-target", required=True)
    allocate.add_argument("--out", required=True)
    allocate.add_argument("--max-candidates", type=int, default=50000)
    allocate.add_argument("--max-edit-sites", type=int, default=16)
    allocate.add_argument("--max-branch-bodies", type=int, default=128)
    allocate.add_argument("--allow-large-search", action="store_true")
    allocate.set_defaults(func=cmd_allocate_branch)

    trace = sub.add_parser("compare-trace")
    trace.add_argument("--candidate", required=True)
    trace.add_argument("--pairs", required=True)
    trace.add_argument("--max-ops", type=int, default=40)
    trace.set_defaults(func=cmd_compare_trace)

    surgeon = sub.add_parser("route-surgeon")
    surgeon.add_argument("--candidate", required=True)
    surgeon.add_argument("--map", required=True)
    surgeon.add_argument("--target")
    surgeon.add_argument("--target-index", type=int)
    surgeon.add_argument("--max-ops", type=int, default=80)
    surgeon.add_argument("--out", required=True)
    surgeon.set_defaults(func=cmd_route_surgeon)

    patch = sub.add_parser("patch-enum")
    patch.add_argument("--candidate", required=True)
    patch.add_argument("--map", required=True)
    patch.add_argument("--target")
    patch.add_argument("--target-index", type=int)
    patch.add_argument("--route-report", required=True)
    patch.add_argument("--out", required=True)
    patch.add_argument("--max-sites", type=int, default=12)
    patch.add_argument("--max-edits", type=int, default=2)
    patch.add_argument("--max-candidates", type=int, default=50000)
    patch.add_argument("--allow-regression", action="store_true")
    patch.set_defaults(func=cmd_patch_enum)

    repair = sub.add_parser("repair-branch")
    repair.add_argument("--map", required=True)
    repair.add_argument("--seed-candidate", required=True)
    repair.add_argument("--target")
    repair.add_argument("--target-index", type=int)
    repair.add_argument("--out", required=True)
    repair.add_argument("--max-sites", type=int, default=12)
    repair.add_argument("--max-edits", type=int, default=2)
    repair.add_argument("--max-candidates", type=int, default=50000)
    repair.set_defaults(func=cmd_repair_branch)

    smoke_parser = sub.add_parser("smoke")
    smoke_parser.set_defaults(func=cmd_smoke)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
