//! Trace capture: the oracle-side log of an attempt session.
//!
//! When `MALBOLGE_RUNGS_TRACE_DIR` is set, every `verify` and `execute`
//! invocation appends one JSON line to `<dir>/oracle-log.jsonl` — timestamp,
//! command, rung, full candidate bytes, canonical hash, and the native
//! outcome. The sequence of evaluator calls is the search trajectory: what was
//! tried, in what order, and what the judge said each time.
//!
//! `trace bundle` packs the log with an optional session transcript and a
//! free-form manifest into a single submittable JSON document (schema
//! `malbolge-rungs.trace-bundle.v1`); `trace submit` posts it to the board's
//! private intake. Traces are collected, not published — see ENVIRONMENT.md.

use std::io::Write as _;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use sha2::{Digest, Sha256};

pub const TRACE_DIR_ENV: &str = "MALBOLGE_RUNGS_TRACE_DIR";
pub const TRACE_SESSION_ENV: &str = "MALBOLGE_RUNGS_TRACE_SESSION";
pub const BUNDLE_SCHEMA: &str = "malbolge-rungs.trace-bundle.v1";
pub const INTAKE_URL: &str = "https://oklo.org/malbolge-api/submit.php";

fn now_iso() -> String {
    // Seconds-precision UTC without a time dependency.
    let out = std::process::Command::new("date")
        .args(["-u", "+%Y-%m-%dT%H:%M:%SZ"])
        .output();
    out.ok()
        .filter(|o| o.status.success())
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
        .unwrap_or_default()
}

fn session_id() -> String {
    std::env::var(TRACE_SESSION_ENV)
        .unwrap_or_else(|_| format!("pid-{}", std::process::id()))
}

/// Append one oracle-call record when tracing is enabled. Failures to write
/// the trace never affect the verification result.
pub fn log_oracle_call(record: serde_json::Value) {
    let Ok(dir) = std::env::var(TRACE_DIR_ENV) else {
        return;
    };
    let dir = PathBuf::from(dir);
    let _ = std::fs::create_dir_all(&dir);
    let mut obj = record;
    if let Some(map) = obj.as_object_mut() {
        map.insert("ts".into(), serde_json::json!(now_iso()));
        map.insert("session".into(), serde_json::json!(session_id()));
    }
    if let Ok(mut f) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(dir.join("oracle-log.jsonl"))
    {
        let _ = writeln!(f, "{}", obj);
    }
}

/// Build a submittable bundle from a trace directory.
pub fn bundle(
    trace_dir: &Path,
    transcript: Option<&Path>,
    manifest_pairs: &[String],
    out: &Path,
) -> Result<()> {
    let log_path = trace_dir.join("oracle-log.jsonl");
    let log_text = std::fs::read_to_string(&log_path)
        .with_context(|| format!("reading {} (was {TRACE_DIR_ENV} set during the run?)",
                                 log_path.display()))?;
    let calls: Vec<serde_json::Value> = log_text
        .lines()
        .filter(|l| !l.trim().is_empty())
        .map(serde_json::from_str)
        .collect::<Result<_, _>>()
        .context("parsing oracle-log.jsonl")?;

    let transcript_text = match transcript {
        Some(p) => Some(
            std::fs::read_to_string(p)
                .with_context(|| format!("reading transcript {}", p.display()))?,
        ),
        None => None,
    };

    let mut manifest = serde_json::Map::new();
    for pair in manifest_pairs {
        let (k, v) = pair
            .split_once('=')
            .with_context(|| format!("manifest entry {pair} must be key=value"))?;
        manifest.insert(k.trim().to_string(), serde_json::json!(v.trim()));
    }

    let bundle = serde_json::json!({
        "schema": BUNDLE_SCHEMA,
        "created": now_iso(),
        "session": session_id(),
        "manifest": manifest,
        "oracle_calls": calls,
        "transcript": transcript_text,
    });
    let text = serde_json::to_string(&bundle)?;
    let sha = hex::encode(Sha256::digest(text.as_bytes()));
    std::fs::write(out, &text).with_context(|| format!("writing {}", out.display()))?;
    println!(
        "bundle: {} calls, {} bytes, sha256 {} -> {}",
        bundle["oracle_calls"].as_array().map(|a| a.len()).unwrap_or(0),
        text.len(),
        sha,
        out.display()
    );
    Ok(())
}

/// Submit a bundle to the private intake. Shells out to `curl`; on any
/// failure, prints instructions for submitting manually.
pub fn submit(bundle_path: &Path) -> Result<bool> {
    let output = std::process::Command::new("curl")
        .args([
            "-sS",
            "--max-time",
            "120",
            "-X",
            "POST",
            "-H",
            "Content-Type: application/json",
            "--data-binary",
            &format!("@{}", bundle_path.display()),
            INTAKE_URL,
        ])
        .output();
    match output {
        Ok(out) if out.status.success() => {
            let body = String::from_utf8_lossy(&out.stdout);
            println!("{}", body.trim());
            Ok(body.contains("\"ok\":true") || body.contains("\"ok\": true"))
        }
        _ => {
            println!(
                "submission failed. Submit manually:\n  curl -X POST -H 'Content-Type: application/json' \\\n    --data-binary @{} {}",
                bundle_path.display(),
                INTAKE_URL
            );
            Ok(false)
        }
    }
}
