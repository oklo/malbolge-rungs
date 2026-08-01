//! Static leaderboard-site generator.
//!
//! `malbolge-rungs site --out <dir>` renders the leaderboard as a small static
//! website: an index table plus one detail page per solved rung showing the
//! winning program, its hash, and a verification transcript.
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

const CSS: &str = r#"
:root {
  --fg: #1c1c1c; --muted: #737373; --faint: #a3a3a3; --line: #e6e6e6;
  --bg: #ffffff; --pre-bg: #f7f7f7; --green: #0a7d33; --amber: #96690a;
  --link: #1d4ed8;
}
@media (prefers-color-scheme: dark) {
  :root {
    --fg: #d6d6d6; --muted: #8a8a8a; --faint: #6b6b6b; --line: #2a2a2a;
    --bg: #121212; --pre-bg: #1b1b1b; --green: #4fbf74; --amber: #d4a017;
    --link: #7ea6f4;
  }
}
* { box-sizing: border-box; }
body {
  font: 12.5px/1.6 ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas,
    "Liberation Mono", monospace;
  color: var(--fg); background: var(--bg);
  max-width: 66rem; margin: 3rem auto 5rem; padding: 0 1.25rem;
}
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }
h1 { font-size: 15px; font-weight: 600; margin: 0 0 .25rem; }
h2 { font-size: 12.5px; font-weight: 600; margin: 2.2rem 0 .6rem;
     text-transform: uppercase; letter-spacing: .07em; color: var(--muted); }
.sub { color: var(--muted); margin: 0 0 2rem; }
table { border-collapse: collapse; width: 100%; }
th {
  text-align: left; font-weight: 600; font-size: 10.5px;
  text-transform: uppercase; letter-spacing: .07em; color: var(--muted);
  padding: .3em .7em .4em 0; border-bottom: 1px solid var(--fg);
  white-space: nowrap;
}
td { padding: .34em .7em .34em 0; border-bottom: 1px solid var(--line);
     vertical-align: baseline; }
td.note { color: var(--muted); }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
th.num { text-align: right; }
.solved { color: var(--green); }
.open { color: var(--faint); }
.unverified { color: var(--amber); }
.dim { color: var(--faint); }
pre {
  background: var(--pre-bg); border: 1px solid var(--line);
  padding: .8rem .9rem; overflow-x: auto; white-space: pre-wrap;
  word-break: break-all; font-size: 12px; line-height: 1.5;
}
dl { margin: 0; }
dt { float: left; clear: left; width: 11rem; color: var(--muted); }
dd { margin: 0 0 .2rem 11.5rem; }
footer { margin-top: 3.5rem; padding-top: .8rem; border-top: 1px solid var(--line);
         color: var(--faint); font-size: 11.5px; }
"#;

fn esc(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}

fn page(title: &str, depth: usize, body: &str) -> String {
    let prefix = "../".repeat(depth);
    format!(
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n\
         <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n\
         <title>{}</title>\n<style>{}</style>\n</head>\n<body>\n\
         <p class=\"dim\"><a href=\"{}index.html\">malbolge-rungs</a> · \
         <a href=\"{}\">github</a></p>\n{}\n</body>\n</html>\n",
        esc(title),
        CSS,
        prefix,
        REPO_URL,
        body
    )
}

struct SolvedEntry {
    record: LeaderboardRecord,
    rung: Rung,
    program: Vec<u8>,
    outcome: VerifyOutcome,
}

/// Generate the static site. Fails if any claimed solution does not re-verify.
pub fn generate_site(out_dir: &Path, epochs: u32) -> Result<()> {
    let records = load_leaderboard();

    // Re-verify every solved record first; refuse to render a site that would
    // publish an unverified claim.
    let mut solved = Vec::new();
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
        solved.push(SolvedEntry {
            record: record.clone(),
            rung,
            program,
            outcome,
        });
    }

    std::fs::create_dir_all(out_dir.join("s"))?;

    let generated = build_stamp();
    std::fs::write(
        out_dir.join("index.html"),
        page("malbolge-rungs", 0, &index_body(&records, &solved, &generated)),
    )?;
    for entry in &solved {
        std::fs::write(
            out_dir.join("s").join(format!("{}.html", entry.record.rung_id)),
            page(&entry.record.rung_id, 1, &detail_body(entry, &generated)),
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
    solved: &[SolvedEntry],
    generated: &str,
) -> String {
    let mut b = String::new();
    let _ = writeln!(b, "<h1>malbolge-rungs</h1>");
    let _ = writeln!(
        b,
        "<p class=\"sub\">A ladder of classic-Malbolge programming challenges, \
         adjudicated by a single deterministic ground-truth VM \
         (<a href=\"{REPO_URL}/blob/main/docs/classic-malbolge-51-v0.md\">Classic-Malbolge-51 v0</a>). \
         Every <span class=\"solved\">solved</span> entry links to the winning program and was \
         re-verified on the native evaluator when this page was generated. \
         {} of {} rungs solved.</p>",
        solved.len(),
        records.len()
    );

    let _ = writeln!(
        b,
        "<table>\n<tr><th>rung</th><th>status</th><th>solver</th>\
         <th>date</th><th class=\"num\">bytes</th><th>notes</th></tr>"
    );
    for record in records {
        let (rung_cell, bytes_cell, solver_cell, date_cell) = if record.status == Status::Solved {
            let entry = solved
                .iter()
                .find(|e| e.record.rung_id == record.rung_id)
                .expect("solved entry present");
            (
                format!(
                    "<a href=\"s/{0}.html\">{0}</a>",
                    esc(&record.rung_id)
                ),
                format!("{}", entry.program.len()),
                esc(record.solver.as_deref().unwrap_or("—")),
                esc(record.date.as_deref().unwrap_or("—")),
            )
        } else {
            (
                esc(&record.rung_id),
                "—".to_string(),
                "—".to_string(),
                "—".to_string(),
            )
        };
        let _ = writeln!(
            b,
            "<tr><td>{}</td><td>{}</td><td>{}</td><td class=\"dim\">{}</td>\
             <td class=\"num\">{}</td><td class=\"note\">{}</td></tr>",
            rung_cell,
            status_cell(record),
            solver_cell,
            date_cell,
            bytes_cell,
            esc(record.note.as_deref().unwrap_or("")),
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

fn detail_body(entry: &SolvedEntry, generated: &str) -> String {
    let record = &entry.record;
    let rung = &entry.rung;
    let source = String::from_utf8_lossy(&entry.program);
    let sha = hex::encode(Sha256::digest(&entry.program));

    let mut b = String::new();
    let _ = writeln!(b, "<h1>{}</h1>", esc(&record.rung_id));
    let _ = writeln!(b, "<p class=\"sub\">{}</p>", esc(&rung.title));

    let _ = writeln!(b, "<h2>Record</h2>\n<dl>");
    let _ = writeln!(
        b,
        "<dt>solver</dt><dd>{}</dd>",
        esc(record.solver.as_deref().unwrap_or("—"))
    );
    let _ = writeln!(
        b,
        "<dt>date</dt><dd>{}</dd>",
        esc(record.date.as_deref().unwrap_or("—"))
    );
    let _ = writeln!(
        b,
        "<dt>challenge</dt><dd>{:?} / {:?}, {} case(s), max program {} bytes</dd>",
        rung.family, rung.transform, rung.cases, rung.max_program_len
    );
    if let Some(note) = &record.note {
        let _ = writeln!(b, "<dt>note</dt><dd>{}</dd>", esc(note));
    }
    let _ = writeln!(
        b,
        "<dt>program</dt><dd><a href=\"{REPO_URL}/blob/main/{0}\">{0}</a> \
         ({1} bytes)</dd>",
        esc(record.best_program.as_deref().unwrap_or("")),
        entry.program.len()
    );
    let _ = writeln!(b, "<dt>sha256</dt><dd>{sha}</dd>");
    let _ = writeln!(b, "</dl>");

    let _ = writeln!(b, "<h2>Program</h2>\n<pre>{}</pre>", esc(&source));

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
