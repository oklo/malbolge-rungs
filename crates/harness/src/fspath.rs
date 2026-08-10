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

/// Open a repo-relative path for reading with full containment safety:
/// [`resolve_within_repo`] first (lexical + canonical containment), then open
/// refusing to follow a final-component symlink, requiring a regular file that
/// is not a hard link. This closes the two reads canonicalization alone does
/// not: a hard link inside the repo whose inode lives outside it (canonicalize
/// returns the in-repo name, so the lexical + `starts_with` check passes), and
/// a path swapped for a symlink between the check and the open.
pub fn open_within_repo(repo_root: &Path, rel: &str) -> Result<std::fs::File, String> {
    open_hardened(&resolve_within_repo(repo_root, rel)?)
}

/// Open an already-resolved path with the containment safety checks: no symlink
/// follow (`O_NOFOLLOW`), a regular file, and — on Unix — a single link, so it
/// cannot be a hard link aliasing content elsewhere on the filesystem.
pub fn open_hardened(path: &Path) -> Result<std::fs::File, String> {
    let mut opts = std::fs::OpenOptions::new();
    opts.read(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        opts.custom_flags(libc::O_NOFOLLOW);
    }
    let file = opts
        .open(path)
        .map_err(|e| format!("opening {}: {e}", path.display()))?;
    let meta = file
        .metadata()
        .map_err(|e| format!("stat {}: {e}", path.display()))?;
    if !meta.is_file() {
        return Err(format!("{} is not a regular file", path.display()));
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        if meta.nlink() > 1 {
            return Err(format!(
                "{} is a hard link (nlink {}); refusing to read a possibly out-of-repo inode",
                path.display(),
                meta.nlink()
            ));
        }
    }
    Ok(file)
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

    #[cfg(unix)]
    #[test]
    fn open_hardened_rejects_hard_link() {
        use std::fs;
        let dir = std::env::temp_dir();
        let pid = std::process::id();
        let a = dir.join(format!("mal-fspath-hlink-a-{pid}"));
        let b = dir.join(format!("mal-fspath-hlink-b-{pid}"));
        let _ = fs::remove_file(&a);
        let _ = fs::remove_file(&b);
        fs::write(&a, "secret").unwrap();
        // A hard link aliases the same inode; canonicalization can't see it, so
        // open_hardened must reject it on nlink.
        if fs::hard_link(&a, &b).is_ok() {
            assert!(open_hardened(&b).is_err(), "a hard link (nlink 2) must be rejected");
        }
        let _ = fs::remove_file(&a);
        let _ = fs::remove_file(&b);
    }

    #[cfg(unix)]
    #[test]
    fn open_hardened_rejects_symlink_and_accepts_regular() {
        use std::fs;
        let dir = std::env::temp_dir();
        let pid = std::process::id();
        let target = dir.join(format!("mal-fspath-sl-target-{pid}"));
        let link = dir.join(format!("mal-fspath-sl-link-{pid}"));
        let _ = fs::remove_file(&target);
        let _ = fs::remove_file(&link);
        fs::write(&target, "x").unwrap();
        assert!(open_hardened(&target).is_ok(), "a plain regular file opens");
        if std::os::unix::fs::symlink(&target, &link).is_ok() {
            assert!(open_hardened(&link).is_err(), "O_NOFOLLOW must reject a symlink");
        }
        let _ = fs::remove_file(&link);
        let _ = fs::remove_file(&target);
    }
}
