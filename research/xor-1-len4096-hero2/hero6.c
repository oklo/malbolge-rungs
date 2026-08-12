/* hero.c -- global optimiser for the private-CODE-block architecture on
 * L2.R0d.xor-1-len4096.
 *
 * Architecture (prior art, research/xor-1-len4096-push/build.py):
 *   33 bytes of prologue leave m[72] = 9b and A = 9b, then JMP at address 32
 *   sets c = 9b, so input b executes its own block at 9b+1..9b+9 with d = 73.
 *
 * Prior art reached 229/256 with a greedy phase-1/2/3 assembler.  What binds is
 * COUPLING: every block starts with d = 73, so the operand cells every input
 * reads are the low blocks' code bytes, and the far tape past the program end
 * is shared by everyone.  This file treats that as one joint problem:
 *
 *   - exact per-input DFS over the block's own cells given the rest of the tape
 *   - full 59049-cell memory, so blocks that walk into the crazy-filled tail
 *     past the program end are modelled (prior art's 229 uses that: input 17
 *     reads m[19713])
 *   - local search over the whole tape, re-scoring all 256 inputs per move
 *
 * The post-prologue state is computed in closed form rather than simulated:
 * the prologue executes 0..32 exactly once (so those cells are enciphered),
 * leaves m[71] = crazy(b,121), m[72] = 9b, A = 9b, and jumps to c = 9b+1 with
 * d = 73.  Nothing else in memory is touched.
 *
 * Build: cc -O3 -o hero hero.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#include <math.h>

#define M 59049
static const char *XLAT2 =
    "5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";
enum { JMP = 4, OUT = 5, IN = 23, ROT = 39, MOVD = 40, CRZ = 62, NOP = 68, HLT = 81 };
static const int CODES[8] = {JMP, OUT, IN, ROT, MOVD, CRZ, NOP, HLT};
static const int CT[3][3] = {{1, 0, 0}, {1, 0, 2}, {2, 2, 1}};

static int crazyw(int a, int d) {
    int r = 0, p = 1;
    for (int i = 0; i < 10; i++) { r += CT[d % 3][a % 3] * p; a /= 3; d /= 3; p *= 3; }
    return r;
}
static inline int rotr(int w) { return w / 3 + (w % 3) * 19683; }
static int byte_for(int code, int a) {
    int v = ((code - a) % 94 + 94) % 94;
    while (v < 33) v += 94;
    return v;                       /* always in 33..126 */
}
static inline int code_of(int w, int a) { return (w + a) % 94; }
static uint8_t X2[128];

/* ---------------- program layout ---------------- */
static int N = 2305;
static int PROLEN = 33;
static uint8_t prog[M];
static int forced_addr[6] = {40, 62, 71, 72, 73, 123};
static int forced_val[6]  = {122, 71, 121, 121, 61, 70};
static const char *PROLOGUE = "u'&%:9\"!}}|zzywwvttsqqpnnmkkjhhgf";

static int fixedmask[M];
static void mark_fixed(void) {
    memset(fixedmask, 0, sizeof(fixedmask));
    for (int a = 0; a < PROLEN; a++) fixedmask[a] = 1;
    for (int i = 0; i < 6; i++) fixedmask[forced_addr[i]] = 1;
}
static inline int is_fixed(int a) { return a < 0 || a >= M ? 1 : fixedmask[a]; }

/* ---------------- memory ---------------- */
static uint16_t mem[M];          /* live: post-prologue image, b-independent part */
static int und_a[16384];
static uint16_t und_v[16384];
static int nund;
static inline void wr(int a, int v) { und_a[nund] = a; und_v[nund] = mem[a]; nund++; mem[a] = (uint16_t)v; }
static inline void unwind(int to) { while (nund > to) { nund--; mem[und_a[nund]] = und_v[nund]; } }

static void rebuild_all(void) {
    for (int a = 0; a < N; a++) mem[a] = prog[a];
    for (int a = N; a < M; a++) mem[a] = crazyw(mem[a - 1], mem[a - 2]);
    /* addresses 0..PROLEN-2 execute and are enciphered in place; the JMP at
     * PROLEN-1 is NOT -- the canonical cycle enciphers m[c] after c has already
     * become the jump target, so cell 9b is enciphered instead (done per-input). */
    for (int a = 0; a < PROLEN - 1; a++) mem[a] = X2[prog[a]];
    nund = 0;
}
/* change one program cell in place; the crazy-filled tail only depends on the
 * last two program bytes, which the optimiser never touches. */
static inline void poke(int a, int byte) {
    prog[a] = (uint8_t)byte; mem[a] = (uint16_t)byte;
    if (a >= N - 2) for (int x = N; x < M; x++) mem[x] = crazyw(mem[x - 1], mem[x - 2]);
}

/* ---------------- simulator ---------------- */
static int rec_touch, tl[128], ntl;
static inline void touch(int a) { if (rec_touch && ntl < 128) tl[ntl++] = a; }

static int simulate(int b) {
    int base = nund;
    wr(71, crazyw(b, 121));
    wr(72, 9 * b);
    int A = 9 * b, C = 9 * b + 1, D = 73, outn = 0, outb = -1;
    int target = b ^ 0x51, ok = 0;
    ntl = 0; touch(9 * b);
    { int t = mem[9 * b]; if (t < 33 || t > 126) { unwind(base); return 0; } wr(9 * b, X2[t]); }
    for (int step = 0; step < 2048; step++) {
        touch(C);
        int w = mem[C];
        if (w < 33 || w > 126) break;
        int code = code_of(w, C);
        if (code == JMP || code == ROT || code == MOVD || code == CRZ) touch(D);
        if (code == IN) break;                       /* a second IN reads seed-dependent bytes */
        if (code == HLT) { ok = (outn == 1 && outb == target); break; }
        switch (code) {
            case JMP: C = mem[D]; break;
            case OUT: if (outn >= 1) goto done; outb = A & 255; outn = 1; break;
            case ROT: { int v = rotr(mem[D]); wr(D, v); A = v; break; }
            case MOVD: D = mem[D]; break;
            case CRZ: { int v = crazyw(A, mem[D]); wr(D, v); A = v; break; }
            default: break;
        }
        {
            int wc = mem[C];
            if (wc < 33 || wc > 126) goto done;
            wr(C, X2[wc]);
        }
        C = (C + 1) % M; D = (D + 1) % M;
    }
done:
    unwind(base);
    return ok;
}

static int solved[256];
static int score_all(void) {
    int s = 0;
    for (int b = 0; b < 256; b++) { solved[b] = simulate(b); s += solved[b]; }
    return s;
}

/* ---------------- exact per-input DFS over chosen cells ---------------- */
static uint8_t mut_of[M], asg[M];
static int dfs_target, dfs_steps_cap;
static long dfs_nodes, dfs_node_cap;

#define MAXSOL 4096
#define MAXCELL 64
static int sol_n[MAXSOL], sol_addr[MAXSOL][MAXCELL];
static uint8_t sol_byte[MAXSOL][MAXCELL];
static int nsol;
static int cur_addr[MAXCELL], cur_byte[MAXCELL], ncur;

static int rec(int A, int C, int D, int outn, int outb, int steps);

static int branch(int X, int A, int C, int D, int outn, int outb, int steps) {
    if (ncur >= MAXCELL) return 0;
    int base = nund;
    for (int k = 0; k < 8; k++) {
        int v = byte_for(CODES[k], X);
        wr(X, v);
        asg[X] = 1;
        cur_addr[ncur] = X; cur_byte[ncur] = v; ncur++;
        int r = rec(A, C, D, outn, outb, steps);
        ncur--;
        asg[X] = 0;
        unwind(base);
        if (r && nsol >= MAXSOL) return 1;
    }
    return 0;
}

static void record_solution(void) {
    if (nsol >= MAXSOL) return;
    sol_n[nsol] = ncur;
    for (int i = 0; i < ncur; i++) { sol_addr[nsol][i] = cur_addr[i]; sol_byte[nsol][i] = (uint8_t)cur_byte[i]; }
    nsol++;
}

static int rec(int A, int C, int D, int outn, int outb, int steps) {
    if (++dfs_nodes > dfs_node_cap) return 0;
    if (steps >= dfs_steps_cap) return 0;
    if (mut_of[C] && !asg[C]) return branch(C, A, C, D, outn, outb, steps);
    int w = mem[C];
    if (w < 33 || w > 126) return 0;
    int code = code_of(w, C);
    if (code == IN) return 0;
    if (code == HLT) {
        if (outn == 1 && outb == dfs_target) { record_solution(); return 1; }
        return 0;
    }
    if (code == OUT && (outn >= 1 || (A & 255) != dfs_target)) return 0;
    if (code == JMP || code == ROT || code == MOVD || code == CRZ)
        if (mut_of[D] && !asg[D]) return branch(D, A, C, D, outn, outb, steps);
    int base = nund;
    int nA = A, nC = C, nD = D, nOn = outn, nOb = outb;
    switch (code) {
        case JMP: nC = mem[D]; break;
        case OUT: nOb = A & 255; nOn = 1; break;
        case ROT: { int v = rotr(mem[D]); wr(D, v); nA = v; break; }
        case MOVD: nD = mem[D]; break;
        case CRZ: { int v = crazyw(A, mem[D]); wr(D, v); nA = v; break; }
        default: break;
    }
    {
        int wc = mem[C];
        if (wc < 33 || wc > 126) { unwind(base); return 0; }
        wr(C, X2[wc]);
    }
    int r = rec(nA, (nC + 1) % M, (nD + 1) % M, nOn, nOb, steps + 1);
    unwind(base);
    return r;
}

static int solve_input(int b, const int *cells, int ncells, int stepcap, long nodecap) {
    for (int i = 0; i < ncells; i++) mut_of[cells[i]] = 1;
    nsol = 0; ncur = 0;
    dfs_target = b ^ 0x51; dfs_steps_cap = stepcap;
    dfs_nodes = 0; dfs_node_cap = nodecap;
    int base = nund;
    wr(71, crazyw(b, 121));
    wr(72, 9 * b);
    if (mut_of[9 * b] && !asg[9 * b]) {
        /* cell 9b is the last cell of block b-1; the dispatch JMP enciphers it
         * before b's block runs, so its post-encipherment value is what b sees. */
        mut_of[9 * b] = 0;
    }
    { int t = mem[9 * b];
      if (t >= 33 && t <= 126) { wr(9 * b, X2[t]); rec(9 * b, 9 * b + 1, 73, 0, -1, 0); } }
    unwind(base);
    for (int i = 0; i < ncells; i++) mut_of[cells[i]] = 0;
    return nsol;
}

static int block_cells(int b, int span, int *out) {
    int n = 0;
    for (int a = 9 * b + 1; a <= 9 * b + span; a++)
        if (a >= 0 && a < N && !is_fixed(a)) out[n++] = a;
    return n;
}

/* ---------------- incremental scoring ---------------- */
static uint64_t own[M][4];                 /* own[a] = bitset of inputs whose run touches a */
static int tlist[256][128], ntlist[256];
static int cur_score;

static void resim(int b) {
    uint64_t bit = 1ULL << (b & 63); int wd = b >> 6;
    for (int i = 0; i < ntlist[b]; i++) own[tlist[b][i]][wd] &= ~bit;
    rec_touch = 1;
    int ok = simulate(b);
    rec_touch = 0;
    cur_score += ok - solved[b];
    solved[b] = ok;
    ntlist[b] = ntl;
    for (int i = 0; i < ntl; i++) { tlist[b][i] = tl[i]; own[tl[i]][wd] |= bit; }
}
static void full_resim(void) {
    memset(own, 0, sizeof(own));
    memset(solved, 0, sizeof(solved));
    cur_score = 0;
    for (int b = 0; b < 256; b++) { ntlist[b] = 0; resim(b); }
}
/* apply byte changes at addrs[0..n), re-scoring only the inputs that can be
 * affected (an input whose trace never reads a changed cell cannot change). */
static uint64_t aff[4];
static void apply_changes(const int *addrs, const uint8_t *bytes, int n) {
    aff[0] = aff[1] = aff[2] = aff[3] = 0;
    int tailchange = 0;
    for (int i = 0; i < n; i++) {
        if (addrs[i] >= N - 2) tailchange = 1;
        for (int w = 0; w < 4; w++) aff[w] |= own[addrs[i]][w];
    }
    /* the last two program bytes seed the crazy-filled tail, so changing them
     * rewrites every cell past the program end -- every input is affected. */
    if (tailchange) aff[0] = aff[1] = aff[2] = aff[3] = ~0ULL;
    for (int i = 0; i < n; i++) poke(addrs[i], bytes[i]);
    for (int w = 0; w < 4; w++) {
        uint64_t m = aff[w];
        while (m) { int t = __builtin_ctzll(m); m &= m - 1; resim(w * 64 + t); }
    }
}

/* ---------------- driver ---------------- */
static uint64_t rng_s = 88172645463325252ULL;
static uint64_t rnd(void) { rng_s ^= rng_s << 13; rng_s ^= rng_s >> 7; rng_s ^= rng_s << 17; return rng_s; }
static double rnd01(void) { return (double)(rnd() >> 11) / 9007199254740992.0; }

static void init_prog(const char *seedfile) {
    for (int a = 0; a < PROLEN; a++) prog[a] = (uint8_t)PROLOGUE[a];
    prog[32] = (uint8_t)byte_for(JMP, 32);
    for (int a = PROLEN; a < N; a++) prog[a] = (uint8_t)byte_for(NOP, a);
    for (int i = 0; i < 6; i++) if (forced_addr[i] < N) prog[forced_addr[i]] = (uint8_t)forced_val[i];
    if (seedfile) {
        FILE *f = fopen(seedfile, "rb");
        if (!f) { fprintf(stderr, "no seed %s\n", seedfile); exit(1); }
        static uint8_t buf[M];
        int n = (int)fread(buf, 1, M, f);
        fclose(f);
        for (int a = PROLEN; a < n && a < N; a++) if (!is_fixed(a)) prog[a] = buf[a];
        fprintf(stderr, "seeded %d bytes from %s (N=%d)\n", n, seedfile, N);
    }
}

static void write_prog(const char *path) {
    for (int a = 0; a < N; a++) {
        int c = code_of(prog[a], a), ok = 0;
        for (int k = 0; k < 8; k++) if (CODES[k] == c) ok = 1;
        if (!ok || prog[a] < 33 || prog[a] > 126) { fprintf(stderr, "ILLEGAL byte %d at %d\n", prog[a], a); exit(1); }
    }
    FILE *f = fopen(path, "wb");
    fwrite(prog, 1, N, f);
    fclose(f);
}

static const char *OUTPATH = "cand.mal";
static void write_prog_to(const char *path) {
    for (int a = 0; a < N; a++) {
        int c = code_of(prog[a], a), ok = 0;
        for (int k = 0; k < 8; k++) if (CODES[k] == c) ok = 1;
        if (!ok || prog[a] < 33 || prog[a] > 126) { fprintf(stderr, "ILLEGAL byte %d at %d\n", prog[a], a); exit(1); }
    }
    FILE *f = fopen(path, "wb"); fwrite(prog, 1, N, f); fclose(f);
}
static int span = 9, stepcap = 14;
static long nodecap = 4000000L;

/* try to re-solve input b; returns the delta actually applied (0 if none) */
static int try_input(int b, double T, int forceaccept) {
    int cells[MAXCELL];
    int ncells = 0;
    for (int a = 9 * b + 1; a <= 9 * b + span; a++)
        if (a >= 0 && a < N && !is_fixed(a)) cells[ncells++] = a;
    if (!ncells) return 0;
    int found = solve_input(b, cells, ncells, stepcap, nodecap);
    if (!found) return 0;
    /* evaluate a random sample of the solutions, keep the best */
    int tries = found < 24 ? found : 24;
    int bestdelta = -999, bestidx = -1;
    int before = cur_score;
    for (int t = 0; t < tries; t++) {
        int s = (tries == found) ? t : (int)(rnd() % found);
        uint8_t save[MAXCELL]; int ad[MAXCELL];
        for (int i = 0; i < sol_n[s]; i++) { ad[i] = sol_addr[s][i]; save[i] = prog[ad[i]]; }
        apply_changes(ad, sol_byte[s], sol_n[s]);
        int d = cur_score - before;
        apply_changes(ad, save, sol_n[s]);
        if (d > bestdelta) { bestdelta = d; bestidx = s; }
    }
    if (bestidx < 0) return 0;
    int accept = bestdelta > 0 || forceaccept ||
                 (T > 0 && rnd01() < exp((double)bestdelta / T));
    if (!accept) return 0;
    apply_changes(sol_addr[bestidx], sol_byte[bestidx], sol_n[bestidx]);
    return bestdelta;
}

/* ---- per-input feasibility upper bound: let the DFS also choose the shared
 * cells, ignoring what other inputs need.  An input that fails here cannot be
 * solved by ANY tape (within the step cap), so it is a structural wall. ---- */
static int only_b = -1;
static long feas_nodes = 200000000L;
static void feasibility(int hot_lo, int hot_hi) {
    int cells[MAXCELL];
    int nfeas = 0;
    printf("infeasible:");
    for (int b = 0; b < 256; b++) {
        if (only_b >= 0 && b != only_b) continue;
        if (only_b < 0 && solved[b]) { nfeas++; continue; }
        int nc = 0;
        for (int a = 9 * b + 1; a <= 9 * b + span && a < N; a++) if (!is_fixed(a)) cells[nc++] = a;
        for (int a = hot_lo; a <= hot_hi && nc < MAXCELL; a++)
            if (!is_fixed(a) && (a < 9 * b + 1 || a > 9 * b + span)) cells[nc++] = a;
        int f = solve_input(b, cells, nc, stepcap, feas_nodes);
        if (f) nfeas++;
        else printf(" %d%s", b, dfs_nodes > feas_nodes ? "(capped)" : "(exhaustive)");
    }
    printf("\n feasible %d/256 (mutable = own block + hot [%d,%d], step cap %d)\n",
           nfeas, hot_lo, hot_hi, stepcap);
}


/* ---- exhaustive block-local assembly repair, to fixpoint ----
 * For every currently-unsolved input, run the exact DFS over its own block and
 * take the witness with the best GLOBAL delta, applying it whenever it costs
 * nothing.  This is what the sweep uses as its repair operator instead of the
 * random repair_pass: perturbing a shared cell breaks many inputs at once, and
 * only an exact per-input search says whether they can be put back. */
static int wit_cap = 40;
static long asm_nodes = 3000000L;
static int assemble_fix(int maxpass) {
    for (int pass = 0; pass < maxpass; pass++) {
        int before = cur_score;
        for (int b = 0; b < 256; b++) {
            if (solved[b]) continue;
            int cells[MAXCELL], nc = 0;
            for (int a = 9 * b + 1; a <= 9 * b + span && a < N; a++)
                if (!is_fixed(a)) cells[nc++] = a;
            if (!nc) continue;
            int f = solve_input(b, cells, nc, stepcap, asm_nodes);
            if (!f) continue;
            int tries = f < wit_cap ? f : wit_cap;
            int bd = -999, bi = -1, base0 = cur_score;
            for (int t = 0; t < tries; t++) {
                int s2 = (tries == f) ? t : (int)(rnd() % f);
                uint8_t save[MAXCELL]; int ad[MAXCELL];
                for (int i = 0; i < sol_n[s2]; i++) { ad[i] = sol_addr[s2][i]; save[i] = prog[ad[i]]; }
                apply_changes(ad, sol_byte[s2], sol_n[s2]);
                int d = cur_score - base0;
                apply_changes(ad, save, sol_n[s2]);
                if (d > bd) { bd = d; bi = s2; }
            }
            if (bi >= 0 && bd >= 0) apply_changes(sol_addr[bi], sol_byte[bi], sol_n[bi]);
        }
        if (cur_score == before) break;
    }
    return cur_score;
}
/* reroll: a SOLVED input may be holding a witness that blocks its neighbours.
 * Re-search it and take any witness that is globally >= as good. */
static int reroll_pass(int lo, int hi) {
    for (int b = 0; b < 256; b++) {
        if (9 * b + 9 < lo || 9 * b + 1 > hi) continue;
        if (!solved[b]) continue;
        int cells[MAXCELL], nc = 0;
        for (int a = 9 * b + 1; a <= 9 * b + span && a < N; a++)
            if (!is_fixed(a)) cells[nc++] = a;
        if (!nc) continue;
        int f = solve_input(b, cells, nc, stepcap, asm_nodes);
        if (f <= 1) continue;
        int tries = f < wit_cap ? f : wit_cap;
        int bd = 0, bi = -1, base0 = cur_score;
        for (int t = 0; t < tries; t++) {
            int s2 = (tries == f) ? t : (int)(rnd() % f);
            uint8_t save[MAXCELL]; int ad[MAXCELL];
            for (int i = 0; i < sol_n[s2]; i++) { ad[i] = sol_addr[s2][i]; save[i] = prog[ad[i]]; }
            apply_changes(ad, sol_byte[s2], sol_n[s2]);
            int d = cur_score - base0;
            apply_changes(ad, save, sol_n[s2]);
            if (d > bd) { bd = d; bi = s2; }
        }
        if (bi >= 0 && bd > 0) apply_changes(sol_addr[bi], sol_byte[bi], sol_n[bi]);
    }
    return cur_score;
}

/* ---- directed coordinate sweep over the shared cells ---- */
static uint8_t snap[M];
static void take_snap(void) { memcpy(snap, prog, N); }
static void restore_snap(void) {
    for (int a = 0; a < N; a++) if (prog[a] != snap[a]) { prog[a] = snap[a]; mem[a] = snap[a]; }
    for (int a = 0; a < PROLEN - 1; a++) mem[a] = X2[prog[a]];
    full_resim();
}
static int repair_pass(int rounds) {
    for (int k = 0; k < rounds; k++) {
        int cand[256], nc = 0;
        for (int b = 0; b < 256; b++) if (!solved[b]) cand[nc++] = b;
        if (!nc) break;
        try_input(cand[rnd() % nc], 0.0, 0);
    }
    return cur_score;
}


/* ---- -map: how many inputs touch each address (the contested surface) ---- */
static void dump_map(int lo, int hi) {
    for (int a = lo; a <= hi && a < N; a++) {
        int n = 0;
        for (int w = 0; w < 4; w++) n += __builtin_popcountll(own[a][w]);
        if (n) printf("%d %d %s\n", a, n, is_fixed(a) ? "FIXED" : "");
    }
}

/* ---- -need B: exhaustive DFS for input B with a wider mutable set; report
 * which cells OUTSIDE B's own block each witness needs to change. ---- */
static void need(int b, int lo, int hi) {
    int cells[MAXCELL], nc = 0;
    for (int a = 9 * b + 1; a <= 9 * b + span && a < N; a++) if (!is_fixed(a)) cells[nc++] = a;
    int ownlo = 9 * b + 1, ownhi = 9 * b + span;
    for (int a = lo; a <= hi && nc < MAXCELL && a < N; a++)
        if (!is_fixed(a) && (a < ownlo || a > ownhi)) cells[nc++] = a;
    int f = solve_input(b, cells, nc, stepcap, feas_nodes);
    printf("b=%d witnesses=%d nodes=%ld %s\n", b, f, dfs_nodes,
           dfs_nodes > feas_nodes ? "CAPPED" : "exhaustive");
    for (int t = 0; t < f; t++) {
        printf("  w%d:", t);
        for (int i = 0; i < sol_n[t]; i++) {
            int a = sol_addr[t][i];
            int outside = (a < ownlo || a > ownhi);
            if (sol_byte[t][i] != prog[a] || outside)
                printf(" %d%s=%d%s", a, outside ? "*" : "", sol_byte[t][i],
                       sol_byte[t][i] == prog[a] ? "(same)" : "");
        }
        printf("\n");
    }
}

/* ---- -tape: coordinate sweep over the shared tape, exhaustive repair ----
 * hero1's would_try_next #1.  The previous sweep used a random repair_pass(120),
 * which samples witnesses; a shared-cell change breaks 10-40 inputs at once and
 * only an exact per-input search says whether they can all be put back. */
static uint8_t tsnap[M];
static void adopt(const uint8_t *p) {
    memcpy(prog, p, N);
    for (int a = 0; a < N; a++) mem[a] = prog[a];
    for (int a = N; a < M; a++) mem[a] = crazyw(mem[a - 1], mem[a - 2]);
    for (int a = 0; a < PROLEN - 1; a++) mem[a] = X2[prog[a]];
    full_resim();
}
static void tape_sweep(int lo, int hi, int seconds, const char *out) {
    time_t t0 = time(NULL);
    static uint8_t bestprog[M];
    assemble_fix(6);
    memcpy(bestprog, prog, N);
    int best = cur_score;
    fprintf(stderr, "tape start %d/256 window [%d,%d]\n", cur_score, lo, hi);
    int pass = 0;
    while (time(NULL) - t0 < seconds) {
        pass++;
        int improved = 0;
        /* randomised cell order so parallel instances explore differently */
        int order[M], no = 0;
        for (int a = lo; a <= hi && a < N; a++) if (!is_fixed(a)) order[no++] = a;
        if (hi >= N - 3) { } else { order[no++] = N - 2; order[no++] = N - 1; }
        for (int i = no - 1; i > 0; i--) { int j = (int)(rnd() % (i + 1)); int t = order[i]; order[i] = order[j]; order[j] = t; }
        for (int oi = 0; oi < no; oi++) {
            if (time(NULL) - t0 >= seconds) break;
            int a = order[oi];
            memcpy(tsnap, prog, N);
            int base = cur_score, bsc = -1;
            static uint8_t bp[M];
            for (int k = 0; k < 8; k++) {
                int nb = byte_for(CODES[k], a);
                int ad[1] = {a}; uint8_t bb[1] = {(uint8_t)nb};
                apply_changes(ad, bb, 1);
                assemble_fix(4);
                reroll_pass(lo, hi);
                assemble_fix(3);
                if (cur_score > bsc) { bsc = cur_score; memcpy(bp, prog, N); }
                adopt(tsnap);
            }
            if (bsc > base) { adopt(bp); improved = 1;
                fprintf(stderr, "  [%3lds] tape cell %d -> %d/256\n", (long)(time(NULL)-t0), a, cur_score); }
            if (cur_score > best) { best = cur_score; memcpy(bestprog, prog, N);
                write_prog_to(out); }
        }
        fprintf(stderr, "tape pass %d: %d/256 (best %d)\n", pass, cur_score, best);
        if (!improved) {
            /* kick: randomise a few shared cells at once, repair, keep if not much worse */
            for (int j = 0; j < 3; j++) {
                int a; do { a = lo + (int)(rnd() % (hi - lo + 1)); } while (is_fixed(a) || a >= N);
                int ad[1] = {a}; uint8_t bb[1] = {(uint8_t)byte_for(CODES[rnd() % 8], a)};
                apply_changes(ad, bb, 1);
            }
            assemble_fix(6); reroll_pass(lo, hi); assemble_fix(4);
            if (cur_score < best - 3) adopt(bestprog);
        }
    }
    adopt(bestprog);
    fprintf(stderr, "tape final %d/256\n", cur_score);
    printf("wrong:");
    for (int b = 0; b < 256; b++) if (!solved[b]) printf(" %d", b);
    printf("\n");
    write_prog_to(out);
}

/* ---- -force B: witness-driven coordinated moves ----
 * Single-cell coordinate descent is at a local optimum (a full sweep of the
 * shared window with exhaustive repair moves nothing).  What the -need probes
 * show is that the stuck inputs need SEVERAL shared cells set together --
 * b=8 and b=9 both want m[74]=118 and m[75]=117, which no single-cell move can
 * reach.  So: enumerate witnesses for the stuck input over its own block PLUS
 * the shared window, apply the whole witness as one move (which makes b solved
 * by construction), and let the exhaustive assembly repair pay for the damage. */
static void force(int b, int lo, int hi, int seconds, const char *out, int sample) {
    time_t t0 = time(NULL);
    static uint8_t base[M], bestprog[M];
    assemble_fix(6);
    memcpy(base, prog, N); memcpy(bestprog, prog, N);
    int best = cur_score, base_score = cur_score;
    int cells[MAXCELL], nc = 0;
    int ownlo = 9 * b + 1, ownhi = 9 * b + span;
    for (int a = ownlo; a <= ownhi && a < N; a++) if (!is_fixed(a)) cells[nc++] = a;
    for (int a = lo; a <= hi && nc < MAXCELL && a < N; a++)
        if (!is_fixed(a) && (a < ownlo || a > ownhi)) cells[nc++] = a;
    int f = solve_input(b, cells, nc, stepcap, feas_nodes);
    fprintf(stderr, "force b=%d: %d witnesses (nodes %ld%s) base %d/256\n",
            b, f, dfs_nodes, dfs_nodes > feas_nodes ? " CAPPED" : "", base_score);
    if (!f) { printf("force b=%d: NO WITNESS\n", b); return; }
    /* copy witnesses out -- solve_input's buffers get reused by assemble_fix */
    static int wn[MAXSOL], wa[MAXSOL][MAXCELL]; static uint8_t wb[MAXSOL][MAXCELL];
    for (int t = 0; t < f; t++) { wn[t] = sol_n[t];
        for (int i = 0; i < sol_n[t]; i++) { wa[t][i] = sol_addr[t][i]; wb[t][i] = sol_byte[t][i]; } }
    int tried = 0;
    for (int t = 0; t < f && tried < sample; t++, tried++) {
        if (time(NULL) - t0 >= seconds) break;
        int idx = (f <= sample) ? t : (int)(rnd() % f);
        adopt(base);
        apply_changes(wa[idx], wb[idx], wn[idx]);
        assemble_fix(6); reroll_pass(34, hi); assemble_fix(4);
        if (cur_score > best) {
            best = cur_score; memcpy(bestprog, prog, N); write_prog_to(out);
            fprintf(stderr, "  force b=%d w%d -> %d/256  wrong:", b, idx, cur_score);
            for (int x = 0; x < 256; x++) if (!solved[x]) fprintf(stderr, " %d", x);
            fprintf(stderr, "\n");
        }
    }
    adopt(bestprog);
    fprintf(stderr, "force b=%d final %d/256 (%d witnesses tried)\n", b, cur_score, tried);
    printf("wrong:");
    for (int x = 0; x < 256; x++) if (!solved[x]) printf(" %d", x);
    printf("\n");
    write_prog_to(out);
}

/* ---- -hunt: compounding witness-driven search over ALL unsolved inputs ----
 * Two fixes over -force.  (1) Witnesses are tried LEAST-DISRUPTIVE FIRST:
 * b=255's wide witnesses each rewrite ~25 shared cells, which breaks 40 other
 * inputs and costs ~60s of repair for one probe.  Sorting by the number of
 * cells that actually differ from the current tape puts the cheap, plausible
 * moves first.  (2) Improvements are adopted as the new base, so gains compound
 * within one run instead of each probe restarting from the seed. */
static int wcnt[MAXSOL], word_[MAXSOL];
static int cmp_w(const void *x, const void *y) {
    int a = *(const int *)x, b2 = *(const int *)y;
    return wcnt[a] - wcnt[b2];
}
static void hunt(int lo, int hi, int seconds, const char *out, int sample) {
    time_t t0 = time(NULL);
    static uint8_t bestprog[M], base[M];
    assemble_fix(6);
    memcpy(bestprog, prog, N);
    int best = cur_score;
    fprintf(stderr, "hunt start %d/256 window [%d,%d] span=%d steps=%d\n", best, lo, hi, span, stepcap);
    static int wn[MAXSOL], wa[MAXSOL][MAXCELL]; static uint8_t wb[MAXSOL][MAXCELL];
    while (time(NULL) - t0 < seconds) {
        int targets[256], nt = 0;
        for (int b = 0; b < 256; b++) if (!solved[b]) targets[nt++] = b;
        if (!nt) break;
        for (int i = nt - 1; i > 0; i--) { int j = (int)(rnd() % (i + 1)); int t = targets[i]; targets[i] = targets[j]; targets[j] = t; }
        int progressed = 0;
        for (int ti = 0; ti < nt; ti++) {
            if (time(NULL) - t0 >= seconds) break;
            int b = targets[ti];
            memcpy(base, prog, N);
            int cells[MAXCELL], nc = 0;
            int ownlo = 9 * b + 1, ownhi = 9 * b + span;
            for (int a = ownlo; a <= ownhi && a < N; a++) if (!is_fixed(a)) cells[nc++] = a;
            for (int a = lo; a <= hi && nc < MAXCELL && a < N; a++)
                if (!is_fixed(a) && (a < ownlo || a > ownhi)) cells[nc++] = a;
            if (!nc) continue;
            int f = solve_input(b, cells, nc, stepcap, feas_nodes);
            if (!f) continue;
            for (int t = 0; t < f; t++) { wn[t] = sol_n[t]; wcnt[t] = 0; word_[t] = t;
                for (int i = 0; i < sol_n[t]; i++) { wa[t][i] = sol_addr[t][i]; wb[t][i] = sol_byte[t][i];
                    if (sol_byte[t][i] != prog[sol_addr[t][i]]) wcnt[t]++; } }
            qsort(word_, f, sizeof(int), cmp_w);
            int lim = f < sample ? f : sample;
            for (int t = 0; t < lim; t++) {
                if (time(NULL) - t0 >= seconds) break;
                int idx = word_[t];
                apply_changes(wa[idx], wb[idx], wn[idx]);
                assemble_fix(3);
                if (cur_score > best) {
                    best = cur_score; memcpy(bestprog, prog, N); memcpy(base, prog, N);
                    write_prog_to(out); progressed = 1;
                    fprintf(stderr, "  [%4lds] hunt b=%d w%d(%d chg) -> %d/256  wrong:",
                            (long)(time(NULL) - t0), b, idx, wcnt[idx], cur_score);
                    for (int x = 0; x < 256; x++) if (!solved[x]) fprintf(stderr, " %d", x);
                    fprintf(stderr, "\n");
                    break;
                }
                adopt(base);
            }
        }
        if (!progressed) {
            /* lateral kick: accept an equal-score witness for a random unsolved
             * input, so the next round searches from a different tape */
            int b = targets[rnd() % nt];
            memcpy(base, prog, N);
            int cells[MAXCELL], nc = 0;
            int ownlo = 9 * b + 1, ownhi = 9 * b + span;
            for (int a = ownlo; a <= ownhi && a < N; a++) if (!is_fixed(a)) cells[nc++] = a;
            for (int a = lo; a <= hi && nc < MAXCELL && a < N; a++)
                if (!is_fixed(a) && (a < ownlo || a > ownhi)) cells[nc++] = a;
            int f = nc ? solve_input(b, cells, nc, stepcap, feas_nodes) : 0;
            int done = 0;
            for (int t = 0; t < f && t < 64 && !done; t++) {
                int idx = (int)(rnd() % f);
                for (int i = 0; i < sol_n[idx]; i++) { wa[idx][i] = sol_addr[idx][i]; wb[idx][i] = sol_byte[idx][i]; }
                apply_changes(wa[idx], wb[idx], sol_n[idx]);
                assemble_fix(3); reroll_pass(lo, hi); assemble_fix(2);
                if (cur_score >= best - 1) done = 1; else adopt(base);
            }
            if (!done) adopt(bestprog);
        }
    }
    adopt(bestprog);
    fprintf(stderr, "hunt final %d/256\n", cur_score);
    printf("wrong:");
    for (int b = 0; b < 256; b++) if (!solved[b]) printf(" %d", b);
    printf("\n");
    write_prog_to(out);
}

int main(int argc, char **argv) {
    for (int v = 33; v <= 126; v++) X2[v] = (uint8_t)XLAT2[v - 33];
    const char *seed = NULL, *out = "cand.mal";
    int seconds = 60, mode = 0, hot_hi = 140, hot_lo2 = 33, sample_n = 400;
    double T0 = 0.7;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-s")) seed = argv[++i];
        else if (!strcmp(argv[i], "-o")) out = argv[++i];
        else if (!strcmp(argv[i], "-t")) seconds = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-N")) N = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-span")) span = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-steps")) stepcap = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-T")) T0 = atof(argv[++i]);
        else if (!strcmp(argv[i], "-nodes")) nodecap = atol(argv[++i]);
        else if (!strcmp(argv[i], "-feas")) mode = 1;
        else if (!strcmp(argv[i], "-only")) only_b = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-fnodes")) feas_nodes = atol(argv[++i]);
        else if (!strcmp(argv[i], "-sweep")) mode = 2;
        else if (!strcmp(argv[i], "-assemble")) mode = 3;
        else if (!strcmp(argv[i], "-hot")) hot_hi = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-map")) mode = 4;
        else if (!strcmp(argv[i], "-need")) { mode = 5; only_b = atoi(argv[++i]); }
        else if (!strcmp(argv[i], "-lo")) hot_lo2 = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-tape")) mode = 6;
        else if (!strcmp(argv[i], "-force")) { mode = 7; only_b = atoi(argv[++i]); }
        else if (!strcmp(argv[i], "-hunt")) mode = 8;
        else if (!strcmp(argv[i], "-sample")) sample_n = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-wit")) wit_cap = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-anodes")) asm_nodes = atol(argv[++i]);
        else if (!strcmp(argv[i], "-r")) rng_s = strtoull(argv[++i], 0, 10) * 2654435761u + 12345;
    }
    time_t t0_sweep = time(NULL);
    mark_fixed();
    init_prog(seed);
    rebuild_all();
    full_resim();
    fprintf(stderr, "start %d/256  N=%d span=%d steps=%d T=%.2f\n", cur_score, N, span, stepcap, T0);
    if (mode == 1) { feasibility(hot_lo2, hot_hi); return 0; }
    if (mode == 4) { dump_map(0, N - 1); return 0; }
    if (mode == 5) { need(only_b, hot_lo2, hot_hi); return 0; }
    if (mode == 6) { tape_sweep(hot_lo2, hot_hi, seconds, out); return 0; }
    if (mode == 7) { force(only_b, hot_lo2, hot_hi, seconds, out, sample_n); return 0; }
    if (mode == 8) { hunt(hot_lo2, hot_hi, seconds, out, sample_n); return 0; }
    if (mode == 3) {
        /* assembly pass: exhaustive block-local search per input, applied
         * whenever it does not cost anything globally.  Blocks above ~163 are
         * private, so most of these compose without interacting at all. */
        for (int pass = 0; pass < 4; pass++) {
            int before = cur_score;
            for (int b = 0; b < 256; b++) {
                if (solved[b]) continue;
                int cells[MAXCELL], nc = 0;
                for (int a = 9 * b + 1; a <= 9 * b + span && a < N; a++)
                    if (!is_fixed(a)) cells[nc++] = a;
                if (!nc) continue;
                int f = solve_input(b, cells, nc, stepcap, feas_nodes);
                if (!f) continue;
                int bd = -999, bi = -1, base0 = cur_score;
                for (int t = 0; t < f; t++) {
                    uint8_t save[MAXCELL]; int ad[MAXCELL];
                    for (int i = 0; i < sol_n[t]; i++) { ad[i] = sol_addr[t][i]; save[i] = prog[ad[i]]; }
                    apply_changes(ad, sol_byte[t], sol_n[t]);
                    int d = cur_score - base0;
                    apply_changes(ad, save, sol_n[t]);
                    if (d > bd) { bd = d; bi = t; }
                }
                if (bi >= 0 && bd >= 0) {
                    apply_changes(sol_addr[bi], sol_byte[bi], sol_n[bi]);
                    fprintf(stderr, "  assemble b=%d (+%d) -> %d/256\n", b, bd, cur_score);
                }
            }
            fprintf(stderr, "assemble pass %d: %d/256\n", pass, cur_score);
            if (cur_score == before) break;
        }
        printf("wrong:");
        for (int b = 0; b < 256; b++) if (!solved[b]) printf(" %d", b);
        printf("\n");
        write_prog(out);
        return 0;
    }
    if (mode == 2) {
        int improved = 1, pass = 0;
        while (improved && time(NULL) - t0_sweep < seconds) {
            improved = 0; pass++;
            for (int a = 33; a <= hot_hi; a++) {
                if (is_fixed(a) || a >= N) continue;
                take_snap();
                int base = cur_score, bestsc = -1, bestk = -1;
                uint8_t bestp[M]; int have = 0;
                for (int k = 0; k < 8; k++) {
                    int nb = byte_for(CODES[k], a);
                    if (nb == snap[a] && k) {}
                    int ad[1] = {a}; uint8_t bb[1] = {(uint8_t)nb};
                    apply_changes(ad, bb, 1);
                    repair_pass(120);
                    if (cur_score > bestsc) { bestsc = cur_score; bestk = k; memcpy(bestp, prog, N); have = 1; }
                    restore_snap();
                }
                if (have && bestsc > base) {
                    memcpy(prog, bestp, N);
                    for (int x = 0; x < N; x++) mem[x] = prog[x];
                    for (int x = 0; x < PROLEN - 1; x++) mem[x] = X2[prog[x]];
                    full_resim();
                    improved = 1;
                    fprintf(stderr, "  sweep pass %d cell %d -> %d/256\n", pass, a, cur_score);
                }
            }
        }
        fprintf(stderr, "sweep final %d/256\n", cur_score);
        printf("wrong:");
        for (int b = 0; b < 256; b++) if (!solved[b]) printf(" %d", b);
        printf("\n");
        write_prog(out);
        return 0;
    }

    static uint8_t bestprog[M];
    memcpy(bestprog, prog, N);
    int best = cur_score;
    time_t t0 = t0_sweep;
    long rounds = 0;
    long since_best = 0;

    while (time(NULL) - t0 < seconds) {
        rounds++;
        double frac = (double)(time(NULL) - t0) / (double)seconds;
        double T = T0 * (1.0 - 0.85 * frac);
        int r = (int)(rnd() % 100);
        if (r < 55) {
            /* repair: pick an unsolved input */
            int cand[256], nc = 0;
            for (int b = 0; b < 256; b++) if (!solved[b]) cand[nc++] = b;
            if (!nc) break;
            try_input(cand[rnd() % nc], T, 0);
        } else if (r < 85) {
            /* reroll: pick a solved input and take a different solution */
            int b = (int)(rnd() % 256);
            try_input(b, T, 0);
        } else {
            /* jitter: randomise a shared cell, then repair whoever broke */
            int a;
            /* the crazy-filled tail past the program end is read by real
             * solutions (e.g. m[19713]); it is a function of the last two
             * program bytes, so those are design variables too. */
            if (rnd() % 8 == 0) a = N - 2 + (int)(rnd() % 2);
            else do { a = 33 + (int)(rnd() % 160); } while (is_fixed(a) || a >= N);
            uint8_t nb = (uint8_t)byte_for(CODES[rnd() % 8], a);
            int ad[1] = {a}; uint8_t bb[1] = {nb};
            uint8_t old = prog[a];
            int before = cur_score;
            apply_changes(ad, bb, 1);
            for (int k = 0; k < 6; k++) {
                int cand[256], nc = 0;
                for (int b = 0; b < 256; b++) if (!solved[b]) cand[nc++] = b;
                if (!nc) break;
                try_input(cand[rnd() % nc], T, 0);
            }
            if (cur_score < before && rnd01() > exp((double)(cur_score - before) / (T + 1e-9))) {
                uint8_t ob[1] = {old};
                apply_changes(ad, ob, 1);
            }
        }
        if (cur_score > best) {
            best = cur_score;
            memcpy(bestprog, prog, N);
            since_best = 0;
            fprintf(stderr, "[%3lds] best %d/256 (round %ld)\n", (long)(time(NULL) - t0), best, rounds);
        } else if (++since_best > 30000) {
            memcpy(prog, bestprog, N); rebuild_all(); full_resim(); since_best = 0;
        }
    }
    memcpy(prog, bestprog, N);
    rebuild_all();
    full_resim();
    fprintf(stderr, "final %d/256 after %ld rounds\n", cur_score, rounds);
    printf("wrong:");
    for (int b = 0; b < 256; b++) if (!solved[b]) printf(" %d", b);
    printf("\n");
    write_prog(out);
    return 0;
}
