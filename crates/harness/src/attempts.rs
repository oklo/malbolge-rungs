//! Structured attempt records: the machine-readable log of serious attempts
//! at board rungs, successful or not (`docs/attempts/*.json`, schema
//! `malbolge-rungs.attempt.v1`).
//!
//! The board's leaderboard records wins; attempt records keep the rest —
//! method, consumed budget, and the best candidate reached. A record that
//! claims a best-candidate score names the program file, and validation
//! re-runs it on the native VM and rejects the record if the claimed per-case
//! score is not exactly what the evaluator observes.
//!
//! What the VM verifies is the candidate score — nothing more. A record's
//! budget, search narrative, and structural conclusions are contributor
//! claims, and several confidently-stated impossibility claims in this corpus
//! were disproved by the next attempt. Aggregates and rung pages therefore use
//! only counts this repository's own verifier observed ([`attach_observed`]),
//! never claimed numbers.

use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};

use crate::leaderboard::Solver;
use crate::registry::find_rung;
use crate::verify::verify_rung;
use sha2::Digest as _;

const REPO_ROOT: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../..");

pub const ATTEMPT_SCHEMA: &str = "malbolge-rungs.attempt.v1";
/// A submittable attempt bundle: the record plus its report and artifact
/// contents, POSTed to the unattended-admission intake (no PR, no auth). The
/// bundle envelope stays private; an admitted bundle's record, report,
/// candidate program, and cited artifacts are committed publicly.
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
    /// Digest of the rung definition this attempt was made against.
    ///
    /// Rung contracts can change when one turns out to measure something other
    /// than what it claims — `cat` was minted with a 16-byte input cap and
    /// re-spec'd to 255 hours later, and every Transform rung's epoch rule
    /// changed the same day. Without this, a record's findings read as current
    /// while describing a rung that no longer exists. Filled in on submit.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rung_digest: Option<String>,
    /// Counts this repository's own verifier observed for the claimed best
    /// candidate under the CURRENT rung contract, across every epoch the rung
    /// requires (the worst epoch is reported). Computed by
    /// [`attach_observed`]; never read from the submitted JSON, but emitted in
    /// the API DTO so claimed and observed stay visibly separate.
    #[serde(skip_deserializing, skip_serializing_if = "Option::is_none")]
    pub observed: Option<ObservedScore>,
    /// Why `observed` is absent despite a claimed candidate — a renamed rung,
    /// a pruned program file. Distinguishes "unverifiable" from "no candidate
    /// was ever claimed", which would otherwise render identically.
    #[serde(skip_deserializing, skip_serializing_if = "Option::is_none")]
    pub observed_error: Option<String>,
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

/// A score the board's own verifier produced, as opposed to one a record
/// claims. Claimed counts are validated against epoch 0 of the contract they
/// were made under; this is the worst epoch of a full required-epochs run
/// under the CURRENT contract, so it can sit at or below a valid claim — and
/// far below a stale or lucky-draw one.
#[derive(Clone, Copy, Debug, Serialize)]
pub struct ObservedScore {
    pub correct_cases: u32,
    pub total_cases: u32,
}

/// Re-run every record's claimed best candidate on the native VM and attach
/// what the verifier observed. This is the only score aggregation is allowed
/// to use: a claimed count that cannot be reproduced here contributes nothing.
///
/// The run covers every epoch the rung requires and reports the WORST epoch.
/// One epoch is exactly the lucky draw a seed-dependent rung's `min_epochs`
/// exists to reject — a constant-output candidate that matches epoch 0 of a
/// 256-epoch rung must not be published as an observed near-solve. A record
/// whose candidate cannot be verified at all (renamed rung, pruned file) gets
/// an explicit `observed_error` instead of silently rendering like a record
/// that never claimed a candidate.
pub fn attach_observed(records: &mut [AttemptRecord]) {
    let root = PathBuf::from(REPO_ROOT);
    for rec in records.iter_mut() {
        let Some(cand) = &rec.best_candidate else { continue };
        let Some(rung) = find_rung(&rec.rung_id) else {
            rec.observed_error = Some(format!("rung {} is not in the registry", rec.rung_id));
            continue;
        };
        let path = match crate::fspath::resolve_within_repo(&root, &cand.program) {
            Ok(p) => p,
            Err(e) => {
                rec.observed_error = Some(format!("candidate {e}"));
                continue;
            }
        };
        let program = match std::fs::read(&path) {
            Ok(b) => b,
            Err(e) => {
                rec.observed_error = Some(format!("candidate {}: {e}", cand.program));
                continue;
            }
        };
        let outcome = verify_rung(&rung, &program, rung.required_epochs());
        rec.observed = if rung.sweeps_first_byte() {
            // An exhaustive sweep is an enumeration, not a re-draw: epoch i
            // pins case j's first byte to (i+j) mod 256, so the epochs
            // together cover the input space exactly once. Sum them — this is
            // how "249/256" is even expressible, and the worst single epoch
            // of an enumeration is 0 or 1 and says nothing.
            Some(ObservedScore {
                correct_cases: outcome.epochs.iter().map(|e| e.correct_cases).sum(),
                total_cases: outcome.epochs.iter().map(|e| e.total_cases).sum(),
            })
        } else {
            // Re-drawn epochs: report the WORST epoch — one lucky draw is
            // exactly what min_epochs exists to reject.
            outcome
                .epochs
                .iter()
                .min_by_key(|e| e.correct_cases)
                .map(|worst| ObservedScore {
                    correct_cases: worst.correct_cases,
                    total_cases: worst.total_cases,
                })
        };
    }
}

/// Digest of a rung's current definition — the contract a claim was made under.
pub fn rung_digest(rung_id: &str) -> Option<String> {
    let rung = find_rung(rung_id)?;
    let canon = serde_json::to_string(&rung).ok()?;
    Some(hex::encode(&sha2::Sha256::digest(canon.as_bytes())[..8]))
}

fn attempts_dir() -> PathBuf {
    PathBuf::from(REPO_ROOT).join("docs/attempts")
}

/// Load every attempt record, sorted by file name (dates sort naturally).
pub fn load_attempts() -> Vec<AttemptRecord> {
    load_attempts_at(Path::new(REPO_ROOT))
}

/// Load the attempt records of an arbitrary repository root. Everything that
/// takes a `--repo` (the admission worker's worktree) must read the corpus
/// from THAT tree — the compile-time root belongs to the source checkout, and
/// mixing the two silently attributes one tree's leaderboard from another
/// tree's records.
pub fn load_attempts_at(root: &Path) -> Vec<AttemptRecord> {
    let mut out = Vec::new();
    let Ok(entries) = std::fs::read_dir(root.join("docs/attempts")) else {
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
                    .strip_prefix(root)
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
        let problems = validate_record(&root, &rec, Strictness::Historical);
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

/// Validate a FRESH record at the admission trust boundary. On top of the
/// historical checks this requires that the record's `rung_digest` exactly
/// matches the current rung definition, and that the claimed score matches a
/// fresh native run unconditionally — no drift tolerance. Grandfathering
/// across contract changes exists only for records already in the repository
/// (the historical loader path, [`validate_attempts`]); a bundle arriving now
/// was made now, and a stale digest means it must be resubmitted against the
/// current contract rather than admitted with an uncheckable score.
pub fn validate_record_fresh(root: &Path, rec: &AttemptRecord) -> Vec<String> {
    validate_record(root, rec, Strictness::Fresh)
}

/// How to treat a score claim made under a rung contract that has since
/// changed.
#[derive(Clone, Copy, PartialEq)]
enum Strictness {
    /// Repository corpus: a mismatch under a changed contract is drift, not a
    /// false claim — failing it would punish the submitter for our correction.
    Historical,
    /// Admission: the digest must be current and the score must reproduce.
    Fresh,
}

/// Validate one record; returns its problems (empty = valid). Schema tag, known
/// rung, sane outcome, referenced files contained in the repo, and — when a best
/// candidate is claimed — an exact match between the claimed score and a fresh
/// native run.
fn validate_record(root: &Path, rec: &AttemptRecord, strictness: Strictness) -> Vec<String> {
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
    // A dangling `builds_on` is not this record's fault. It happens whenever a
    // cited record is still queued, or was rejected on its own merits — a good
    // record was stuck permanently behind a lookup-table submission that
    // deserved its rejection. The citation is dropped at render time; the work
    // is kept.
    for prior in &rec.builds_on {
        if prior.starts_with('/') || prior.contains("..") {
            problems.push(format!("builds_on {prior:?} is absolute or contains traversal"));
        }
    }
    if strictness == Strictness::Fresh {
        let current = rung_digest(&rec.rung_id);
        match (&rec.rung_digest, &current) {
            (None, _) => problems.push(
                "record carries no rung_digest; fresh submissions must be stamped \
                 against the current rung definition (attempts submit does this)"
                    .to_string(),
            ),
            (Some(got), Some(want)) if got != want => problems.push(format!(
                "rung_digest {got} does not match the current rung definition {want} — \
                 the contract changed; re-verify and resubmit against it"
            )),
            _ => {}
        }
    }
    if let (Some(cand), Some(rung)) = (&rec.best_candidate, &rung) {
        match crate::fspath::resolve_within_repo(root, &cand.program) {
            Err(e) => problems.push(format!("candidate {e}")),
            Ok(safe_path) => match std::fs::read(&safe_path) {
                Err(_) => problems.push(format!("candidate {} does not exist", cand.program)),
                Ok(program) => {
                    // A historical claim can only be held against the contract
                    // it was made under. Rung definitions change when one turns
                    // out to measure something other than what it claims, and a
                    // record written before such a change is stale rather than
                    // false. A FRESH record gets no such tolerance: its score
                    // must reproduce on the current contract, full stop —
                    // otherwise a hostile bundle could publish an arbitrary
                    // number by omitting or staling its digest.
                    let same_contract = rec.rung_digest.is_some()
                        && rec.rung_digest == rung_digest(&rec.rung_id);
                    let outcome = verify_rung(rung, &program, 1);
                    let ep = &outcome.epochs[0];
                    let mismatch = ep.correct_cases != cand.claimed_correct_cases
                        || ep.total_cases != cand.claimed_total_cases;
                    if mismatch && (same_contract || strictness == Strictness::Fresh) {
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
/// and POST it to the unattended-admission intake — no PR, no auth. This is
/// the frictionless path for a sandboxed agent that produced a record it
/// can't open a PR for. The envelope is private; if admission succeeds, the
/// record, report, candidate program, and cited artifacts become public.
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

    // Stamp the contract this attempt was made against. Rung definitions can
    // change when one turns out to measure something other than what it claims,
    // and without this a record's findings read as current while describing a
    // rung that no longer exists.
    if let Some(rung) = find_rung(&rec.rung_id) {
        if let Ok(canon) = serde_json::to_string(&rung) {
            let digest = sha2::Sha256::digest(canon.as_bytes());
            rec.rung_digest = Some(hex::encode(&digest[..8]));
        }
    }

    // Submissions face the fresh-admission bar, so a record the intake would
    // reject is caught here, before it is sent. The digest was stamped above,
    // so the only way this rejects on the digest is a registry change racing
    // the submit — in which case rebuilding against the new contract is right.
    let problems = validate_record(&root, &rec, Strictness::Fresh);
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
