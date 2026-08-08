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
  --code-bg: #f4f2ee; --green: #2e7d3a; --amber: #a06a12;
  --serif: "Charter", "Bitstream Charter", "Sitka Text", Cambria, Georgia, serif;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  --mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #101214; --text: #d6d3cd; --text-soft: #8f8d88; --faint: #6d6b66;
    --rule: #2a2d31; --accent: #e06a35; --accent-hover: #f08a55;
    --code-bg: #1a1d20; --green: #7fb069; --amber: #d4a017;
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
  font-family: var(--sans); font-size: 1.55rem; font-weight: 700;
  letter-spacing: -0.01em; margin: 0 0 .4rem;
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
.solved { color: var(--green); }
.open { color: var(--faint); }
.unverified { color: var(--amber); }
.dim { color: var(--faint); }
p.long { max-width: 45rem; margin: 0 0 1.25em; }
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
@media (max-width: 44rem) {
  body { margin-top: 1.5rem; }
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
    let _ = depth;
    format!(
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n\
         <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n\
         <title>{}</title>\n<style>{}</style>\n</head>\n<body>\n{}\n</body>\n</html>\n",
        esc(title),
        CSS,
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
        let program = std::fs::read(PathBuf::from(REPO_ROOT).join(&program_rel))
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
    std::fs::copy(
        PathBuf::from(REPO_ROOT).join("assets/malbolge.jpg"),
        out_dir.join("malbolge.jpg"),
    )
    .context("copying assets/malbolge.jpg")?;

    let generated = build_stamp();
    std::fs::write(
        out_dir.join("index.html"),
        page("malbolge-rungs", 0, &index_body(&records, &solved, &generated)),
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
        std::fs::write(
            out_dir.join("s").join(format!("{}.html", record.rung_id)),
            page(
                &record.rung_id,
                1,
                &detail_body(record, &rung, entry, &generated),
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
    generated: &str,
) -> String {
    let mut b = String::new();
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
         <p class=\"intro\">The Malbolge language provides a \
         compelling benchmarking framework. There is almost no training data to \
         imitate and no idiom library to lean on. Even a one-byte transform \
         demands first-principles reasoning about an adversarial machine. The empty \
         rungs below await the minds that will solve them.</p>"
    );
    let _ = writeln!(
        b,
        "<p class=\"sub\"><a href=\"attempt.html\">Attempt a rung.</a></p>"
    );

    let _ = writeln!(
        b,
        "<table>\n<tr><th class=\"num\">#</th><th>rung</th><th>status</th><th>model</th>\
         <th>harness</th><th>date</th><th class=\"num\">bytes</th><th>notes</th></tr>"
    );
    for record in records {
        let entry = solved
            .iter()
            .find(|(id, _)| *id == record.rung_id)
            .map(|(_, e)| e);
        let bytes_cell = entry
            .map(|e| e.program.len().to_string())
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
             <td class=\"note\"><span class=\"txt\">{7}</span>{8}</td></tr>",
            record.rank.map(|r| r.to_string()).unwrap_or_default(),
            esc(&record.rung_id),
            status_cell(record),
            model_cell,
            harness_cell,
            date_cell,
            bytes_cell,
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
         Using the rungs as an RL / eval substrate (reward oracle, procedural instance \
         generation, contamination policy): \
         <a href=\"{REPO_URL}/blob/main/ENVIRONMENT.md\">ENVIRONMENT.md</a>. \
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
    let _ = writeln!(
        b,
        "<p class=\"long\">The task: write a classic-Malbolge program that solves an open \
         rung. One command is the judge. It runs your program on the native \
         <a href=\"{REPO_URL}/blob/main/docs/classic-malbolge-51-v0.md\">Classic-Malbolge-51 v0</a> \
         evaluator over the rung's cases and exits 0 only on a pass. There is no partial \
         credit except on coverage rungs, no appeal, and no other judge — the Python VM in \
         <code>tools/hell_lite</code> is a diagnostic aid whose verdict counts for nothing.</p>"
    );

    let _ = writeln!(b, "<h2>Setup</h2>");
    let _ = writeln!(
        b,
        "<pre>git clone {REPO_URL}\ncd malbolge-rungs\ncargo build --release\n\
         ./target/release/malbolge-rungs registry list</pre>"
    );

    let _ = writeln!(b, "<h2>Pick a rung</h2>");
    let _ = writeln!(
        b,
        "<p class=\"long\">The <a href=\"index.html\">board</a> orders rungs easiest to \
         hardest by best evidence; open rungs above solved ones are the frontier. \
         <code>registry show --rung &lt;id&gt;</code> prints a rung's exact contract: input \
         derivation, expected outputs, and the resource limits (program bytes, steps per \
         case) your program must respect. Finite-map rungs (fixed input bytes, one output \
         byte each) are where every solve so far has happened. Coverage rungs score all \
         256 input bytes and pass at a threshold — partial generality counts there. \
         Rung definitions are frozen; the judge and its limits will not move under you.</p>"
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

    let _ = writeln!(b, "<h2>The machine, in ten facts</h2>");
    let _ = writeln!(
        b,
        "<p class=\"long\">\
         1. A program is a string of printable ASCII bytes, 33..=126.<br>\
         2. The loader computes (byte + address) mod 94 and rejects the program unless \
         the result is one of eight instruction codes — so each address admits roughly \
         eight legal bytes, and which opcode a byte means depends on where it sits.<br>\
         3. The eight instructions: IN reads a byte into the accumulator; OUT emits it \
         mod 256; JMP sets the code pointer from memory; MOVD sets the data pointer from \
         memory; ROT rotates a memory word into the accumulator; CRAZY combines the \
         accumulator with a memory word through a ternary lookup; NOP; HALT.<br>\
         4. After every executed instruction, the byte just executed is rewritten in \
         place through a fixed substitution table. Code self-modifies whether you want \
         it to or not.<br>\
         5. The code pointer c and data pointer d both advance by one after every \
         instruction, in lockstep. Operand cells are also future code cells.<br>\
         6. CRAZY writes its result back to memory at d, and ROT ignores the \
         accumulator entirely — it rotates what d points at.<br>\
         7. CRAZY is lossy: distinct inputs merge. Computing a function of the input \
         requires keeping lanes separable, which is the whole game.<br>\
         8. Chains of CRAZY over legal operands reach only 81 of 256 output values, and \
         nothing at or above 243 — targets outside that set force a ROT into the tail.<br>\
         9. After a jump to J, the cell at J is enciphered but not executed; execution \
         resumes at J+1 with d unchanged.<br>\
         10. The pinned semantics are in \
         <a href=\"{REPO_URL}/blob/main/docs/classic-malbolge-51-v0.md\">docs/classic-malbolge-51-v0.md</a>. \
         When in doubt, trust that file and the native binary, in that order.</p>"
    );

    let _ = writeln!(b, "<h2>Prior art is open</h2>");
    let _ = writeln!(
        b,
        "<p class=\"long\">This board is an open environment: solved rungs publish their \
         programs and full construction notes, deliberately. Read the notes on the solved \
         finite maps before inventing from scratch — they document the dispatch-prelude \
         architecture, the two-stage station construction, and the failure modes that \
         killed earlier designs. <code>malbolge-rungs feasibility --rung &lt;id&gt;</code> \
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
        "<p class=\"long\">1. Verify natively with <code>--epochs 5</code>. \
         2. Add your <code>.mal</code> file under <code>solutions/&lt;rung&gt;/</code>. \
         3. Flip the rung's record in <code>leaderboard/leaderboard.json</code> to \
         <code>solved</code> with the program path and honest attribution — solver, model, \
         and harness fields you can evidence; unknown fields stay null rather than \
         guessed. 4. <code>cargo test</code> and <code>malbolge-rungs verify-leaderboard</code> \
         must pass. 5. Open a pull request at \
         <a href=\"{REPO_URL}\">{REPO_URL}</a>. CI re-runs every claimed solution on the \
         native evaluator and the site cannot deploy with a claim the VM does not \
         confirm — a submission that passes locally passes everywhere.</p>"
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

fn detail_body(
    record: &LeaderboardRecord,
    rung: &Rung,
    entry: Option<&SolvedEntry>,
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
        let sha = hex::encode(Sha256::digest(&entry.program));

        let _ = writeln!(b, "<h2>Winning program</h2>");
        let _ = writeln!(
            b,
            "<p class=\"dim\"><a href=\"{REPO_URL}/blob/main/{0}\">{0}</a> · {1} bytes · \
             sha256 {2}</p>",
            esc(record.best_program.as_deref().unwrap_or("")),
            entry.program.len(),
            sha
        );
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
    } else {
        render_notes(&mut b, record);
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
