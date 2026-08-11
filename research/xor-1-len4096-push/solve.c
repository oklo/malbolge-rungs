/* Assembler for L2.R0d.xor-1-len4096: exhaustive per-input block search for L2.R0d.xor-1-len4096.
 *
 * Architecture (see build.py): 33 bytes of prologue leave m[72] = 9b, then a JMP
 * at address 32 sets c = 9b, so input b executes its own nine-byte block at
 * 9b+1..9b+9.  Every one of those nine cells may hold any of the eight legal
 * instructions, so each input chooses its own straight-line program -- including
 * ROT and MOVD, the two instructions that let the accumulator's top five trits
 * be steered at all.
 *
 * For each input this does a full DFS over the 8^9 instruction assignments with
 * pruning (crash, leaving the block, output limit) and reports the exact set of
 * output bytes the block can produce, plus a witness for the target b^0x51.
 *
 * Soundness detail: the block's cells are both code and potential operands.  The
 * DFS assigns them in execution order, so if a step reads a block cell at an
 * index the DFS has not decided yet, that index is pinned to the value actually
 * read (the base program's filler byte) for the rest of the branch.
 *
 * Build:  cc -O2 -o search search.c
 * Usage:  ./search <base.mal> [maskhex]
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#define M 59049
static const char *XLAT2 =
    "5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";
static const int CODES[8] = {4, 5, 23, 39, 40, 62, 68, 81};
static const int CT[3][3] = {{1, 0, 0}, {1, 0, 2}, {2, 2, 1}};
static int POW3[11];

static uint16_t base[M];      /* memory image of the base program */
static int proglen;
static uint8_t progb[M];      /* base program bytes */

static uint16_t mem[M];
static int A, C, D, ii, outn, outbyte;

/* undo log */
typedef struct { int addr; uint16_t old; } Undo;

static int crazy(int a, int d) {
    int r = 0;
    for (int i = 0; i < 10; i++) {
        r += CT[d % 3][a % 3] * POW3[i];
        a /= 3; d /= 3;
    }
    return r;
}
static int rotr(int w) { return w / 3 + (w % 3) * 19683; }
static int code_of(int w, int a) { return (w + a) % 94; }
static int byte_for(int code, int a) {
    int v = ((code - a) % 94 + 94) % 94;
    while (v < 33) v += 94;
    return v <= 126 ? v : -1;
}

/* ---- reachability bookkeeping ---- */
static int blockbase;         /* 9b+1 */
static int pinned[10];        /* -1 = free, else forced byte */
static int fixed_cell[10];    /* 1 if the cell is prologue/forced in the base program */
static int assigned[10];      /* 1 once the cell has been executed: its value is fixed by encipherment */
static unsigned char reach[256];
#define MAXDEPTH 40
static int witness[MAXDEPTH + 2], wlen, found;
static int curbyte[10], solbyte[10];
static int target;
static long nodes;
/* strict mode: a block may only READ cells no other input's block can change --
 * the prologue (0..32), the six forced data cells, and its own nine cells.
 * Solutions found under it are independent, so assembling them cannot interact. */
static int strict = 0;
static int is_safe(int a) {
    if (a < 33) return 1;
    if (a == 40 || a == 62 || a == 71 || a == 72 || a == 73 || a == 123) return 1;
    return a >= blockbase && a <= blockbase + 8;
}

/* returns 1 if the run halted with a single output byte */
static int step_once(Undo *log, int *nlog) {
    int w = mem[C];
    if (w < 33 || w > 126) return -1;             /* invalid runtime instruction */
    int code = code_of(w, C);
    if (strict && (code == 4 || code == 39 || code == 40 || code == 62) && !is_safe(D)) return -1;
    switch (code) {
        case 4: C = mem[D]; break;
        case 5:
            if (outn >= 1) return -1;             /* output limit is 1 on this rung */
            outbyte = A % 256; outn++;
            break;
        case 23: A = 59048; break;                /* input already consumed */
        case 39: {
            int v = rotr(mem[D]);
            log[*nlog].addr = D; log[*nlog].old = mem[D]; (*nlog)++;
            mem[D] = v; A = v; break;
        }
        case 40: D = mem[D]; break;
        case 62: {
            int v = crazy(A, mem[D]);
            log[*nlog].addr = D; log[*nlog].old = mem[D]; (*nlog)++;
            mem[D] = v; A = v; break;
        }
        case 81: return 1;                        /* halt, no encipher, no increment */
        default: break;
    }
    int wc = mem[C];
    if (wc < 33 || wc > 126) return -1;
    log[*nlog].addr = C; log[*nlog].old = mem[C]; (*nlog)++;
    mem[C] = (uint16_t)(unsigned char)XLAT2[wc - 33];
    C = (C + 1) % M;
    D = (D + 1) % M;
    return 0;
}

/* record which block cells a step reads, so read-ahead pins them */
static void note_reads(int code, Undo *log, int *nlog) {
    (void)log; (void)nlog;
    if (code == 4 || code == 40 || code == 39 || code == 62) {
        int idx = D - blockbase;
        if (idx >= 0 && idx < 9) {
            if (pinned[idx] < 0) pinned[idx] = mem[D] <= 126 ? mem[D] : 0x7fff;
        }
    }
}

static void dfs(int depth) {
    nodes++;
    if (found) return;
    if (depth > MAXDEPTH) return;                     /* a JMP can loop inside the block */
    if (C < blockbase || C > blockbase + 8) return;   /* left the block */
    int idx = C - blockbase;
    int cand[8], ncand = 0;
    if (assigned[idx]) {
        cand[ncand++] = mem[C];                       /* re-executed: enciphered value, no choice */
    } else if (fixed_cell[idx]) {
        cand[ncand++] = mem[C];   /* runtime value: cells 71/72 were rewritten by the prologue */
    } else if (pinned[idx] >= 0 && pinned[idx] != 0x7fff) {
        cand[ncand++] = pinned[idx];
    } else if (pinned[idx] == 0x7fff) {
        return;                                        /* read-ahead saw a non-byte */
    } else {
        for (int k = 0; k < 8; k++) {
            int v = byte_for(CODES[k], C);
            if (v > 0) cand[ncand++] = v;
        }
    }
    int sA = A, sC = C, sD = D, sOutn = outn, sOut = outbyte;
    int spin[10]; memcpy(spin, pinned, sizeof spin);
    int sass = assigned[idx];
    for (int t = 0; t < ncand && !found; t++) {
        Undo log[8]; int nlog = 0;
        log[nlog].addr = C; log[nlog].old = mem[C]; nlog++;
        mem[C] = (uint16_t)cand[t];
        int scur = curbyte[idx];
        if (!assigned[idx] && !fixed_cell[idx]) curbyte[idx] = cand[t];
        assigned[idx] = 1;
        int code = code_of(cand[t], C);
        witness[depth] = code;
        note_reads(code, log, &nlog);
        int r = step_once(log, &nlog);
        if (r == 1) {
            if (outn == 1) {
                reach[outbyte] = 1;
                if (outbyte == target) {
                    found = 1; wlen = depth + 1;
                    memcpy(solbyte, curbyte, sizeof solbyte);
                }
            }
        } else if (r == 0) {
            dfs(depth + 1);
        }
        while (nlog > 0) { nlog--; mem[log[nlog].addr] = log[nlog].old; }
        A = sA; C = sC; D = sD; outn = sOutn; outbyte = sOut;
        memcpy(pinned, spin, sizeof spin);
        assigned[idx] = sass; curbyte[idx] = scur;
    }
}


/* ---- full-program simulation (mirrors the native VM) ---- */
static int simulate(int b, int *steps_out) {
    static uint16_t m2[M];
    memcpy(m2, base, sizeof(uint16_t) * M);
    int a = 0, c = 0, d = 0, ii2 = 0, on = 0, ob = -1;
    for (int st = 0; st < 2048; st++) {
        int w = m2[c];
        if (w < 33 || w > 126) { if (steps_out) *steps_out = st; return -2; }
        int code = code_of(w, c);
        if (code == 4) c = m2[d];
        else if (code == 5) { if (on >= 1) return -3; ob = a % 256; on++; }
        else if (code == 23) { a = (ii2++ == 0) ? b : 59048; }
        else if (code == 39) { m2[d] = rotr(m2[d]); a = m2[d]; }
        else if (code == 40) d = m2[d];
        else if (code == 62) { m2[d] = crazy(a, m2[d]); a = m2[d]; }
        else if (code == 81) { if (steps_out) *steps_out = st + 1; return on == 1 ? ob : -4; }
        int wc = m2[c];
        if (wc < 33 || wc > 126) return -2;
        m2[c] = (uint16_t)(unsigned char)XLAT2[wc - 33];
        c = (c + 1) % M; d = (d + 1) % M;
    }
    return -5;
}

static void refill(int from) {
    for (int i = from; i < M; i++) base[i] = (uint16_t)crazy(base[i - 1], base[i - 2]);
}

static int run_prologue(int b) {
    memcpy(mem, base, sizeof(uint16_t) * M);
    A = 0; C = 0; D = 0; outn = 0; outbyte = -1;
    for (int steps = 0; steps < 33; steps++) {
        int w = mem[C];
        if (w < 33 || w > 126) return 0;
        int code = code_of(w, C);
        if (code == 23) A = b;
        else if (code == 4) C = mem[D];
        else if (code == 39) { mem[D] = rotr(mem[D]); A = mem[D]; }
        else if (code == 40) D = mem[D];
        else if (code == 62) { mem[D] = crazy(A, mem[D]); A = mem[D]; }
        else if (code == 5 || code == 81) return 0;
        int wc = mem[C];
        if (wc < 33 || wc > 126) return 0;
        mem[C] = (uint16_t)(unsigned char)XLAT2[wc - 33];
        C = (C + 1) % M; D = (D + 1) % M;
    }
    return C == blockbase;
}

static int try_solve(int b, int mask) {
    blockbase = 9 * b + 1;
    if (!run_prologue(b)) return 0;
    target = b ^ mask;
    memset(reach, 0, sizeof reach);
    found = 0; wlen = 0;
    for (int i = 0; i < 10; i++) {
        pinned[i] = -1; assigned[i] = 0; curbyte[i] = -1; solbyte[i] = -1;
        int a = blockbase + i;
        fixed_cell[i] = (a < 33 || a == 40 || a == 62 || a == 71 || a == 72 || a == 73 || a == 123) ? 1 : 0;
    }
    dfs(0);
    if (!found) return 0;
    int lo = M;
    for (int i = 0; i < 9; i++) {
        if (solbyte[i] < 0) continue;
        int a = blockbase + i;
        progb[a] = (uint8_t)solbyte[i];
        base[a] = (uint16_t)solbyte[i];
        if (a < lo) lo = a;
    }
    if (lo >= proglen - 2) refill(proglen);
    return 1;
}

int main(int argc, char **argv) {
    POW3[0] = 1;
    for (int i = 1; i <= 10; i++) POW3[i] = POW3[i - 1] * 3;
    if (argc < 3) { fprintf(stderr, "usage: solve base.mal out.mal [maskhex] [iters]\n"); return 2; }
    int mask = argc > 3 ? (int)strtol(argv[3], NULL, 16) : 0x51;
    int iters = argc > 4 ? atoi(argv[4]) : 8;

    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror("open"); return 2; }
    proglen = (int)fread(progb, 1, M, f);
    fclose(f);
    while (proglen > 0 && (progb[proglen - 1] == '\n' || progb[proglen - 1] == ' ')) proglen--;
    for (int i = 0; i < proglen; i++) base[i] = progb[i];
    refill(proglen);

    int correct[256];
    /* ---- phase 1: independent (strict) solutions only ---- */
    strict = 1;
    int n1 = 0;
    for (int b = 0; b < 256; b++) n1 += try_solve(b, mask);
    int chk = 0;
    for (int b = 0; b < 256; b++) chk += (simulate(b, NULL) == (b ^ mask));
    printf("phase 1 (independent blocks): solved %d, verified %d/256\n", n1, chk);
    fflush(stdout);

    /* ---- phase 2: allow foreign reads, greedily, rolling back any regression ---- */
    strict = 0;
    for (int b = 0; b < 256; b++) correct[b] = (simulate(b, NULL) == (b ^ mask));
    int gained = 0;
    for (int pass = 0; pass < 3; pass++) {
        int g0 = gained;
        for (int b = 0; b < 256; b++) {
            if (correct[b]) continue;
            uint8_t save[9]; uint16_t saveb[9];
            for (int i = 0; i < 9; i++) { save[i] = progb[9 * b + 1 + i]; saveb[i] = base[9 * b + 1 + i]; }
            if (!try_solve(b, mask)) continue;
            int ok = 1;
            for (int x = 0; x < 256 && ok; x++)
                if (correct[x] && simulate(x, NULL) != (x ^ mask)) ok = 0;
            if (ok && simulate(b, NULL) == (b ^ mask)) { correct[b] = 1; gained++; }
            else {
                for (int i = 0; i < 9; i++) { progb[9 * b + 1 + i] = save[i]; base[9 * b + 1 + i] = saveb[i]; }
                if (9 * b + 9 >= proglen - 2) refill(proglen);
            }
        }
        printf("phase 2 pass %d: +%d\n", pass, gained - g0);
        fflush(stdout);
        if (gained == g0) break;
    }
    for (int it = 0; it < 0; it++) {
        int nfix = 0, ncorrect = 0;
        for (int b = 0; b < 256; b++) {
            int got = simulate(b, NULL);
            if (got == (b ^ mask)) { correct[b] = 1; ncorrect++; continue; }
            correct[b] = 0;
            if (try_solve(b, mask)) {
                nfix++;
                if (simulate(b, NULL) == (b ^ mask)) { correct[b] = 1; ncorrect++; }
            }
        }
        /* recount from scratch: writing one block can disturb another */
        ncorrect = 0;
        for (int b = 0; b < 256; b++) {
            correct[b] = (simulate(b, NULL) == (b ^ mask));
            ncorrect += correct[b];
        }
        printf("iter %d: repaired %d, correct %d/256\n", it, nfix, ncorrect);
        fflush(stdout);
        if (ncorrect == 256 || nfix == 0) break;
    }

    FILE *g = fopen(argv[2], "wb");
    fwrite(progb, 1, proglen, g);
    fclose(g);
    int ncorrect = 0;
    printf("wrong:");
    for (int b = 0; b < 256; b++) {
        int got = simulate(b, NULL);
        if (got == (b ^ mask)) ncorrect++;
        else printf(" %d(%d)", b, got);
    }
    printf("\nfinal %d/256 -> %s (%d bytes)\n", ncorrect, argv[2], proglen);
    return 0;
}
