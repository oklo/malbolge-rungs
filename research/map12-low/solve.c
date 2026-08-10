/* Exact table solver for L2.FM2l.xor51-map12-low.
 *
 * Architecture is the cov40/cov48 data-dispatch table (see
 * docs/attempts/2026-08-10-claude-cov48.md):
 *
 *     IN                       A = b
 *     CRZ W1, CRZ W2           A = b + K0        (parked in a cell)
 *     MOVD                     D = b + K0 + 1    (the input IS the index)
 *     CRZ x K                  A = crazy^K(b+K0, mem[b+K0+1 .. b+K0+K])
 *     OUT, HALT                out = A mod 256
 *
 * For a coverage rung you maximise how many of 256 inputs land on target; for
 * a finite map only the rung's twelve inputs must land, and every table cell
 * outside their windows is free.  Windows of inputs closer than K apart do
 * overlap, so this is not twelve independent problems: it is a
 * transfer-matrix feasibility DP over the cell range, state = the last K-1
 * byte choices (each address admits exactly 8 loader-valid bytes).
 *
 * usage: solve K0 K [emit]
 *   default    : per-input feasibility + joint SAT/UNSAT
 *   with "emit": also prints "<address> <byte>" for every table cell
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const int OPS[8] = {4, 5, 23, 39, 40, 62, 68, 81};

static int legal_byte(int addr, int op) {
    int b = ((op - addr) % 94 + 94) % 94;
    if (b < 33) b += 94;
    return b;
}

static int crazy_trit(int a, int d) {
    static const int T[3][3] = {{1, 0, 0}, {1, 0, 2}, {2, 2, 1}}; /* T[d][a] */
    return T[d][a];
}

static int crazy_word(int a, int d) {
    int out = 0, f = 1;
    for (int i = 0; i < 10; i++) {
        out += crazy_trit(a % 3, d % 3) * f;
        a /= 3; d /= 3; f *= 3;
    }
    return out;
}

/* the rung's twelve inputs; target = input ^ 0x51 */
static const int INPUTS[12] = {0x08, 0x37, 0x35, 0x1a, 0x2a, 0x32,
                               0x38, 0x2f, 0x0d, 0x18, 0x3b, 0x14};

static int K0, K, ncells, addr_lo;
static int (*cand)[8];

/* chain the K bytes given by choice digits d[0..K-1] (oldest first) starting
 * at cell `first` for input b */
static int chain(int b, int first, const int *d) {
    int acc = b + K0;
    for (int i = 0; i < K; i++) acc = crazy_word(acc, cand[first + i][d[i]]);
    return acc;
}

/* reachable accumulator set after walking the window, ignoring other lanes */
static int per_input_feasible(int b, long *count) {
    int first = b + K0 + 1 - addr_lo;
    static unsigned char cur[59049], nxt[59049];
    memset(cur, 0, sizeof cur);
    cur[b + K0] = 1;
    for (int i = 0; i < K; i++) {
        memset(nxt, 0, sizeof nxt);
        for (int a = 0; a < 59049; a++) {
            if (!cur[a]) continue;
            for (int j = 0; j < 8; j++) nxt[crazy_word(a, cand[first + i][j])] = 1;
        }
        memcpy(cur, nxt, sizeof cur);
    }
    long hits = 0;
    for (int a = 0; a < 59049; a++) if (cur[a] && (a % 256) == (b ^ 0x51)) hits++;
    *count = hits;
    return hits > 0;
}

int main(int argc, char **argv) {
    K0 = argc > 1 ? atoi(argv[1]) : 2916;
    K  = argc > 2 ? atoi(argv[2]) : 6;
    int emit = argc > 3;

    int lo = 255, hi = 0;
    for (int i = 0; i < 12; i++) {
        if (INPUTS[i] < lo) lo = INPUTS[i];
        if (INPUTS[i] > hi) hi = INPUTS[i];
    }
    addr_lo = K0 + lo + 1;
    int addr_hi = K0 + hi + K;
    ncells = addr_hi - addr_lo + 1;

    cand = malloc(ncells * sizeof(*cand));
    for (int c = 0; c < ncells; c++)
        for (int j = 0; j < 8; j++) cand[c][j] = legal_byte(addr_lo + c, OPS[j]);

    int all_ok = 1;
    for (int i = 0; i < 12; i++) {
        long hits;
        int ok = per_input_feasible(INPUTS[i], &hits);
        if (!emit)
            fprintf(stderr, "input %02x -> %02x : %ld / 8^%d solutions%s\n",
                    INPUTS[i], INPUTS[i] ^ 0x51, hits, K, ok ? "" : "   DEAD");
        all_ok &= ok;
    }
    if (!all_ok) { printf("UNSAT (per-input) K0=%d K=%d\n", K0, K); return 1; }

    int *ends = malloc(ncells * sizeof(int));
    for (int i = 0; i < ncells; i++) ends[i] = -1;
    for (int i = 0; i < 12; i++) ends[INPUTS[i] + K0 + K - addr_lo] = INPUTS[i];

    long nstate = 1;
    for (int i = 0; i < K - 1; i++) nstate *= 8;
    long div = nstate / 8;

    unsigned char *reach = malloc(nstate), *next = malloc(nstate);
    int *parent = emit ? malloc((size_t)ncells * nstate * sizeof(int)) : NULL;
    memset(reach, 1, nstate); /* first K-1 cells unconstrained */

    for (int c = K - 1; c < ncells; c++) {
        memset(next, 0, nstate);
        for (long s = 0; s < nstate; s++) {
            if (!reach[s]) continue;
            int digits[16];
            long t = s;
            for (int i = K - 2; i >= 0; i--) { digits[i] = (int)(t % 8); t /= 8; }
            for (int j = 0; j < 8; j++) {
                if (ends[c] >= 0) {
                    digits[K - 1] = j;
                    if ((chain(ends[c], c - K + 1, digits) % 256) != (ends[c] ^ 0x51))
                        continue;
                }
                long ns = (s % div) * 8 + j;
                if (!next[ns]) {
                    next[ns] = 1;
                    if (emit) parent[(size_t)c * nstate + ns] = (int)s;
                }
            }
        }
        unsigned char *tmp = reach; reach = next; next = tmp;
        long live = 0;
        for (long s = 0; s < nstate; s++) live += reach[s];
        if (!live) { printf("UNSAT (joint) K0=%d K=%d at addr %d\n", K0, K, addr_lo + c); return 1; }
        if (!emit) fprintf(stderr, "  cell %d (addr %d)%s live=%ld\n", c, addr_lo + c,
                           ends[c] >= 0 ? " [window ends]" : "", live);
    }

    if (!emit) { printf("SAT K0=%d K=%d cells=%d\n", K0, K, ncells); return 0; }

    /* reconstruct */
    long s = -1;
    for (long i = 0; i < nstate; i++) if (reach[i]) { s = i; break; }
    int *choice = malloc(ncells * sizeof(int));
    for (int c = ncells - 1; c >= K - 1; c--) {
        choice[c] = (int)(s % 8);
        s = parent[(size_t)c * nstate + s];
    }
    /* the seed state s now holds the first K-1 choices, oldest digit highest */
    for (int i = K - 2; i >= 0; i--) { choice[i] = (int)(s % 8); s /= 8; }

    for (int c = 0; c < ncells; c++) printf("%d %d\n", addr_lo + c, cand[c][choice[c]]);
    return 0;
}
