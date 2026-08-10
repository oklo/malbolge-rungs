/* Max-count table DP for L2.FM2l.xor51-map12-low.
 *
 * Same transfer matrix as research/map12-low/solve.c, but instead of asking
 * "can all twelve lanes be satisfied at once" it maximises how many are --
 * so the rung gets a natively verified number even when the joint problem is
 * UNSAT.  State = the last K-1 byte choices (8 loader-valid bytes per
 * address); value = lanes satisfied so far.
 *
 * usage: maxtable K0 K [emit]
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const int OPS[8] = {4, 5, 23, 39, 40, 62, 68, 81};
static const int INPUTS[12] = {0x08, 0x37, 0x35, 0x1a, 0x2a, 0x32,
                               0x38, 0x2f, 0x0d, 0x18, 0x3b, 0x14};
static int K0, K, ncells, addr_lo;
static int (*cand)[8];

static int legal_byte(int addr, int op) {
    int b = ((op - addr) % 94 + 94) % 94;
    if (b < 33) b += 94;
    return b;
}
static int crazy_trit(int a, int d) {
    static const int T[3][3] = {{1, 0, 0}, {1, 0, 2}, {2, 2, 1}};
    return T[d][a];
}
static int crazy_word(int a, int d) {
    int o = 0, f = 1;
    for (int i = 0; i < 10; i++) { o += crazy_trit(a % 3, d % 3) * f; a /= 3; d /= 3; f *= 3; }
    return o;
}

int main(int argc, char **argv) {
    K0 = argc > 1 ? atoi(argv[1]) : 567;
    K  = argc > 2 ? atoi(argv[2]) : 4;
    int emit = argc > 3;

    int lo = 255, hi = 0;
    for (int i = 0; i < 12; i++) {
        if (INPUTS[i] < lo) lo = INPUTS[i];
        if (INPUTS[i] > hi) hi = INPUTS[i];
    }
    addr_lo = K0 + lo + 1;
    ncells = (K0 + hi + K) - addr_lo + 1;

    cand = malloc(ncells * sizeof(*cand));
    for (int c = 0; c < ncells; c++)
        for (int j = 0; j < 8; j++) cand[c][j] = legal_byte(addr_lo + c, OPS[j]);

    int *ends = malloc(ncells * sizeof(int));
    for (int i = 0; i < ncells; i++) ends[i] = -1;
    for (int i = 0; i < 12; i++) ends[INPUTS[i] + K0 + K - addr_lo] = INPUTS[i];

    long nstate = 1;
    for (int i = 0; i < K - 1; i++) nstate *= 8;
    long div = nstate / 8;

    signed char *val = malloc(nstate), *nval = malloc(nstate);
    int *parent = malloc((size_t)ncells * nstate * sizeof(int));
    memset(val, 0, nstate); /* first K-1 cells unconstrained, 0 lanes scored */

    for (int c = K - 1; c < ncells; c++) {
        memset(nval, -1, nstate);
        for (long s = 0; s < nstate; s++) {
            if (val[s] < 0) continue;
            int digits[24];
            long t = s;
            for (int i = K - 2; i >= 0; i--) { digits[i] = (int)(t % 8); t /= 8; }
            for (int j = 0; j < 8; j++) {
                int gain = 0;
                if (ends[c] >= 0) {
                    int b = ends[c], acc = b + K0;
                    digits[K - 1] = j;
                    for (int i = 0; i < K; i++) acc = crazy_word(acc, cand[c - K + 1 + i][digits[i]]);
                    gain = (acc % 256) == (b ^ 0x51);
                }
                long ns = (s % div) * 8 + j;
                if (val[s] + gain > nval[ns]) {
                    nval[ns] = val[s] + gain;
                    parent[(size_t)c * nstate + ns] = (int)s;
                }
            }
        }
        signed char *tmp = val; val = nval; nval = tmp;
    }

    long bs = 0;
    for (long s = 0; s < nstate; s++) if (val[s] > val[bs]) bs = s;
    fprintf(stderr, "K0=%d K=%d best=%d/12\n", K0, K, val[bs]);
    if (!emit) { printf("%d\n", val[bs]); return 0; }

    int *choice = malloc(ncells * sizeof(int));
    long s = bs;
    for (int c = ncells - 1; c >= K - 1; c--) { choice[c] = (int)(s % 8); s = parent[(size_t)c * nstate + s]; }
    for (int i = K - 2; i >= 0; i--) { choice[i] = (int)(s % 8); s /= 8; }
    for (int c = 0; c < ncells; c++) printf("%d %d\n", addr_lo + c, cand[c][choice[c]]);
    return 0;
}
