/* perm_dp.c -- exact table DP for the dispatch architecture, extended with a
 * new degree of freedom: the LOW-TRIT PERMUTATION of the dispatch map.
 *
 * Prior art (research/cov40/table_dp.c, research/cov48/table_dp2.c) fixed the
 * dispatch at two CRAZY layers, which forces the composed map on trits 0..5 to
 * be the identity (M1 o M1 = id is the only injective composition of two rows),
 * hence index(b) = b + K0 with K0 a multiple of 729.  The table cells used by
 * inputs are then 256 CONSECUTIVE cells, and consecutive inputs share k-1 of
 * their k cells -- maximal coupling, which is what caps the DP.
 *
 * With THREE CRAZY layers the only injective composed low map is M1 itself
 * (M1oM1oM1 = M1; anything containing M0 or M2 is non-injective and stays so),
 * so index(b) = pi(b) + K0 with pi = trit-wise (0->1, 1->0, 2->2) on trits 0..5.
 * pi is injective but NOT order preserving: it scatters the 256 used cells over
 * a 365-wide window, so many inputs get cells no other input reads.  Less
 * coupling should mean a higher DP optimum at the same depth k.
 *
 * This program scores both index maps exactly, for every reachable offset and
 * depth k = 1..6, and dumps the winning table bytes.
 *
 * Legal source byte at address a: b in 33..126 with (b + a) mod 94 in OPS.
 * (The +94 bump is the loader rule; research/cov40/table_dp.c had this wrong,
 * see docs/attempts/2026-08-10-claude-cov48.md.)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const int M[3][3] = {{1,0,0},{1,0,2},{2,2,1}};
static const int OPS[8] = {4,5,23,39,40,62,68,81};
#define LIMIT 4096

static int crz(int a, int d) {
    int r = 0, p = 1, i;
    for (i = 0; i < 10; i++) { r += M[d%3][a%3]*p; p *= 3; a /= 3; d /= 3; }
    return r;
}
static int legal_byte(int a, int op) {
    int b = ((op - a) % 94 + 94) % 94;
    if (b < 33) b += 94;
    return b;
}

static int L[LIMIT][8];
static int TGT[256];

/* pi_id: identity on trits 0..5 (2-layer dispatch)
 * pi_m1: trit-wise M1 on trits 0..5 (3-layer dispatch) */
static int apply_pi(int b, int mode) {
    if (mode == 0) return b;
    int r = 0, p = 1, i;
    for (i = 0; i < 6; i++) { r += M[1][b%3]*p; p *= 3; b /= 3; }
    return r;
}

/* DP: cells ascending; state = last k-1 choices; input b scores at cell idx(b)+k */
static long dp_run(int mode, int K0, int k, int *table_out, int *lo_out, int *hi_out) {
    int idx[256], owner[LIMIT];
    int lo = 1 << 30, hi = -1, b, c;
    for (c = 0; c < LIMIT; c++) owner[c] = -1;
    for (b = 0; b < 256; b++) {
        idx[b] = apply_pi(b, mode) + K0;
        if (idx[b] + k >= LIMIT) return -1;          /* table would exceed length limit */
        if (idx[b] + 1 < lo) lo = idx[b] + 1;
        if (idx[b] + k > hi) hi = idx[b] + k;
        owner[idx[b] + k] = b;                       /* injective: one owner per cell */
    }
    *lo_out = lo; *hi_out = hi;

    int nstate = 1; int i;
    for (i = 0; i < k-1; i++) nstate *= 8;
    int ncell = hi - lo + 1;
    signed char *par = malloc((size_t)ncell * nstate);
    int *cur = malloc(sizeof(int)*nstate), *nxt = malloc(sizeof(int)*nstate);
    if (!par || !cur || !nxt) { fprintf(stderr,"oom\n"); exit(1); }
    /* state encodes choices of cells (c-k+1 .. c-1), most recent in low digits */
    for (i = 0; i < nstate; i++) cur[i] = 0;
    int step;
    for (step = 0; step < ncell; step++) {
        c = lo + step;
        for (i = 0; i < nstate; i++) nxt[i] = -1;
        int s, ch;
        for (s = 0; s < nstate; s++) {
            if (cur[s] < 0) continue;
            for (ch = 0; ch < 8; ch++) {
                int hit = 0;
                int ob = owner[c];
                if (ob >= 0 && c - k + 1 >= lo) {
                    /* reconstruct the k choices for cells c-k+1..c */
                    int chs[8]; int t, ss = s;
                    for (t = k-2; t >= 0; t--) { chs[t] = ss % 8; ss /= 8; }
                    chs[k-1] = ch;
                    int A = idx[ob];
                    for (t = 0; t < k; t++) A = crz(A, L[c-k+1+t][chs[t]]);
                    if ((A & 255) == TGT[ob]) hit = 1;
                }
                int ns = (k > 1) ? ((s * 8 + ch) % nstate) : 0;
                int v = cur[s] + hit;
                if (v > nxt[ns]) { nxt[ns] = v; par[(size_t)step*nstate + ns] = (signed char)(s & 0x7f); }
            }
        }
        memcpy(cur, nxt, sizeof(int)*nstate);
        /* remember choice too: recover by replaying below */
    }
    int best = -1, bs = 0;
    for (i = 0; i < nstate; i++) if (cur[i] > best) { best = cur[i]; bs = i; }

    if (table_out) {
        /* backtrack: state after step encodes the last k-1 choices; walk back */
        int *chsel = malloc(sizeof(int)*ncell);
        int s = bs;
        for (step = ncell-1; step >= 0; step--) {
            int ps = par[(size_t)step*nstate + s];
            /* the choice made at this step is the low digit of s (when k>1) */
            chsel[step] = (k > 1) ? (s % 8) : -1;
            s = ps;
        }
        if (k == 1) { /* independent per cell: choose greedily */
            for (step = 0; step < ncell; step++) {
                c = lo + step; int ob = owner[c]; int ch, pick = 0;
                for (ch = 0; ch < 8; ch++) {
                    if (ob >= 0 && (crz(idx[ob], L[c][ch]) & 255) == TGT[ob]) { pick = ch; break; }
                }
                chsel[step] = pick;
            }
        }
        for (step = 0; step < ncell; step++) table_out[step] = chsel[step];
        free(chsel);
    }
    free(par); free(cur); free(nxt);
    return best;
}

/* independent re-scorer: given the chosen table, count hits by direct simulation */
static int rescore(int mode, int K0, int k, const int *chsel, int lo, int hi) {
    int n = 0, b;
    for (b = 0; b < 256; b++) {
        int idx = apply_pi(b, mode) + K0, t, A = idx;
        for (t = 1; t <= k; t++) {
            int c = idx + t;
            A = crz(A, L[c][chsel[c - lo]]);
        }
        if ((A & 255) == TGT[b]) n++;
    }
    return n;
}

int main(int argc, char **argv) {
    int a, i, b;
    for (a = 0; a < LIMIT; a++) for (i = 0; i < 8; i++) L[a][i] = legal_byte(a, OPS[i]);
    for (b = 0; b < 256; b++) TGT[b] = b ^ 0x51;

    int modes[2] = {0, 1};
    const char *nm[2] = {"id  (2-layer)", "M1  (3-layer)"};
    int mi, K0, k;
    for (mi = 0; mi < 2 && argc < 4; mi++) {
        for (K0 = 0; K0 <= 3645; K0 += 729) {
            printf("pi=%s K0=%-5d :", nm[modes[mi]], K0);
            for (k = 1; k <= 6; k++) {
                int lo, hi;
                long s = dp_run(modes[mi], K0, k, NULL, &lo, &hi);
                if (s < 0) printf("   --");
                else printf(" %4ld", s);
            }
            printf("\n");
        }
    }
    /* dump the table for a requested config: perm_dp <mode> <K0> <k> */
    if (argc >= 4) {
        int mode = atoi(argv[1]); K0 = atoi(argv[2]); k = atoi(argv[3]);
        int lo, hi;
        int *tbl = malloc(sizeof(int)*LIMIT);
        long s = dp_run(mode, K0, k, tbl, &lo, &hi);
        int rs = rescore(mode, K0, k, tbl, lo, hi);
        fprintf(stderr, "config mode=%d K0=%d k=%d  dp=%ld rescore=%d  cells %d..%d\n",
                mode, K0, k, s, rs, lo, hi);
        FILE *f = fopen("table.txt", "w");
        fprintf(f, "%d %d %d %d %d %d\n", mode, K0, k, lo, hi, rs);
        for (i = lo; i <= hi; i++) fprintf(f, "%d %d\n", i, L[i][tbl[i-lo]]);
        fclose(f);
    }
    return 0;
}
