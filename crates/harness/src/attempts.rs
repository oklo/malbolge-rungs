//! Structured attempt records: the machine-readable log of serious attempts
//! at board rungs, successful or not (`docs/attempts/*.json`, schema
//! `malbolge-rungs.attempt.v1`).
//!
//! The board's leaderboard records wins; attempt records keep the rest —
//! method, consumed budget, and the best candidate reached. A record that
//! claims a best-candidate score names the program file, and validation
//! re-runs it on the native VM and rejects the record if the claimed per-case
//! score is not exactly what the evaluator observes. Failed traces therefore
//! carry the same evidentiary weight as solves, which is what makes the
//! accumulated corpus usable as training or evaluation data.

use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};

use crate::leaderboard::Solver;
use crate::registry::find_rung;
use crate::verify::verify_rung;

const REPO_ROOT: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../..");

pub const ATTEMPT_SCHEMA: &str = "malbolge-rungs.attempt.v1";
/// A submittable attempt bundle: the record plus its report and artifact
/// contents, POSTed to the private intake (no PR, no auth).
pub const ATTEMPT_BUNDLE_SCHEMA: &str = "malbolge-rungs.attempt-bundle.v1";
pub const ATTEMPT_INTAKE_URL: &str = "https://oklo.org/malbolge-api/attempt.php";

/// One structured attempt record. Serializing this type is the corpus API's
/// public DTO: only these known fields are emitted, so unknown fields present
/// in a submitted record never reach the API.
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct AttemptRecord {
    pub schema: String,
    pub rung_id: String,
    /// ISO date of the attempt.
    pub date: String,
    /// "solved" or "unsolved". Solved attempts are the method record behind a
    /// leaderboard claim; unsolved attempts are the negative-trace corpus.
    pub outcome: String,
    #[serde(default)]
    pub solver: Option<Solver>,
    /// One-to-three sentences: method and where it stopped.
    #[serde(default)]
    pub summary: Option<String>,
    /// Free-form run provenance (model version, tokens, wall time, ...).
    #[serde(default)]
    pub manifest: Option<serde_json::Map<String, serde_json::Value>>,
    /// Free-form search budget (configurations, nodes, wall seconds, ...).
    #[serde(default)]
    pub budget: Option<serde_json::Map<String, serde_json::Value>>,
    /// The best program the attempt reached, with its claimed native score.
    /// Validation re-runs it and requires an exact match.
    #[serde(default)]
    pub best_candidate: Option<BestCandidate>,
    /// Repo-relative path of the narrative report, if one exists.
    #[serde(default)]
    pub report: Option<String>,
    /// Repo-relative paths of further artifacts (logs, candidate sets, ...).
    #[serde(default)]
    pub artifacts: Vec<String>,
    /// Repo-relative paths of prior attempt records this attempt built on — the
    /// lineage that makes the corpus's compounding visible and credits the chain.
    #[serde(default)]
    pub builds_on: Vec<String>,
    /// Record file path (filled at load time; never read from the JSON, but
    /// emitted as `file` in the API DTO).
    #[serde(skip_deserializing, rename = "file")]
    pub path: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct BestCandidate {
    /// Repo-relative path of the candidate program.
    pub program: String,
    pub claimed_correct_cases: u32,
    pub claimed_total_cases: u32,
}

fn attempts_dir() -> PathBuf {
    PathBuf::from(REPO_ROOT).join("docs/attempts")
}

/// Load every attempt record, sorted by file name (dates sort naturally).
pub fn load_attempts() -> Vec<AttemptRecord> {
    let mut out = Vec::new();
    let Ok(entries) = std::fs::read_dir(attempts_dir()) else {
        return out;
    };
    let mut paths: Vec<PathBuf> = entries
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.extension().is_some_and(|x| x == "json"))
        .collect();
    paths.sort();
    for path in paths {
        let text = match std::fs::read_to_string(&path) {
            Ok(t) => t,
            Err(_) => continue,
        };
        match serde_json::from_str::<AttemptRecord>(&text) {
            Ok(mut rec) => {
                rec.path = path
                    .strip_prefix(REPO_ROOT)
                    .unwrap_or(&path)
                    .to_string_lossy()
                    .trim_start_matches('/')
                    .to_string();
                out.push(rec);
            }
            Err(_) => {
                // Unparseable records still surface: validate() reports them.
            }
        }
    }
    out
}

pub struct AttemptValidation {
    pub file: String,
    pub ok: bool,
    pub detail: String,
}

/// Validate every record: schema tag, known rung, sane outcome, existing
/// referenced files, and — when a best candidate is claimed — an exact match
/// between the claimed score and a fresh native run.
pub fn validate_attempts() -> (Vec<AttemptValidation>, bool) {
    let mut results = Vec::new();
    let mut all_ok = true;
    let root = PathBuf::from(REPO_ROOT);

    // Report unparseable json files explicitly.
    if let Ok(entries) = std::fs::read_dir(attempts_dir()) {
        for path in entries.filter_map(|e| e.ok().map(|e| e.path())) {
            if path.extension().is_some_and(|x| x == "json") {
                let text = std::fs::read_to_string(&path).unwrap_or_default();
                if serde_json::from_str::<AttemptRecord>(&text).is_err() {
                    all_ok = false;
                    results.push(AttemptValidation {
                        file: path.to_string_lossy().to_string(),
                        ok: false,
                        detail: "does not parse as an attempt record".to_string(),
                    });
                }
            }
        }
    }

    for rec in load_attempts() {
        let problems = validate_record(&root, &rec);
        let ok = problems.is_empty();
        if !ok {
            all_ok = false;
        }
        results.push(AttemptValidation {
            file: rec.path.clone(),
            ok,
            detail: if ok {
                match &rec.best_candidate {
                    Some(c) => format!(
                        "{} · best candidate verified {}/{}",
                        rec.outcome, c.claimed_correct_cases, c.claimed_total_cases
                    ),
                    None => rec.outcome.clone(),
                }
            } else {
                problems.join("; ")
            },
        });
    }
    (results, all_ok)
}

/// Validate one record against a repository root — the same checks
/// `validate_attempts` runs, exposed for the admission path.
pub fn validate_record_at(root: &Path, rec: &AttemptRecord) -> Vec<String> {
    validate_record(root, rec)
}

/// Validate one record; returns its problems (empty = valid). Schema tag, known
/// rung, sane outcome, referenced files contained in the repo, and — when a best
/// candidate is claimed — an exact match between the claimed score and a fresh
/// native run.
fn validate_record(root: &Path, rec: &AttemptRecord) -> Vec<String> {
    let mut problems = Vec::new();
    if rec.schema != ATTEMPT_SCHEMA {
        problems.push(format!("schema must be {ATTEMPT_SCHEMA}"));
    }
    if rec.outcome != "solved" && rec.outcome != "unsolved" {
        problems.push("outcome must be \"solved\" or \"unsolved\"".to_string());
    }
    let rung = find_rung(&rec.rung_id);
    if rung.is_none() {
        problems.push(format!("unknown rung {}", rec.rung_id));
    }
    if let Some(report) = &rec.report {
        if let Err(e) = crate::fspath::resolve_within_repo(root, report) {
            problems.push(format!("report {e}"));
        }
    }
    for artifact in &rec.artifacts {
        if let Err(e) = crate::fspath::resolve_within_repo(root, artifact) {
            problems.push(format!("artifact {e}"));
        }
    }
    for prior in &rec.builds_on {
        if let Err(e) = crate::fspath::resolve_within_repo(root, prior) {
            problems.push(format!("builds_on {e}"));
        }
    }
    if let (Some(cand), Some(rung)) = (&rec.best_candidate, &rung) {
        match crate::fspath::resolve_within_repo(root, &cand.program) {
            Err(e) => problems.push(format!("candidate {e}")),
            Ok(safe_path) => match std::fs::read(&safe_path) {
                Err(_) => problems.push(format!("candidate {} does not exist", cand.program)),
                Ok(program) => {
                    let outcome = verify_rung(rung, &program, 1);
                    let ep = &outcome.epochs[0];
                    if ep.correct_cases != cand.claimed_correct_cases
                        || ep.total_cases != cand.claimed_total_cases
                    {
                        problems.push(format!(
                            "claimed {}/{} but the native VM observes {}/{}",
                            cand.claimed_correct_cases,
                            cand.claimed_total_cases,
                            ep.correct_cases,
                            ep.total_cases
                        ));
                    }
                }
            },
        }
    }
    problems
}

/// Per-file and whole-bundle size cap; matches the intake's cap so a bundle the
/// server would reject is caught before it is even built, and no single file is
/// read into memory unbounded.
const MAX_BUNDLE_BYTES: u64 = 8 * 1024 * 1024;

/// Bundle a validated attempt record with its report and referenced artifacts
/// and POST it to the private intake — no PR, no auth. This is the frictionless
/// path for a sandboxed agent that produced a record it can't open a PR for.
///
/// Refuses to submit a record that does not validate. The record itself and
/// every report/artifact is read through the hardened opener
/// ([`crate::fspath::open_within_repo`]): inside the repo, a regular file, not a
/// symlink and not a hard link — so a crafted record cannot make this read (and
/// exfiltrate) a file outside the repo, and each read is size-capped before
/// allocation. The bundle is streamed to curl on stdin, so no temporary file is
/// created.
pub fn submit_attempt(record_path: &Path) -> Result<bool> {
    let root = PathBuf::from(REPO_ROOT);
    let root_canon = root.canonicalize().context("resolving repository root")?;

    // The record must resolve inside the repo before it is read, and is read
    // through the same hardened opener as its artifacts.
    let rec_canon = record_path
        .canonicalize()
        .with_context(|| format!("{} does not exist", record_path.display()))?;
    if !rec_canon.starts_with(&root_canon) {
        anyhow::bail!("record {} is outside the repository", record_path.display());
    }
    let rec_file =
        crate::fspath::open_hardened(&rec_canon).map_err(|e| anyhow::anyhow!("record {e}"))?;
    let text = read_capped(rec_file, MAX_BUNDLE_BYTES).map_err(|e| anyhow::anyhow!("record {e}"))?;
    let mut rec: AttemptRecord = serde_json::from_str(&text)
        .with_context(|| format!("{} is not a valid attempt record", record_path.display()))?;
    rec.path = rec_canon
        .strip_prefix(&root_canon)
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|_| record_path.to_string_lossy().to_string());

    let problems = validate_record(&root, &rec);
    if !problems.is_empty() {
        println!("refusing to submit: this record does not validate:");
        for p in &problems {
            println!("  - {p}");
        }
        return Ok(false);
    }

    let report_text = match &rec.report {
        Some(r) => {
            let f = crate::fspath::open_within_repo(&root, r).map_err(|e| anyhow::anyhow!("report {e}"))?;
            Some(read_capped(f, MAX_BUNDLE_BYTES).map_err(|e| anyhow::anyhow!("report {r}: {e}"))?)
        }
        None => None,
    };
    let mut artifacts = serde_json::Map::new();
    for a in &rec.artifacts {
        let f = crate::fspath::open_within_repo(&root, a).map_err(|e| anyhow::anyhow!("artifact {e}"))?;
        let content =
            read_capped(f, MAX_BUNDLE_BYTES).map_err(|e| anyhow::anyhow!("artifact {a}: {e}"))?;
        artifacts.insert(a.clone(), serde_json::Value::String(content));
    }
    // The candidate program travels with the bundle. A submitter who cannot open
    // a pull request has no other way to deliver the bytes that were verified,
    // and a claimed score is not reviewable without them. validate_record has
    // already resolved this path inside the repo and re-run it on the VM.
    if let Some(cand) = &rec.best_candidate {
        if !artifacts.contains_key(&cand.program) {
            let f = crate::fspath::open_within_repo(&root, &cand.program)
                .map_err(|e| anyhow::anyhow!("candidate {e}"))?;
            let content = read_capped(f, MAX_BUNDLE_BYTES)
                .map_err(|e| anyhow::anyhow!("candidate {}: {e}", cand.program))?;
            artifacts.insert(cand.program.clone(), serde_json::Value::String(content));
        }
    }

    let bundle = serde_json::json!({
        "schema": ATTEMPT_BUNDLE_SCHEMA,
        "created": crate::trace::now_iso(),
        "record": serde_json::to_value(&rec)?,
        "report": report_text,
        "artifacts": artifacts,
    });
    let body = serde_json::to_string(&bundle)?;
    if body.len() as u64 > MAX_BUNDLE_BYTES {
        anyhow::bail!(
            "bundle is {} bytes, over the {} MiB intake cap — trim artifacts",
            body.len(),
            MAX_BUNDLE_BYTES / (1024 * 1024)
        );
    }

    // Streamed to curl on stdin: no temporary file, nothing to clean up.
    crate::trace::http_post_body(ATTEMPT_INTAKE_URL, &body)
}

/// Read an open file to a String, refusing anything over `max_bytes` — checked
/// against the file's own metadata before allocation, then bounded on read.
fn read_capped(file: std::fs::File, max_bytes: u64) -> Result<String> {
    use std::io::Read as _;
    let meta = file.metadata().context("stat")?;
    if meta.len() > max_bytes {
        anyhow::bail!("file is {} bytes, over the {}-byte limit", meta.len(), max_bytes);
    }
    let mut s = String::new();
    file.take(max_bytes + 1).read_to_string(&mut s).context("read")?;
    if s.len() as u64 > max_bytes {
        anyhow::bail!("file exceeds the {}-byte limit", max_bytes);
    }
    Ok(s)
}
