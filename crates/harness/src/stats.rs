//! Aggregate attempt statistics: the public tally of who has tried each rung
//! and how close they got, without exposing any trace.
//!
//! Two disjoint streams feed the aggregate, so neither double-counts the
//! other:
//!
//! * **Public attempt records** (`docs/attempts/*.json`) — visible in the
//!   repository, counted by the generator directly.
//! * **Private submissions** — traces posted to the intake are private, but a
//!   vault-side aggregator distills them to per-rung *counts* and commits them
//!   as `leaderboard/attempt-stats.json`. Only numbers cross into the public
//!   repository; candidate bytes, transcripts, and identities never do.
//!
//! The result is a per-rung headline (attempts, best verified score, latest
//! date) rendered on rung pages and served at `/api/attempt-stats.json`.

use std::collections::BTreeMap;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};

use crate::attempts::AttemptRecord;

const REPO_ROOT: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../..");

/// The committed private-submission counts (numbers only).
#[derive(Debug, Deserialize)]
struct PrivateStatsFile {
    #[serde(default)]
    rungs: BTreeMap<String, PrivateRungStats>,
}

#[derive(Debug, Deserialize)]
struct PrivateRungStats {
    #[serde(default)]
    attempts: u64,
    #[serde(default)]
    best_correct: Option<u32>,
    #[serde(default)]
    best_total: Option<u32>,
    #[serde(default)]
    latest: Option<String>,
}

/// One rung's public-facing aggregate.
#[derive(Clone, Debug, Default, Serialize)]
pub struct RungAggregate {
    pub attempts: u64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub best_correct: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub best_total: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub latest: Option<String>,
}

impl RungAggregate {
    fn record_best(&mut self, correct: u32, total: u32) {
        if self.best_correct.map_or(true, |c| correct > c) {
            self.best_correct = Some(correct);
            self.best_total = Some(total);
        }
    }
    fn record_latest(&mut self, date: &str) {
        if self.latest.as_deref().map_or(true, |d| date > d) {
            self.latest = Some(date.to_string());
        }
    }
    /// A compact "best 7/12" fragment, if a best score is known.
    pub fn best_fragment(&self) -> Option<String> {
        match (self.best_correct, self.best_total) {
            (Some(c), Some(t)) => Some(format!("{c}/{t}")),
            _ => None,
        }
    }
}

/// Compute per-rung aggregates from the public records plus, if present, the
/// committed private-submission counts.
pub fn compute_aggregates(public: &[AttemptRecord]) -> BTreeMap<String, RungAggregate> {
    let mut out: BTreeMap<String, RungAggregate> = BTreeMap::new();

    for rec in public {
        let agg = out.entry(rec.rung_id.clone()).or_default();
        agg.attempts += 1;
        if let Some(c) = &rec.best_candidate {
            agg.record_best(c.claimed_correct_cases, c.claimed_total_cases);
        }
        agg.record_latest(&rec.date);
    }

    let private_path = PathBuf::from(REPO_ROOT).join("leaderboard/attempt-stats.json");
    if let Ok(text) = std::fs::read_to_string(&private_path) {
        if let Ok(file) = serde_json::from_str::<PrivateStatsFile>(&text) {
            for (rung, s) in file.rungs {
                let agg = out.entry(rung).or_default();
                agg.attempts += s.attempts;
                if let (Some(c), Some(t)) = (s.best_correct, s.best_total) {
                    agg.record_best(c, t);
                }
                if let Some(d) = s.latest {
                    agg.record_latest(&d);
                }
            }
        }
    }

    out
}

/// Board-wide total attempts across all rungs.
pub fn total_attempts(aggs: &BTreeMap<String, RungAggregate>) -> u64 {
    aggs.values().map(|a| a.attempts).sum()
}
