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
/// Cap on the number of files one bundle may materialise. A legitimate bundle
/// is a record, a report, a candidate, and a handful of research files; the
/// byte caps alone would let an 8 MiB bundle expand into thousands of tiny
/// files and directories.
const MAX_FILES_PER_BUNDLE: usize = 32;
/// The only directories a submission may write into.
const ALLOWED_PREFIXES: [&str; 3] = ["docs/attempts/", "research/", "solutions/"];

const BUNDLE_SCHEMA: &str = "malbolge-rungs.attempt-bundle.v1";

/// Epochs needed before a pass means anything on this rung.
///
/// Coverage and finite-map rungs enumerate fixed inputs, so one epoch is
/// definitive. Exhaustive transform rungs enumerate the complete first-byte
/// domain across their required epochs. Other transform and hash-prefix rungs
/// re-draw inputs and targets, so a single epoch can be passed by a program that
/// got lucky on one draw — the constant-output overfit the board exists to
/// reject.
pub fn epochs_for(rung: &crate::types::Rung) -> u32 {
    rung.required_epochs()
}

/// Outcome of admitting one bundle.
#[derive(Debug)]
pub struct Admission {
    pub bundle: String,
    pub rung_id: String,
    /// Repo-relative paths written (empty on a dry run or a rejection).
    pub files: Vec<String>,
    /// Every rung this submission's program was credited on, as
    /// (rung_id, metric, displaced_a_standing_credit). A program is evidence
    /// about any rung it clears, so this is usually more than the named one.
    pub credited: Vec<(String, String, bool)>,
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
    // No dotfile components. A submission has no business writing .gitignore,
    // .gitattributes, or anything else the toolchain interprets — a
    // research/.gitignore could silently drop files from the admission commit.
    if rel.split('/').any(|c| c.starts_with('.')) {
        bail!("path {rel:?} contains a dot-prefixed component");
    }
    if rel.ends_with('/') {
        bail!("path {rel:?} names a directory, not a file");
    }
    if !ALLOWED_PREFIXES.iter().any(|p| rel.starts_with(p)) {
        bail!(
            "path {rel:?} is outside the admission allowlist ({})",
            ALLOWED_PREFIXES.join(", ")
        );
    }
    Ok(repo.join(rel))
}

/// What to do with a submitted path that already exists in the repository.
enum Existing {
    /// Byte-identical to what is already there: the submission cites prior art
    /// rather than trying to replace it, which is the compounding the board
    /// exists to encourage. Skip the write and keep the bundle.
    Identical,
    /// Different content under a path already in use. This is the case the
    /// no-overwrite rule is for.
    Conflict,
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
    // A bundle may only materialise what its record declares: the artifacts
    // list plus the candidate program. Without this closure, `artifacts` is an
    // arbitrary write-anything-under-the-allowlist channel — every member was
    // materialised whether or not the record cited it.
    let declared: std::collections::BTreeSet<&str> = rec
        .artifacts
        .iter()
        .map(|s| s.as_str())
        .chain(rec.best_candidate.as_ref().map(|c| c.program.as_str()))
        .collect();
    if let Some(arts) = bundle.get("artifacts").and_then(|a| a.as_object()) {
        for (rel, content) in arts {
            if !declared.contains(rel.as_str()) {
                bail!(
                    "bundle ships {rel:?}, which the record neither lists in \
                     artifacts nor names as its candidate — undeclared files \
                     are not admitted"
                );
            }
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

    if seen.len() > MAX_FILES_PER_BUNDLE {
        bail!(
            "bundle materialises {} files, over the {MAX_FILES_PER_BUNDLE}-file cap",
            seen.len()
        );
    }
    let mut total = 0usize;
    let mut targets = Vec::new();
    for (rel, content) in &seen {
        if content.len() > MAX_FILE_BYTES {
            bail!("{rel} is {} bytes, over the per-file cap", content.len());
        }
        let abs = check_path(repo, rel)?;
        // Look at what is at the target WITHOUT following links. `exists()`
        // follows symlinks and reports false for a broken one, so a planted
        // symlink used to sail through to the write, which then wrote through
        // it — a write outside the repository chosen by whoever planted it.
        match std::fs::symlink_metadata(&abs) {
            Ok(m) if m.file_type().is_symlink() => bail!(
                "path {rel:?} is a symlink in the working tree — admission \
                 never writes through links"
            ),
            Ok(m) if m.is_file() => {
                let same = std::fs::read_to_string(&abs)
                    .map(|on_disk| on_disk == *content)
                    .unwrap_or(false);
                match if same { Existing::Identical } else { Existing::Conflict } {
                    Existing::Identical => continue,
                    Existing::Conflict => bail!(
                        "path {rel:?} already exists with different content — \
                         admission never overwrites"
                    ),
                }
            }
            Ok(_) => bail!("path {rel:?} exists and is not a regular file"),
            Err(_) => {}
        }
        total += content.len();
        targets.push((abs, content.clone(), rel.clone()));
    }
    if total > MAX_TOTAL_BYTES {
        bail!("bundle writes {total} bytes, over the total cap");
    }

    if dry_run {
        return Ok(Admission {
            bundle: bundle_path.display().to_string(),
            rung_id: rec.rung_id.clone(),
            files: targets.into_iter().map(|(_, _, rel)| rel).collect(),
            credited: Vec::new(),
        });
    }

    // --- write, and unwind completely on any later failure -------------------
    // Everything that mutates the repository happens inside this closure —
    // including the leaderboard update, whose failure used to strand the
    // record files on disk because it ran after the rollback scope had closed.
    // The leaderboard file itself is replaced by atomic rename as the final
    // mutation, so on any error the repository holds either the full admission
    // or none of it.
    let mut written: Vec<PathBuf> = Vec::new();
    let mut created_dirs: Vec<PathBuf> = Vec::new();
    let mut finish = || -> Result<Vec<(String, String, bool)>> {
        for (_, content, rel) in &targets {
            let abs = create_new_no_symlinks(repo, rel, content, &mut created_dirs)?;
            written.push(abs);
        }

        // Our verifier, not their claim, at the fresh-admission bar: the
        // record's rung_digest must match the current rung definition and the
        // claimed score must reproduce exactly on a fresh native run.
        // Grandfathering across contract changes is for records already in the
        // repository, never for a bundle arriving now.
        let problems = crate::attempts::validate_record_fresh(repo, &rec);
        if !problems.is_empty() {
            bail!("record does not validate: {}", problems.join("; "));
        }

        // A record claiming a solve must actually pass its own rung.
        if rec.outcome == "solved" {
            let (ok, m) = verify_claim(repo, &rec)?;
            if !ok {
                bail!("record claims a solve that does not pass the rung: {m}");
            }
        }
        // Sweep whatever program the attempt reached, whether or not it claimed
        // a solve. An attempt that fails its own rung can still clear others:
        // the xor-1-len4096 attempt missed a rung demanding all 256 cases and
        // its candidate passed the entire coverage ladder up to cov96.
        if rec.best_candidate.is_some() {
            update_leaderboard(repo, &rec, &record_rel)
        } else {
            Ok(Vec::new())
        }
    };

    match finish() {
        Ok(credited) => Ok(Admission {
            bundle: bundle_path.display().to_string(),
            rung_id: rec.rung_id.clone(),
            files: targets.into_iter().map(|(_, _, rel)| rel).collect(),
            credited,
        }),
        Err(e) => {
            for p in written.iter().rev() {
                let _ = std::fs::remove_file(p);
            }
            // Directories this admission created unwind too (deepest first);
            // remove_dir refuses to delete anything non-empty, so a directory
            // that gained unrelated content in the meantime survives.
            for d in created_dirs.iter().rev() {
                let _ = std::fs::remove_dir(d);
            }
            Err(e)
        }
    }
}

/// Create the file for `rel` under `repo` with create-new semantics, making
/// missing parent directories one component at a time and refusing to traverse
/// any symlinked component. The final open is O_CREAT|O_EXCL (plus O_NOFOLLOW):
/// it fails if anything — file, directory, or symlink, broken included —
/// already sits at the target, so a planted link can neither be written
/// through nor replaced. Directories created here are appended to
/// `created_dirs` so a failed admission can unwind them.
fn create_new_no_symlinks(
    repo: &Path,
    rel: &str,
    content: &str,
    created_dirs: &mut Vec<PathBuf>,
) -> Result<PathBuf> {
    use std::io::Write as _;
    let parts: Vec<&str> = rel.split('/').filter(|p| !p.is_empty()).collect();
    let (file_name, dirs) = parts.split_last().context("empty admission path")?;
    let mut cur = repo.to_path_buf();
    for d in dirs {
        cur.push(d);
        match std::fs::symlink_metadata(&cur) {
            Ok(m) if m.file_type().is_symlink() => bail!(
                "{} on the path of {rel:?} is a symlink — admission never \
                 traverses links",
                cur.display()
            ),
            Ok(m) if m.is_dir() => {}
            Ok(_) => bail!("{} exists and is not a directory", cur.display()),
            Err(_) => {
                std::fs::create_dir(&cur)
                    .with_context(|| format!("creating directory {}", cur.display()))?;
                created_dirs.push(cur.clone());
            }
        }
    }
    cur.push(file_name);
    let mut opts = std::fs::OpenOptions::new();
    opts.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        opts.custom_flags(libc::O_NOFOLLOW);
    }
    let mut file = opts
        .open(&cur)
        .with_context(|| format!("creating {rel} (create-new refuses existing targets)"))?;
    file.write_all(content.as_bytes())
        .with_context(|| format!("writing {rel}"))?;
    Ok(cur)
}

/// Build the board's metric string from the verifier's own counts — never from
/// a submission. One implementation serves the solve check, the admission
/// sweep, and the recredit repair pass, so the format cannot drift between
/// paths.
fn format_metric(
    rung: &crate::types::Rung,
    outcome: &crate::verify::VerifyOutcome,
    epoch: &crate::verify::EpochResult,
    program_len: usize,
) -> String {
    if rung.sweeps_first_byte() {
        let correct: u32 = outcome.epochs.iter().map(|e| e.correct_cases).sum();
        let total: u32 = outcome.epochs.iter().map(|e| e.total_cases).sum();
        format!(
            "{correct}/{total} exhaustive cases, native re-verification; {program_len} bytes"
        )
    } else if outcome.coverage {
        format!(
            "{}/{} correct (>= {} required), native re-verification; {program_len} bytes",
            epoch.correct_cases, epoch.total_cases, outcome.required_correct
        )
    } else {
        format!(
            "{}/{} cases, native re-verification; {program_len} bytes",
            epoch.correct_cases, epoch.total_cases
        )
    }
}

/// Attribution follows the program in both directions: present fields are
/// written, absent fields are REMOVED. Leaving them alone kept a displaced
/// solver's name and manifest attached to a program they did not write. Both
/// leaderboard writers go through here, so the next attribution rule change is
/// one edit, not a synchronized pair.
fn apply_attribution(
    obj: &mut serde_json::Map<String, serde_json::Value>,
    solver: &Option<crate::leaderboard::Solver>,
    manifest: &Option<serde_json::Map<String, serde_json::Value>>,
) -> Result<()> {
    match solver {
        Some(s) => {
            obj.insert("solver".into(), serde_json::to_value(s)?);
        }
        None => {
            obj.remove("solver");
        }
    }
    match manifest {
        Some(m) => {
            obj.insert("manifest".into(), serde_json::to_value(m)?);
        }
        None => {
            obj.remove("manifest");
        }
    }
    Ok(())
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
    let outcome = crate::verify::verify_rung(&rung, &bytes, epochs_for(&rung));

    // Report the epoch that decided the outcome. Reporting epoch 0 on a failure
    // produces "claims a solve that does not pass the rung: 2/2 cases", naming
    // the one epoch that passed — which is exactly the draw a lookup table gets
    // lucky on, and the reason the rejection needs to point at the other four.
    let first = outcome
        .epochs
        .iter()
        .find(|e| !e.passed)
        .or_else(|| outcome.epochs.first())
        .context("verifier returned no epochs")?;
    Ok((
        outcome.passed,
        format_metric(&rung, &outcome, first, bytes.len()),
    ))
}

/// Credit a submitted program on every rung it passes, not only the one its
/// record names.
///
/// A program is evidence about any rung it clears. Considering only the named
/// rung understated the board twice in one day: cov36 kept a 3178-byte credit
/// when a 1717-byte program passed it, and a 1950-byte program that solved
/// cov64 also cleared cov48 and cov48-len2048 without anyone noticing. The rule
/// applied here is the one the board already states — the verifier is the judge,
/// and a rung goes to the smallest program that passes it.
///
/// So: sweep the candidate across the ladder, claim open rungs it clears, and
/// displace a standing credit only when this program is strictly smaller.
/// Rungs already held by something smaller are left alone.
fn update_leaderboard(
    repo: &Path,
    rec: &AttemptRecord,
    record_rel: &str,
) -> Result<Vec<(String, String, bool)>> {
    let cand = rec.best_candidate.as_ref().context("solved record needs a candidate")?;
    let cand_path = crate::fspath::resolve_within_repo(repo, &cand.program)
        .map_err(|e| anyhow::anyhow!("candidate {e}"))?;
    let bytes = std::fs::read(&cand_path)?;

    let path = repo.join("leaderboard/leaderboard.json");
    let text = std::fs::read_to_string(&path).context("reading leaderboard")?;
    let mut board: serde_json::Value = serde_json::from_str(&text)?;
    let arr = board.as_array_mut().context("leaderboard is not an array")?;

    let display = rec
        .solver
        .as_ref()
        .map(|s| s.display.clone())
        .unwrap_or_else(|| "unattributed submission".to_string());

    let mut changed = Vec::new();
    for entry in arr.iter_mut() {
        let rung_id = match entry.get("rung_id").and_then(|v| v.as_str()) {
            Some(s) => s.to_string(),
            None => continue,
        };
        let solved_now = entry.get("status").and_then(|s| s.as_str()) == Some("solved");

        let own = rung_id == rec.rung_id;

        // An incidental pass never displaces a standing credit. map8's program
        // clears map4, map6, map7a and map7b because their inputs are subsets of
        // its own — crediting it on size alone would erase four solves that
        // people actually aimed at those rungs, and with them the board's record
        // of who did what. An incidental pass may only fill an OPEN rung.
        if solved_now && !own {
            continue;
        }
        // On its own rung, a submission displaces the standing credit only by
        // being smaller. That is what lets an aimed solve replace one held by
        // subsumption. Fail CLOSED when the incumbent's size cannot be
        // established (missing or unresolvable best_program): displacing on
        // unknown would let any new submission take over a rung whose
        // incumbent path happens not to resolve in this tree, erasing the
        // standing credit — and its attribution — without a comparison.
        if solved_now {
            let held = entry
                .get("best_program")
                .and_then(|p| p.as_str())
                .and_then(|p| crate::fspath::resolve_within_repo(repo, p).ok())
                .and_then(|p| std::fs::metadata(p).ok())
                .map(|m| m.len() as usize);
            match held {
                Some(n) if n > bytes.len() => {}
                _ => continue,
            }
        }

        let Some(rung) = crate::registry::find_rung(&rung_id) else { continue };
        let outcome = crate::verify::verify_rung(&rung, &bytes, epochs_for(&rung));
        if !outcome.passed {
            continue;
        }
        let Some(first) = outcome.epochs.first() else { continue };
        let metric = format_metric(&rung, &outcome, first, bytes.len());

        let obj = entry.as_object_mut().context("leaderboard entry is not an object")?;
        obj.insert("status".into(), serde_json::json!("solved"));
        obj.insert("best_program".into(), serde_json::json!(cand.program));
        obj.insert("date".into(), serde_json::json!(rec.date));
        obj.insert("metric".into(), serde_json::json!(metric.clone()));
        apply_attribution(obj, &rec.solver, &rec.manifest)?;
        obj.insert(
            "note".into(),
            serde_json::json!(if own {
                format!("Solved by {display}.")
            } else {
                format!("Solved by {display}'s {} program, which also passes this rung.", rec.rung_id)
            }),
        );
        obj.insert(
            "note_long".into(),
            serde_json::json!(if own {
                format!(
                    "Re-verified on the native VM at admission and again at each deploy: {metric}. \
                     The submitter's account is in {record_rel}."
                )
            } else {
                format!(
                    "The program submitted for {} passes this rung too ({metric}); a rung is \
                     credited to the smallest passing program. The submitter's account is in \
                     {record_rel}.",
                    rec.rung_id
                )
            }),
        );
        changed.push((rung_id, metric, solved_now));
    }

    write_leaderboard_atomic(&path, &board)?;
    Ok(changed)
}

/// Replace the leaderboard via temp-file-plus-rename in its own directory, so
/// a crash or full disk mid-write can never leave a truncated board — the file
/// is always either the old version or the new one.
fn write_leaderboard_atomic(path: &Path, board: &serde_json::Value) -> Result<()> {
    let text = serde_json::to_string_pretty(board)? + "\n";
    let tmp = path.with_extension(format!("json.tmp.{}", std::process::id()));
    std::fs::write(&tmp, &text).with_context(|| format!("writing {}", tmp.display()))?;
    std::fs::rename(&tmp, path).with_context(|| {
        let _ = std::fs::remove_file(&tmp);
        format!("renaming {} into place", tmp.display())
    })?;
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
    fn allows_an_existing_path_for_the_identical_bytes_check() {
        // check_path no longer decides this; admit_bundle compares content, so
        // citing prior art resolves to a skip and only differing bytes conflict.
        let r = repo();
        assert!(check_path(&r, "solutions/cov32/cov32-two-crazy.mal").is_ok());
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

    #[test]
    fn rejects_dotfile_components() {
        let r = repo();
        assert!(check_path(&r, "research/.gitignore").is_err());
        assert!(check_path(&r, "docs/attempts/.hidden/rec.json").is_err());
        assert!(check_path(&r, "solutions/x/.DS_Store").is_err());
        assert!(check_path(&r, "research/x/dir/").is_err());
    }

    // ---- end-to-end admission against a throwaway repository ----------------

    const TEST_RUNG: &str = "L0.R0.hello-world";
    const RECORD_REL: &str = "docs/attempts/2099-01-01-test-hello.json";
    const CAND_REL: &str = "research/admtest/cand.mal";

    struct TempRepo {
        root: PathBuf,
    }

    impl TempRepo {
        fn new(tag: &str) -> Self {
            let root =
                std::env::temp_dir().join(format!("mal-admit-{tag}-{}", std::process::id()));
            let _ = std::fs::remove_dir_all(&root);
            for d in ["docs/attempts", "solutions", "research", "leaderboard"] {
                std::fs::create_dir_all(root.join(d)).unwrap();
            }
            std::fs::write(
                root.join("leaderboard/leaderboard.json"),
                serde_json::to_string_pretty(&serde_json::json!([
                    {"rung_id": TEST_RUNG, "rank": 1, "status": "open"}
                ]))
                .unwrap(),
            )
            .unwrap();
            Self { root }
        }

        fn bundle_path(&self, bundle: &serde_json::Value) -> PathBuf {
            let p = self.root.join("bundle.json");
            std::fs::write(&p, serde_json::to_string(bundle).unwrap()).unwrap();
            p
        }
    }

    impl Drop for TempRepo {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.root);
        }
    }

    /// The shipped halt program and its native epoch-0 score on TEST_RUNG.
    fn passing_candidate() -> (String, u32, u32) {
        let text =
            std::fs::read_to_string(repo().join("solutions/hello-world/halt-no-output.mal"))
                .unwrap();
        let rung = crate::registry::find_rung(TEST_RUNG).unwrap();
        let out = crate::verify::verify_rung(&rung, text.as_bytes(), 1);
        let ep = &out.epochs[0];
        (text, ep.correct_cases, ep.total_cases)
    }

    fn record(digest: Option<String>, correct: u32, total: u32) -> serde_json::Value {
        serde_json::json!({
            "schema": "malbolge-rungs.attempt.v1",
            "rung_id": TEST_RUNG,
            "date": "2099-01-01",
            "outcome": "unsolved",
            "best_candidate": {
                "program": CAND_REL,
                "claimed_correct_cases": correct,
                "claimed_total_cases": total,
            },
            "rung_digest": digest,
            "file": RECORD_REL,
        })
    }

    fn bundle_for(rec: serde_json::Value, artifacts: serde_json::Value) -> serde_json::Value {
        serde_json::json!({
            "schema": BUNDLE_SCHEMA,
            "record": rec,
            "artifacts": artifacts,
        })
    }

    #[test]
    fn admits_a_valid_fresh_record_and_credits_open_rungs() {
        let (text, c, t) = passing_candidate();
        let tr = TempRepo::new("happy");
        let digest = crate::attempts::rung_digest(TEST_RUNG);
        let b = bundle_for(record(digest, c, t), serde_json::json!({CAND_REL: text}));
        let adm = admit_bundle(&tr.root, &tr.bundle_path(&b), false).unwrap();
        assert!(tr.root.join(RECORD_REL).is_file());
        assert!(tr.root.join(CAND_REL).is_file());
        assert!(adm.credited.iter().any(|(r, _, _)| r == TEST_RUNG));
        let board =
            std::fs::read_to_string(tr.root.join("leaderboard/leaderboard.json")).unwrap();
        assert!(board.contains("\"solved\""));
    }

    #[test]
    fn admits_a_fresh_exhaustive_sweep_score() {
        // A sweep rung has one case in each of 256 epochs. Admission used to
        // compare this 251/256 claim with epoch 0's 0/1 or 1/1, so the only way
        // to submit the candidate was to omit best_candidate—and the board
        // consequently rendered an em dash.
        const SWEEP_RUNG: &str = "L2.R0d.xor-1-len4096";
        let text = std::fs::read_to_string(repo().join(
            "research/xor-1-len4096-codex/runs/hero1-joint150151-short-o0-0.mal",
        ))
        .unwrap();
        let tr = TempRepo::new("sweep-score");
        let rec = serde_json::json!({
            "schema": "malbolge-rungs.attempt.v1",
            "rung_id": SWEEP_RUNG,
            "date": "2099-01-01",
            "outcome": "unsolved",
            "best_candidate": {
                "program": CAND_REL,
                "claimed_correct_cases": 251,
                "claimed_total_cases": 256,
            },
            "rung_digest": crate::attempts::rung_digest(SWEEP_RUNG),
            "file": RECORD_REL,
        });
        let b = bundle_for(rec, serde_json::json!({CAND_REL: text}));
        let adm = admit_bundle(&tr.root, &tr.bundle_path(&b), false).unwrap();
        assert!(tr.root.join(RECORD_REL).is_file());
        assert!(tr.root.join(CAND_REL).is_file());
        assert_eq!(adm.rung_id, SWEEP_RUNG);
    }

    #[test]
    fn fresh_admission_requires_a_current_rung_digest() {
        let (text, c, t) = passing_candidate();
        for (tag, digest) in [("nodigest", None), ("stale", Some("00d1ge5700000000".to_string()))]
        {
            let tr = TempRepo::new(tag);
            let b = bundle_for(record(digest, c, t), serde_json::json!({CAND_REL: text}));
            let err = admit_bundle(&tr.root, &tr.bundle_path(&b), false).unwrap_err();
            assert!(err.to_string().contains("rung_digest"), "{err:#}");
            assert!(!tr.root.join(RECORD_REL).exists(), "rollback must remove the record");
            assert!(
                !tr.root.join("research/admtest").exists(),
                "rollback must remove directories the admission created"
            );
        }
    }

    #[test]
    fn fresh_admission_rejects_a_forged_score() {
        let (text, c, t) = passing_candidate();
        let tr = TempRepo::new("forged");
        let digest = crate::attempts::rung_digest(TEST_RUNG);
        let b = bundle_for(record(digest, c + 1, t + 1), serde_json::json!({CAND_REL: text}));
        let err = admit_bundle(&tr.root, &tr.bundle_path(&b), false).unwrap_err();
        assert!(err.to_string().contains("native VM observes"), "{err:#}");
        assert!(!tr.root.join(RECORD_REL).exists());
    }

    #[cfg(unix)]
    #[test]
    fn refuses_to_write_through_a_planted_symlink() {
        let (text, c, t) = passing_candidate();
        let tr = TempRepo::new("symlink-final");
        let outside =
            std::env::temp_dir().join(format!("mal-admit-outside-f-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&outside);
        std::fs::create_dir_all(&outside).unwrap();
        std::fs::create_dir_all(tr.root.join("research/admtest")).unwrap();
        // A broken symlink: exists() is false for it, so the old pre-check
        // sailed past it and the write followed it out of the repository.
        std::os::unix::fs::symlink(outside.join("evil.txt"), tr.root.join(CAND_REL)).unwrap();
        let digest = crate::attempts::rung_digest(TEST_RUNG);
        let b = bundle_for(record(digest, c, t), serde_json::json!({CAND_REL: text}));
        let err = admit_bundle(&tr.root, &tr.bundle_path(&b), false).unwrap_err();
        assert!(err.to_string().contains("symlink"), "{err:#}");
        assert!(!outside.join("evil.txt").exists(), "nothing may appear outside the repo");
        let _ = std::fs::remove_dir_all(&outside);
    }

    #[cfg(unix)]
    #[test]
    fn refuses_a_symlinked_parent_directory() {
        let (text, c, t) = passing_candidate();
        let tr = TempRepo::new("symlink-parent");
        let outside =
            std::env::temp_dir().join(format!("mal-admit-outside-p-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&outside);
        std::fs::create_dir_all(&outside).unwrap();
        std::os::unix::fs::symlink(&outside, tr.root.join("research/admtest")).unwrap();
        let digest = crate::attempts::rung_digest(TEST_RUNG);
        let b = bundle_for(record(digest, c, t), serde_json::json!({CAND_REL: text}));
        let err = admit_bundle(&tr.root, &tr.bundle_path(&b), false).unwrap_err();
        assert!(err.to_string().contains("symlink"), "{err:#}");
        assert!(
            !outside.join("cand.mal").exists(),
            "nothing may be written through a symlinked directory"
        );
        let _ = std::fs::remove_dir_all(&outside);
    }

    #[test]
    fn rejects_undeclared_artifacts() {
        let (text, c, t) = passing_candidate();
        let tr = TempRepo::new("undeclared");
        let digest = crate::attempts::rung_digest(TEST_RUNG);
        let b = bundle_for(
            record(digest, c, t),
            serde_json::json!({
                CAND_REL: text,
                "research/admtest/uninvited.py": "print('hi')",
            }),
        );
        let err = admit_bundle(&tr.root, &tr.bundle_path(&b), false).unwrap_err();
        assert!(err.to_string().contains("undeclared"), "{err:#}");
        assert!(!tr.root.join("research/admtest/uninvited.py").exists());
    }

    #[test]
    fn rejects_duplicate_paths_with_conflicting_content() {
        let (text, c, t) = passing_candidate();
        let tr = TempRepo::new("duplicate");
        let digest = crate::attempts::rung_digest(TEST_RUNG);
        // The record's own landing path shipped again as a declared artifact
        // with different bytes: last-writer-wins must not decide this.
        let mut rec = record(digest, c, t);
        rec["artifacts"] = serde_json::json!([RECORD_REL]);
        let b = bundle_for(
            rec,
            serde_json::json!({CAND_REL: text, RECORD_REL: "not the record"}),
        );
        let err = admit_bundle(&tr.root, &tr.bundle_path(&b), false).unwrap_err();
        assert!(err.to_string().contains("twice with different content"), "{err:#}");
    }

    #[test]
    fn caps_the_files_one_bundle_may_create() {
        let (text, c, t) = passing_candidate();
        let tr = TempRepo::new("filecap");
        let digest = crate::attempts::rung_digest(TEST_RUNG);
        let mut rec = record(digest, c, t);
        let mut arts = serde_json::Map::new();
        arts.insert(CAND_REL.to_string(), serde_json::json!(text));
        let mut declared = Vec::new();
        for i in 0..MAX_FILES_PER_BUNDLE {
            let rel = format!("research/admtest/part-{i}.txt");
            arts.insert(rel.clone(), serde_json::json!("x"));
            declared.push(rel);
        }
        rec["artifacts"] = serde_json::json!(declared);
        let b = bundle_for(rec, serde_json::Value::Object(arts));
        let err = admit_bundle(&tr.root, &tr.bundle_path(&b), false).unwrap_err();
        assert!(err.to_string().contains("-file cap"), "{err:#}");
        assert!(!tr.root.join("research/admtest").exists(), "the cap fires before any write");
    }

    #[test]
    fn a_leaderboard_failure_rolls_back_every_file_written() {
        let (text, c, t) = passing_candidate();
        let tr = TempRepo::new("rollback");
        std::fs::write(tr.root.join("leaderboard/leaderboard.json"), "not json").unwrap();
        let digest = crate::attempts::rung_digest(TEST_RUNG);
        let b = bundle_for(record(digest, c, t), serde_json::json!({CAND_REL: text}));
        assert!(admit_bundle(&tr.root, &tr.bundle_path(&b), false).is_err());
        assert!(!tr.root.join(RECORD_REL).exists(), "record must be rolled back");
        assert!(!tr.root.join(CAND_REL).exists(), "candidate must be rolled back");
        assert!(!tr.root.join("research/admtest").exists(), "created dirs must be rolled back");
        assert_eq!(
            std::fs::read_to_string(tr.root.join("leaderboard/leaderboard.json")).unwrap(),
            "not json",
            "a failed admission must leave the leaderboard byte-identical"
        );
    }

    #[test]
    fn identical_prior_art_is_cited_not_rewritten() {
        let (text, c, t) = passing_candidate();
        let tr = TempRepo::new("priorart");
        std::fs::create_dir_all(tr.root.join("research/admtest")).unwrap();
        std::fs::write(tr.root.join(CAND_REL), &text).unwrap();
        let digest = crate::attempts::rung_digest(TEST_RUNG);
        let b = bundle_for(record(digest, c, t), serde_json::json!({CAND_REL: text}));
        let adm = admit_bundle(&tr.root, &tr.bundle_path(&b), false).unwrap();
        assert!(
            adm.files.iter().all(|f| f != CAND_REL),
            "an identical existing file is skipped, not rewritten: {:?}",
            adm.files
        );
    }

    #[test]
    fn an_unmeasurable_incumbent_is_never_displaced() {
        let (text, c, t) = passing_candidate();
        let tr = TempRepo::new("failclosed");
        // A solved entry whose best_program does not resolve in this tree:
        // with no size to compare, displacement must not happen at all.
        std::fs::write(
            tr.root.join("leaderboard/leaderboard.json"),
            serde_json::to_string_pretty(&serde_json::json!([
                {"rung_id": TEST_RUNG, "rank": 1, "status": "solved",
                 "best_program": "solutions/hello-world/vanished.mal",
                 "solver": {"display": "Standing Holder"}}
            ]))
            .unwrap(),
        )
        .unwrap();
        let digest = crate::attempts::rung_digest(TEST_RUNG);
        let b = bundle_for(record(digest, c, t), serde_json::json!({CAND_REL: text}));
        let adm = admit_bundle(&tr.root, &tr.bundle_path(&b), false).unwrap();
        assert!(
            adm.credited.is_empty(),
            "an incumbent whose size cannot be established keeps the rung: {:?}",
            adm.credited
        );
        let board: serde_json::Value = serde_json::from_str(
            &std::fs::read_to_string(tr.root.join("leaderboard/leaderboard.json")).unwrap(),
        )
        .unwrap();
        assert_eq!(board[0]["solver"]["display"], "Standing Holder");
    }

    #[test]
    fn displacement_clears_stale_attribution() {
        let (text, c, t) = passing_candidate();
        let tr = TempRepo::new("displace");
        // Standing credit: a larger on-disk program (same bytes plus trailing
        // whitespace, which the evaluator canonicalizes away) with a named
        // solver and manifest attached.
        std::fs::create_dir_all(tr.root.join("solutions/hello-world")).unwrap();
        std::fs::write(tr.root.join("solutions/hello-world/big.mal"), format!("{text}\n\n"))
            .unwrap();
        std::fs::write(
            tr.root.join("leaderboard/leaderboard.json"),
            serde_json::to_string_pretty(&serde_json::json!([
                {"rung_id": TEST_RUNG, "rank": 1, "status": "solved",
                 "best_program": "solutions/hello-world/big.mal",
                 "solver": {"display": "Previous Holder", "model": "old-model"},
                 "manifest": {"tokens": 1},
                 "date": "2098-01-01"}
            ]))
            .unwrap(),
        )
        .unwrap();
        let digest = crate::attempts::rung_digest(TEST_RUNG);
        let b = bundle_for(record(digest, c, t), serde_json::json!({CAND_REL: text}));
        let adm = admit_bundle(&tr.root, &tr.bundle_path(&b), false).unwrap();
        assert!(
            adm.credited.iter().any(|(r, _, displaced)| r == TEST_RUNG && *displaced),
            "the smaller aimed program must displace the standing credit: {:?}",
            adm.credited
        );
        let board: serde_json::Value = serde_json::from_str(
            &std::fs::read_to_string(tr.root.join("leaderboard/leaderboard.json")).unwrap(),
        )
        .unwrap();
        let entry = &board[0];
        assert!(
            entry.get("solver").is_none(),
            "the displaced solver's attribution must not survive onto a program \
             they did not write: {entry}"
        );
        assert!(entry.get("manifest").is_none(), "stale manifest must be cleared");
    }

    #[test]
    fn exhaustive_sweep_metric_reports_the_complete_contract() {
        const SWEEP_RUNG: &str = "L2.R0d.xor-1-len4096";
        let rung = crate::registry::find_rung(SWEEP_RUNG).unwrap();
        let bytes = std::fs::read(repo().join(
            "research/xor-1-len4096-codex/runs/hero1-joint150151-short-o0-0.mal",
        ))
        .unwrap();
        let outcome = crate::verify::verify_rung(&rung, &bytes, epochs_for(&rung));
        assert_eq!(
            format_metric(&rung, &outcome, &outcome.epochs[0], bytes.len()),
            "251/256 exhaustive cases, native re-verification; 2605 bytes"
        );
    }
}

/// Re-credit every rung to the smallest program on hand that passes it.
///
/// Admission sweeps a submission across the ladder, but records admitted before
/// that behaviour existed were only ever checked against the rung they named.
/// This is the repair pass, and it is idempotent: gather every candidate program
/// the repository knows about — shipped solutions and every attempt record's
/// best candidate — and give each rung to the smallest one the native VM says
/// passes it. Attribution follows the program: whichever record claims it.
pub fn recredit_all(repo: &Path) -> Result<Vec<(String, String, String, String)>> {
    // program path -> owning record (for attribution)
    let mut owner: std::collections::BTreeMap<String, AttemptRecord> = Default::default();
    let mut programs: std::collections::BTreeSet<String> = Default::default();

    // The corpus of the tree being recredited — NOT the compile-time source
    // checkout. With `--repo` pointing at the admission worktree the two
    // differ, and mixing them attributes this tree's leaderboard from another
    // tree's records while missing programs that exist only here.
    for rec in crate::attempts::load_attempts_at(repo) {
        if let Some(c) = &rec.best_candidate {
            programs.insert(c.program.clone());
            owner.entry(c.program.clone()).or_insert(rec.clone());
        }
    }
    for entry in glob_solutions(repo) {
        programs.insert(entry);
    }

    let path = repo.join("leaderboard/leaderboard.json");
    let mut board: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(&path)?)?;
    let mut changes = Vec::new();

    for entry in board.as_array_mut().context("leaderboard is not an array")? {
        let rung_id = match entry.get("rung_id").and_then(|v| v.as_str()) {
            Some(s) => s.to_string(),
            None => continue,
        };
        let Some(rung) = crate::registry::find_rung(&rung_id) else { continue };

        // Revoke a standing credit that no longer holds. Admission once ran
        // every rung at a single epoch, which let a seed-dependent rung be
        // credited to a program that passed one lucky draw. A repair pass that
        // can only add credits cannot undo that, so check the incumbent first.
        if entry.get("status").and_then(|s| s.as_str()) == Some("solved") {
            let holds = entry
                .get("best_program")
                .and_then(|p| p.as_str())
                .and_then(|p| crate::fspath::resolve_within_repo(repo, p).ok())
                .and_then(|abs| std::fs::read(abs).ok())
                .map(|b| crate::verify::verify_rung(&rung, &b, epochs_for(&rung)).passed)
                .unwrap_or(false);
            if !holds {
                let was = entry
                    .get("best_program").and_then(|p| p.as_str())
                    .unwrap_or("(unknown)").to_string();
                let obj = entry.as_object_mut().context("entry is not an object")?;
                obj.insert("status".into(), serde_json::json!("open"));
                obj.insert("best_program".into(), serde_json::Value::Null);
                obj.insert("solver".into(), serde_json::Value::Null);
                obj.insert("date".into(), serde_json::Value::Null);
                obj.insert("metric".into(), serde_json::Value::Null);
                obj.insert("note".into(), serde_json::json!(
                    "Open. A previous credit here did not survive re-verification at full epochs."));
                obj.remove("note_long");
                changes.push((rung_id.clone(), was, "(revoked — open)".to_string(),
                              format!("failed re-verification at {} epochs", epochs_for(&rung))));
                continue;
            }
        }

        // Smallest passing program wins the rung.
        let mut best: Option<(usize, String, String)> = None;
        for p in &programs {
            let Ok(abs) = crate::fspath::resolve_within_repo(repo, p) else { continue };
            let Ok(bytes) = std::fs::read(&abs) else { continue };
            if best.as_ref().is_some_and(|(n, _, _)| *n <= bytes.len()) {
                continue;
            }
            let outcome = crate::verify::verify_rung(&rung, &bytes, epochs_for(&rung));
            if !outcome.passed {
                continue;
            }
            let first = outcome.epochs.first().context("no epochs")?;
            best = Some((
                bytes.len(),
                p.clone(),
                format_metric(&rung, &outcome, first, bytes.len()),
            ));
        }

        let Some((_, prog, metric)) = best else { continue };
        let current = entry.get("best_program").and_then(|p| p.as_str()).unwrap_or("");
        if current == prog {
            continue;
        }
        // Same rule as admission: an incidental pass fills an open rung and
        // never displaces a standing credit, so a subset-input solve cannot
        // quietly take over the rungs beneath it.
        let solved_now = entry.get("status").and_then(|s| s.as_str()) == Some("solved");
        let aimed = owner.get(&prog).is_some_and(|r| r.rung_id == rung_id);
        if solved_now && !aimed {
            continue;
        }
        let was = if current.is_empty() { "(open)".to_string() } else { current.to_string() };

        let obj = entry.as_object_mut().context("entry is not an object")?;
        obj.insert("status".into(), serde_json::json!("solved"));
        obj.insert("best_program".into(), serde_json::json!(prog));
        obj.insert("metric".into(), serde_json::json!(metric.clone()));
        // Attribution follows the program that now holds the rung; whatever
        // the displaced credit carried is removed, not inherited.
        match owner.get(&prog) {
            Some(rec) => {
                obj.insert("date".into(), serde_json::json!(rec.date));
                apply_attribution(obj, &rec.solver, &rec.manifest)?;
                let display = rec.solver.as_ref().map(|s| s.display.as_str()).unwrap_or("an unattributed submission");
                let own = rec.rung_id == rung_id;
                obj.insert("note".into(), serde_json::json!(if own {
                    format!("Solved by {display}.")
                } else {
                    format!("Solved by {display}'s {} program, the smallest on the board that passes this rung.", rec.rung_id)
                }));
                obj.insert("note_long".into(), serde_json::json!(format!(
                    "Credited to the smallest program on the board that passes this rung ({metric}). \
                     It was submitted for {}. The submitter's account is in {}.",
                    rec.rung_id, rec.path
                )));
            }
            None => {
                // A shipped solution with no owning attempt record: the credit
                // is real (the verifier just confirmed it) but carries no
                // attribution, so none is shown.
                apply_attribution(obj, &None, &None)?;
                obj.insert("date".into(), serde_json::Value::Null);
                obj.insert("note".into(), serde_json::json!(format!(
                    "Credited to {prog}, the smallest shipped program that passes this rung."
                )));
                obj.remove("note_long");
            }
        }
        changes.push((rung_id, was, prog, metric));
    }

    write_leaderboard_atomic(&path, &board)?;
    Ok(changes)
}

fn glob_solutions(repo: &Path) -> Vec<String> {
    let mut out = Vec::new();
    let root = repo.join("solutions");
    let Ok(dirs) = std::fs::read_dir(&root) else { return out };
    for d in dirs.filter_map(|e| e.ok()) {
        let Ok(files) = std::fs::read_dir(d.path()) else { continue };
        for f in files.filter_map(|e| e.ok()) {
            let p = f.path();
            if p.extension().is_some_and(|x| x == "mal") {
                if let Ok(rel) = p.strip_prefix(repo) {
                    out.push(rel.to_string_lossy().to_string());
                }
            }
        }
    }
    out
}
