//! `malbolge-rungs` CLI: inspect the rung registry, verify a candidate program
//! against a rung on the native VM, and render / re-verify the leaderboard.

use std::process::ExitCode;

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};

use classic_malbolge::{
    ClassicExecutionLimits, ClassicMalbolge51Profile, ClassicMalbolgeExecutor, NativeClassicBackend,
};
use sha2::Digest as _;

use harness::attempts::{load_attempts, validate_attempts};
use harness::trace;
use harness::dispatch::feasibility;
use harness::generate::{generate_coverage, generate_finite_map, RangeClass, TransformArg};
use harness::leaderboard::{load_leaderboard, render_markdown, verify_leaderboard, Status};
use harness::registry::{find_rung, load_registry};
use harness::types::Rung;
use harness::verify::verify_rung;

/// Stable schema tag on `verify --json` output.
const VERIFY_SCHEMA: &str = "malbolge-rungs.verify.v1";
/// Stable schema tag on `feasibility --json` output.
const FEASIBILITY_SCHEMA: &str = "malbolge-rungs.feasibility.v1";

#[derive(Parser)]
#[command(
    name = "malbolge-rungs",
    about = "MAL-51 rung registry + native-VM verification harness"
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// List every rung in the ladder.
    Registry {
        #[command(subcommand)]
        what: RegistryCmd,
    },
    /// Run a program once on the native VM and print the result as JSON.
    Execute {
        /// Path to the classic-Malbolge program.
        #[arg(long)]
        program: String,
        /// Input bytes as hex (e.g. `02`).
        #[arg(long, default_value = "")]
        input_hex: String,
    },
    /// Verify candidate program(s) against a rung on the native VM.
    Verify {
        /// Rung id from the registry, e.g. L2.FM1.xor51-map4.
        #[arg(long, conflicts_with = "rung_file")]
        rung: Option<String>,
        /// Path to a rung JSON file (e.g. produced by `generate-rung`).
        #[arg(long)]
        rung_file: Option<String>,
        /// Path(s) to candidate classic-Malbolge program(s). Repeat the flag
        /// to verify a batch in one invocation.
        #[arg(long, required = true, num_args = 1)]
        program: Vec<String>,
        /// Number of deterministic seed epochs to run (all must pass).
        #[arg(long, default_value_t = 1)]
        epochs: u32,
        /// Print every case, not just the summary.
        #[arg(long)]
        verbose: bool,
        /// Emit the full outcome as stable JSON (schema malbolge-rungs.verify.v1)
        /// instead of human-readable text.
        #[arg(long)]
        json: bool,
    },
    /// Bundle or submit a capture of this session's evaluator calls.
    /// Enable capture by setting MALBOLGE_RUNGS_TRACE_DIR before running
    /// verify/execute; see ENVIRONMENT.md ("Leave a trace").
    Trace {
        #[command(subcommand)]
        what: TraceCmd,
    },
    /// List or validate the structured attempt records in docs/attempts/.
    Attempts {
        #[command(subcommand)]
        what: AttemptsCmd,
    },
    /// Mint a procedural rung instance as JSON (loadable via `verify --rung-file`).
    GenerateRung {
        #[command(subcommand)]
        what: GenerateCmd,
    },
    /// Score an input set's dispatch feasibility (a cheap difficulty estimate
    /// for finite-map instances).
    Feasibility {
        /// Comma-separated input bytes as hex, e.g. `02,06,09,30`.
        #[arg(long, conflicts_with_all = ["rung", "rung_file"])]
        inputs: Option<String>,
        /// Score a registry rung's finite-map inputs.
        #[arg(long)]
        rung: Option<String>,
        /// Score a rung JSON file's finite-map inputs.
        #[arg(long, conflicts_with = "rung")]
        rung_file: Option<String>,
        /// Emit JSON (schema malbolge-rungs.feasibility.v1).
        #[arg(long)]
        json: bool,
    },
    /// Show the leaderboard.
    Leaderboard {
        /// Render as a Markdown table.
        #[arg(long)]
        render: Option<String>,
    },
    /// Re-verify every claimed leaderboard solution on the native VM.
    VerifyLeaderboard {
        #[arg(long, default_value_t = 1)]
        epochs: u32,
    },
    /// Generate the static leaderboard website (re-verifies every claimed
    /// solution natively first; fails rather than publish a stale claim).
    Site {
        /// Output directory for the generated site.
        #[arg(long, default_value = "_site")]
        out: String,
        #[arg(long, default_value_t = 3)]
        epochs: u32,
    },
}

#[derive(Subcommand)]
enum TraceCmd {
    /// Pack the oracle log, an optional transcript, and manifest key=value
    /// pairs into one submittable JSON bundle.
    Bundle {
        /// Trace directory (defaults to $MALBOLGE_RUNGS_TRACE_DIR).
        #[arg(long)]
        dir: Option<String>,
        /// Session transcript file to embed (strongly encouraged — it is the
        /// reasoning half of the trace).
        #[arg(long)]
        transcript: Option<String>,
        /// Free-form provenance, repeatable: --manifest model=... --manifest tokens=...
        #[arg(long = "manifest")]
        manifest: Vec<String>,
        #[arg(long, default_value = "trace-bundle.json")]
        out: String,
    },
    /// Submit a bundle to the board's private intake.
    Submit {
        #[arg(long, default_value = "trace-bundle.json")]
        bundle: String,
        /// Submit even when the bundle captured almost no evaluator calls — a
        /// trace that records none of the search. Off by default so a run that
        /// forgot to set MALBOLGE_RUNGS_TRACE_DIR cannot silently submit nothing.
        #[arg(long)]
        allow_thin: bool,
    },
}

#[derive(Subcommand)]
enum AttemptsCmd {
    /// List every attempt record.
    List,
    /// Validate every record; re-runs claimed best candidates natively.
    Validate,
}

#[derive(Subcommand)]
enum GenerateCmd {
    /// A finite-map instance: k distinct seeded input bytes, one output byte each.
    FiniteMap {
        /// Number of input bytes (2..=32).
        #[arg(long)]
        k: usize,
        /// Byte-range class. Low-byte sets are structurally harder for
        /// crz-dispatch than high-byte sets.
        #[arg(long, value_enum, default_value_t = RangeClass::Mixed)]
        range: RangeClass,
        /// Generator seed; the same seed always yields the same instance.
        #[arg(long, default_value_t = 0)]
        seed: u64,
        /// Per-byte transform the program must compute.
        #[arg(long, value_enum, default_value_t = TransformArg::Xor51)]
        transform: TransformArg,
        /// Program-length cap in bytes (default scales with k: 256·k, clamped
        /// to 512..=4096, matching the registry ladder).
        #[arg(long)]
        max_program_len: Option<u64>,
        /// Step cap per case.
        #[arg(long, default_value_t = 2048)]
        max_steps_per_case: u64,
        /// Skip the dispatch-feasibility difficulty estimate.
        #[arg(long)]
        skip_feasibility: bool,
        /// Write the rung JSON here instead of stdout.
        #[arg(long)]
        out: Option<String>,
    },
    /// A coverage instance: all 256 single-byte inputs, pass at a threshold.
    Coverage {
        /// Minimum correct cases out of 256 required to pass.
        #[arg(long)]
        threshold: u32,
        /// Per-byte transform the program must compute.
        #[arg(long, value_enum, default_value_t = TransformArg::Xor51)]
        transform: TransformArg,
        #[arg(long, default_value_t = 4096)]
        max_program_len: u64,
        #[arg(long, default_value_t = 2048)]
        max_steps_per_case: u64,
        /// Write the rung JSON here instead of stdout.
        #[arg(long)]
        out: Option<String>,
    },
}

#[derive(Subcommand)]
enum RegistryCmd {
    /// List all rung ids with family/transform/case summary.
    List,
    /// Show one rung as JSON-ish detail.
    Show {
        #[arg(long)]
        rung: String,
    },
}

fn main() -> ExitCode {
    match run() {
        Ok(code) => code,
        Err(err) => {
            eprintln!("error: {err:#}");
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<ExitCode> {
    let cli = Cli::parse();
    match cli.command {
        Command::Registry { what } => {
            registry_cmd(what);
            Ok(ExitCode::SUCCESS)
        }
        Command::Execute {
            program,
            input_hex,
        } => cmd_execute(&program, &input_hex),
        Command::Verify {
            rung,
            rung_file,
            program,
            epochs,
            verbose,
            json,
        } => cmd_verify(rung.as_deref(), rung_file.as_deref(), &program, epochs, verbose, json),
        Command::Trace { what } => cmd_trace(what),
        Command::Attempts { what } => cmd_attempts(what),
        Command::GenerateRung { what } => cmd_generate(what),
        Command::Feasibility {
            inputs,
            rung,
            rung_file,
            json,
        } => cmd_feasibility(inputs.as_deref(), rung.as_deref(), rung_file.as_deref(), json),
        Command::Leaderboard { render } => {
            cmd_leaderboard(render.as_deref());
            Ok(ExitCode::SUCCESS)
        }
        Command::VerifyLeaderboard { epochs } => cmd_verify_leaderboard(epochs),
        Command::Site { out, epochs } => {
            harness::site::generate_site(std::path::Path::new(&out), epochs)?;
            Ok(ExitCode::SUCCESS)
        }
    }
}

fn registry_cmd(what: RegistryCmd) {
    match what {
        RegistryCmd::List => {
            for r in load_registry() {
                let extra = if !r.finite_map_inputs.is_empty() {
                    format!(
                        "  inputs={:?}",
                        r.finite_map_inputs
                            .iter()
                            .map(|b| format!("{b:02x}"))
                            .collect::<Vec<_>>()
                    )
                } else if let Some(m) = r.min_correct_cases {
                    format!("  min_correct={m}/{}", r.cases)
                } else {
                    String::new()
                };
                println!(
                    "{:<32} L{} {:<17} {:<10} cases={}{}",
                    r.id,
                    r.level,
                    format!("{:?}", r.family),
                    format!("{:?}", r.transform),
                    r.cases,
                    extra
                );
            }
        }
        RegistryCmd::Show { rung } => match find_rung(&rung) {
            Some(r) => {
                println!("id:               {}", r.id);
                println!("title:            {}", r.title);
                println!("level:            {}", r.level);
                println!("status:           {}", r.status);
                println!("family:           {:?}", r.family);
                println!("transform:        {:?}", r.transform);
                if !r.finite_map_inputs.is_empty() {
                    println!(
                        "finite_map_inputs: {:?}",
                        r.finite_map_inputs
                            .iter()
                            .map(|b| format!("0x{b:02x}"))
                            .collect::<Vec<_>>()
                    );
                }
                if let Some(m) = r.min_correct_cases {
                    println!("min_correct_cases: {m}");
                }
                println!("output_bytes:     {}", r.output_bytes);
                println!("cases:            {}", r.cases);
                println!("max_program_len:  {}", r.max_program_len);
                println!("max_steps_per_case: {}", r.max_steps_per_case);
                println!("max_output_len:   {}", r.max_output_len);
                println!("max_memory_cells: {}", r.max_memory_cells);
                if !r.purpose.is_empty() {
                    println!("purpose:          {}", r.purpose);
                }
            }
            None => eprintln!("unknown rung: {rung}"),
        },
    }
}

fn cmd_execute(program: &str, input_hex: &str) -> Result<ExitCode> {
    let bytes = std::fs::read(program).with_context(|| format!("reading program {program}"))?;
    let input = hex::decode(input_hex.trim()).context("decoding --input-hex")?;
    let limits = ClassicExecutionLimits::from(&ClassicMalbolge51Profile::default());
    let report = NativeClassicBackend
        .execute(&bytes, &input, &limits)
        .context("native execution")?;
    // JSON compatible with the source `classic execute` output, so downstream
    // diagnostic tooling (tools/hell_lite) can parse it.
    let json = serde_json::json!({
        "output": report.output,
        "output_hex": hex::encode(&report.output),
        "steps": report.steps,
        "memory_used_cells": report.memory_used_cells,
        "status": format!("{:?}", report.status),
        "backend_kind": format!("{:?}", report.backend_kind),
    });
    trace::log_oracle_call(serde_json::json!({
        "cmd": "execute",
        "input_hex": input_hex.trim(),
        "program_hex": hex::encode(&bytes),
        "canonical_sha256": hex::encode(sha2::Sha256::digest(
            classic_malbolge::canonicalize_fixture_source(&bytes)
                .unwrap_or_else(|_| bytes.clone()))),
        "steps": report.steps,
        "status": format!("{:?}", report.status),
        "output_hex": hex::encode(&report.output),
    }));
    println!("{}", serde_json::to_string_pretty(&json)?);
    Ok(ExitCode::SUCCESS)
}

/// Resolve the rung either from the embedded registry (`--rung`) or from a
/// JSON rung file (`--rung-file`, e.g. minted by `generate-rung`).
fn load_rung_arg(rung_id: Option<&str>, rung_file: Option<&str>) -> Result<Rung> {
    match (rung_id, rung_file) {
        (Some(id), None) => find_rung(id).with_context(|| format!("unknown rung: {id}")),
        (None, Some(path)) => {
            let text = std::fs::read_to_string(path)
                .with_context(|| format!("reading rung file {path}"))?;
            serde_json::from_str(&text).with_context(|| format!("parsing rung file {path}"))
        }
        _ => anyhow::bail!("pass exactly one of --rung or --rung-file"),
    }
}

fn cmd_verify(
    rung_id: Option<&str>,
    rung_file: Option<&str>,
    programs: &[String],
    epochs: u32,
    verbose: bool,
    json: bool,
) -> Result<ExitCode> {
    let rung = load_rung_arg(rung_id, rung_file)?;
    let mut all_passed = true;
    let mut json_results = Vec::new();

    for program in programs {
        let bytes =
            std::fs::read(program).with_context(|| format!("reading program {program}"))?;
        let outcome = verify_rung(&rung, &bytes, epochs);
        all_passed &= outcome.passed;
        trace::log_oracle_call(serde_json::json!({
            "cmd": "verify",
            "rung": rung.id,
            "program_hex": hex::encode(&bytes),
            "canonical_sha256": hex::encode(sha2::Sha256::digest(
                classic_malbolge::canonicalize_fixture_source(&bytes)
                    .unwrap_or_else(|_| bytes.clone()))),
            "epochs": epochs,
            "passed": outcome.passed,
            "correct": outcome.epochs.iter().map(|e| e.correct_cases).min(),
            "total": outcome.epochs.first().map(|e| e.total_cases),
        }));

        if json {
            json_results.push(serde_json::json!({
                "program": program,
                "program_sha256": hex::encode(sha2::Sha256::digest(&bytes)),
                "program_len": bytes.len(),
                "outcome": outcome,
            }));
            continue;
        }

        println!(
            "rung: {}  ({:?} / {:?})  program: {}",
            outcome.rung_id, rung.family, rung.transform, program
        );
        for ep in &outcome.epochs {
            if outcome.coverage {
                println!(
                    "  epoch {} seed={}…  {}/{} correct (>= {} required)  {}",
                    ep.epoch,
                    &ep.seed_hex[..8],
                    ep.correct_cases,
                    ep.total_cases,
                    outcome.required_correct,
                    if ep.passed { "PASS" } else { "FAIL" }
                );
            } else {
                println!(
                    "  epoch {} seed={}…  {}/{} cases  {}",
                    ep.epoch,
                    &ep.seed_hex[..8],
                    ep.correct_cases,
                    ep.total_cases,
                    if ep.passed { "PASS" } else { "FAIL" }
                );
            }
            if let Some(f) = &ep.failure {
                println!("    reason: {f}");
            }
            if verbose {
                for c in &ep.cases {
                    println!(
                        "    case {:>3}: in={} exp={} got={} [{}] {}",
                        c.index,
                        c.input_hex,
                        c.expected_hex,
                        c.observed_hex.as_deref().unwrap_or("<none>"),
                        c.status,
                        if c.correct { "ok" } else { "MISS" }
                    );
                }
            }
        }
        println!(
            "RESULT: {} (native evaluator)",
            if outcome.passed { "PASS" } else { "FAIL" }
        );
    }

    if json {
        let envelope = serde_json::json!({
            "schema": VERIFY_SCHEMA,
            "rung_id": rung.id,
            "epochs": epochs,
            "all_passed": all_passed,
            "results": json_results,
        });
        println!("{}", serde_json::to_string_pretty(&envelope)?);
    }
    Ok(if all_passed {
        ExitCode::SUCCESS
    } else {
        ExitCode::FAILURE
    })
}

fn write_generated(json: String, out: Option<&str>) -> Result<()> {
    match out {
        Some(path) => {
            std::fs::write(path, json.as_bytes()).with_context(|| format!("writing {path}"))?;
            eprintln!("wrote {path}");
        }
        None => println!("{json}"),
    }
    Ok(())
}

fn cmd_trace(what: TraceCmd) -> Result<ExitCode> {
    match what {
        TraceCmd::Bundle { dir, transcript, manifest, out } => {
            let dir = dir
                .or_else(|| std::env::var(harness::trace::TRACE_DIR_ENV).ok())
                .context("pass --dir or set MALBOLGE_RUNGS_TRACE_DIR")?;
            trace::bundle(
                std::path::Path::new(&dir),
                transcript.as_deref().map(std::path::Path::new),
                &manifest,
                std::path::Path::new(&out),
            )?;
            Ok(ExitCode::SUCCESS)
        }
        TraceCmd::Submit { bundle, allow_thin } => {
            let ok = trace::submit(std::path::Path::new(&bundle), allow_thin)?;
            Ok(if ok { ExitCode::SUCCESS } else { ExitCode::FAILURE })
        }
    }
}

fn cmd_attempts(what: AttemptsCmd) -> Result<ExitCode> {
    match what {
        AttemptsCmd::List => {
            for a in load_attempts() {
                println!(
                    "{:<12} {:<32} {:<9} {}",
                    a.date,
                    a.rung_id,
                    a.outcome,
                    a.solver.as_ref().map(|s| s.display.as_str()).unwrap_or("—"),
                );
            }
            Ok(ExitCode::SUCCESS)
        }
        AttemptsCmd::Validate => {
            let (results, all_ok) = validate_attempts();
            if results.is_empty() {
                println!("no attempt records");
            }
            for r in &results {
                println!("[{}] {}  ({})", if r.ok { "PASS" } else { "FAIL" }, r.file, r.detail);
            }
            Ok(if all_ok { ExitCode::SUCCESS } else { ExitCode::FAILURE })
        }
    }
}

fn cmd_generate(what: GenerateCmd) -> Result<ExitCode> {
    let (generated, out) = match what {
        GenerateCmd::FiniteMap {
            k,
            range,
            seed,
            transform,
            max_program_len,
            max_steps_per_case,
            skip_feasibility,
            out,
        } => (
            generate_finite_map(
                k,
                range,
                seed,
                transform,
                max_program_len,
                max_steps_per_case,
                skip_feasibility,
            )?,
            out,
        ),
        GenerateCmd::Coverage {
            threshold,
            transform,
            max_program_len,
            max_steps_per_case,
            out,
        } => (
            generate_coverage(threshold, transform, max_program_len, max_steps_per_case)?,
            out,
        ),
    };
    let json = serde_json::to_string_pretty(&generated)?;
    write_generated(json, out.as_deref())?;
    Ok(ExitCode::SUCCESS)
}

fn cmd_feasibility(
    inputs: Option<&str>,
    rung_id: Option<&str>,
    rung_file: Option<&str>,
    json: bool,
) -> Result<ExitCode> {
    let bytes: Vec<u8> = if let Some(list) = inputs {
        list.split(',')
            .map(|s| u8::from_str_radix(s.trim(), 16).with_context(|| format!("bad hex byte {s}")))
            .collect::<Result<_>>()?
    } else {
        let rung = load_rung_arg(rung_id, rung_file)?;
        anyhow::ensure!(
            !rung.finite_map_inputs.is_empty(),
            "{} has no finite-map inputs; feasibility scoring applies to FiniteMap rungs",
            rung.id
        );
        rung.finite_map_inputs.clone()
    };
    anyhow::ensure!(bytes.len() >= 2, "need at least two input bytes");

    let report = feasibility(&bytes);
    if json {
        let envelope = serde_json::json!({
            "schema": FEASIBILITY_SCHEMA,
            "report": report,
            "difficulty_class": report.difficulty_class(),
        });
        println!("{}", serde_json::to_string_pretty(&envelope)?);
    } else {
        println!(
            "inputs: {}",
            report
                .inputs
                .iter()
                .map(|b| format!("{b:02x}"))
                .collect::<Vec<_>>()
                .join(",")
        );
        println!("dispatch configs enumerated: {}", report.configs_enumerated);
        println!("separating configs:          {}", report.separating_configs);
        if let Some(g) = report.best_min_gap {
            println!("best min landing gap:        {g}");
        }
        if let Some(s) = report.widest_spread {
            println!("widest landing spread:       {s}");
        }
        println!("difficulty class:            {}", report.difficulty_class());
    }
    Ok(ExitCode::SUCCESS)
}

fn cmd_leaderboard(render: Option<&str>) {
    match render {
        Some("md") | Some("markdown") => print!("{}", render_markdown()),
        _ => {
            for r in load_leaderboard() {
                let status = match r.status {
                    Status::Solved => "solved",
                    Status::Open => "open",
                    Status::Unverified => "unverified",
                };
                println!(
                    "{:<32} {:<11} {:<20} {}",
                    r.rung_id,
                    status,
                    r.solver.as_ref().map(|s| s.display.as_str()).unwrap_or("—"),
                    r.metric.as_deref().unwrap_or("—"),
                );
            }
        }
    }
}

fn cmd_verify_leaderboard(epochs: u32) -> Result<ExitCode> {
    let (results, all_ok) = verify_leaderboard(epochs);
    if results.is_empty() {
        println!("no `solved` records to verify");
    }
    for r in &results {
        println!(
            "[{}] {:<32} {}  ({})",
            if r.passed { "PASS" } else { "FAIL" },
            r.rung_id,
            r.program,
            r.detail
        );
    }
    if all_ok {
        println!("\nverify-leaderboard: OK — every claimed solution re-verified on the native VM");
        Ok(ExitCode::SUCCESS)
    } else {
        println!("\nverify-leaderboard: FAILED — a claimed solution no longer passes");
        Ok(ExitCode::FAILURE)
    }
}
