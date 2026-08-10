//! Automatic admission of submitted attempt bundles.
//!
//! The board's guarantee is that every score it publishes was re-run on the
//! native VM. That guarantee is machine-enforced, so admission can be too: this
//! module materialises a submitted bundle into the repository, re-verifies any
//! claimed score, and — when the claim is a solve that holds — flips the
//! leaderboard record. Nothing here asks a human to adjudicate.
//!
//! What it deliberately does NOT do is take the submitter's prose as board
//! voice. An attempt's narrative stays in the attempt record, attributed to the
//! submitter; the leaderboard note this writes is generated from verified facts,
//! and the metric string comes from our own verifier rather than from the
//! claim. A submitter can be wrong about mathematics in their own report — the
//! cov32 record was — without that error becoming something the board asserts.
//!
//! Admission is the trust boundary, so it is strict about the filesystem:
//! submitted paths are attacker-chosen strings, and this writes them. Every path
//! must sit under one of three prefixes, contain no traversal, use a restricted
//! character set, and name a file that does not already exist. A bundle that
//! fails any check is rolled back completely and quarantined with a reason.

use anyhow::{bail, Context, Result};
use std::path::{Path, PathBuf};

use crate::attempts::AttemptRecord;

/// Per-file cap on materialised content.
const MAX_FILE_BYTES: usize = 1024 * 1024;
/// Cap on everything one bundle may write.
const MAX_TOTAL_BYTES: usize = 8 * 1024 * 1024;
/// The only directories a submission may write into.
const ALLOWED_PREFIXES: [&str; 3] = ["docs/attempts/", "research/", "solutions/"];

const BUNDLE_SCHEMA: &str = "malbolge-rungs.attempt-bundle.v1";

/// Outcome of admitting one bundle.
#[derive(Debug)]
pub struct Admission {
    pub bundle: String,
    pub rung_id: String,
    /// Repo-relative paths written (empty on a dry run or a rejection).
    pub files: Vec<String>,
    /// Set when the record claimed a solve and our own verifier agreed.
    pub solved: bool,
    /// Metric produced by our verifier, never copied from the submission.
    pub metric: Option<String>,
}

/// A path is admissible if it is repo-relative, traversal-free, drawn from a
/// restricted character set, sits under an allowed prefix, and names something
/// that does not yet exist. The last condition is what stops a submission from
/// rewriting a shipped solution, another agent's record, or the evaluator.
fn check_path(repo: &Path, rel: &str) -> Result<PathBuf> {
    if rel.is_empty() || rel.len() > 200 {
        bail!("path {rel:?} has an implausible length");
    }
    if rel.starts_with('/') || rel.contains("..") || rel.contains("//") {
        bail!("path {rel:?} is absolute or contains traversal");
    }
    if !rel
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | '-' | '/'))
    {
        bail!("path {rel:?} uses characters outside [A-Za-z0-9._-/]");
    }
    if !ALLOWED_PREFIXES.iter().any(|p| rel.starts_with(p)) {
        bail!(
            "path {rel:?} is outside the admission allowlist ({})",
            ALLOWED_PREFIXES.join(", ")
        );
    }
    let abs = repo.join(rel);
    if abs.exists() {
        bail!("path {rel:?} already exists — admission never overwrites");
    }
    Ok(abs)
}

/// Materialise one bundle into `repo`. On any failure every file written by this
/// call is removed, so a rejected bundle leaves no trace in the working tree.
pub fn admit_bundle(repo: &Path, bundle_path: &Path, dry_run: bool) -> Result<Admission> {
    let raw = std::fs::read_to_string(bundle_path)
        .with_context(|| format!("reading {}", bundle_path.display()))?;
    if raw.len() > MAX_TOTAL_BYTES {
        bail!("bundle is {} bytes, over the {MAX_TOTAL_BYTES} cap", raw.len());
    }
    let bundle: serde_json::Value =
        serde_json::from_str(&raw).context("bundle is not valid JSON")?;

    match bundle.get("schema").and_then(|s| s.as_str()) {
        Some(BUNDLE_SCHEMA) => {}
        other => bail!("unexpected bundle schema {other:?}, want {BUNDLE_SCHEMA}"),
    }

    let rec_value = bundle
        .get("record")
        .context("bundle has no record")?
        .clone();
    // Typed parse drops unknown fields, exactly as the corpus API does.
    let rec: AttemptRecord =
        serde_json::from_value(rec_value.clone()).context("record does not parse")?;

    if crate::registry::find_rung(&rec.rung_id).is_none() {
        bail!("record names rung {:?}, which is not in the registry", rec.rung_id);
    }
    if rec.outcome != "solved" && rec.outcome != "unsolved" {
        bail!("record outcome {:?} is neither solved nor unsolved", rec.outcome);
    }

    // Where the record itself lands. `file` is set by the submitting client.
    let record_rel = bundle
        .get("record")
        .and_then(|r| r.get("file"))
        .and_then(|f| f.as_str())
        .context("record has no file path")?
        .to_string();

    // Collect every write first, so the allowlist is fully checked before any
    // byte hits the disk.
    let mut writes: Vec<(String, String)> = Vec::new();
    let record_text = serde_json::to_string_pretty(&rec_value)? + "\n";
    writes.push((record_rel.clone(), record_text));

    if let (Some(report_rel), Some(report_text)) = (
        rec.report.as_deref(),
        bundle.get("report").and_then(|r| r.as_str()),
    ) {
        writes.push((report_rel.to_string(), report_text.to_string()));
    }
    if let Some(arts) = bundle.get("artifacts").and_then(|a| a.as_object()) {
        for (rel, content) in arts {
            let text = content
                .as_str()
                .with_context(|| format!("artifact {rel} is not text"))?;
            writes.push((rel.clone(), text.to_string()));
        }
    }

    // A bundle may name the same path twice — a record that lists its own report
    // in `artifacts`, for instance. Identical content collapses to one write;
    // conflicting content is a rejection, since otherwise the last writer would
    // silently win and the no-overwrite guarantee would hold only across
    // bundles, not within one.
    let mut seen: std::collections::BTreeMap<String, String> = std::collections::BTreeMap::new();
    for (rel, content) in writes {
        match seen.get(&rel) {
            Some(prior) if *prior != content => {
                bail!("bundle lists {rel} twice with different content")
            }
            Some(_) => {}
            None => {
                seen.insert(rel, content);
            }
        }
    }

    let mut total = 0usize;
    let mut targets = Vec::new();
    for (rel, content) in &seen {
        if content.len() > MAX_FILE_BYTES {
            bail!("{rel} is {} bytes, over the per-file cap", content.len());
        }
        total += content.len();
        targets.push((check_path(repo, rel)?, content.clone(), rel.clone()));
    }
    if total > MAX_TOTAL_BYTES {
        bail!("bundle writes {total} bytes, over the total cap");
    }

    if dry_run {
        return Ok(Admission {
            bundle: bundle_path.display().to_string(),
            rung_id: rec.rung_id.clone(),
            files: targets.into_iter().map(|(_, _, rel)| rel).collect(),
            solved: false,
            metric: None,
        });
    }

    // --- write, and unwind completely on any later failure -------------------
    let mut written: Vec<PathBuf> = Vec::new();
    let mut finish = || -> Result<(bool, Option<String>)> {
        for (abs, content, rel) in &targets {
            if let Some(parent) = abs.parent() {
                std::fs::create_dir_all(parent)
                    .with_context(|| format!("creating directory for {rel}"))?;
            }
            std::fs::write(abs, content).with_context(|| format!("writing {rel}"))?;
            written.push(abs.clone());
        }

        // Our verifier, not their claim. validate_record re-runs the candidate
        // natively and requires an exact match against the score asserted.
        let problems = crate::attempts::validate_record_at(repo, &rec);
        if !problems.is_empty() {
            bail!("record does not validate: {}", problems.join("; "));
        }

        let mut solved = false;
        let mut metric = None;
        if rec.outcome == "solved" {
            let (ok, m) = verify_claim(repo, &rec)?;
            if !ok {
                bail!("record claims a solve that does not pass the rung: {m}");
            }
            solved = true;
            metric = Some(m);
        }
        Ok((solved, metric))
    };

    match finish() {
        Ok((solved, metric)) => {
            if solved {
                update_leaderboard(repo, &rec, metric.as_deref().unwrap_or(""), &record_rel)?;
            }
            Ok(Admission {
                bundle: bundle_path.display().to_string(),
                rung_id: rec.rung_id.clone(),
                files: targets.into_iter().map(|(_, _, rel)| rel).collect(),
                solved,
                metric,
            })
        }
        Err(e) => {
            for p in written.iter().rev() {
                let _ = std::fs::remove_file(p);
            }
            Err(e)
        }
    }
}

/// Re-run the claimed program against its rung and build the metric ourselves
/// from the verifier's own counts. Nothing in the returned string is copied from
/// the submission.
fn verify_claim(repo: &Path, rec: &AttemptRecord) -> Result<(bool, String)> {
    let cand = rec
        .best_candidate
        .as_ref()
        .context("a solved record must name a best_candidate")?;
    let rung = crate::registry::find_rung(&rec.rung_id).context("rung vanished")?;
    let program_path = crate::fspath::resolve_within_repo(repo, &cand.program)
        .map_err(|e| anyhow::anyhow!("candidate {e}"))?;
    let bytes = std::fs::read(&program_path)
        .with_context(|| format!("reading candidate {}", cand.program))?;
    let outcome = crate::verify::verify_rung(&rung, &bytes, 1);

    let first = outcome
        .epochs
        .first()
        .context("verifier returned no epochs")?;
    let metric = if outcome.coverage {
        format!(
            "{}/{} correct (>= {} required), native re-verification; {} bytes",
            first.correct_cases,
            first.total_cases,
            outcome.required_correct,
            bytes.len()
        )
    } else {
        format!(
            "{}/{} cases, native re-verification; {} bytes",
            first.correct_cases,
            first.total_cases,
            bytes.len()
        )
    };
    Ok((outcome.passed, metric))
}

/// Flip a leaderboard record to solved. Board voice is generated here from
/// verified facts; the submitter's account stays in their attempt record.
fn update_leaderboard(repo: &Path, rec: &AttemptRecord, metric: &str, record_rel: &str) -> Result<()> {
    let path = repo.join("leaderboard/leaderboard.json");
    let text = std::fs::read_to_string(&path).context("reading leaderboard")?;
    let mut board: serde_json::Value = serde_json::from_str(&text)?;
    let arr = board.as_array_mut().context("leaderboard is not an array")?;

    let entry = arr
        .iter_mut()
        .find(|e| e.get("rung_id").and_then(|v| v.as_str()) == Some(rec.rung_id.as_str()))
        .with_context(|| format!("no leaderboard record for {}", rec.rung_id))?;

    if entry.get("status").and_then(|s| s.as_str()) == Some("solved") {
        // Already solved: the attempt record still lands, the claim does not
        // displace the standing one.
        return Ok(());
    }

    let cand = rec.best_candidate.as_ref().context("solved record needs a candidate")?;
    let display = rec
        .solver
        .as_ref()
        .map(|s| s.display.clone())
        .unwrap_or_else(|| "unattributed submission".to_string());

    let obj = entry.as_object_mut().context("leaderboard entry is not an object")?;
    obj.insert("status".into(), serde_json::json!("solved"));
    obj.insert("best_program".into(), serde_json::json!(cand.program));
    obj.insert("date".into(), serde_json::json!(rec.date));
    obj.insert("metric".into(), serde_json::json!(metric));
    if let Some(s) = &rec.solver {
        obj.insert("solver".into(), serde_json::to_value(s)?);
    }
    if let Some(m) = &rec.manifest {
        obj.insert("manifest".into(), serde_json::to_value(m)?);
    }
    obj.insert(
        "note".into(),
        serde_json::json!(format!("Solved by {display}. Admitted automatically after native re-verification.")),
    );
    obj.insert(
        "note_long".into(),
        serde_json::json!(format!(
            "Admitted automatically: the program was re-run on the native VM at admission and again at \
             deploy, giving {metric}. The account of how it was built is the submitter's own and is \
             recorded in {record_rel}; the board does not restate it here."
        )),
    );

    std::fs::write(&path, serde_json::to_string_pretty(&board)? + "\n")?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn repo() -> PathBuf {
        PathBuf::from(concat!(env!("CARGO_MANIFEST_DIR"), "/../.."))
    }

    #[test]
    fn rejects_traversal_and_absolute_paths() {
        let r = repo();
        assert!(check_path(&r, "../etc/passwd").is_err());
        assert!(check_path(&r, "/etc/passwd").is_err());
        assert!(check_path(&r, "docs/attempts/../../x").is_err());
    }

    #[test]
    fn rejects_paths_outside_the_allowlist() {
        let r = repo();
        assert!(check_path(&r, "crates/harness/src/verify.rs").is_err());
        assert!(check_path(&r, ".github/workflows/verify-pr.yml").is_err());
        assert!(check_path(&r, "leaderboard/leaderboard.json").is_err());
        assert!(check_path(&r, "Cargo.toml").is_err());
    }

    #[test]
    fn refuses_to_overwrite_an_existing_file() {
        let r = repo();
        // A shipped solution must not be displaceable by a submission.
        assert!(check_path(&r, "solutions/cov32/cov32-two-crazy.mal").is_err());
    }

    #[test]
    fn accepts_a_fresh_path_under_an_allowed_prefix() {
        let r = repo();
        assert!(check_path(&r, "research/newrung/build.py").is_ok());
        assert!(check_path(&r, "docs/attempts/2099-01-01-someone-rung.json").is_ok());
    }

    #[test]
    fn rejects_odd_characters() {
        let r = repo();
        assert!(check_path(&r, "research/x/$(whoami).py").is_err());
        assert!(check_path(&r, "research/x/a b.py").is_err());
    }
}
