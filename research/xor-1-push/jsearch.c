/* Joint search over the shared code tape for L2.R0.xor-1 (stride-1 JMP dispatch).
 *
 * Architecture (research/xor-1-push/build.py):
 *   9-byte prologue, byte 8 = JMP off m[72] = b, so input b begins executing at
 *   c = b+1 with A = b and D = 73.  Cells 9..255 minus {40,62,71,72,73,123} are
 *   free; each holds one of the 8 loader-legal bytes at its address, and that one
 *   byte is simultaneously an instruction (for whichever inputs execute it) and an
 *   operand value (for whichever inputs' CRZ/MOVD/ROT read it).
 *
 * Unlike the stride-9 sibling rung there are no private blocks: cell a is input
 * a-1's first instruction, input a-2's second, ... and every input reads the same
 * operand stream m[73], m[74], ... at the same step index.  So this is one
 * constraint-satisfaction problem over ~241 cells with 256 constraints.
 *
 * Phases:
 *   -1 (mode=ind)  per-input DFS with every cell free: how many inputs are
 *                  individually reachable at all (an upper bound on any tape).
 *    0 (mode=solve) greedy assembly: repeatedly DFS an unsolved input against the
 *                  cells already committed, commit, re-simulate all 256, roll back
 *                  any commit that loses ground.
 *
 * Build: cc -O2 -o jsearch jsearch.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <math.h>

#define M 59049
#define NA 1024                 /* addresses modelled; runs never need more */
#define LPROG 256
#define MASK 0x51

static const char *XLAT2 =
    "5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";
static const int CODES[8] = {4, 5, 23, 39, 40, 62, 68, 81};
/* JMP OUT IN ROT MOVD CRZ NOP HLT */
static const int CT[3][3] = {{1, 0, 0}, {1, 0, 2}, {2, 2, 1}};
static int POW3[11];

static int crazy(int a, int d) {
    int r = 0;
    for (int i = 0; i < 10; i++) { r += CT[d % 3][a % 3] * POW3[i]; a /= 3; d /= 3; }
    return r;
}
static int rotr(int w) { return w / 3 + (w % 3) * 19683; }
static int code_of(int w, int a) { return (w + a) % 94; }
static int byte_for(int code, int a) {
    int v = ((code - a) % 94 + 94) % 94;
    while (v < 33) v += 94;
    return v <= 126 ? v : -1;
}
static int is_valid_code(int c) {
    for (int i = 0; i < 8; i++) if (CODES[i] == c) return 1;
    return 0;
}

/* ---------------- program layout ---------------- */
/* ARCH 0: prologue ends with JMP off m[72]=b  -> input b executes from b+1, D=73.
   ARCH 1: prologue ends with MOVD off m[72]=b  -> D = b+1 (private data window),
           then cell 9 is a JMP off m[b+1], so the ROUTING BYTE at b+1 sends input b
           to one of its 8 legal addresses (all in 34..127) as a shared code tail,
           while D keeps walking the private table b+2, b+3, ...  This is the
           "JMP off a table cell into one of eight tails" that the previous record
           on this rung named as its next measurement, with ROT allowed in the tail. */
static int ARCH = 0;
static int PROLOGUE[10] = {23, 40, 40, 40, 62, 62, 40, 40, 4, 0};
static int PLEN = 9;
static int DATA_A[6] = {40, 62, 71, 72, 73, 123};
static int DATA_V[6] = {122, 71, 121, 121, 61, 70};

static int pinned[LPROG];       /* 1 = not searchable */
static int gval[LPROG];         /* committed byte, or 0 if free+unassigned */
static int defbyte[LPROG];      /* byte used for unassigned cells when simulating */
static int legal[LPROG][8];     /* legal bytes at each address, indexed by CODES[] */
static uint16_t fillmem[NA];    /* addresses >= LPROG */

static void build_layout(int last2a, int last2b) {
    /* ARCH 2: cell 8 is MOVD (D = b+1, the private table) and cell 9 onward is
       FREE.  Picking NOP at 9.. reproduces the previous record's straight-line
       shape exactly; picking JMP at 9 routes input b to m[b+1] as a shared tail
       while D keeps walking its own table.  So ARCH 2 strictly contains the
       68/256 family and can be seeded from its program. */
    if (ARCH == 1) { PROLOGUE[8] = 40; PROLOGUE[9] = 4; PLEN = 10; }
    else if (ARCH == 2) { PROLOGUE[8] = 40; PLEN = 9; }
    else { PROLOGUE[8] = 4; PLEN = 9; }
    for (int a = 0; a < LPROG; a++) {
        pinned[a] = 0; gval[a] = 0;
        for (int i = 0; i < 8; i++) legal[a][i] = byte_for(CODES[i], a);
    }
    for (int a = 0; a < PLEN; a++) { pinned[a] = 1; gval[a] = byte_for(PROLOGUE[a], a); }
    for (int i = 0; i < 6; i++) { pinned[DATA_A[i]] = 1; gval[DATA_A[i]] = DATA_V[i]; }
    /* the crazy fill depends only on the last two bytes, so those are pinned */
    pinned[254] = 1; gval[254] = last2a;
    pinned[255] = 1; gval[255] = last2b;
    for (int a = 0; a < LPROG; a++)
        defbyte[a] = pinned[a] ? gval[a] : legal[a][6];   /* NOP by default */
    fillmem[LPROG - 1] = gval[255];
    fillmem[LPROG - 2] = gval[254];
    for (int a = LPROG; a < NA; a++)
        fillmem[a] = crazy(fillmem[a - 1], fillmem[a - 2]);
}

/* ---------------- plain simulator (scoring) ----------------
   smem is kept equal to the program image at all times; a run logs every write
   and rolls it back, so scoring a tape costs O(steps) instead of O(memory).   */
static uint16_t smem[NA];
static int simlog_a[512]; static uint16_t simlog_v[512]; static int simlog_n;
static int last_out;
static void smem_sync(void) {
    for (int a = 0; a < LPROG; a++) smem[a] = gval[a] ? gval[a] : defbyte[a];
    for (int a = LPROG; a < NA; a++) smem[a] = fillmem[a];
}
#define SW(A_, V_) do { simlog_a[simlog_n] = (A_); simlog_v[simlog_n] = smem[A_]; \
                        simlog_n++; smem[A_] = (V_); } while (0)

static int sim_ok(int b, int *steps_out) {
    last_out = -1; simlog_n = 0;
    int A = 0, C = 0, D = 0, ii = 0, outn = 0, ob = -1, res = 0;
    for (int step = 0; step < 120; step++) {
        if (C >= NA || D >= NA) break;
        int w = smem[C];
        if (w < 33 || w > 126) break;
        int code = code_of(w, C);
        if (!is_valid_code(code)) break;
        if (code == 4) { C = smem[D]; if (C < 0 || C >= NA) break; }
        else if (code == 5) { if (outn >= 1) break; ob = A % 256; outn++; }
        else if (code == 23) { if (ii == 0) { A = b; ii = 1; } else break; }
        else if (code == 39) { SW(D, rotr(smem[D])); A = smem[D]; }
        else if (code == 40) { D = smem[D]; if (D >= NA) break; }
        else if (code == 62) { SW(D, crazy(A, smem[D])); A = smem[D]; }
        else if (code == 81) {
            if (steps_out) *steps_out = step + 1;
            if (outn == 1) last_out = ob;
            res = (outn == 1 && ob == (b ^ MASK));
            break;
        }
        int wc = smem[C];
        if (wc < 33 || wc > 126) break;
        SW(C, (uint8_t)XLAT2[wc - 33]);
        C++; D++;
        if (simlog_n > 480) break;
    }
    while (simlog_n) { simlog_n--; smem[simlog_a[simlog_n]] = simlog_v[simlog_n]; }
    return res;
}

/* ---------------- DFS over free cells ---------------- */
static uint16_t mv[NA];
static uint8_t mk[NA];          /* value determined */
static uint8_t ec[NA];          /* pending XLAT2 applications for undetermined cells */

typedef struct { int kind; int addr; uint16_t oldv; uint8_t oldk, olde; } Undo;
static Undo ulog[512];
static int ulen;

static int newasg[64], newval[64], nnew;
static int best_nnew, best_asg[64], best_val[64];
static int found;
static int target, curb;
static long nodes, nodecap;
static int maxsteps, maxnew;
static int indep_mode;
static int solved[256];          /* 1 = ignore committed values, everything free */

static void setmem(int a, int v) {
    ulog[ulen].kind = 0; ulog[ulen].addr = a; ulog[ulen].oldv = mv[a];
    ulog[ulen].oldk = mk[a]; ulog[ulen].olde = ec[a]; ulen++;
    mv[a] = v; mk[a] = 1;
}
static void undo_to(int n) {
    while (ulen > n) {
        ulen--;
        int a = ulog[ulen].addr;
        mv[a] = ulog[ulen].oldv; mk[a] = ulog[ulen].oldk; ec[a] = ulog[ulen].olde;
    }
}

/* Resolve cell a to a concrete value.  Returns:
   >=0  value (already determined)
   -1   free: caller must branch over the 8 legal bytes                       */
static int peek(int a) {
    if (a >= LPROG) return fillmem[a];
    if (mk[a]) return mv[a];
    return -1;
}
static int enc_apply(int byte, int n) {
    for (int i = 0; i < n; i++) {
        if (byte < 33 || byte > 126) return -1;
        byte = (uint8_t)XLAT2[byte - 33];
    }
    return byte;
}

static int dfs(int A, int C, int D, int outn, int step);

/* choose a value for cell `a`, then continue via dfs; returns 1 if solved */
static int branch_and_go(int a, int A, int C, int D, int outn, int step) {
    int save = ulen, savn = nnew;
    for (int i = 0; i < 8; i++) {
        int by = legal[a][i];
        if (by < 0) continue;
        int v = enc_apply(by, ec[a]);
        if (v < 0) continue;
        setmem(a, v);
        newasg[nnew] = a; newval[nnew] = by; nnew++;
        if (dfs(A, C, D, outn, step)) return 1;
        undo_to(save); nnew = savn;
    }
    return 0;
}

static int dfs(int A, int C, int D, int outn, int step) {
    if (++nodes > nodecap) return 0;
    if (step >= maxsteps) return 0;
    if (C < 0 || C >= NA || D < 0 || D >= NA) return 0;
    if (nnew > maxnew) return 0;

    int w = peek(C);
    if (w < 0) {
        if (nnew >= maxnew) return 0;
        return branch_and_go(C, A, C, D, outn, step);
    }
    if (w < 33 || w > 126) return 0;
    int code = code_of(w, C);
    if (!is_valid_code(code)) return 0;

    int save = ulen, savn = nnew;
    int nA = A, nC = C, nD = D, nout = outn;

    if (code == 23) return 0;                       /* IN is banned: harness feeds 32 bytes */
    if (code == 5) {
        if (outn >= 1) return 0;
        if ((A % 256) != target) return 0;          /* the strong prune */
        nout = 1;
    } else if (code == 81) {
        if (outn != 1) return 0;
        /* success */
        if (nnew < best_nnew) {
            best_nnew = nnew;
            for (int i = 0; i < nnew; i++) { best_asg[i] = newasg[i]; best_val[i] = newval[i]; }
        }
        found = 1;
        return 1;
    } else if (code == 4 || code == 39 || code == 40 || code == 62) {
        int dv = peek(D);
        if (dv < 0) {
            if (nnew >= maxnew) return 0;
            return branch_and_go(D, A, C, D, outn, step);
        }
        if (code == 4) { nC = dv; if (nC < 0 || nC >= NA) return 0; }
        else if (code == 39) { int r = rotr(dv); setmem(D, r); nA = r; }
        else if (code == 40) { nD = dv; if (nD >= NA) return 0; }
        else { int r = crazy(A, dv); setmem(D, r); nA = r; }
    }
    /* encipher the executed cell (for JMP that is the cell we landed on) */
    int encaddr = (code == 4) ? nC : C;
    int ev = peek(encaddr);
    if (ev < 0) {
        /* jumped onto an undecided cell: it is enciphered before execution */
        if (encaddr < LPROG) { ulog[ulen].kind = 1; ulog[ulen].addr = encaddr;
            ulog[ulen].oldv = mv[encaddr]; ulog[ulen].oldk = mk[encaddr];
            ulog[ulen].olde = ec[encaddr]; ulen++; ec[encaddr]++; }
    } else {
        if (ev < 33 || ev > 126) return 0;
        setmem(encaddr, (uint8_t)XLAT2[ev - 33]);
    }
    int r = dfs(nA, encaddr + 1, nD + 1, nout, step + 1);
    if (r) return 1;
    undo_to(save); nnew = savn;
    return 0;
}

static void init_run(int b) {
    for (int a = 0; a < NA; a++) { mv[a] = 0; mk[a] = 0; ec[a] = 0; }
    for (int a = LPROG; a < NA; a++) { mv[a] = fillmem[a]; mk[a] = 1; }
    for (int a = 0; a < LPROG; a++) {
        if (pinned[a]) { mv[a] = gval[a]; mk[a] = 1; }
        else if (!indep_mode && gval[a]) { mv[a] = gval[a]; mk[a] = 1; }
    }
    /* prologue cells 0..7 have executed and been enciphered; cell 8 (the JMP)
       is enciphered by its own jump, i.e. only when the landing address is 8 */
    int nexec = (ARCH == 2) ? PLEN : PLEN - 1;
    for (int a = 0; a < nexec; a++) mv[a] = (uint8_t)XLAT2[gval[a] - 33];
    mv[71] = crazy(b, 121); mk[71] = 1;
    mv[72] = b;             mk[72] = 1;
    /* the JMP enciphers the cell it lands on (address b) before c becomes b+1 */
    if (ARCH == 0 && b < LPROG) {
        if (mk[b]) {
            if (mv[b] < 33 || mv[b] > 126) { mk[b] = 2; }   /* dead: caller checks */
            else mv[b] = (uint8_t)XLAT2[mv[b] - 33];
        } else ec[b]++;
    }
    ulen = 0; nnew = 0;
}

static int solve_input(int b, int cap, int msteps, int mnew) {
    if (ARCH == 0 && (b == 70 || b == 71)) return 0;
    target = b ^ MASK; curb = b;
    init_run(b);
    if (b < LPROG && mk[b] == 2) return 0;
    if (b + 1 >= NA) return 0;
    /* iterative deepening on FOOTPRINT: the joint phase needs the solution that
       pins the fewest shared cells, not the first one the DFS stumbles on. */
    nodecap = cap;
    for (int mn = 0; mn <= mnew; mn++) {
        init_run(b);
        nodes = 0; maxnew = mn; maxsteps = msteps;
        found = 0; best_nnew = 999;
        int ok = ARCH ? dfs(b, ARCH == 2 ? 9 : 9, b + 1, 0, 0) : dfs(b, b + 1, 73, 0, 0);
        if (ok) return 1;
    }
    return 0;
}


/* ---------------- simulated annealing over the whole tape ---------------- */
static uint64_t rs = 88172645463325252ULL;
static uint64_t rnd(void) { rs ^= rs << 13; rs ^= rs >> 7; rs ^= rs << 17; return rs; }

static int freelist[LPROG], nfree;
static int popcount8(int x) { int n = 0; while (x) { n += x & 1; x >>= 1; } return n; }

/* score = 1000*solved + 8*(halted with exactly one output) + bit agreement */
static long full_score(int *nsolved) {
    long s = 0; int n = 0;
    for (int b = 0; b < 256; b++) {
        int ok = sim_ok(b, NULL);
        solved[b] = ok;
        if (ok) { s += 1000; n++; }
        else if (last_out >= 0) s += 8 + (8 - popcount8(last_out ^ (b ^ MASK)));
    }
    if (nsolved) *nsolved = n;
    return s;
}

static void anneal(long iters, double t0, double t1) {
    smem_sync();
    int nsol; long cur = full_score(&nsol);
    long best = cur; int bestv[LPROG]; memcpy(bestv, gval, sizeof gval);
    int bestn = nsol;
    for (long it = 0; it < iters; it++) {
        double frac = (double)it / (double)iters;
        double T = t0 * pow(t1 / t0, frac);
        int a = freelist[rnd() % nfree];
        int old = gval[a];
        int nv = legal[a][rnd() % 8];
        if (nv < 0 || nv == old) continue;
        gval[a] = nv; smem[a] = nv;
        long s = full_score(&nsol);
        long d = s - cur;
        if (d >= 0 || exp((double)d / T) > (double)(rnd() % 1000000) / 1000000.0) {
            cur = s;
            if (s > best) { best = s; bestn = nsol; memcpy(bestv, gval, sizeof gval); }
        } else { gval[a] = old; smem[a] = old ? old : defbyte[a]; }
        if ((it % 200000) == 0)
            fprintf(stderr, "  it=%ld T=%.1f cur=%ld best=%ld (%d/256)\n", it, T, cur, best, bestn);
    }
    memcpy(gval, bestv, sizeof gval);
    smem_sync();
    full_score(&nsol);
    fprintf(stderr, "anneal done: %d/256\n", nsol);
}

/* DFS repair: try to fix one unsolved input using only cells nobody solved needs */
static int repair_pass(void) {
    int gained = 0, nsol;
    smem_sync();
    long cur = full_score(&nsol);
    for (int b = 255; b >= 0; b--) {
        if (solved[b]) continue;
        if (!solve_input(b, 2000000L, 12, 7)) continue;
        int savea[64], savev[64], nsv = best_nnew;
        for (int i = 0; i < nsv; i++) { savea[i] = best_asg[i]; savev[i] = gval[best_asg[i]]; }
        for (int i = 0; i < nsv; i++) gval[best_asg[i]] = best_val[i];
        smem_sync();
        long s = full_score(&nsol);
        if (s <= cur) { for (int i = 0; i < nsv; i++) gval[savea[i]] = savev[i]; smem_sync(); full_score(&nsol); }
        else { cur = s; gained++; }
    }
    return gained;
}

/* ---------------- driver ---------------- */
static int rescore(void) {
    int n = 0;
    for (int b = 0; b < 256; b++) { solved[b] = sim_ok(b, NULL); n += solved[b]; }
    return n;
}

int main(int argc, char **argv) {
    POW3[0] = 1; for (int i = 1; i <= 10; i++) POW3[i] = POW3[i - 1] * 3;
    const char *mode = argc > 1 ? argv[1] : "solve";
    { const char *e = getenv("ARCH"); if (e) ARCH = atoi(e); }
    int l2a = (argc > 3 && atoi(argv[2])) ? atoi(argv[2]) : byte_for(5, 254);
    int l2b = (argc > 3 && atoi(argv[3])) ? atoi(argv[3]) : byte_for(81, 255);
    build_layout(l2a, l2b);

    if (!strcmp(mode, "ind")) {
        indep_mode = 1;
        int n = 0, hist[64]; memset(hist, 0, sizeof hist);
        for (int b = 0; b < 256; b++) {
            int ok = solve_input(b, 40000000L, 14, 12);
            if (ok) { n++; hist[best_nnew]++; }
            else printf("unreachable %d\n", b);
        }
        printf("individually reachable: %d/256\n", n);
        for (int i = 0; i < 20; i++) if (hist[i]) printf("  needs %2d free cells: %d\n", i, hist[i]);
        return 0;
    }

    if (!strcmp(mode, "anneal")) {
        long iters = argc > 5 ? atol(argv[5]) : 4000000L;
        unsigned long seed = argc > 6 ? strtoul(argv[6], 0, 10) : 12345;
        rs = seed * 2862933555777941757ULL + 3037000493ULL;
        nfree = 0;
        for (int a = 0; a < LPROG; a++) if (!pinned[a]) freelist[nfree++] = a;
        const char *seed_f = getenv("SEED");
        if (seed_f) {
            FILE *sf = fopen(seed_f, "rb");
            unsigned char buf[LPROG];
            if (sf && fread(buf, 1, LPROG, sf) == LPROG)
                for (int a = 0; a < LPROG; a++) { if (!pinned[a]) gval[a] = buf[a]; }
            if (sf) fclose(sf);
            fprintf(stderr, "seeded from %s\n", seed_f);
        } else
            for (int a = 0; a < LPROG; a++) if (!pinned[a]) gval[a] = legal[a][rnd() % 8];
        smem_sync();
        for (int round = 0; round < 6; round++) {
            { const char *e0=getenv("T0"), *e1=getenv("T1");
              anneal(iters, e0?atof(e0):60.0, e1?atof(e1):1.5); }
            int g = repair_pass();
            int nsol; full_score(&nsol);
            fprintf(stderr, "round %d: repair +%d -> %d/256\n", round, g, nsol);
        }
        int nsol; smem_sync(); full_score(&nsol);
        FILE *g = fopen(argc > 4 ? argv[4] : "cand.mal", "wb");
        for (int a = 0; a < LPROG; a++) fputc(gval[a] ? gval[a] : defbyte[a], g);
        fclose(g);
        printf("final %d/256\n", nsol);
        for (int b = 0; b < 256; b++) if (!solved[b]) printf("miss %d\n", b);
        return 0;
    }

    /* greedy assembly with rollback */
    smem_sync();
    int cur = rescore();
    fprintf(stderr, "start %d/256\n", cur);
    int order[256];
    for (int i = 0; i < 256; i++) order[i] = i;
    for (int pass = 0; pass < 8; pass++) {
        int improved = 0;
        /* alternate direction each pass */
        for (int idx = 0; idx < 256; idx++) {
            int b = (pass % 2) ? order[idx] : order[255 - idx];
            if (solved[b]) continue;
            if (!solve_input(b, 3000000L, 12, 8)) continue;
            int savea[64], savev[64], nsv = best_nnew;
            for (int i = 0; i < nsv; i++) { savea[i] = best_asg[i]; savev[i] = gval[best_asg[i]]; }
            for (int i = 0; i < nsv; i++) gval[best_asg[i]] = best_val[i];
            smem_sync();
            int nn = rescore();
            if (nn <= cur) {
                for (int i = 0; i < nsv; i++) gval[savea[i]] = savev[i];
                smem_sync();
                rescore();
            } else { cur = nn; improved = 1; }
        }
        fprintf(stderr, "pass %d -> %d/256\n", pass, cur);
        if (!improved) break;
    }
    /* emit the program */
    FILE *f = fopen(argc > 4 ? argv[4] : "cand.mal", "wb");
    for (int a = 0; a < LPROG; a++) fputc(gval[a] ? gval[a] : defbyte[a], f);
    fclose(f);
    printf("final %d/256\n", cur);
    for (int b = 0; b < 256; b++) if (!solved[b]) printf("miss %d\n", b);
    return 0;
}
