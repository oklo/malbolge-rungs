/* Exhaustive per-input search over private CODE blocks for L2.R0d.xor-1-len4096.
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
static int assigned[10];
static int touched[10];   /* written by CRAZY/ROT during the run: its value is no longer ours to choose */      /* 1 once the cell has been executed: its value is fixed by encipherment */
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
            if (D >= blockbase && D < blockbase + 10) touched[D - blockbase] = 1;
            log[*nlog].addr = D; log[*nlog].old = mem[D]; (*nlog)++;
            mem[D] = v; A = v; break;
        }
        case 40: D = mem[D]; break;
        case 62: {
            int v = crazy(A, mem[D]);
            if (D >= blockbase && D < blockbase + 10) touched[D - blockbase] = 1;
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
    if (assigned[idx] || touched[idx]) {
        cand[ncand++] = mem[C];   /* already executed or written at runtime: no choice left */
    } else if (fixed_cell[idx]) {
        cand[ncand++] = mem[C];   /* runtime value: cells 71/72 were rewritten by the prologue */
    } else if (pinned[idx] >= 0 && pinned[idx] != 0x7fff) {
        cand[ncand++] = pinned[idx];
    } else if (pinned[idx] == 0x7fff) {
        return;                                        /* read-ahead saw a non-byte */
    } else {
        for (int k = 0; k < 8; k++) {
            /* IN is banned inside a block: the harness feeds a 32-byte hash, so a
             * second IN reads a byte that changes every epoch (crates/harness/src/
             * challenge.rs derives the input as a full Hash32 and expects
             * first_byte ^ 0x51).  A block that reads it is not a solution. */
            if (CODES[k] == 23) continue;
            int v = byte_for(CODES[k], C);
            if (v > 0) cand[ncand++] = v;
        }
    }
    int sA = A, sC = C, sD = D, sOutn = outn, sOut = outbyte;
    int spin[10]; memcpy(spin, pinned, sizeof spin);
    int stou[10]; memcpy(stou, touched, sizeof stou);
    int sass = assigned[idx];
    for (int t = 0; t < ncand && !found; t++) {
        Undo log[8]; int nlog = 0;
        log[nlog].addr = C; log[nlog].old = mem[C]; nlog++;
        mem[C] = (uint16_t)cand[t];
        int scur = curbyte[idx];
        /* only record cells that were a genuinely free choice: a runtime-written or
         * read-ahead-pinned cell's value is not ours to put back into the source. */
        if (!assigned[idx] && !fixed_cell[idx] && !touched[idx] && pinned[idx] < 0)
            curbyte[idx] = cand[t];
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
        memcpy(touched, stou, sizeof stou);
        assigned[idx] = sass; curbyte[idx] = scur;
    }
}

int main(int argc, char **argv) {
    POW3[0] = 1;
    for (int i = 1; i <= 10; i++) POW3[i] = POW3[i - 1] * 3;
    if (argc < 2) { fprintf(stderr, "usage: search base.mal [maskhex]\n"); return 2; }
    int mask = argc > 2 ? (int)strtol(argv[2], NULL, 16) : 0x51;

    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror("open"); return 2; }
    proglen = (int)fread(progb, 1, M, f);
    fclose(f);
    /* strip trailing whitespace */
    while (proglen > 0 && (progb[proglen - 1] == '\n' || progb[proglen - 1] == ' ')) proglen--;
    for (int i = 0; i < proglen; i++) {
        if (progb[i] < 33 || progb[i] > 126) { fprintf(stderr, "bad byte at %d\n", i); return 2; }
        int c = code_of(progb[i], i);
        int ok = 0; for (int k = 0; k < 8; k++) if (CODES[k] == c) ok = 1;
        if (!ok) { fprintf(stderr, "illegal source at %d\n", i); return 2; }
    }
    for (int i = 0; i < proglen; i++) base[i] = progb[i];
    for (int i = proglen; i < M; i++) base[i] = (uint16_t)crazy(base[i - 1], base[i - 2]);

    int solved = 0;
    long totnodes = 0;
    for (int b = 0; b < 256; b++) {
        memcpy(mem, base, sizeof(uint16_t) * M);
        A = 0; C = 0; D = 0; ii = 0; outn = 0; outbyte = -1;
        /* prologue: run until the dispatch JMP has landed us in the block */
        blockbase = 9 * b + 1;
        int ok = 1, steps = 0;
        while (steps < 33) {   /* the prologue is exactly cells 0..32 */
            int w = mem[C];
            if (w < 33 || w > 126) { ok = 0; break; }
            int code = code_of(w, C);
            if (code == 23) { A = b; }
            else if (code == 4) { C = mem[D]; }
            else if (code == 39) { mem[D] = rotr(mem[D]); A = mem[D]; }
            else if (code == 40) { D = mem[D]; }
            else if (code == 62) { mem[D] = crazy(A, mem[D]); A = mem[D]; }
            else if (code == 5) { ok = 0; break; }
            else if (code == 81) { ok = 0; break; }
            int wc = mem[C];
            if (wc < 33 || wc > 126) { ok = 0; break; }
            mem[C] = (uint16_t)(unsigned char)XLAT2[wc - 33];
            C = (C + 1) % M; D = (D + 1) % M; steps++;

        }
        if (!ok || C != blockbase) { printf("b=%3d DISPATCH-FAIL\n", b); continue; }

        target = b ^ mask;
        memset(reach, 0, sizeof reach);
        found = 0; wlen = 0;
        for (int i = 0; i < 10; i++) {
            pinned[i] = -1; assigned[i] = 0; touched[i] = 0; curbyte[i] = -1; solbyte[i] = -1;
            int a = blockbase + i;
            fixed_cell[i] = (a < 33 || a == 40 || a == 62 || a == 71 || a == 72 || a == 73 || a == 123) ? 1 : 0;
        }
        nodes = 0;
        dfs(0);
        totnodes += nodes;
        int nreach = 0;
        for (int i = 0; i < 256; i++) nreach += reach[i];
        printf("b=%3d target=%3d reach=%3d %s", b, target, nreach, found ? "HIT" : "miss");
        if (found) { printf(" witness="); for (int i = 0; i < wlen; i++) printf("%d,", witness[i]); }
        printf("\n");
        solved += found;
    }
    printf("solved %d/256   nodes=%ld\n", solved, totnodes);
    return 0;
}
