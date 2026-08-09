//! The verification-backed leaderboard.
//!
//! A leaderboard entry is never a recorded claim — a `solved` entry names an
//! actual candidate `.mal` program, and `verify_leaderboard` re-runs every
//! claimed solution on the native VM. If any no longer passes its rung, the
//! check fails. Only native-evaluator passes count as solved.

use std::path::PathBuf;

use serde::Deserialize;

use crate::registry::find_rung;
use crate::verify::verify_rung;

/// Repo root, resolved at build time from this crate's location.
const REPO_ROOT: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../..");

/// Verification status of a rung on the leaderboard.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Status {
    /// A native-verified program exists and is shipped.
    Solved,
    /// No solution; frontier open.
    Open,
    /// Designed to be solvable but no verified program exists yet.
    Unverified,
}

/// Granular attribution for whoever produced the winning program, with the
/// fields benchmarking sites conventionally record. Only evidenced values are
/// populated; unknown fields stay null rather than being guessed.
#[derive(Clone, Debug, Deserialize)]
pub struct Solver {
    /// Short display name for the leaderboard table, e.g. "GPT-5.5 (Codex)".
    pub display: String,
    /// "llm-agent" | "tool" | "human" | "canonical".
    #[serde(default, rename = "type")]
    pub kind: Option<String>,
    /// Exact model name as recorded in the original evaluation report.
    #[serde(default)]
    pub model: Option<String>,
    #[serde(default)]
    pub provider: Option<String>,
    /// Harness / scaffold the model ran in (long form, for detail pages).
    #[serde(default)]
    pub harness: Option<String>,
    /// Short harness name for the leaderboard table column.
    #[serde(default)]
    pub harness_short: Option<String>,
    /// Public provenance URL for the harness (repo, product page).
    #[serde(default)]
    pub harness_url: Option<String>,
    #[serde(default)]
    pub notes: Option<String>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct LeaderboardRecord {
    pub rung_id: String,
    /// Ladder position, easiest -> hardest (best-evidence estimate; the site
    /// sorts by this).
    #[serde(default)]
    pub rank: Option<u32>,
    pub status: Status,
    /// Path (relative to repo root) of the shipped solution, for `solved` rungs.
    #[serde(default)]
    pub best_program: Option<String>,
    #[serde(default)]
    pub solver: Option<Solver>,
    #[serde(default)]
    pub date: Option<String>,
    /// Human-readable verification metric, e.g. "4/4 cases" or "27/256 (best
    /// known, below 32 threshold)".
    #[serde(default)]
    pub metric: Option<String>,
    /// One-line note shown in the leaderboard table.
    #[serde(default)]
    pub note: Option<String>,
    /// Extended discussion shown on the rung's detail page.
    #[serde(default)]
    pub note_long: Option<String>,
    /// Optional run manifest for the winning attempt (free-form key/value:
    /// exact model version, harness version, token count, wall time, evaluator
    /// invocations, ...). Rendered verbatim on the rung's detail page.
    #[serde(default)]
    pub manifest: Option<serde_json::Map<String, serde_json::Value>>,
}

/// Load the leaderboard from `leaderboard/leaderboard.json` at runtime, so
/// editing the data is reflected immediately by a re-run (no rebuild needed).
/// Records are returned in ladder order (ascending `rank`).
pub fn load_leaderboard() -> Vec<LeaderboardRecord> {
    let path = PathBuf::from(REPO_ROOT).join("leaderboard/leaderboard.json");
    let text = std::fs::read_to_string(&path)
        .unwrap_or_else(|err| panic!("reading {}: {err}", path.display()));
    let mut records: Vec<LeaderboardRecord> =
        serde_json::from_str(&text).expect("leaderboard.json is valid");
    records.sort_by_key(|r| r.rank.unwrap_or(u32::MAX));
    records
}

/// Outcome of re-verifying a single `solved` record.
pub struct ReverifyResult {
    pub rung_id: String,
    pub program: String,
    pub passed: bool,
    pub detail: String,
}

/// Re-verify every `solved` record against the native VM.
/// Returns `(results, all_ok)`.
pub fn verify_leaderboard(epochs: u32) -> (Vec<ReverifyResult>, bool) {
    let mut results = Vec::new();
    let mut all_ok = true;
    for record in load_leaderboard() {
        if record.status != Status::Solved {
            continue;
        }
        let program_rel = match &record.best_program {
            Some(p) => p.clone(),
            None => {
                all_ok = false;
                results.push(ReverifyResult {
                    rung_id: record.rung_id.clone(),
                    program: "<none>".to_string(),
                    passed: false,
                    detail: "record marked solved but has no best_program".to_string(),
                });
                continue;
            }
        };
        // Resolve the submitted path symlink-safely: it must stay inside the
        // repository, so a committed symlink cannot make verification read
        // (and the site publish) a file outside the tree.
        let safe_path = match crate::fspath::resolve_within_repo(
            std::path::Path::new(REPO_ROOT),
            &program_rel,
        ) {
            Ok(p) => p,
            Err(detail) => {
                all_ok = false;
                results.push(ReverifyResult {
                    rung_id: record.rung_id.clone(),
                    program: program_rel,
                    passed: false,
                    detail,
                });
                continue;
            }
        };
        let rung = match find_rung(&record.rung_id) {
            Some(r) => r,
            None => {
                all_ok = false;
                results.push(ReverifyResult {
                    rung_id: record.rung_id.clone(),
                    program: program_rel,
                    passed: false,
                    detail: "rung id not found in registry".to_string(),
                });
                continue;
            }
        };
        let program = match std::fs::read(&safe_path) {
            Ok(bytes) => bytes,
            Err(err) => {
                all_ok = false;
                results.push(ReverifyResult {
                    rung_id: record.rung_id.clone(),
                    program: program_rel,
                    passed: false,
                    detail: format!("cannot read program: {err}"),
                });
                continue;
            }
        };
        let outcome = verify_rung(&rung, &program, epochs);
        if !outcome.passed {
            all_ok = false;
        }
        let detail = if outcome.passed {
            let ep = &outcome.epochs[0];
            if outcome.coverage {
                format!(
                    "{}/{} correct (>= {} required), {} epoch(s)",
                    ep.correct_cases, ep.total_cases, outcome.required_correct, outcome.epochs.len()
                )
            } else {
                format!(
                    "{} cases exact-match across {} epoch(s)",
                    ep.total_cases,
                    outcome.epochs.len()
                )
            }
        } else {
            outcome
                .epochs
                .iter()
                .find_map(|e| e.failure.clone())
                .unwrap_or_else(|| "failed".to_string())
        };
        results.push(ReverifyResult {
            rung_id: record.rung_id.clone(),
            program: program_rel,
            passed: outcome.passed,
            detail,
        });
    }
    (results, all_ok)
}

/// Render the leaderboard as a Markdown table.
pub fn render_markdown() -> String {
    let mut out = String::new();
    out.push_str("| Rung | Status | Solver | Metric | Program | Note |\n");
    out.push_str("|------|--------|--------|--------|---------|------|\n");
    for record in load_leaderboard() {
        let status = match record.status {
            Status::Solved => "✅ solved",
            Status::Open => "⬜ open",
            Status::Unverified => "🟨 unverified",
        };
        out.push_str(&format!(
            "| `{}` | {} | {} | {} | {} | {} |\n",
            record.rung_id,
            status,
            record
                .solver
                .as_ref()
                .map(|s| s.display.as_str())
                .unwrap_or("—"),
            record.metric.as_deref().unwrap_or("—"),
            record
                .best_program
                .as_deref()
                .map(|p| format!("`{p}`"))
                .unwrap_or_else(|| "—".to_string()),
            record.note.as_deref().unwrap_or("—"),
        ));
    }
    out
}
