# GPT-6 Astra solves the five-epoch hash-prefix lookup

The native verifier passes `L4.R0.hash-prefix-1` over all five required epochs.
The program is 286 bytes, SHA-256
`264399918a74db9a3fd3600a8e8a1ca3c6b45a8f7170f6c0fe481a5d3d163cb6`.
Solver: **GPT-6 Astra**, OpenAI, Codex. Date: 2026-09-05.

This is the registry's public five-row lookup task. It does not implement SHA-256
or claim correctness on additional epochs. The five first-byte mappings are
`74:5e, 62:c8, b8:a5, 76:6a, fa:93`.

## Construction

The map8 prologue supplies the basic dispatcher. With operands 89 and 85,
two CRAZY operations map the five bytes to landing words 108, 90, 179, 125,
and 245 respectively. Execution starts at each word plus one, with D=50.
The five private code intervals are `[91,108)`, `[109,125)`, `[126,179)`,
`[180,245)`, and `[246,286)`. The landing word cells themselves stay fixed
because JUMP enciphers its destination before the program counter advances.

The new C search synthesizes instructions directly inside those intervals.
It assigns loader-valid bytes as code and operands are first encountered,
models self-modification and register state, and rejects reads from another
lane's variable interval. Every other source cell is a fixed constant.
This restriction allows the five witnesses to compose without a shared
assignment search. The native verifier remains the judge of the composition.

The initial NOP constant pool allowed three of five lanes. Deterministically
randomized constant pools with seeds 600000, 600001, and 600002 produced
native results of three, four, and five passing epochs. Each lane search used
at most 300,000 nodes per depth, with depth limits 5 through 22. The successful
search's 1,024-byte tape was truncated to 286 bytes and verified again.

Earlier searches extended map8's two-stage routing geometry for input-byte
positions 0 through 3. They did not produce a complete candidate before the
direct-tail construction succeeded. Those bounded failures do not establish
an impossibility result for two-stage routing.

## Reproduce

From the repository root:

```sh
cargo build --release
python3 research/astra-2026-09-05/derive_cases.py
cc -O3 research/astra-2026-09-05/private.c -o /tmp/astra-private
python3 research/astra-2026-09-05/direct_search.py /tmp/astra-private
./target/release/malbolge-rungs verify --rung L4.R0.hash-prefix-1 \
  --program solutions/hash-prefix-1/gpt-6-astra.mal --json
```

`direct-search.jsonl` records each constant-pool seed, per-lane search outcome,
node count, and depth. `solution-verify.json` contains all five native cases.
The structured record reports the harness's required worst-epoch score, 1/1;
the complete verification covers five epochs, each with one case.

## Prior work and budget

This builds on the original hash-prefix attempt's identification of the public
lookup structure, the map8 dispatcher, and the XOR-256 attempt's independent
block synthesis method. The C solver and constant-pool search here are new.

The user authorized up to one sixth of their weekly Astra allocation. Session
telemetry reported 3% weekly use at the first observation and at this solve;
the rounded meter does not provide an exact task charge. About fifteen minutes
of wall time included repository inspection, prior-work review, implementation,
and verification. Search continues on the next hash-prefix rung separately.
