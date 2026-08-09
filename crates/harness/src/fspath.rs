//! Symlink-safe resolution of repo-relative paths that originate in submitted
//! data — leaderboard `best_program`, attempt-record program/report/artifact
//! paths.
//!
//! A lexical check (reject absolute paths and `..`) is not sufficient on its
//! own: a symlink committed *inside* the repository passes that check yet
//! resolves to a target outside the tree, so reading or rendering it would
//! disclose an arbitrary file the process can read (an SSH key, a CI secret).
//! Because the site generator renders a solved rung's program bytes into a
//! published page, that is a file-disclosure vector on the deploy path.
//!
//! `resolve_within_repo` requires that a path both passes the lexical check
//! *and* resolves canonically (following every symlink) to a location inside
//! the canonical repository root. Nonexistent paths return an error too, so
//! callers get one function for "safe, present, and inside the repo".

use std::path::{Component, Path, PathBuf};

/// Resolve `rel` under `repo_root`, rejecting absolute paths, `..`, and any
/// path (including via symlinks) that escapes the repository. On success the
/// returned path is canonical and guaranteed inside the repo.
pub fn resolve_within_repo(repo_root: &Path, rel: &str) -> Result<PathBuf, String> {
    let p = Path::new(rel);
    if p.is_absolute() || !p.components().all(|c| matches!(c, Component::Normal(_))) {
        return Err(format!(
            "path {rel} must be repo-relative (no absolute paths, no `..`)"
        ));
    }
    let root = repo_root
        .canonicalize()
        .map_err(|e| format!("cannot resolve repository root: {e}"))?;
    let real = root
        .join(p)
        .canonicalize()
        .map_err(|_| format!("path {rel} does not resolve to an existing file"))?;
    if !real.starts_with(&root) {
        return Err(format!("path {rel} escapes the repository"));
    }
    Ok(real)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_absolute_and_dotdot() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        assert!(resolve_within_repo(&root, "/etc/passwd").is_err());
        assert!(resolve_within_repo(&root, "../../../etc/passwd").is_err());
        assert!(resolve_within_repo(&root, "solutions/../../etc/passwd").is_err());
    }

    #[test]
    fn accepts_a_real_in_repo_file() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        assert!(resolve_within_repo(&root, "solutions/hello-world/halt-no-output.mal").is_ok());
    }

    #[test]
    fn rejects_symlink_escaping_the_repo() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let canon_root = root.canonicalize().unwrap();
        let link = canon_root.join("solutions/hello-world/__fspath_test_link.mal");
        let _ = std::fs::remove_file(&link);
        // A symlink to a file outside the repo, with a clean repo-relative path.
        #[cfg(unix)]
        std::os::unix::fs::symlink("/etc/hosts", &link).unwrap();
        let result = resolve_within_repo(&root, "solutions/hello-world/__fspath_test_link.mal");
        let _ = std::fs::remove_file(&link);
        assert!(result.is_err(), "symlink escaping the repo must be rejected");
    }
}
