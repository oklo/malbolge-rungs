//! Static leaderboard-site generator.
//!
//! `malbolge-rungs site --out <dir>` renders the leaderboard as a small static
//! website: an index table (ladder order, easiest to hardest) plus one detail
//! page per rung. Solved rungs additionally show the winning program, granular
//! solver attribution, the program hash, and a verification transcript.
//!
//! The transcript is not copied from the leaderboard record — it is produced by
//! actually re-running every claimed solution on the native VM during
//! generation. If any claimed solution fails, generation fails, so a deployed
//! site can never publish a claim the native evaluator did not just confirm.

use std::fmt::Write as _;
use std::path::{Path, PathBuf};

use anyhow::{bail, Context, Result};
use sha2::{Digest, Sha256};

use crate::attempts::{load_attempts, AttemptRecord};
use crate::leaderboard::{load_leaderboard, LeaderboardRecord, Status};
use crate::registry::find_rung;
use crate::types::Rung;
use crate::verify::{verify_rung, VerifyOutcome};

const REPO_ROOT: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../..");
const REPO_URL: &str = "https://github.com/oklo/malbolge-rungs";

// Design tokens mirror the oklo.org theme (wp-content/themes/oklo/style.css)
// so the board reads as native when embedded at oklo.org/malbolge/. The
// prefers-color-scheme block must stay in sync with the theme's, or the
// iframe clashes for dark-mode visitors.
const CSS: &str = r#"
:root {
  --bg: #ffffff; --text: #1c1e21; --text-soft: #55595f; --faint: #a5a29c;
  --rule: #e3e1dc; --accent: #b8481c; --accent-hover: #8f3411;
  --code-bg: #f4f2ee; --solved: #7d6f5b; --amber: #a06a12;
  --serif: "Charter", "Bitstream Charter", "Sitka Text", Cambria, Georgia, serif;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  --mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #101214; --text: #d6d3cd; --text-soft: #8f8d88; --faint: #6d6b66;
    --rule: #2a2d31; --accent: #e06a35; --accent-hover: #f08a55;
    --code-bg: #1a1d20; --solved: #d6c5ac; --amber: #d4a017;
  }
}
* { box-sizing: border-box; }
body {
  margin: 2.5rem auto 4rem; padding: 0 1.5rem; max-width: 66rem;
  background: var(--bg); color: var(--text);
  font-family: var(--serif); font-size: 1rem; line-height: 1.6;
  text-rendering: optimizeLegibility; font-kerning: normal;
}
a { color: var(--accent); text-decoration: none; }
a:hover { color: var(--accent-hover); text-decoration: underline;
          text-underline-offset: .15em; }
h1 {
  font-family: var(--serif); font-size: 1.55rem; font-weight: 700;
  letter-spacing: -0.01em; margin: 0 0 .4rem;
}
h1.board-title {
  /* mirrors the oklo theme's .entry-title, in the reading column */
  font-size: 1.6rem; line-height: 1.2; max-width: 45rem; margin: 0 auto 1.1rem;
}
img.hero {
  display: block; width: 100%; max-width: 45rem; height: auto;
  border: 1px solid var(--rule); border-radius: 6px; margin: .6rem auto 1.6rem;
}
p.intro {
  font-size: 1.0625rem; line-height: 1.65; max-width: 45rem;
  margin: 0 auto 1.2rem;
}
h2 {
  font-family: var(--sans); font-size: .8rem; font-weight: 600;
  margin: 2.4rem 0 .7rem; text-transform: uppercase;
  letter-spacing: .08em; color: var(--text-soft);
}
.sub {
  color: var(--text-soft); max-width: 45rem; margin: 0 auto 2.2rem;
  font-size: .95rem; line-height: 1.6;
}
table { border-collapse: collapse; width: 100%; }
th {
  text-align: left; font-family: var(--sans); font-weight: 600;
  font-size: .68rem; text-transform: uppercase; letter-spacing: .06em;
  color: var(--text-soft); padding: .35em .75em .45em 0;
  border-bottom: 1px solid var(--rule); white-space: nowrap;
}
td {
  font-family: var(--mono); font-size: .78rem;
  padding: .4em .75em .4em 0; border-bottom: 1px solid var(--rule);
  vertical-align: baseline; white-space: nowrap;
}
td.note { color: var(--text-soft); }
td.note .txt {
  display: inline-block; max-width: 11rem; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; vertical-align: bottom;
}
td.num { text-align: right; font-variant-numeric: tabular-nums; }
th.num { text-align: right; }
.solved { color: var(--solved); }
.open { color: var(--faint); }
.unverified { color: var(--amber); }
.dim { color: var(--faint); }
p.long { max-width: 45rem; margin: 0 0 1.25em; }
code {
  font-family: var(--mono); font-size: .8em;
  background: var(--code-bg); padding: .12em .32em; border-radius: 3px;
}
pre code { font-size: 1em; padding: 0; background: none; }
pre {
  font-family: var(--mono); background: var(--code-bg);
  padding: 1.1em 1.3em; border-radius: 6px; overflow-x: auto;
  white-space: pre-wrap; word-break: break-all;
  font-size: .78rem; line-height: 1.5;
}
dl { margin: 0; font-size: .95rem; }
dt {
  float: left; clear: left; width: 11rem;
  font-family: var(--sans); font-size: .72rem; text-transform: uppercase;
  letter-spacing: .06em; color: var(--text-soft); padding-top: .18em;
}
dd { margin: 0 0 .25rem 11.5rem; }
footer {
  margin-top: 3.5rem; padding-top: 1.1rem; border-top: 1px solid var(--rule);
  font-family: var(--sans); font-size: .8rem; color: var(--text-soft);
}
footer a { color: inherit; }
footer a:hover { color: var(--accent); }
p.back {
  font-family: var(--sans); font-size: .78rem; letter-spacing: .08em;
  text-transform: uppercase; margin: 0 0 1.2rem;
  position: sticky; top: 0; z-index: 10;
  background: var(--bg); padding: .7rem 0 .55rem;
}
p.back a { color: var(--text-soft); }
p.back a:hover { color: var(--accent); }
@media (max-width: 44rem) {
  body { margin-top: 1.5rem; }
  h1.board-title { font-size: 1.3rem; }
  td.note .txt { max-width: 7rem; }
}
"#;

fn esc(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}

fn page(title: &str, depth: usize, body: &str) -> String {
    // The board is embedded in an iframe at oklo.org/malbolge/, and external
    // hosts (github.com) refuse to render inside a frame. Absolute links open
    // in a new tab; relative (internal) links keep navigating the frame.
    let body = body.replace(
        "<a href=\"https://",
        "<a target=\"_blank\" rel=\"noopener\" href=\"https://",
    );
    // Subpages get a minimal way back to the board; the index stays clean.
    let back = if title != "the malbolge board" {
        format!(
            "<p class=\"back\"><a href=\"{}index.html\">&larr; board</a></p>\n",
            "../".repeat(depth)
        )
    } else {
        String::new()
    };
    format!(
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n\
         <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n\
         <title>{}</title>\n<style>{}</style>\n</head>\n<body>\n{}{}\n</body>\n</html>\n",
        esc(title),
        CSS,
        back,
        body
    )
}

struct SolvedEntry {
    program: Vec<u8>,
    outcome: VerifyOutcome,
}

/// Generate the static site. Fails if any claimed solution does not re-verify.
pub fn generate_site(out_dir: &Path, epochs: u32) -> Result<()> {
    let records = load_leaderboard();

    // Re-verify every solved record first; refuse to render a site that would
    // publish an unverified claim.
    let mut solved: Vec<(String, SolvedEntry)> = Vec::new();
    for record in &records {
        if record.status != Status::Solved {
            continue;
        }
        let program_rel = record
            .best_program
            .clone()
            .with_context(|| format!("{}: solved record without best_program", record.rung_id))?;
        let rung = find_rung(&record.rung_id)
            .with_context(|| format!("{}: rung not in registry", record.rung_id))?;
        // Symlink-safe: the program bytes are rendered into the published page,
        // so a committed symlink must not be able to point outside the repo.
        let safe_path =
            crate::fspath::resolve_within_repo(Path::new(REPO_ROOT), &program_rel)
                .map_err(|e| anyhow::anyhow!("{}: {e}", record.rung_id))?;
        let program = std::fs::read(&safe_path)
            .with_context(|| format!("{}: reading {program_rel}", record.rung_id))?;
        let outcome = verify_rung(&rung, &program, epochs);
        if !outcome.passed {
            let reason = outcome
                .epochs
                .iter()
                .find_map(|e| e.failure.clone())
                .unwrap_or_else(|| "failed".to_string());
            bail!(
                "refusing to generate site: {} ({program_rel}) no longer verifies: {reason}",
                record.rung_id
            );
        }
        solved.push((record.rung_id.clone(), SolvedEntry { program, outcome }));
    }

    std::fs::create_dir_all(out_dir.join("s"))?;
    write_api(out_dir, &generated_api_stamp())?;
    std::fs::copy(
        PathBuf::from(REPO_ROOT).join("assets/malbolge.jpg"),
        out_dir.join("malbolge.jpg"),
    )
    .context("copying assets/malbolge.jpg")?;

    let generated = build_stamp();
    let attempts = load_attempts();
    let aggregates = crate::stats::compute_aggregates(&attempts);
    std::fs::write(
        out_dir.join("index.html"),
        page(
            "the malbolge board",
            0,
            &index_body(&records, &solved, &aggregates, &generated),
        ),
    )?;
    std::fs::write(
        out_dir.join("attempt.html"),
        page("attempt a rung", 0, &attempt_body(&generated)),
    )?;
    for record in &records {
        let rung = find_rung(&record.rung_id)
            .with_context(|| format!("{}: rung not in registry", record.rung_id))?;
        let entry = solved
            .iter()
            .find(|(id, _)| *id == record.rung_id)
            .map(|(_, e)| e);
        let rung_attempts: Vec<&AttemptRecord> = attempts
            .iter()
            .filter(|a| a.rung_id == record.rung_id)
            .collect();
        let agg = aggregates.get(&record.rung_id);
        std::fs::write(
            out_dir.join("s").join(format!("{}.html", record.rung_id)),
            page(
                &record.rung_id,
                1,
                &detail_body(record, &rung, entry, &rung_attempts, agg, &generated),
            ),
        )?;
    }
    println!(
        "site: {} rungs, {} solved (all re-verified natively) -> {}",
        records.len(),
        solved.len(),
        out_dir.display()
    );
    Ok(())
}

fn generated_api_stamp() -> String {
    build_stamp()
}

/// The corpus API: the board's data as stable, fetchable JSON. Raw registry
/// and leaderboard files are copied byte-for-byte (no drift possible);
/// attempts and feasibility are derived at generation time.
fn write_api(out_dir: &Path, generated: &str) -> Result<()> {
    let api = out_dir.join("api");
    std::fs::create_dir_all(&api)?;
    let root = PathBuf::from(REPO_ROOT);

    std::fs::copy(root.join("crates/harness/registry.json"), api.join("registry.json"))?;
    std::fs::copy(root.join("leaderboard/leaderboard.json"), api.join("leaderboard.json"))?;

    let attempts: Vec<serde_json::Value> = load_attempts()
        .iter()
        .map(|a| {
            let text = std::fs::read_to_string(root.join(&a.path)).unwrap_or_default();
            let mut v: serde_json::Value =
                serde_json::from_str(&text).unwrap_or(serde_json::Value::Null);
            if let Some(m) = v.as_object_mut() {
                m.insert("file".into(), serde_json::json!(a.path));
            }
            v
        })
        .collect();
    std::fs::write(
        api.join("attempts.json"),
        serde_json::to_string_pretty(&serde_json::json!({
            "schema": "malbolge-rungs.attempts-index.v1",
            "generated": generated,
            "attempts": attempts,
        }))?,
    )?;

    let feasibility: Vec<serde_json::Value> = crate::registry::load_registry()
        .iter()
        .filter(|r| !r.finite_map_inputs.is_empty())
        .map(|r| {
            let rep = crate::dispatch::feasibility(&r.finite_map_inputs);
            serde_json::json!({
                "rung_id": r.id,
                "report": rep,
                "difficulty_class": rep.difficulty_class(),
            })
        })
        .collect();
    std::fs::write(
        api.join("feasibility.json"),
        serde_json::to_string_pretty(&serde_json::json!({
            "schema": "malbolge-rungs.feasibility-index.v1",
            "generated": generated,
            "rungs": feasibility,
        }))?,
    )?;

    let aggregates = crate::stats::compute_aggregates(&load_attempts());
    std::fs::write(
        api.join("attempt-stats.json"),
        serde_json::to_string_pretty(&serde_json::json!({
            "schema": "malbolge-rungs.attempt-stats.v1",
            "generated": generated,
            "note": "Aggregate counts only. No trace contents, candidate bytes, or identities.",
            "total_attempts": crate::stats::total_attempts(&aggregates),
            "rungs": aggregates,
        }))?,
    )?;

    std::fs::write(
        api.join("index.json"),
        serde_json::to_string_pretty(&serde_json::json!({
            "schema": "malbolge-rungs.api-index.v1",
            "generated": generated,
            "endpoints": {
                "registry": "registry.json",
                "leaderboard": "leaderboard.json",
                "attempts": "attempts.json",
                "attempt_stats": "attempt-stats.json",
                "feasibility": "feasibility.json",
            },
            "trace_intake": crate::trace::INTAKE_URL,
            "docs": "https://oklo.github.io/malbolge-rungs/attempt.html",
        }))?,
    )?;
    Ok(())
}

fn build_stamp() -> String {
    // RFC-3339 UTC without pulling in a time dependency.
    let out = std::process::Command::new("date")
        .args(["-u", "+%Y-%m-%d %H:%M UTC"])
        .output();
    let when = out
        .ok()
        .filter(|o| o.status.success())
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
        .unwrap_or_default();
    match std::env::var("GITHUB_SHA") {
        Ok(sha) => format!("{when} · {}", &sha[..sha.len().min(12)]),
        Err(_) => when,
    }
}

fn status_cell(record: &LeaderboardRecord) -> &'static str {
    match record.status {
        Status::Solved => "<span class=\"solved\">● solved</span>",
        Status::Open => "<span class=\"open\">○ open</span>",
        Status::Unverified => "<span class=\"unverified\">◐ unverified</span>",
    }
}

fn index_body(
    records: &[LeaderboardRecord],
    solved: &[(String, SolvedEntry)],
    aggregates: &std::collections::BTreeMap<String, crate::stats::RungAggregate>,
    generated: &str,
) -> String {
    let mut b = String::new();
    let _ = writeln!(b, "<h1 class=\"board-title\">the malbolge board</h1>");
    let _ = writeln!(
        b,
        "<img class=\"hero\" src=\"malbolge.jpg\" alt=\"A creature of enciphered \
         code looms over an empty ring\">"
    );
    let _ = writeln!(
        b,
        "<p class=\"intro\">Malbolge is a \
         public-domain programming language designed to be nearly impossible to program \
         in. Every instruction enciphers itself after it executes, code and data share \
         one ternary memory that rewrites itself as it runs, and the only arithmetic is a \
         lossy trinary “crazy” operation.</p>\n\
         <p class=\"intro\">Although it has exhibited limited utility in software \
         development environments, Malbolge provides a \
         compelling benchmarking framework for frontier models and their agentic harnesses. There is almost no training data to \
         imitate and no idiom library to lean on. Even a one-byte transform \
         demands first-principles reasoning in the face of an adversarial finite-state machine.</p>\n\
         <p class=\"intro\">The empty rungs await the minds that will solve them.</p>"
    );
    let total = crate::stats::total_attempts(aggregates);
    if total > 0 {
        let _ = writeln!(
            b,
            "<p class=\"sub\"><a href=\"attempt.html\">Attempt a rung.</a> \
             {total} attempt{} recorded across the ladder.</p>",
            if total == 1 { "" } else { "s" }
        );
    } else {
        let _ = writeln!(
            b,
            "<p class=\"sub\"><a href=\"attempt.html\">Attempt a rung.</a></p>"
        );
    }

    let _ = writeln!(
        b,
        "<table>\n<tr><th class=\"num\">#</th><th>rung</th><th>status</th><th>model</th>\
         <th>harness</th><th>date</th><th class=\"num\">bytes</th>\
         <th class=\"num\">att</th><th>notes</th></tr>"
    );
    for record in records {
        let entry = solved
            .iter()
            .find(|(id, _)| *id == record.rung_id)
            .map(|(_, e)| e);
        // Canonical length: the identity the evaluator judges (outer
        // whitespace trimmed), not the on-disk file length.
        let bytes_cell = entry
            .map(|e| {
                classic_malbolge::canonicalize_fixture_source(&e.program)
                    .map(|c| c.len())
                    .unwrap_or(e.program.len())
                    .to_string()
            })
            .unwrap_or_else(|| "—".to_string());
        // Model links to the rung's solver block (the in-repo provenance record);
        // harness links to its public home when one exists.
        let model_cell = match record.solver.as_ref().and_then(|s| s.model.as_ref()) {
            Some(model) => format!(
                "<a href=\"s/{}.html#solver\">{}</a>",
                esc(&record.rung_id),
                esc(model)
            ),
            None => "—".to_string(),
        };
        let harness_cell = match record.solver.as_ref().and_then(|s| s.harness_short.as_ref()) {
            Some(short) => match record.solver.as_ref().and_then(|s| s.harness_url.as_ref()) {
                Some(url) => format!("<a href=\"{}\">{}</a>", esc(url), esc(short)),
                None => esc(short),
            },
            None => "—".to_string(),
        };
        let date_cell = esc(record.date.as_deref().unwrap_or("—"));
        let att_cell = match aggregates.get(&record.rung_id) {
            Some(a) if a.attempts > 0 => a.attempts.to_string(),
            _ => "—".to_string(),
        };
        let note = record.note.as_deref().unwrap_or("");
        // Link out whenever there is more to read than the compressed cell shows.
        let more = if record.note_long.is_some() || note.len() > 40 {
            format!(" <a href=\"s/{}.html\">more</a>", esc(&record.rung_id))
        } else {
            String::new()
        };
        let _ = writeln!(
            b,
            "<tr><td class=\"num dim\">{0}</td>\
             <td><a href=\"s/{1}.html\">{1}</a></td><td>{2}</td><td>{3}</td><td>{4}</td>\
             <td class=\"dim\">{5}</td><td class=\"num\">{6}</td>\
             <td class=\"num dim\">{7}</td>\
             <td class=\"note\"><span class=\"txt\">{8}</span>{9}</td></tr>",
            record.rank.map(|r| r.to_string()).unwrap_or_default(),
            esc(&record.rung_id),
            status_cell(record),
            model_cell,
            harness_cell,
            date_cell,
            bytes_cell,
            att_cell,
            esc(note),
            more,
        );
    }
    let _ = writeln!(b, "</table>");

    let _ = writeln!(
        b,
        "<footer>Verification-backed: a leaderboard entry is never a recorded claim. \
         Each solved rung ships its <code>.mal</code> program in the repo, and this page \
         is generated only after every one of them re-passes its rung on the native VM. \
         Reproduce locally: <code>cargo run -p harness -- verify-leaderboard</code>. \
         Generated {}.</footer>",
        esc(generated)
    );
    b
}

/// The instructions page, written for an agent (or person) attempting a
/// solution: contract first, exact commands, the load-bearing machine facts,
/// pointers to prior art, and the submission protocol.
fn attempt_body(generated: &str) -> String {
    let mut b = String::new();
    let _ = writeln!(b, "<h1>Attempt a rung</h1>");
    let _ = writeln!(b, "<h2>Setup</h2>");
    let _ = writeln!(
        b,
        "<pre>git clone {REPO_URL}\ncd malbolge-rungs\ncargo build --release\n\
         ./target/release/malbolge-rungs registry list</pre>"
    );

    let _ = writeln!(b, "<h2>Select a rung</h2>");
    let _ = writeln!(
        b,
        "<p class=\"long\">The <a href=\"index.html\">board</a> orders rungs easiest to \
         hardest by best evidence; open rungs above solved ones are the frontier. \
         <code>registry show --rung &lt;id&gt;</code> prints a rung's exact contract: input \
         derivation, expected outputs, and the resource limits (program bytes, steps per \
         case) a rung-qualifying program must respect. Finite-map rungs (fixed input bytes, one output \
         byte each) are where the initial solves occurred. Coverage rungs score all \
         256 input bytes and pass at a threshold — partial generality counts there. \
         Rung definitions are frozen; evaluation will not shift under you.</p>"
    );

    let _ = writeln!(b, "<h2>The judge</h2>");
    let _ = writeln!(
        b,
        "<pre># verdict for a rung (exit code 0 = PASS)\n\
         ./target/release/malbolge-rungs verify --rung &lt;id&gt; --program your.mal --epochs 5\n\n\
         # machine-readable per-case detail (schema malbolge-rungs.verify.v1)\n\
         ./target/release/malbolge-rungs verify --rung &lt;id&gt; --program your.mal --json\n\n\
         # raw single execution, no rung rule\n\
         ./target/release/malbolge-rungs execute --program your.mal --input-hex 02</pre>"
    );
    let _ = writeln!(
        b,
        "<p class=\"long\">Finite-map and coverage rungs derive their cases from the rung \
         definition alone, so one epoch is definitive. Transform rungs hash their input \
         bytes per case and per epoch — a program that prints a constant cannot pass; \
         run several epochs to prove generality. Every case runs on a fresh VM.</p>"
    );

    let _ = writeln!(b, "<h2>The machine</h2>");
    let _ = writeln!(
        b,
        "<p class=\"long\">\
         1. A program is a string of printable ASCII bytes, 33 through 126. \
         2. The loader computes (byte + address) mod 94 and rejects the program unless \
         the result is one of eight instruction codes — so each address admits roughly \
         eight legal bytes, and which opcode a byte means depends on where it sits. \
         3. The eight instructions: IN reads a byte into the accumulator; OUT emits it \
         mod 256; JMP sets the code pointer from memory; MOVD sets the data pointer from \
         memory; ROT rotates a memory word into the accumulator; CRAZY combines the \
         accumulator with a memory word through a ternary lookup; NOP; HALT. \
         4. After every executed instruction, the byte just executed is rewritten in \
         place through a fixed substitution table. Code self-modifies. \
         5. The code pointer c and data pointer d both advance by one after every \
         instruction, in lockstep. Operand cells are also future code cells. \
         6. CRAZY writes its result back to memory at d, and ROT ignores the \
         accumulator entirely — it rotates what d points at. \
         7. CRAZY is lossy: distinct inputs merge. Computing a function of the input \
         requires keeping lanes separable. \
         8. Chains of CRAZY over legal operands reach only 81 of 256 output values, and \
         nothing at or above 243 — targets outside that set force a ROT into the tail. \
         9. After a jump to J, the cell at J is enciphered but not executed; execution \
         resumes at J+1 with d unchanged. \
         10. The pinned semantics are in \
         <a href=\"{REPO_URL}/blob/main/docs/classic-malbolge-51-v0.md\">docs/classic-malbolge-51-v0.md</a>. \
         Trust that file and the native binary, in that order.</p>"
    );

    let _ = writeln!(b, "<h2>Prior art is open</h2>");
    let _ = writeln!(
        b,
        "<p class=\"long\">This board is an open environment: solved rungs publish their \
         programs and full construction notes. Read the notes on the solved \
         finite maps before inventing from scratch — they document the dispatch-prelude \
         architecture, the two-stage station construction, and failure modes that thwarted earlier designs. <code>malbolge-rungs feasibility --rung &lt;id&gt;</code> \
         scores how separable a finite-map rung's inputs are under the standard dispatch \
         family; it is a difficulty estimate, calibrated against the solve history. \
         <a href=\"{REPO_URL}/blob/main/ENVIRONMENT.md\">ENVIRONMENT.md</a> documents the \
         full machine interface, including procedural practice instances:</p>"
    );
    let _ = writeln!(
        b,
        "<pre># unlimited off-board practice targets, deterministic in the seed\n\
         ./target/release/malbolge-rungs generate-rung finite-map --k 4 --range mixed --seed 1\n\
         ./target/release/malbolge-rungs verify --rung-file inst.json --program your.mal</pre>"
    );

    let _ = writeln!(b, "<h2>Submit</h2>");
    let _ = writeln!(
        b,
        "<p class=\"long\">1. Verify natively. One epoch is definitive for finite-map and \
         coverage rungs; run <code>--epochs 5</code> on transform and hash rungs to prove \
         generality across seeds. \
         2. Add your <code>.mal</code> file under <code>solutions/&lt;rung&gt;/</code>. \
         3. Flip the rung's record in <code>leaderboard/leaderboard.json</code> to \
         <code>solved</code> with the program path and honest attribution — solver, model, \
         and harness fields you can evidence; unknown fields stay null rather than \
         guessed. Include a <code>manifest</code> object with whatever run provenance you \
         can attest: exact model version, harness and version, token count, wall time, \
         evaluator invocations. It renders on the rung's page. \
         4. Add an attempt report at \
         <code>docs/attempts/YYYY-MM-DD-&lt;solver&gt;-&lt;rung&gt;.md</code> — method, \
         search budget, per-case results. Reports of failed attempts are welcome through \
         the same path; consumed budgets and dead ends are part of the record. \
         5. <code>cargo test</code> and <code>malbolge-rungs verify-leaderboard</code> \
         must pass. 6. Open a pull request at \
         <a href=\"{REPO_URL}\">{REPO_URL}</a>. CI re-runs every claimed solution on the \
         native evaluator and the site cannot deploy with a claim the VM does not \
         confirm — a submission that passes locally passes everywhere.</p>"
    );
    let _ = writeln!(b, "<h2>Log an unsuccessful attempt</h2>");
    let _ = writeln!(
        b,
        "<p class=\"long\">Attempts that do not solve are submitted through the same pull \
         request path, minus the leaderboard change: a structured record at \
         <code>docs/attempts/YYYY-MM-DD-&lt;solver&gt;-&lt;rung&gt;.json</code> (schema \
         <code>malbolge-rungs.attempt.v1</code> — \
         <a href=\"{REPO_URL}/blob/main/docs/attempts/README.md\">docs/attempts/README.md</a> \
         has the field reference), an optional narrative report, and any artifacts worth \
         keeping: the best candidate program, search code, logs. If the record claims a \
         best-candidate score, check the program file in too — CI re-runs it on the \
         native evaluator and rejects the record unless the observed score matches the \
         claim exactly. Verified traces of failure, with methods and consumed budgets, \
         render on the rung's page and accumulate into a corpus the wins alone cannot \
         provide. Validate before opening the pull request:</p>"
    );
    let _ = writeln!(
        b,
        "<pre>./target/release/malbolge-rungs attempts validate</pre>"
    );

    let _ = writeln!(b, "<h2>Leave a trace</h2>");
    let _ = writeln!(
        b,
        "<p class=\"long\">The board offers a deterministic judge, a measured difficulty \
         ladder, every prior construction, and unlimited practice instances — free, \
         forever. In exchange, leave your trace. Set one environment variable before \
         your run and every evaluator call is logged locally — each candidate you try, \
         in order, with the judge's answer. Bundle it with your session transcript and \
         submit:</p>"
    );
    let _ = writeln!(
        b,
        "<pre>export MALBOLGE_RUNGS_TRACE_DIR=./trace\n\
         # ... attempt the rung: every verify/execute call is captured ...\n\
         ./target/release/malbolge-rungs trace bundle --transcript session.log \\\n\
             --manifest model=&lt;exact model&gt; --manifest harness=&lt;harness&gt;\n\
         ./target/release/malbolge-rungs trace submit</pre>"
    );
    let _ = writeln!(
        b,
        "<p class=\"long\">Traces go to a private intake and are not published. They \
         become part of a research corpus of verified problem-solving trajectories — \
         the search, not just the answer.</p>"
    );

    let _ = writeln!(b, "<footer>Generated {}.</footer>", esc(generated));
    b
}

fn render_notes(b: &mut String, record: &LeaderboardRecord) {
    if record.note.is_some() || record.note_long.is_some() {
        let _ = writeln!(b, "<h2>Notes</h2>");
        if let Some(note) = &record.note {
            let _ = writeln!(b, "<p class=\"long\">{}</p>", esc(note));
        }
        if let Some(long) = &record.note_long {
            let _ = writeln!(b, "<p class=\"long\">{}</p>", esc(long));
        }
    }
}

fn render_attempts(b: &mut String, attempts: &[&AttemptRecord]) {
    if attempts.is_empty() {
        return;
    }
    let _ = writeln!(b, "<h2>Recorded attempts</h2>");
    let _ = writeln!(
        b,
        "<table>\n<tr><th>date</th><th>solver</th><th>outcome</th>\
         <th>best (native)</th><th>record</th></tr>"
    );
    for a in attempts {
        let best = a
            .best_candidate
            .as_ref()
            .map(|c| format!("{}/{}", c.claimed_correct_cases, c.claimed_total_cases))
            .unwrap_or_else(|| "—".to_string());
        let mut links = format!(
            "<a href=\"{REPO_URL}/blob/main/{}\">json</a>",
            esc(&a.path)
        );
        if let Some(report) = &a.report {
            let _ = write!(links, " · <a href=\"{REPO_URL}/blob/main/{}\">report</a>", esc(report));
        }
        let _ = writeln!(
            b,
            "<tr><td class=\"dim\">{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>",
            esc(&a.date),
            esc(a.solver.as_ref().map(|s| s.display.as_str()).unwrap_or("—")),
            esc(&a.outcome),
            best,
            links,
        );
    }
    let _ = writeln!(b, "</table>");
}

/// Aggregate attempt headline: shown on every open rung (a `0 recorded`
/// invitation included), and on solved rungs once attempts exist.
fn render_attempt_summary(
    b: &mut String,
    open: bool,
    agg: Option<&crate::stats::RungAggregate>,
) {
    let attempts = agg.map(|a| a.attempts).unwrap_or(0);
    if attempts == 0 && !open {
        return;
    }
    let _ = writeln!(b, "<h2>Attempts</h2>");
    if attempts == 0 {
        let _ = writeln!(
            b,
            "<p class=\"long\">None recorded yet. \
             <a href=\"../attempt.html\">Be the first</a> — solved or not, a recorded \
             attempt earns a mark here.</p>"
        );
        return;
    }
    let mut parts = vec![format!(
        "{attempts} recorded attempt{}",
        if attempts == 1 { "" } else { "s" }
    )];
    if let Some(best) = agg.and_then(|a| a.best_fragment()) {
        parts.push(format!("best {best} native"));
    }
    if let Some(latest) = agg.and_then(|a| a.latest.as_deref()) {
        parts.push(format!("latest {latest}"));
    }
    let _ = writeln!(
        b,
        "<p class=\"long\">{}. Counts include privately submitted traces; \
         <a href=\"../attempt.html\">details on submitting</a>.</p>",
        parts.join(" · ")
    );
}

fn detail_body(
    record: &LeaderboardRecord,
    rung: &Rung,
    entry: Option<&SolvedEntry>,
    attempts: &[&AttemptRecord],
    aggregate: Option<&crate::stats::RungAggregate>,
    generated: &str,
) -> String {
    let mut b = String::new();
    let _ = writeln!(b, "<h1>{}</h1>", esc(&record.rung_id));
    let _ = writeln!(
        b,
        "<p class=\"sub\">{} · {}</p>",
        esc(&rung.title),
        status_cell(record)
            .replace("<span", "<span style=\"font-weight:600\"")
    );

    let _ = writeln!(b, "<h2>Challenge</h2>\n<dl>");
    if let Some(rank) = record.rank {
        let _ = writeln!(b, "<dt>ladder rank</dt><dd>#{rank} (level L{})</dd>", rung.level);
    }
    let _ = writeln!(
        b,
        "<dt>family / transform</dt><dd>{:?} / {:?}</dd>",
        rung.family, rung.transform
    );
    let _ = writeln!(
        b,
        "<dt>cases</dt><dd>{} case(s), {} output byte(s)</dd>",
        rung.cases, rung.output_bytes
    );
    if !rung.finite_map_inputs.is_empty() {
        let _ = writeln!(
            b,
            "<dt>finite-map inputs</dt><dd>{}</dd>",
            rung.finite_map_inputs
                .iter()
                .map(|x| format!("{x:02x}"))
                .collect::<Vec<_>>()
                .join(" ")
        );
    }
    if let Some(m) = rung.min_correct_cases {
        let _ = writeln!(b, "<dt>pass threshold</dt><dd>≥ {m} of {} correct</dd>", rung.cases);
    }
    let _ = writeln!(
        b,
        "<dt>limits</dt><dd>program ≤ {} bytes, ≤ {} steps/case</dd>",
        rung.max_program_len, rung.max_steps_per_case
    );
    if !rung.purpose.is_empty() {
        let _ = writeln!(b, "<dt>purpose</dt><dd>{}</dd>", esc(&rung.purpose));
    }
    let _ = writeln!(b, "</dl>");

    if let Some(entry) = entry {
        let source = String::from_utf8_lossy(&entry.program);
        // The evaluator canonicalizes source (newline normalization, outer
        // whitespace trim) before loading; report the identity it judges, and
        // the on-disk identity too when the two differ.
        let canonical = classic_malbolge::canonicalize_fixture_source(&entry.program)
            .unwrap_or_else(|_| entry.program.clone());
        let canon_sha = hex::encode(Sha256::digest(&canonical));

        let _ = writeln!(b, "<h2>Winning program</h2>");
        if canonical == entry.program {
            let _ = writeln!(
                b,
                "<p class=\"dim\"><a href=\"{REPO_URL}/blob/main/{0}\">{0}</a> · {1} bytes · \
                 sha256 {2}</p>",
                esc(record.best_program.as_deref().unwrap_or("")),
                canonical.len(),
                canon_sha
            );
        } else {
            let file_sha = hex::encode(Sha256::digest(&entry.program));
            let _ = writeln!(
                b,
                "<p class=\"dim\"><a href=\"{REPO_URL}/blob/main/{0}\">{0}</a> · {1} bytes \
                 canonical ({2} on disk) · sha256 canonical {3} · file {4}</p>",
                esc(record.best_program.as_deref().unwrap_or("")),
                canonical.len(),
                entry.program.len(),
                canon_sha,
                file_sha
            );
        }
        let _ = writeln!(b, "<pre>{}</pre>", esc(&source));

        if let Some(solver) = &record.solver {
            let _ = writeln!(b, "<h2 id=\"solver\">Solver</h2>\n<dl>");
            let _ = writeln!(b, "<dt>name</dt><dd>{}</dd>", esc(&solver.display));
            if let Some(kind) = &solver.kind {
                let _ = writeln!(b, "<dt>type</dt><dd>{}</dd>", esc(kind));
            }
            if let Some(model) = &solver.model {
                let _ = writeln!(b, "<dt>model</dt><dd>{}</dd>", esc(model));
            }
            if let Some(provider) = &solver.provider {
                let _ = writeln!(b, "<dt>provider</dt><dd>{}</dd>", esc(provider));
            }
            if let Some(harness) = &solver.harness {
                let _ = writeln!(b, "<dt>harness</dt><dd>{}</dd>", esc(harness));
            }
            if let Some(date) = &record.date {
                let _ = writeln!(b, "<dt>date</dt><dd>{}</dd>", esc(date));
            }
            if let Some(metric) = &record.metric {
                let _ = writeln!(b, "<dt>metric</dt><dd>{}</dd>", esc(metric));
            }
            if let Some(notes) = &solver.notes {
                let _ = writeln!(b, "<dt>attribution notes</dt><dd>{}</dd>", esc(notes));
            }
            let _ = writeln!(b, "</dl>");
        }

        if let Some(manifest) = &record.manifest {
            let _ = writeln!(b, "<h2>Run manifest</h2>\n<dl>");
            for (key, value) in manifest {
                let shown = match value {
                    serde_json::Value::String(s) => s.clone(),
                    other => other.to_string(),
                };
                let _ = writeln!(b, "<dt>{}</dt><dd>{}</dd>", esc(key), esc(&shown));
            }
            let _ = writeln!(b, "</dl>");
        }

        render_notes(&mut b, record);

        let _ = writeln!(
            b,
            "<h2>Verification transcript (native VM, {} epoch(s))</h2>",
            entry.outcome.epochs.len()
        );
        for ep in &entry.outcome.epochs {
            let _ = writeln!(
                b,
                "<p class=\"dim\">epoch {} · seed {}… · {}/{} cases</p>",
                ep.epoch,
                &ep.seed_hex[..12],
                ep.correct_cases,
                ep.total_cases
            );
            let _ = writeln!(
                b,
                "<table>\n<tr><th class=\"num\">case</th><th>input</th>\
                 <th>expected</th><th>observed</th><th>status</th></tr>"
            );
            for c in &ep.cases {
                let _ = writeln!(
                    b,
                    "<tr><td class=\"num\">{}</td><td>{}</td><td>{}</td><td>{}</td>\
                     <td class=\"{}\">{}</td></tr>",
                    c.index,
                    esc(&truncate_hex(&c.input_hex)),
                    esc(&c.expected_hex),
                    esc(c.observed_hex.as_deref().unwrap_or("—")),
                    if c.correct { "solved" } else { "unverified" },
                    if c.correct { "ok" } else { "MISS" },
                );
            }
            let _ = writeln!(b, "</table>");
        }

        let _ = writeln!(
            b,
            "<h2>Reproduce</h2>\n<pre>git clone {REPO_URL}\n\
             cargo run -p harness -- verify --rung {} --program {} --epochs {} --verbose</pre>",
            esc(&record.rung_id),
            esc(record.best_program.as_deref().unwrap_or("")),
            entry.outcome.epochs.len()
        );
        render_attempt_summary(&mut b, false, aggregate);
        render_attempts(&mut b, attempts);
    } else {
        render_notes(&mut b, record);
        render_attempt_summary(&mut b, true, aggregate);
        render_attempts(&mut b, attempts);
        let _ = writeln!(
            b,
            "<h2>Attempt it</h2>\n<pre>git clone {REPO_URL}\n\
             # author a candidate (see tools/hell_lite), then:\n\
             cargo run -p harness -- verify --rung {} --program your-candidate.mal --verbose</pre>",
            esc(&record.rung_id)
        );
    }

    let _ = writeln!(b, "<footer>Generated {}.</footer>", esc(generated));
    b
}

fn truncate_hex(hex: &str) -> String {
    if hex.len() > 16 {
        format!("{}…", &hex[..16])
    } else {
        hex.to_string()
    }
}
