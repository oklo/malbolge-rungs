//! MAL-51 rung harness: the rung registry, deterministic challenge-case
//! derivation, and native-VM verification, extracted from the source MAL-51
//! project without any of its chain/coin machinery.

pub mod attempts;
pub mod challenge;
pub mod dispatch;
pub mod generate;
pub mod hashing;
pub mod leaderboard;
pub mod registry;
pub mod site;
pub mod types;
pub mod verify;

pub use registry::{find_rung, load_registry};
pub use types::{ChallengeCase, Family, Rung, Transform};
pub use verify::{verify_rung, VerifyOutcome};
