/* dp64.c -- exact table DP for the dispatch architecture, with a CORRECT
 * backtrack at every depth.
 *
 * Prior art: research/cov40/table_dp.c, research/cov48/table_dp2.c (2-layer,
 * index(b) = b + K0), research/cov36/perm_dp.c (adds the 3-layer permuting
 * dispatch, index(b) = pi(b) + K0 with pi = trit-wise M1 on trits 0..5).
 *
 * BUG FIXED HERE.  perm_dp.c stores the DP parent as
 *     par[step*nstate + ns] = (signed char)(s & 0x7f)
 * and recovers the per-cell choice as `s % 8` of the *successor* state.  The
 * state space is nstate = 8^(k-1), so for k >= 4 (nstate >= 512) the parent
 * index is truncated to 7 bits and the recovered table is garbage.  It happened
 * not to matter for cov36, which shipped k = 3 (nstate = 64).  At k = 6 the
 * extracted table rescores 0 while the DP optimum says 68.
 *
 * The fix: the transition is ns = (s*8 + ch) mod 8^(k-1), which drops exactly
 * the top octal digit of s.  Store that dropped digit (0..7, one byte) and the
 * predecessor is fully determined:
 *     ch  = ns % 8
 *     s   = dropped * 8^(k-2) + ns / 8
 *
 * Every emitted table is re-scored by direct simulation of all 256 inputs
 * against the emitted bytes before it is written out.
 *
 * Legal source byte at address a: b in 33..126 with (b + a) mod 94 in OPS,
 * with the loader's +94 bump (see docs/attempts/2026-08-10-claude-cov48.md).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const int M[3][3] = {{1,0,0},{1,0,2},{2,2,1}};
static const int OPS[8] = {4,5,23,39,40,62,68,81};
#define LIMIT 4096

static int CT[243][243];
static void init_crz(void) {
    int a, d, i, r, p, aa, dd;
    for (a = 0; a < 243; a++) for (d = 0; d < 243; d++) {
        r = 0; p = 1; aa = a; dd = d;
        for (i = 0; i < 5; i++) { r += M[dd%3][aa%3]*p; p *= 3; aa /= 3; dd /= 3; }
        CT[a][d] = r;
    }
}
static inline int crz(int a, int d) { return CT[a%243][d%243] + 243*CT[a/243][d/243]; }

static int legal_byte(int a, int op) {
    int b = ((op - a) % 94 + 94) % 94;
    if (b < 33) b += 94;
    return b;
}

static int L[LIMIT][8];
static int TGT[256];

static int apply_pi(int b, int mode) {
    int r = 0, p = 1, i;
    if (mode == 0) return b;
    for (i = 0; i < 6; i++) { r += M[1][b%3]*p; p *= 3; b /= 3; }
    return r;
}

/* returns DP optimum, or -1 if the table would not fit under LIMIT.
 * chsel_out (size >= ncell) receives the chosen octal index per cell. */
static long dp_run(int mode, int K0, int k, int *chsel_out, int *lo_out, int *hi_out) {
    static int idx[256], owner[LIMIT];
    int lo = 1 << 30, hi = -1, b, c, i;
    for (c = 0; c < LIMIT; c++) owner[c] = -1;
    for (b = 0; b < 256; b++) {
        idx[b] = apply_pi(b, mode) + K0;
        if (idx[b] + k >= LIMIT) return -1;
        if (idx[b] + 1 < lo) lo = idx[b] + 1;
        if (idx[b] + k > hi) hi = idx[b] + k;
        owner[idx[b] + k] = b;              /* index is injective: one owner per cell */
    }
    *lo_out = lo; *hi_out = hi;

    int nstate = 1, top = 1;
    for (i = 0; i < k-1; i++) nstate *= 8;
    for (i = 0; i < k-2; i++) top *= 8;     /* 8^(k-2), weight of the dropped digit */
    int ncell = hi - lo + 1;

    unsigned char *drop = malloc((size_t)ncell * nstate);
    int *cur = malloc(sizeof(int)*nstate), *nxt = malloc(sizeof(int)*nstate);
    if (!drop || !cur || !nxt) { fprintf(stderr, "oom\n"); exit(1); }
    for (i = 0; i < nstate; i++) cur[i] = 0;

    int step, s, ch;
    for (step = 0; step < ncell; step++) {
        c = lo + step;
        for (i = 0; i < nstate; i++) nxt[i] = -1;
        int ob = owner[c];
        int can_score = (ob >= 0 && c - k + 1 >= lo);
        for (s = 0; s < nstate; s++) {
            if (cur[s] < 0) continue;
            int chs[8], t, ss = s, Apre = 0;
            if (can_score) {
                for (t = k-2; t >= 0; t--) { chs[t] = ss % 8; ss /= 8; }
                Apre = idx[ob];
                for (t = 0; t < k-1; t++) Apre = crz(Apre, L[c-k+1+t][chs[t]]);
            }
            int dropped = (k >= 2) ? (s / top) : 0;
            for (ch = 0; ch < 8; ch++) {
                int hit = 0;
                if (can_score && (crz(Apre, L[c][ch]) & 255) == TGT[ob]) hit = 1;
                int ns = (k > 1) ? ((s * 8 + ch) % nstate) : 0;
                int v = cur[s] + hit;
                if (v > nxt[ns]) {
                    nxt[ns] = v;
                    drop[(size_t)step*nstate + ns] = (unsigned char)dropped;
                }
            }
        }
        memcpy(cur, nxt, sizeof(int)*nstate);
    }
    int best = -1, bs = 0;
    for (i = 0; i < nstate; i++) if (cur[i] > best) { best = cur[i]; bs = i; }

    if (chsel_out) {
        if (k == 1) {
            for (step = 0; step < ncell; step++) {
                c = lo + step; int ob = owner[c], pick = 0;
                for (ch = 0; ch < 8; ch++)
                    if (ob >= 0 && (crz(idx[ob], L[c][ch]) & 255) == TGT[ob]) { pick = ch; break; }
                chsel_out[step] = pick;
            }
        } else {
            int st = bs;
            for (step = ncell-1; step >= 0; step--) {
                int dropped = drop[(size_t)step*nstate + st];
                chsel_out[step] = st % 8;               /* choice made at this cell */
                st = dropped * top + st / 8;            /* exact predecessor state */
            }
        }
    }
    free(drop); free(cur); free(nxt);
    return best;
}

/* independent re-scorer: simulate all 256 inputs against the emitted bytes */
static int rescore(int mode, int K0, int k, const int *chsel, int lo) {
    int n = 0, b, t;
    for (b = 0; b < 256; b++) {
        int idx = apply_pi(b, mode) + K0, A = idx;
        for (t = 1; t <= k; t++) A = crz(A, L[idx+t][chsel[idx+t-lo]]);
        if ((A & 255) == TGT[b]) n++;
    }
    return n;
}

int main(int argc, char **argv) {
    int a, i, b, k, K0, mode;
    init_crz();
    for (a = 0; a < LIMIT; a++) for (i = 0; i < 8; i++) L[a][i] = legal_byte(a, OPS[i]);
    for (b = 0; b < 256; b++) TGT[b] = b ^ 0x51;

    if (argc >= 4) {
        mode = atoi(argv[1]); K0 = atoi(argv[2]); k = atoi(argv[3]);
        int lo, hi, *tbl = malloc(sizeof(int)*LIMIT);
        long s = dp_run(mode, K0, k, tbl, &lo, &hi);
        if (s < 0) { fprintf(stderr, "config does not fit\n"); return 1; }
        int rs = rescore(mode, K0, k, tbl, lo);
        fprintf(stderr, "config mode=%d K0=%d k=%d  dp=%ld rescore=%d  cells %d..%d\n",
                mode, K0, k, s, rs, lo, hi);
        const char *out = (argc >= 5) ? argv[4] : "table.txt";
        FILE *f = fopen(out, "w");
        fprintf(f, "%d %d %d %d %d %d\n", mode, K0, k, lo, hi, rs);
        for (i = lo; i <= hi; i++) fprintf(f, "%d %d\n", i, L[i][tbl[i-lo]]);
        fclose(f);
        return 0;
    }

    /* full sweep, with the backtracked table re-scored at every entry so a
     * mismatch between dp and rescore can never go unnoticed again */
    const char *nm[2] = {"id  (2-layer)", "M1  (3-layer)"};
    int *tbl = malloc(sizeof(int)*LIMIT);
    for (mode = 0; mode < 2; mode++) {
        for (K0 = 0; K0 <= 3645; K0 += 729) {
            printf("pi=%s K0=%-5d :", nm[mode], K0);
            for (k = 1; k <= 6; k++) {
                int lo, hi;
                long s = dp_run(mode, K0, k, tbl, &lo, &hi);
                if (s < 0) { printf("     --"); continue; }
                int rs = rescore(mode, K0, k, tbl, lo);
                printf(" %4ld%c", s, (rs == s) ? ' ' : '!');
            }
            printf("\n");
            fflush(stdout);
        }
    }
    return 0;
}
