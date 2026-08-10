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

/// A trace with fewer than this many oracle calls captures at most a single
/// candidate — not a search. `bundle` warns; `submit` refuses without an
/// explicit override. The usual cause is setting `MALBOLGE_RUNGS_TRACE_DIR`
/// after the attempt ran instead of before it, so the real trajectory was
/// never recorded and the bundle holds one throwaway call.
pub const MIN_TRACE_CALLS: usize = 2;

/// A bundle is "thin" when it records almost no evaluator calls.
pub fn is_thin(oracle_calls: usize) -> bool {
    oracle_calls < MIN_TRACE_CALLS
}

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
/// Restrict a path to owner-only (0700 dir / 0600 file). Traces hold candidate
/// programs and transcripts; on a shared machine they must not be world- or
/// group-readable regardless of the process umask. No-op off Unix.
fn lock_down(path: &Path) {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        if let Ok(meta) = std::fs::metadata(path) {
            let mode = if meta.is_dir() { 0o700 } else { 0o600 };
            let _ = std::fs::set_permissions(path, std::fs::Permissions::from_mode(mode));
        }
    }
}

pub fn log_oracle_call(record: serde_json::Value) {
    let Ok(dir) = std::env::var(TRACE_DIR_ENV) else {
        return;
    };
    let dir = PathBuf::from(dir);
    let _ = std::fs::create_dir_all(&dir);
    lock_down(&dir);
    let mut obj = record;
    if let Some(map) = obj.as_object_mut() {
        map.insert("ts".into(), serde_json::json!(now_iso()));
        map.insert("session".into(), serde_json::json!(session_id()));
    }
    let mut opts = std::fs::OpenOptions::new();
    opts.create(true).append(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        opts.mode(0o600);
    }
    let log = dir.join("oracle-log.jsonl");
    if let Ok(mut f) = opts.open(&log) {
        let _ = writeln!(f, "{}", obj);
        lock_down(&log);
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

    let n_calls = calls.len();
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
    lock_down(out);
    println!(
        "bundle: {} calls, {} bytes, sha256 {} -> {}",
        n_calls,
        text.len(),
        sha,
        out.display()
    );
    if is_thin(n_calls) {
        eprintln!(
            "warning: captured only {n_calls} evaluator call{}. A useful trace \
             records the whole search — every verify/execute during the attempt. \
             If you expected more, {} was not set before the attempt ran; set it \
             first, redo the attempt, then bundle again.",
            if n_calls == 1 { "" } else { "s" },
            TRACE_DIR_ENV,
        );
    }
    Ok(())
}

/// Count the oracle calls recorded in a built bundle file.
fn bundle_call_count(bundle_path: &Path) -> Result<usize> {
    let text = std::fs::read_to_string(bundle_path)
        .with_context(|| format!("reading bundle {}", bundle_path.display()))?;
    let value: serde_json::Value = serde_json::from_str(&text)
        .with_context(|| format!("parsing bundle {}", bundle_path.display()))?;
    Ok(value
        .get("oracle_calls")
        .and_then(|c| c.as_array())
        .map(|a| a.len())
        .unwrap_or(0))
}

/// Submit a bundle to the private intake. Shells out to `curl`; on any
/// failure, prints instructions for submitting manually.
///
/// A near-empty bundle (see [`MIN_TRACE_CALLS`]) is refused before the POST
/// unless `allow_thin` is set: it captures none of a search, and letting it
/// through would hand back an `"ok":true` receipt for a trace that records
/// nothing — the failure this guard exists to make loud.
pub fn submit(bundle_path: &Path, allow_thin: bool) -> Result<bool> {
    let calls = bundle_call_count(bundle_path)?;
    if is_thin(calls) && !allow_thin {
        println!(
            "refusing to submit: this bundle has only {calls} evaluator call{}, so \
             it captures essentially none of an attempt. Set {} before your run \
             and redo the attempt so the search is recorded, then bundle and submit \
             again. To submit this thin bundle anyway, pass --allow-thin.",
            if calls == 1 { "" } else { "s" },
            TRACE_DIR_ENV,
        );
        return Ok(false);
    }
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn thin_boundary_is_two_calls() {
        assert!(is_thin(0));
        assert!(is_thin(1));
        assert!(!is_thin(2));
        assert!(!is_thin(50));
    }

    #[test]
    fn bundle_call_count_reads_the_array() {
        let dir = std::env::temp_dir().join(format!("mbtrace-test-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let p = dir.join("b.json");

        std::fs::write(&p, r#"{"oracle_calls":[{"cmd":"verify"},{"cmd":"execute"}]}"#).unwrap();
        assert_eq!(bundle_call_count(&p).unwrap(), 2);

        std::fs::write(&p, r#"{"oracle_calls":[]}"#).unwrap();
        assert_eq!(bundle_call_count(&p).unwrap(), 0);

        // A malformed or field-less bundle counts as zero, not an error path
        // that would let a thin submit slip through.
        std::fs::write(&p, r#"{"schema":"x"}"#).unwrap();
        assert_eq!(bundle_call_count(&p).unwrap(), 0);

        let _ = std::fs::remove_dir_all(&dir);
    }
}
