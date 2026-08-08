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

use std::path::PathBuf;

use serde::Deserialize;

use crate::leaderboard::Solver;
use crate::registry::find_rung;
use crate::verify::verify_rung;

const REPO_ROOT: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../..");

pub const ATTEMPT_SCHEMA: &str = "malbolge-rungs.attempt.v1";

/// One structured attempt record.
#[derive(Clone, Debug, Deserialize)]
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
    /// Record file path (filled at load time, not part of the JSON).
    #[serde(skip)]
    pub path: String,
}

#[derive(Clone, Debug, Deserialize)]
pub struct BestCandidate {
    /// Repo-relative path of the candidate program.
    pub program: String,
    pub claimed_correct_cases: u32,
    pub claimed_total_cases: u32,
}

/// A repo-relative path is safe when it is relative and never steps upward.
/// Everything a record references must live inside the repository.
fn is_safe_rel_path(p: &str) -> bool {
    let path = std::path::Path::new(p);
    !path.is_absolute()
        && path
            .components()
            .all(|c| matches!(c, std::path::Component::Normal(_)))
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
            if !is_safe_rel_path(report) {
                problems.push(format!("report path {report} must be repo-relative"));
            } else if !root.join(report).exists() {
                problems.push(format!("report {report} does not exist"));
            }
        }
        for artifact in &rec.artifacts {
            if !is_safe_rel_path(artifact) {
                problems.push(format!("artifact path {artifact} must be repo-relative"));
            } else if !root.join(artifact).exists() {
                problems.push(format!("artifact {artifact} does not exist"));
            }
        }
        if let (Some(cand), Some(rung)) = (&rec.best_candidate, &rung) {
            if !is_safe_rel_path(&cand.program) {
                problems.push(format!("candidate path {} must be repo-relative", cand.program));
            }
            match std::fs::read(root.join(&cand.program)) {
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
            }
        }
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
