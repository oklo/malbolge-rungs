//! `malbolge-rungs` CLI: inspect the rung registry, verify a candidate program
//! against a rung on the native VM, and render / re-verify the leaderboard.

use std::process::ExitCode;

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};

use classic_malbolge::{
    ClassicExecutionLimits, ClassicMalbolge51Profile, ClassicMalbolgeExecutor, NativeClassicBackend,
};
use harness::leaderboard::{load_leaderboard, render_markdown, verify_leaderboard, Status};
use harness::registry::{find_rung, load_registry};
use harness::verify::verify_rung;

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
    /// Verify a candidate program against a rung on the native VM.
    Verify {
        /// Rung id, e.g. L2.FM1.xor51-map4.
        #[arg(long)]
        rung: String,
        /// Path to the candidate classic-Malbolge program.
        #[arg(long)]
        program: String,
        /// Number of deterministic seed epochs to run (all must pass).
        #[arg(long, default_value_t = 1)]
        epochs: u32,
        /// Print every case, not just the summary.
        #[arg(long)]
        verbose: bool,
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
            program,
            epochs,
            verbose,
        } => cmd_verify(&rung, &program, epochs, verbose),
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
    println!("{}", serde_json::to_string_pretty(&json)?);
    Ok(ExitCode::SUCCESS)
}

fn cmd_verify(rung_id: &str, program: &str, epochs: u32, verbose: bool) -> Result<ExitCode> {
    let rung = find_rung(rung_id).with_context(|| format!("unknown rung: {rung_id}"))?;
    let bytes = std::fs::read(program).with_context(|| format!("reading program {program}"))?;
    let outcome = verify_rung(&rung, &bytes, epochs);

    println!(
        "rung: {}  ({:?} / {:?})",
        outcome.rung_id, rung.family, rung.transform
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
    if outcome.passed {
        println!("RESULT: PASS ({} epoch(s), native evaluator)", outcome.epochs.len());
        Ok(ExitCode::SUCCESS)
    } else {
        println!("RESULT: FAIL");
        Ok(ExitCode::FAILURE)
    }
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
                    "{:<32} {:<11} {:<8} {}",
                    r.rung_id,
                    status,
                    r.solver.as_deref().unwrap_or("—"),
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
