use serde::{Deserialize, Serialize};

pub const CLASSIC_MALBOLGE_51_V0_ID: &str = "classic-malbolge-51-v0";
pub const CLASSIC_MEMORY_CELLS: u64 = 59_049;
pub const CLASSIC_WORD_TRITS: u8 = 10;
pub const CLASSIC_WORD_MAX: u16 = 59_048;
pub const CLASSIC_WORD_MODULUS: usize = 59_049;
pub const CLASSIC_ROTATE_TRIT_FACTOR: u16 = 19_683;
pub const CLASSIC_ENCIPHER_TABLE: &[u8; 94] = b"5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";
pub const FIXTURE_ECHO_PROGRAM: &[u8] = b"fixture:echo";
pub const FIXTURE_REVERSE_PROGRAM: &[u8] = b"fixture:reverse";
pub const FIXTURE_CONSTANT_PROGRAM: &[u8] = b"fixture:constant";
pub const FIXTURE_XOR_MASK_PROGRAM: &[u8] = b"fixture:xor-mask";

const VALID_SOURCE_INSTRUCTION_CODES: [usize; 8] = [4, 5, 23, 39, 40, 62, 68, 81];

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ClassicMalbolge51Profile {
    pub profile_id: String,
    pub source_encoding: SourceEncoding,
    pub memory_size_cells: u64,
    pub word_trits: u8,
    pub memory_initialization: MemoryInitialization,
    pub input_encoding: ByteEncoding,
    pub output_encoding: ByteEncoding,
    pub newline_behavior: NewlineBehavior,
    pub halt_behavior: HaltBehavior,
    pub max_steps: u64,
    pub max_output_len: u64,
    pub max_program_len: u64,
    pub malformed_program_behavior: MalformedProgramBehavior,
    pub preserve_ignored_characters_in_raw_metadata: bool,
    pub challenge_input_mode: ChallengeInputMode,
    pub multi_case_reset: MultiCaseReset,
}

impl Default for ClassicMalbolge51Profile {
    fn default() -> Self {
        Self {
            profile_id: CLASSIC_MALBOLGE_51_V0_ID.to_string(),
            source_encoding: SourceEncoding::Ascii,
            memory_size_cells: CLASSIC_MEMORY_CELLS,
            word_trits: CLASSIC_WORD_TRITS,
            memory_initialization: MemoryInitialization::ClassicProgramThenProfileFill,
            input_encoding: ByteEncoding::RawBytes,
            output_encoding: ByteEncoding::RawBytes,
            newline_behavior: NewlineBehavior::NoTranslation,
            halt_behavior: HaltBehavior::DistinctTerminalStatuses,
            max_steps: 100_000,
            max_output_len: 64,
            max_program_len: 4_096,
            malformed_program_behavior: MalformedProgramBehavior::RejectProof,
            preserve_ignored_characters_in_raw_metadata: true,
            challenge_input_mode: ChallengeInputMode::OneByteStringPerCase,
            multi_case_reset: MultiCaseReset::FreshVmPerCase,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum SourceEncoding {
    Ascii,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum MemoryInitialization {
    ClassicProgramThenProfileFill,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum ByteEncoding {
    RawBytes,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum NewlineBehavior {
    NoTranslation,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum HaltBehavior {
    DistinctTerminalStatuses,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum MalformedProgramBehavior {
    RejectProof,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum ChallengeInputMode {
    OneByteStringPerCase,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum MultiCaseReset {
    FreshVmPerCase,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum ClassicBackendKind {
    Fixture,
    Native,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ClassicExecutionLimits {
    pub max_steps: u64,
    pub max_output_len: u64,
    pub max_program_len: u64,
    pub max_memory_cells: u64,
}

impl From<&ClassicMalbolge51Profile> for ClassicExecutionLimits {
    fn from(profile: &ClassicMalbolge51Profile) -> Self {
        Self {
            max_steps: profile.max_steps,
            max_output_len: profile.max_output_len,
            max_program_len: profile.max_program_len,
            max_memory_cells: profile.memory_size_cells,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct ClassicExecutionReport {
    pub output: Vec<u8>,
    pub steps: u64,
    pub memory_used_cells: u64,
    pub status: ClassicExecutionStatus,
    pub backend_kind: ClassicBackendKind,
    pub public_challenge_eligible: bool,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum ClassicExecutionStatus {
    Success,
    Halted,
    InvalidSource,
    InvalidRuntimeInstruction,
    StepLimitExceeded,
    OutputLimitExceeded,
    MemoryLimitExceeded,
    BackendError(String),
}

pub trait ClassicMalbolgeExecutor {
    fn backend_kind(&self) -> ClassicBackendKind;
    fn public_challenge_eligible(&self) -> bool;
    fn execute(
        &self,
        program: &[u8],
        input: &[u8],
        limits: &ClassicExecutionLimits,
    ) -> Result<ClassicExecutionReport, ClassicMalbolgeError>;
}

#[derive(Clone, Debug)]
pub struct FixtureClassicBackend {
    allow_public_challenge: bool,
}

impl FixtureClassicBackend {
    pub fn simulator_only() -> Self {
        Self {
            allow_public_challenge: false,
        }
    }

    pub fn explicitly_allow_public_challenge_for_tests() -> Self {
        Self {
            allow_public_challenge: true,
        }
    }

    pub fn assert_public_challenge_allowed(&self) -> Result<(), ClassicMalbolgeError> {
        if self.allow_public_challenge {
            Ok(())
        } else {
            Err(ClassicMalbolgeError::FixtureNotPublicChallengeEligible)
        }
    }
}

impl ClassicMalbolgeExecutor for FixtureClassicBackend {
    fn backend_kind(&self) -> ClassicBackendKind {
        ClassicBackendKind::Fixture
    }

    fn public_challenge_eligible(&self) -> bool {
        self.allow_public_challenge
    }

    fn execute(
        &self,
        program: &[u8],
        input: &[u8],
        limits: &ClassicExecutionLimits,
    ) -> Result<ClassicExecutionReport, ClassicMalbolgeError> {
        validate_limits(program, limits)?;
        let canonical = canonicalize_fixture_source(program)?;
        let output = fixture_output(&canonical, input, limits.max_output_len as usize)?;
        if output.len() as u64 > limits.max_output_len {
            return Err(ClassicMalbolgeError::OutputLimitExceeded {
                actual: output.len() as u64,
                limit: limits.max_output_len,
            });
        }

        Ok(ClassicExecutionReport {
            output,
            steps: 1,
            memory_used_cells: canonical.len().max(1) as u64,
            status: ClassicExecutionStatus::Success,
            backend_kind: ClassicBackendKind::Fixture,
            public_challenge_eligible: self.allow_public_challenge,
        })
    }
}

#[derive(Clone, Debug, Default)]
pub struct NativeClassicBackend;

impl ClassicMalbolgeExecutor for NativeClassicBackend {
    fn backend_kind(&self) -> ClassicBackendKind {
        ClassicBackendKind::Native
    }

    fn public_challenge_eligible(&self) -> bool {
        true
    }

    fn execute(
        &self,
        program: &[u8],
        input: &[u8],
        limits: &ClassicExecutionLimits,
    ) -> Result<ClassicExecutionReport, ClassicMalbolgeError> {
        execute_native_classic(program, input, limits)
    }
}

#[derive(Debug, thiserror::Error)]
pub enum ClassicMalbolgeError {
    #[error("program length {actual} exceeds limit {limit}")]
    ProgramTooLarge { actual: u64, limit: u64 },
    #[error("output length {actual} exceeds limit {limit}")]
    OutputLimitExceeded { actual: u64, limit: u64 },
    #[error("memory requirement {actual} exceeds limit {limit}")]
    MemoryLimitExceeded { actual: u64, limit: u64 },
    #[error("invalid classic Malbolge source: {reason}")]
    InvalidSource { reason: String },
    #[error("invalid runtime instruction at address {address}: word value {value}")]
    InvalidRuntimeInstruction { address: u64, value: u16 },
    #[error("classic Malbolge execution exceeded step limit {limit}")]
    StepLimitExceeded { limit: u64 },
    #[error("fixture backend only supports fixture:echo, fixture:reverse, fixture:constant, fixture:xor-mask")]
    UnsupportedFixtureProgram,
    #[error("fixture backend is simulator-only unless explicitly enabled")]
    FixtureNotPublicChallengeEligible,
}

pub fn canonicalize_fixture_source(program: &[u8]) -> Result<Vec<u8>, ClassicMalbolgeError> {
    let mut normalized = Vec::with_capacity(program.len());
    let mut index = 0;
    while index < program.len() {
        match program[index] {
            b'\r' if program.get(index + 1) == Some(&b'\n') => {
                normalized.push(b'\n');
                index += 2;
            }
            b'\r' => {
                normalized.push(b'\n');
                index += 1;
            }
            byte => {
                normalized.push(byte);
                index += 1;
            }
        }
    }
    let start = normalized
        .iter()
        .position(|byte| !byte.is_ascii_whitespace())
        .unwrap_or(normalized.len());
    let end = normalized
        .iter()
        .rposition(|byte| !byte.is_ascii_whitespace())
        .map(|pos| pos + 1)
        .unwrap_or(start);
    Ok(normalized[start..end].to_vec())
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct ExecutableSource {
    bytes: Vec<u8>,
}

pub fn instruction_code(word: u16, address: usize) -> usize {
    (usize::from(word) + address) % 94
}

pub fn trits10(mut word: u16) -> [u8; CLASSIC_WORD_TRITS as usize] {
    let mut trits = [0_u8; CLASSIC_WORD_TRITS as usize];
    for trit in &mut trits {
        *trit = (word % 3) as u8;
        word /= 3;
    }
    trits
}

pub fn word_from_trits10(trits: [u8; CLASSIC_WORD_TRITS as usize]) -> u16 {
    let mut value = 0_u16;
    let mut factor = 1_u16;
    for trit in trits {
        value = value.saturating_add(u16::from(trit) * factor);
        factor = factor.saturating_mul(3);
    }
    value
}

pub fn rotate_right_word(word: u16) -> u16 {
    word / 3 + (word % 3) * CLASSIC_ROTATE_TRIT_FACTOR
}

pub fn crazy_trit(a: u8, d: u8) -> u8 {
    match (d, a) {
        (0, 0) => 1,
        (0, 1) => 0,
        (0, 2) => 0,
        (1, 0) => 1,
        (1, 1) => 0,
        (1, 2) => 2,
        (2, 0) => 2,
        (2, 1) => 2,
        (2, 2) => 1,
        _ => unreachable!("trits are always in 0..=2"),
    }
}

pub fn crazy_word(a: u16, d: u16) -> u16 {
    let a_trits = trits10(a);
    let d_trits = trits10(d);
    let mut result = [0_u8; CLASSIC_WORD_TRITS as usize];
    for index in 0..result.len() {
        result[index] = crazy_trit(a_trits[index], d_trits[index]);
    }
    word_from_trits10(result)
}

fn execute_native_classic(
    program: &[u8],
    input: &[u8],
    limits: &ClassicExecutionLimits,
) -> Result<ClassicExecutionReport, ClassicMalbolgeError> {
    validate_native_limits(program, limits)?;
    let executable = load_executable_source(program, limits)?;
    let mut vm = NativeVm::from_executable(&executable.bytes, input);

    for step_index in 0..limits.max_steps {
        match vm.step(limits.max_output_len)? {
            StepOutcome::Continue => {}
            StepOutcome::Halt => {
                return Ok(ClassicExecutionReport {
                    output: vm.output,
                    steps: step_index + 1,
                    memory_used_cells: CLASSIC_MEMORY_CELLS,
                    status: ClassicExecutionStatus::Halted,
                    backend_kind: ClassicBackendKind::Native,
                    public_challenge_eligible: true,
                });
            }
        }
    }

    Err(ClassicMalbolgeError::StepLimitExceeded {
        limit: limits.max_steps,
    })
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct NativeVm<'a> {
    memory: Vec<u16>,
    a: u16,
    c: usize,
    d: usize,
    input: &'a [u8],
    input_index: usize,
    output: Vec<u8>,
}

impl<'a> NativeVm<'a> {
    fn from_executable(executable: &[u8], input: &'a [u8]) -> Self {
        Self {
            memory: initialize_memory(executable),
            a: 0,
            c: 0,
            d: 0,
            input,
            input_index: 0,
            output: Vec::new(),
        }
    }

    #[cfg(test)]
    fn from_memory(memory: Vec<u16>, input: &'a [u8]) -> Self {
        Self {
            memory,
            a: 0,
            c: 0,
            d: 0,
            input,
            input_index: 0,
            output: Vec::new(),
        }
    }

    fn step(&mut self, max_output_len: u64) -> Result<StepOutcome, ClassicMalbolgeError> {
        let fetched = self.memory[self.c];
        if !is_printable_word(fetched) {
            return Err(ClassicMalbolgeError::InvalidRuntimeInstruction {
                address: self.c as u64,
                value: fetched,
            });
        }

        let code = instruction_code(fetched, self.c);
        match code {
            4 => self.c = usize::from(self.memory[self.d]),
            5 => {
                if self.output.len() as u64 >= max_output_len {
                    return Err(ClassicMalbolgeError::OutputLimitExceeded {
                        actual: self.output.len() as u64 + 1,
                        limit: max_output_len,
                    });
                }
                self.output.push((self.a % 256) as u8);
            }
            23 => {
                self.a = self
                    .input
                    .get(self.input_index)
                    .map(|byte| {
                        self.input_index += 1;
                        u16::from(*byte)
                    })
                    .unwrap_or(CLASSIC_WORD_MAX);
            }
            39 => {
                let rotated = rotate_right_word(self.memory[self.d]);
                self.memory[self.d] = rotated;
                self.a = rotated;
            }
            40 => self.d = usize::from(self.memory[self.d]),
            62 => {
                let value = crazy_word(self.a, self.memory[self.d]);
                self.memory[self.d] = value;
                self.a = value;
            }
            68 => {}
            81 => return Ok(StepOutcome::Halt),
            _ => {}
        }

        encipher_cell(&mut self.memory, self.c)?;
        self.c = (self.c + 1) % CLASSIC_WORD_MODULUS;
        self.d = (self.d + 1) % CLASSIC_WORD_MODULUS;
        Ok(StepOutcome::Continue)
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum StepOutcome {
    Continue,
    Halt,
}

fn validate_native_limits(
    program: &[u8],
    limits: &ClassicExecutionLimits,
) -> Result<(), ClassicMalbolgeError> {
    validate_limits(program, limits)?;
    if limits.max_memory_cells < CLASSIC_MEMORY_CELLS {
        return Err(ClassicMalbolgeError::MemoryLimitExceeded {
            actual: CLASSIC_MEMORY_CELLS,
            limit: limits.max_memory_cells,
        });
    }
    Ok(())
}

fn load_executable_source(
    program: &[u8],
    limits: &ClassicExecutionLimits,
) -> Result<ExecutableSource, ClassicMalbolgeError> {
    let mut executable = Vec::new();
    for byte in program {
        if byte.is_ascii_whitespace() {
            continue;
        }
        if !byte.is_ascii() {
            return Err(ClassicMalbolgeError::InvalidSource {
                reason: format!("non-ASCII byte 0x{byte:02x}"),
            });
        }
        if !(33..=126).contains(byte) {
            return Err(ClassicMalbolgeError::InvalidSource {
                reason: format!("non-printable executable byte 0x{byte:02x}"),
            });
        }
        let address = executable.len();
        let code = instruction_code(u16::from(*byte), address);
        if !VALID_SOURCE_INSTRUCTION_CODES.contains(&code) {
            return Err(ClassicMalbolgeError::InvalidSource {
                reason: format!(
                    "byte 0x{byte:02x} at executable address {address} decodes to invalid source instruction {code}"
                ),
            });
        }
        executable.push(*byte);
        if executable.len() as u64 > limits.max_program_len {
            return Err(ClassicMalbolgeError::ProgramTooLarge {
                actual: executable.len() as u64,
                limit: limits.max_program_len,
            });
        }
    }

    if executable.len() < 2 {
        return Err(ClassicMalbolgeError::InvalidSource {
            reason: "public MAL-51 proofs require at least two executable instructions".to_string(),
        });
    }
    if executable.len() > CLASSIC_WORD_MODULUS {
        return Err(ClassicMalbolgeError::ProgramTooLarge {
            actual: executable.len() as u64,
            limit: CLASSIC_MEMORY_CELLS,
        });
    }

    Ok(ExecutableSource { bytes: executable })
}

fn initialize_memory(executable: &[u8]) -> Vec<u16> {
    let mut memory = vec![0_u16; CLASSIC_WORD_MODULUS];
    for (index, byte) in executable.iter().enumerate() {
        memory[index] = u16::from(*byte);
    }
    for index in executable.len()..CLASSIC_WORD_MODULUS {
        memory[index] = crazy_word(memory[index - 1], memory[index - 2]);
    }
    memory
}

fn encipher_cell(memory: &mut [u16], address: usize) -> Result<(), ClassicMalbolgeError> {
    let word = memory[address];
    memory[address] =
        encipher_word(word).map_err(|value| ClassicMalbolgeError::InvalidRuntimeInstruction {
            address: address as u64,
            value,
        })?;
    Ok(())
}

pub fn encipher_word(word: u16) -> Result<u16, u16> {
    if is_printable_word(word) {
        Ok(u16::from(CLASSIC_ENCIPHER_TABLE[usize::from(word - 33)]))
    } else {
        Err(word)
    }
}

fn is_printable_word(word: u16) -> bool {
    (33..=126).contains(&word)
}

fn validate_limits(
    program: &[u8],
    limits: &ClassicExecutionLimits,
) -> Result<(), ClassicMalbolgeError> {
    let actual = program.len() as u64;
    if actual > limits.max_program_len {
        return Err(ClassicMalbolgeError::ProgramTooLarge {
            actual,
            limit: limits.max_program_len,
        });
    }
    Ok(())
}

fn fixture_output(
    program: &[u8],
    input: &[u8],
    max_output_len: usize,
) -> Result<Vec<u8>, ClassicMalbolgeError> {
    let mut output: Vec<u8> = match program {
        FIXTURE_ECHO_PROGRAM => Ok(input.to_vec()),
        FIXTURE_REVERSE_PROGRAM => Ok(input.iter().rev().copied().collect()),
        FIXTURE_CONSTANT_PROGRAM => Ok(b"constant".to_vec()),
        FIXTURE_XOR_MASK_PROGRAM => Ok(input.iter().map(|byte| byte ^ 0x51).collect()),
        _ => Err(ClassicMalbolgeError::UnsupportedFixtureProgram),
    }?;
    output.truncate(max_output_len);
    Ok(output)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_profile_pins_classic_shape() {
        let profile = ClassicMalbolge51Profile::default();

        assert_eq!(profile.profile_id, CLASSIC_MALBOLGE_51_V0_ID);
        assert_eq!(profile.memory_size_cells, CLASSIC_MEMORY_CELLS);
        assert_eq!(profile.word_trits, CLASSIC_WORD_TRITS);
        assert_eq!(profile.multi_case_reset, MultiCaseReset::FreshVmPerCase);
    }

    #[test]
    fn fixture_echo_executes() {
        let backend = FixtureClassicBackend::simulator_only();
        let limits = ClassicExecutionLimits::from(&ClassicMalbolge51Profile::default());

        let report = backend
            .execute(FIXTURE_ECHO_PROGRAM, b"abc", &limits)
            .unwrap();

        assert_eq!(report.output, b"abc");
        assert_eq!(report.backend_kind, ClassicBackendKind::Fixture);
        assert!(!report.public_challenge_eligible);
    }

    #[test]
    fn fixture_source_normalizes_outer_noise() {
        let backend = FixtureClassicBackend::simulator_only();
        let limits = ClassicExecutionLimits::from(&ClassicMalbolge51Profile::default());

        let report = backend
            .execute(b" \r\nfixture:reverse\n", b"abc", &limits)
            .unwrap();

        assert_eq!(report.output, b"cba");
    }

    #[test]
    fn fixture_backend_is_not_public_by_default() {
        let backend = FixtureClassicBackend::simulator_only();

        assert!(matches!(
            backend.assert_public_challenge_allowed(),
            Err(ClassicMalbolgeError::FixtureNotPublicChallengeEligible)
        ));
    }

    #[test]
    fn source_whitespace_is_ignored() {
        let backend = NativeClassicBackend;
        let limits = ClassicExecutionLimits::from(&ClassicMalbolge51Profile::default());
        let report = backend.execute(b"u\n b\tO", b"a", &limits).unwrap();

        assert_eq!(report.output, b"a");
        assert_eq!(report.status, ClassicExecutionStatus::Halted);
    }

    #[test]
    fn invalid_source_byte_is_rejected() {
        let backend = NativeClassicBackend;
        let limits = ClassicExecutionLimits::from(&ClassicMalbolge51Profile::default());

        assert!(matches!(
            backend.execute(b"Q\x7f", b"", &limits),
            Err(ClassicMalbolgeError::InvalidSource { .. })
        ));
    }

    #[test]
    fn executable_length_below_two_is_rejected() {
        let backend = NativeClassicBackend;
        let limits = ClassicExecutionLimits::from(&ClassicMalbolge51Profile::default());

        assert!(matches!(
            backend.execute(b"Q", b"", &limits),
            Err(ClassicMalbolgeError::InvalidSource { .. })
        ));
    }

    #[test]
    fn encipher_table_length_is_pinned() {
        assert_eq!(CLASSIC_ENCIPHER_TABLE.len(), 94);
    }

    #[test]
    fn encipher_table_entries_are_pinned() {
        assert_eq!(encipher_word(u16::from(b'!')).unwrap(), u16::from(b'5'));
        assert_eq!(encipher_word(u16::from(b'"')).unwrap(), u16::from(b'z'));
        assert_eq!(encipher_word(u16::from(b'~')).unwrap(), u16::from(b'@'));

        let later_word = 33_u16 + 41;
        assert_eq!(
            encipher_word(later_word).unwrap(),
            u16::from(CLASSIC_ENCIPHER_TABLE[41])
        );
        assert_ne!(encipher_word(u16::from(b'!')).unwrap(), u16::from(b'!'));
    }

    #[test]
    fn trit_conversion_round_trips_words() {
        assert_eq!(word_from_trits10(trits10(0)), 0);
        assert_eq!(word_from_trits10(trits10(1)), 1);
        assert_eq!(word_from_trits10(trits10(2)), 2);
        assert_eq!(word_from_trits10(trits10(3)), 3);
        assert_eq!(word_from_trits10(trits10(242)), 242);
        assert_eq!(
            word_from_trits10(trits10(CLASSIC_WORD_MAX)),
            CLASSIC_WORD_MAX
        );
        assert_eq!(trits10(0), [0; CLASSIC_WORD_TRITS as usize]);
        assert_eq!(trits10(1), [1, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
        assert_eq!(trits10(2), [2, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
        assert_eq!(trits10(3), [0, 1, 0, 0, 0, 0, 0, 0, 0, 0]);
        assert_eq!(trits10(242), [2, 2, 2, 2, 2, 0, 0, 0, 0, 0]);
        assert_eq!(trits10(CLASSIC_WORD_MAX), [2; CLASSIC_WORD_TRITS as usize]);
    }

    #[test]
    fn rotate_right_helper_works() {
        assert_eq!(rotate_right_word(0), 0);
        assert_eq!(rotate_right_word(1), CLASSIC_ROTATE_TRIT_FACTOR);
        assert_eq!(rotate_right_word(3), 1);
        assert_eq!(rotate_right_word(CLASSIC_WORD_MAX), CLASSIC_WORD_MAX);
    }

    #[test]
    fn rotate_right_preserves_word_range() {
        for word in 0..=CLASSIC_WORD_MAX {
            assert!(rotate_right_word(word) <= CLASSIC_WORD_MAX);
        }
    }

    #[test]
    fn crazy_operation_table_works() {
        let expected = [
            ((0, 0), 1),
            ((1, 0), 0),
            ((2, 0), 0),
            ((0, 1), 1),
            ((1, 1), 0),
            ((2, 1), 2),
            ((0, 2), 2),
            ((1, 2), 2),
            ((2, 2), 1),
        ];

        for ((a, d), result) in expected {
            assert_eq!(crazy_trit(a, d), result);
        }
    }

    #[test]
    fn crazy_word_uses_ten_trit_padding() {
        let all_ones = word_from_trits10([1; CLASSIC_WORD_TRITS as usize]);

        assert_eq!(crazy_word(0, 0), all_ones);
    }

    #[test]
    fn crazy_word_examples_match_public_operator_test_cases() {
        assert_eq!(crazy_word(0, 0), 29_524);
        assert_eq!(crazy_word(1, 2), 29_525);
        assert_eq!(crazy_word(59_048, 5), 7);
        assert_eq!(crazy_word(36_905, 2_214), 0);
        assert_eq!(crazy_word(11_355, 1_131), 20_650);
        assert_eq!(crazy_word(12_345, 54_321), 54_616);
    }

    #[test]
    fn crazy_word_argument_order_is_locked() {
        let forward = crazy_word(0, 1);
        let reverse = crazy_word(1, 0);

        assert_eq!(forward, word_from_trits10([1; CLASSIC_WORD_TRITS as usize]));
        assert_eq!(reverse, word_from_trits10([0, 1, 1, 1, 1, 1, 1, 1, 1, 1]));
        assert_ne!(forward, reverse);
    }

    #[test]
    fn crazy_word_is_visibly_non_commutative() {
        assert_ne!(crazy_word(0, 1), crazy_word(1, 0));
    }

    #[test]
    fn memory_fill_order_uses_previous_then_second_previous() {
        let memory = initialize_memory(b"QC");

        assert_eq!(memory[0], u16::from(b'Q'));
        assert_eq!(memory[1], u16::from(b'C'));
        assert_eq!(memory[2], crazy_word(u16::from(b'C'), u16::from(b'Q')));
        assert_eq!(memory[3], crazy_word(memory[2], u16::from(b'C')));
        assert_eq!(memory[4], crazy_word(memory[3], memory[2]));
        assert_ne!(memory[2], crazy_word(u16::from(b'Q'), u16::from(b'C')));
    }

    #[test]
    fn printable_source_byte_with_invalid_decoded_instruction_is_rejected() {
        let backend = NativeClassicBackend;
        let limits = ClassicExecutionLimits::from(&ClassicMalbolge51Profile::default());

        assert!(matches!(
            backend.execute(b"!!", b"", &limits),
            Err(ClassicMalbolgeError::InvalidSource { .. })
        ));
    }

    #[test]
    fn executable_length_above_configured_limit_is_rejected() {
        let backend = NativeClassicBackend;
        let mut limits = ClassicExecutionLimits::from(&ClassicMalbolge51Profile::default());
        limits.max_program_len = 2;

        assert!(matches!(
            backend.execute(b"ubO", b"a", &limits),
            Err(ClassicMalbolgeError::ProgramTooLarge {
                actual: 3,
                limit: 2
            })
        ));
    }

    #[test]
    fn executable_length_above_memory_size_is_rejected() {
        let backend = NativeClassicBackend;
        let mut limits = ClassicExecutionLimits::from(&ClassicMalbolge51Profile::default());
        limits.max_program_len = CLASSIC_MEMORY_CELLS + 1;
        let program = valid_source_repeated_nop(CLASSIC_WORD_MODULUS + 1);

        assert!(matches!(
            backend.execute(&program, b"", &limits),
            Err(ClassicMalbolgeError::ProgramTooLarge {
                actual,
                limit: CLASSIC_MEMORY_CELLS
            }) if actual == CLASSIC_MEMORY_CELLS + 1
        ));
    }

    #[test]
    fn nop_instruction_only_enciphers_and_increments_pointers() {
        let mut memory = blank_memory();
        memory[0] = word_for_instruction_code(68, 0);
        let original = memory[0];
        let mut vm = NativeVm::from_memory(memory, b"");

        assert_eq!(vm.step(1).unwrap(), StepOutcome::Continue);

        assert_eq!(vm.memory[0], encipher_word(original).unwrap());
        assert_eq!(vm.a, 0);
        assert_eq!(vm.c, 1);
        assert_eq!(vm.d, 1);
    }

    #[test]
    fn input_instruction_sets_a_and_increments_pointers() {
        let mut memory = blank_memory();
        memory[0] = word_for_instruction_code(23, 0);
        let mut vm = NativeVm::from_memory(memory, b"a");

        assert_eq!(vm.step(1).unwrap(), StepOutcome::Continue);

        assert_eq!(vm.a, u16::from(b'a'));
        assert_eq!(vm.c, 1);
        assert_eq!(vm.d, 1);
    }

    #[test]
    fn exhausted_input_instruction_sets_eof_word() {
        let mut memory = blank_memory();
        memory[0] = word_for_instruction_code(23, 0);
        let mut vm = NativeVm::from_memory(memory, b"");

        assert_eq!(vm.step(1).unwrap(), StepOutcome::Continue);

        assert_eq!(vm.a, CLASSIC_WORD_MAX);
        assert_eq!(vm.c, 1);
        assert_eq!(vm.d, 1);
    }

    #[test]
    fn output_instruction_emits_a_mod_256() {
        let mut memory = blank_memory();
        memory[0] = word_for_instruction_code(5, 0);
        let mut vm = NativeVm::from_memory(memory, b"");
        vm.a = 300;

        assert_eq!(vm.step(1).unwrap(), StepOutcome::Continue);

        assert_eq!(vm.output, vec![44]);
        assert_eq!(vm.c, 1);
        assert_eq!(vm.d, 1);
    }

    #[test]
    fn rotate_instruction_updates_a_and_memory_d() {
        let mut memory = blank_memory();
        memory[0] = word_for_instruction_code(39, 0);
        memory[1] = 3;
        let mut vm = NativeVm::from_memory(memory, b"");
        vm.d = 1;

        assert_eq!(vm.step(1).unwrap(), StepOutcome::Continue);

        assert_eq!(vm.a, 1);
        assert_eq!(vm.memory[1], 1);
        assert_eq!(vm.c, 1);
        assert_eq!(vm.d, 2);
    }

    #[test]
    fn movd_instruction_sets_d_then_post_increment_applies() {
        let mut memory = blank_memory();
        memory[0] = word_for_instruction_code(40, 0);
        memory[1] = 10;
        let mut vm = NativeVm::from_memory(memory, b"");
        vm.d = 1;

        assert_eq!(vm.step(1).unwrap(), StepOutcome::Continue);

        assert_eq!(vm.c, 1);
        assert_eq!(vm.d, 11);
        assert_eq!(vm.a, 0);
    }

    #[test]
    fn crazy_instruction_updates_a_and_memory_d() {
        let mut memory = blank_memory();
        memory[0] = word_for_instruction_code(62, 0);
        memory[1] = 1;
        let mut vm = NativeVm::from_memory(memory, b"");
        vm.a = 0;
        vm.d = 1;

        assert_eq!(vm.step(1).unwrap(), StepOutcome::Continue);

        assert_eq!(vm.a, crazy_word(0, 1));
        assert_eq!(vm.memory[1], crazy_word(0, 1));
        assert_eq!(vm.c, 1);
        assert_eq!(vm.d, 2);
    }

    #[test]
    fn halt_does_not_encipher_or_increment() {
        let mut memory = blank_memory();
        memory[0] = word_for_instruction_code(81, 0);
        let mut vm = NativeVm::from_memory(memory, b"");

        assert_eq!(vm.step(1).unwrap(), StepOutcome::Halt);

        assert_eq!(vm.memory[0], word_for_instruction_code(81, 0));
        assert_eq!(vm.c, 0);
        assert_eq!(vm.d, 0);
    }

    #[test]
    fn jump_enciphers_post_jump_cell_under_pinned_profile() {
        let mut memory = blank_memory();
        memory[0] = word_for_instruction_code(4, 0);
        memory[1] = 10;
        memory[10] = u16::from(b'!');
        let mut vm = NativeVm::from_memory(memory, b"");
        vm.d = 1;

        assert_eq!(vm.step(1).unwrap(), StepOutcome::Continue);

        assert_eq!(vm.memory[0], word_for_instruction_code(4, 0));
        assert_eq!(vm.memory[10], u16::from(b'5'));
        assert_eq!(vm.c, 11);
        assert_eq!(vm.d, 2);
    }

    #[test]
    fn jump_to_non_printable_post_encipher_target_is_rejected() {
        let mut memory = blank_memory();
        memory[0] = word_for_instruction_code(4, 0);
        memory[1] = 10;
        memory[10] = 0;
        let mut vm = NativeVm::from_memory(memory, b"");
        vm.d = 1;

        assert!(matches!(
            vm.step(1),
            Err(ClassicMalbolgeError::InvalidRuntimeInstruction {
                address: 10,
                value: 0
            })
        ));
    }

    #[test]
    fn printable_runtime_unknown_opcode_behaves_as_nop() {
        let mut memory = blank_memory();
        memory[0] = u16::from(b'!');
        let mut vm = NativeVm::from_memory(memory, b"");

        assert_ne!(instruction_code(vm.memory[0], 0), 68);
        assert!(!VALID_SOURCE_INSTRUCTION_CODES.contains(&instruction_code(vm.memory[0], 0)));

        assert_eq!(vm.step(1).unwrap(), StepOutcome::Continue);

        assert_eq!(vm.memory[0], u16::from(b'5'));
        assert_eq!(vm.a, 0);
        assert_eq!(vm.c, 1);
        assert_eq!(vm.d, 1);
    }

    #[test]
    fn runtime_non_printable_instruction_is_rejected() {
        let mut memory = blank_memory();
        memory[0] = 0;
        let mut vm = NativeVm::from_memory(memory, b"");

        assert!(matches!(
            vm.step(1),
            Err(ClassicMalbolgeError::InvalidRuntimeInstruction {
                address: 0,
                value: 0
            })
        ));
    }

    #[test]
    fn halt_no_output_fixture_halts() {
        let backend = NativeClassicBackend;
        let limits = ClassicExecutionLimits::from(&ClassicMalbolge51Profile::default());
        let program = include_bytes!("../../../fixtures/classic/halt_no_output.mal");

        let report = backend.execute(program, b"", &limits).unwrap();

        assert_eq!(report.output, b"");
        assert_eq!(report.status, ClassicExecutionStatus::Halted);
        assert_eq!(report.steps, 1);
    }

    #[test]
    fn nul_output_fixture_emits_nul_and_halts() {
        let backend = NativeClassicBackend;
        let limits = ClassicExecutionLimits::from(&ClassicMalbolge51Profile::default());
        let program = include_bytes!("../../../fixtures/classic/nul_output.mal");

        let report = backend.execute(program, b"", &limits).unwrap();

        assert_eq!(report.output, vec![0]);
        assert_eq!(report.status, ClassicExecutionStatus::Halted);
        assert_eq!(report.steps, 2);
    }

    #[test]
    fn echo_first_byte_fixture_echoes_ascii_input() {
        let backend = NativeClassicBackend;
        let limits = ClassicExecutionLimits::from(&ClassicMalbolge51Profile::default());
        let program = include_bytes!("../../../fixtures/classic/echo_first_byte.mal");

        let report = backend.execute(program, b"\x61", &limits).unwrap();

        assert_eq!(report.output, b"\x61");
        assert_eq!(report.status, ClassicExecutionStatus::Halted);
        assert_eq!(report.steps, 3);
    }

    #[test]
    fn echo_first_byte_fixture_echoes_ff_input() {
        let backend = NativeClassicBackend;
        let limits = ClassicExecutionLimits::from(&ClassicMalbolge51Profile::default());
        let program = include_bytes!("../../../fixtures/classic/echo_first_byte.mal");

        let report = backend.execute(program, b"\xff", &limits).unwrap();

        assert_eq!(report.output, b"\xff");
        assert_eq!(report.status, ClassicExecutionStatus::Halted);
        assert_eq!(report.steps, 3);
    }

    #[test]
    fn exhausted_input_uses_eof_word_deterministically() {
        let backend = NativeClassicBackend;
        let limits = ClassicExecutionLimits::from(&ClassicMalbolge51Profile::default());
        let program = include_bytes!("../../../fixtures/classic/echo_first_byte.mal");

        let report = backend.execute(program, b"", &limits).unwrap();

        assert_eq!(report.output, vec![(CLASSIC_WORD_MAX % 256) as u8]);
        assert_eq!(report.status, ClassicExecutionStatus::Halted);
    }

    #[test]
    fn output_limit_is_enforced() {
        let backend = NativeClassicBackend;
        let mut limits = ClassicExecutionLimits::from(&ClassicMalbolge51Profile::default());
        limits.max_output_len = 0;

        assert!(matches!(
            backend.execute(b"cP", b"", &limits),
            Err(ClassicMalbolgeError::OutputLimitExceeded { .. })
        ));
    }

    #[test]
    fn step_limit_is_enforced() {
        let backend = NativeClassicBackend;
        let mut limits = ClassicExecutionLimits::from(&ClassicMalbolge51Profile::default());
        limits.max_steps = 0;

        assert!(matches!(
            backend.execute(b"QC", b"", &limits),
            Err(ClassicMalbolgeError::StepLimitExceeded { limit: 0 })
        ));
    }

    #[test]
    fn native_backend_reports_native_kind() {
        let backend = NativeClassicBackend;

        assert_eq!(backend.backend_kind(), ClassicBackendKind::Native);
    }

    #[test]
    fn native_backend_is_public_challenge_eligible() {
        let backend = NativeClassicBackend;

        assert!(backend.public_challenge_eligible());
    }

    #[test]
    fn external_oracle_matches_tiny_fixtures_if_configured() {
        let Ok(oracle) = std::env::var("MAL51_CLASSIC_ORACLE") else {
            return;
        };
        let fixtures = [
            ("halt_no_output.mal", b"".as_slice(), b"".as_slice()),
            ("nul_output.mal", b"".as_slice(), b"\x00".as_slice()),
            ("echo_first_byte.mal", b"a".as_slice(), b"a".as_slice()),
        ];

        for (fixture, input, expected_output) in fixtures {
            let output = run_external_oracle(&oracle, fixture, input);
            assert_eq!(
                output, expected_output,
                "oracle output mismatch for {fixture}"
            );
        }
    }

    fn blank_memory() -> Vec<u16> {
        vec![u16::from(b'o'); CLASSIC_WORD_MODULUS]
    }

    fn word_for_instruction_code(code: usize, address: usize) -> u16 {
        for word in 33_u16..=126 {
            if instruction_code(word, address) == code {
                return word;
            }
        }
        panic!("no printable word found for instruction code {code} at address {address}");
    }

    fn valid_source_repeated_nop(len: usize) -> Vec<u8> {
        (0..len)
            .map(|address| word_for_instruction_code(68, address) as u8)
            .collect()
    }

    fn run_external_oracle(oracle: &str, fixture: &str, input: &[u8]) -> Vec<u8> {
        use std::io::Write;
        use std::process::{Command, Stdio};

        let fixture_path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../../fixtures/classic")
            .join(fixture);
        let mut child = Command::new(oracle)
            .arg(&fixture_path)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .spawn()
            .unwrap_or_else(|error| panic!("failed to spawn oracle {oracle}: {error}"));
        child
            .stdin
            .as_mut()
            .expect("oracle stdin was piped")
            .write_all(input)
            .expect("failed to write oracle stdin");
        let output = child.wait_with_output().expect("failed to wait for oracle");
        assert!(
            output.status.success(),
            "oracle exited with {:?}",
            output.status
        );
        output.stdout
    }
}
