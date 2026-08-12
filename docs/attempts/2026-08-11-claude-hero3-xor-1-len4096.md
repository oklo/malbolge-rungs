# Claude attempt: `L2.R0d.xor-1-len4096` (the stride is forced; the sweep was backwards)

Date: 2026-08-11

Outcome: **unsolved**. Best candidate is correct on **249 of 256** input bytes,
measured natively on all 256. That equals hero1's coverage number but reaches it
on the **swapped prologue** — the architecture where `b = 0` is solvable at all —
where the previous best was hero2's 247. Three other things came out of this run:

1. **The dispatch stride of 9 is forced, and the 4096-byte cap cannot buy a wider
   one.** This is the first structural result on this rung that is a *negative*
   about the resource the rung exists to test.
2. **hero2's "single highest-value untried thing" — escape to private tape at
   2305..4095 — does not work for the inputs that need it.** Measured, not argued:
   36 of 256 inputs can move control into that window, and not one of them is in
   the stuck set.
3. **The assembly sweep has been running in the wrong direction for three
   records.** Reversing it, and replacing its acceptance gate, is what took the
   swapped line from 247 to 249 — the first two points of it inside 43 seconds.

Solver: Claude (Opus 5) via Claude Code, autonomous single-session run under a
hard cap of 900k tokens / 150 minutes.

Builds on [`2026-08-11-claude-hero2-xor-1-len4096.json`](2026-08-11-claude-hero2-xor-1-len4096.json)
(247/256, the IN/MOVD prologue swap and the JMP-encipherment fix in the DFS, both
reused unchanged) and through it on
[`2026-08-11-claude-hero1-xor-1-len4096.json`](2026-08-11-claude-hero1-xor-1-len4096.json)
(249/256, the simulator and optimiser),
[`2026-08-11-claude-push-xor-1-len4096.json`](2026-08-11-claude-push-xor-1-len4096.json)
(229/256) and [`2026-08-11-claude-xor-1-len4096.json`](2026-08-11-claude-xor-1-len4096.json)
(119/256).

Artifacts: [`research/xor-1-len4096-hero3/`](../../research/xor-1-len4096-hero3/) —
`hero10.c` (hero2's `hero9.c` plus the `-desc`, `-window`, `-reach` and `-tails`
modes), `stride.py` (the stride proof, runnable), `fleet5.sh` (the run that
produced the candidate), `fleet4.sh` (the run that did not, kept deliberately),
`nc.sh`/`one.sh`, `cand.mal`, `runs/` logs.

## 1. The stride is forced

This rung *is* `L2.R0.xor-1` with the program-length cap raised from **256** to
**4096** and nothing else changed. Every record so far has noted that the cap
"does not bind" — 2305 bytes of an allowed 4096 — and moved on. That reading is
backwards. The cap binds through the **stride**, and the stride is the whole
difficulty of the rung.

The prologue reads `b` with `IN` and then applies eight `ROT`s. `rotr` is a
10-trit rotate right, so eight of them are a rotate *left* by two trits, which is
exactly `×9` for any `b < 3^8`. The dispatch is `c = m[72] = 9b`, so input `b`
owns precisely the nine cells `9b+1..9b+9`. Nine cells is small, and worse, those
nine cells also have to serve as the operand tape every *other* input reads from
`d = 73`. That double duty is the coupling that all four prior records ran into.

A wider stride would dissolve it. It is not available:

* **Rotation is the only information-preserving primitive**, and it only
  multiplies by powers of 3. `×27` puts input 255 at address 6885, past the cap.
  `×9` is the largest power of 3 that fits.
* **`CRZ` cannot substitute.** `crazy(a,d)` is trit-wise with
  `CT = [[1,0,0],[1,0,2],[2,2,1]]`. `CT[1]` is injective; `CT[0]` and `CT[2]` are
  2-to-1. An operand that is a program byte is `≤ 126 < 3^5`, so its trits 5..9
  are all zero and `CT[0]` is what gets applied there. `A = 9b` carries `b`'s
  trits at positions 2..7, so trits 5, 6, 7 of `A` — which are trits 3, 4, 5 of
  `b`, i.e. `b div 27` — are destroyed by the *first* `CRZ`, and nothing later
  recovers them.
* Two `CRZ`s do not help. `stride.py` checks all 94 × 94 = 8836 byte-operand
  pairs: **zero** make `crazy(crazy(9b,K1),K2)` injective over the 256 inputs.

`stride.py` also records the bound that killed the other route I tried first:
`crazy(9b, byte)` is **always ≥ 3^8 + 3^9 = 26244** (measured minimum 27229),
because `A`'s trits 8 and 9 are zero, a byte operand's trits 8 and 9 are zero,
and `CT[0][0] = 1`. So a single `CRZ` always throws the value into the far tail,
and `ROT` cannot bring it back down in one hop, because `crazy`'s output trit is
never 0 where `A`'s trit is 0 — so the low trit is always nonzero and `rotr`
rotates it to the top instead of dividing by 3.

**Consequence for the board:** the 3840 extra bytes this rung grants over
`L2.R0.xor-1` cannot be spent on the thing that would actually help. The two
rungs are much closer than the length caps suggest.

## 2. Escape to private tape: measured, and it is not the answer

hero2 closed with this as "the single highest-value untried thing on this rung":
a block computes a large value into a cell and jumps through it into 2305..4095,
where its solution costs nothing globally. The mechanism is real — the reasoning
was right — but it is testable, and I tested it rather than inheriting it.

`hero10.c -reach -rlo A -rhi B` runs the block-local DFS with the success
condition replaced by "control reached `[A,B]`". Against the shipped candidate at
`N = 4096`, step cap 45:

| target window | inputs that can move **C** there |
|---|---|
| `≥ 2305` (anywhere past the blocks) | 252 / 256 |
| `[2305, 4095]` (the **writable** window) | **36 / 256** |

The first row is the trap. 252 inputs can leave the block region — almost all of
them into the crazy-filled tail around address 19700, which is not program text
and not a design variable beyond the two bytes that seed it. Only 36 can reach
the part you can actually write code into, and a further 211 can only get `d`
there, which buys scratch space, not code space.

The 36 are:

    18 23 24 26 41 59 62 78 96 105 109 110 115 126 127 132 137 138 150 151 152
    155 176 216 223 224 229 231 239 240 250 251 252 253 254 255

The stuck set of the shipped candidate is `0, 1, 3, 4, 8, 9, 255`. **Their
intersection is `{255}`** — and for `b = 255` the mechanism is not a computed
jump at all, it is plain fall-through off the end of its own block. The low
inputs, whose witnesses rewrite 15–40 shared cells and are the entire reason
private tape was attractive, cannot reach the window at any step cap I ran.

This is the expected consequence of §1: getting control to a chosen address needs
a computed value, computed values come from `CRZ`, and `CRZ` against a byte lands
at ≥ 26244. The 36 that succeed are the ones sitting near enough to 2305 to walk
or short-jump there.

## 3. `b = 255` is boxed in at N = 2305, and free at any larger N

Two separate facts, both new:

* Run the DFS for `b = 255` with its own block **plus the whole shared window
  `[34,100]` free**, and it returns **zero witnesses**. It is not tape-limited in
  the ordinary sense; it is boxed in. Its block is `2296..2304`, and cells 2303
  and 2304 are `N-2` and `N-1` — the two bytes that seed the entire crazy tail
  that every tail-reading input depends on. Its code and the global tail are the
  same two bytes.
* Set `N` to anything above 2305 and `b = 255` is solved **for free**, in every
  single configuration I tried (`N` = 2306, 2308, 2311, 2314, 2320, 2332, 2350).
  Its block falls through into unowned tape, and the tail seed moves off its
  block entirely — two independent design variables where there was one.

The price is that moving `N` rewrites the whole tail, which costs the ~8–10
inputs that read it (134, 144, 146, 152, 231, 239, 253, 254 recur across the
scan). One descending pass does not put them back; a full re-optimisation at the
new `N` might, and did not fit in this clock. That is a clean, bounded, and
well-posed next run — see the budget section.

## 4. The sweep was running backwards

This is the part that produced the coverage.

Prior art's assembly pass walks inputs in **ascending** order and accepts a
witness only when the **global** delta is `≥ 0`. Both halves are wrong for this
architecture.

Execution runs forward (`C` increases), and `d` can never exceed about
`126 + stepcap`: `MOVD` sets `d = m[d]`, and `m[d]` is a program byte `≤ 126`,
after which `d` only increments. So **block `b`'s own cells are read only by
inputs lower than `b`** — the ones that run up into them from below. Never by
higher ones.

Order the sweep **descending** and the choice of `b`'s witness cannot disturb
anything already settled. All the damage it does lands on inputs `< b`, which
have not had their turn yet. Which makes the `≥ 0` global gate actively harmful:
it rejects exactly the trades that give a higher block its only witness at the
cost of a lower block's current one — and that lower block would have been
re-solved two iterations later. The correct gate is **"no damage to inputs above
`b`"**, which is what `-desc` in `hero10.c` implements.

With the sweep fixed, the joint problem collapses to a much smaller one: above
the shared window nothing is a free choice any more, so the only real variables
are the ~150 window cells (the code of inputs 4..20, which is also everyone's
operand tape) plus the tail family. `-window` is a coordinate search over exactly
those, with `-desc` as the repair operator. That is hero1's and hero2's
"decomposed objective" (both listed it in `would_try_next`; neither built it),
made exact.

Running `-desc` alone on hero2's 247 candidate does not move the score — but it
sharpens the diagnosis, which is the point: the miss set
`0, 1, 3, 4, 5, 8, 9, 10, 255` is **entirely** the shared window (blocks 0–10)
plus the tail input. Nothing above block 10 was ever the problem.

Then `-window` found `247 → 248` from a **single cell (address 35)**, in 43
seconds, and 249 shortly after. Every number here is a native all-256
measurement.

## 5. A negative result about step caps that cost me 40 minutes

hero2's first recommendation was to re-run the pipeline "at step cap ≥ 45". I
took that literally as a global setting and launched an 11-way fleet at
`steps = 45..70`, `span = 12..16`. **After 40 minutes on 11 cores it had logged
zero probes** — not zero improvements, zero completed probes. Each cell probe is
8 codes × a repair pass, and the DFS cost explodes in the step cap.

The same search at `steps = 36, span = 9` found +1 in 43 seconds and +2 shortly
after. hero2's own measurements already implied this and I did not read them
carefully enough: assembly at `(26,16)`, `(40,18)`, `(40,27)` and `(60,27)` all
returned *exactly* 249 with an identical miss set. The cap does not buy tape
quality.

The cap ≥ 45 finding was about the **sled inputs** specifically — `b = 0`'s sled
is 31 steps of NOP before it even reaches the dispatch JMP, so nothing below ~35
can see its route. That is a statement about four inputs, not a global setting.
The right configuration is cheap probes for the tape and a deep cap only when
searching `0, 1, 3`. `fleet4.sh` (the failed configuration) is kept in the
research directory next to `fleet5.sh` (the one that worked) because the contrast
is the finding.

## 6. Where it stopped

Shipped candidate: `research/xor-1-len4096-hero3/cand.mal`, 2305 bytes,
**249/256** natively, on the swapped prologue. Misses:

    b = 0, 1, 3, 4, 8, 9, 255

Six of the seven are inside the shared window; the seventh is the tail input of
§3. All of `4, 8, 9` are individually feasible with the window free — the DFS
finds 1440, 4096 and 924 witnesses respectively. It is a joint constraint problem
over ~150 cells, and single-cell window moves are exhausted: four second-
generation `-window` runs seeded from the 249 tape produced nothing further in
the time available.

hero1's 249 is on the **old** prologue, where `b = 0` is unreachable and the
ceiling is therefore 255. This 249 is on the swapped prologue, where hero2 proved
`b = 0` reachable natively. Same number, and the two are not equivalent: this one
is on the only line that can still reach 256.

## Budget and what I would do next

Spent: roughly 380k tokens and 130 minutes of the 900k / 150-minute cap. Wall
clock was binding again, and about 40 of those 130 minutes were burned on the
over-deep fleet in §5. Neither the length cap (2305 of 4096) nor the step cap
(≤ 80 of 2048) binds.

**Wall or budget?** Budget, but with the search space now much smaller than any
prior record thought. §4 removes ~245 of the 256 inputs from the problem
permanently: above block 10 nothing is a free choice. What is left is ~150 window
cells and the tail family. That is a small enough space that I would expect a
dedicated run to close it, and I no longer think coverage is where the risk is.

In priority order, with more:

1. **Re-optimise at `N = 2320` (or any `N` above 2305).** §3 makes `b = 255` free
   and decouples the tail seed from its block. The cost is the ~8–10 tail-reading
   inputs, and recovering them is exactly what `-window` + `-desc` is for. This is
   the cheapest remaining structural win and I ran out of clock with it half
   measured.
2. **Two-cell window moves.** Single-cell coordinate descent on the window is now
   exhausted twice over (hero2 on the old tape, this run on the swapped one).
   hero2's `-need` already showed why: `b = 8` and `b = 9` both require
   `m[74] = 118` **and** `m[75] = 117` together. The window is ~150 cells, so
   pairs are ~11k × 64 assignments — large but not hopeless with `-desc` as a
   fast repair, and it is the smallest move class that has not been tried.
3. **Finish the tail-family sweep.** `-tails` is implemented in `hero10.c` and
   enumerates all 64 families with full re-optimisation inside each; I killed it
   for cores and it never completed a family. hero1 flagged this, hero2 flagged
   it, and it is *still* the oldest untried item on this rung. Combine it with (1)
   — at `N > 2305` the family is a genuinely free variable rather than a hostage
   to `b = 255`'s code.
4. **A deep-cap search for `0, 1, 3` only**, on a window frozen by (1)–(3).
   Per §5 this is where step cap ≥ 45 actually belongs, and it is four inputs
   against a fixed tape rather than a joint problem.

I would rank this rung roughly where it sits, and for a reason none of the prior
records gives: §1 says the 4096-byte cap is close to decorative, so this rung is
not much easier than `L2.R0.xor-1` at 256 bytes. What has changed is that the
remaining work is small and well-posed rather than open-ended.

## Warnings for the next agent

**`verify` PASSES on this candidate, with exit code 0, and it is not a solve.**
One case is drawn per epoch and `min_epochs` is 5, so 249/256 passes with
probability `(249/256)^5 ≈ 0.87`. I ran it and it returned `RESULT: PASS` across
all five epochs. Both prior records warned about this; I am repeating it because
it is the single easiest way to file a false claim on this rung. The only honest
measurement is all 256 bytes through `execute` — `nc.sh` does it in under a
second on 14 cores.

**Do not inherit a `would_try_next` either.** hero2's list is the best thing on
this rung and I executed it — but its top-ranked item (§2) is refuted by a
30-second measurement, and its step-cap advice (§5) cost me 40 minutes when
applied globally. Both were reasonable inferences from real structure. This rung
has now had a structural claim overturned in four consecutive records; the
pattern holds, and the fix is the same every time: measure the claim before
building on it.
