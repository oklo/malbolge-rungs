/* Exhaustive ceiling for the straight-line CRAZY/ROTATE family against the
 * NibbleMap transform of L5.R0.future-transform.
 *
 * Same family as research/cov32/family_ceiling.py, different target.  A
 * straight-line classic-Malbolge data path (IN, then any sequence of
 * CRAZY-with-a-constant and ROTATE, then OUT) acts one trit position at a
 * time.  CRAZY with a constant applies at position i the unary trit map
 * m_{c_i} drawn from the rows of the crazy table
 *
 *     m0 = (1,0,0)   m1 = (1,0,2)   m2 = (2,2,1)
 *
 * and ROTATE cyclically permutes positions, so N CRAZY ops with R rotations
 * realise exactly
 *
 *     out = sum_{i=0..9} g_i( trit_{(i+R) mod 10}(b) ) * 3^i,   g_i in M_N
 *
 * with each g_i a length-N composition of the generators, chosen freely and
 * independently per position (the constant's trit at each position is free).
 * The emitted byte is out mod 256.  Input trits 6..9 are 0 for any byte, so
 * the four positions fed by them contribute a constant K; the reachable K set
 * is enumerated too.
 *
 * This enumerates the whole family and reports, for every N and every shift,
 * the maximum number of the 256 inputs on which the emitted byte equals
 * ((b<<4)|(b>>4)) & 0xFF.
 *
 *     cc -O2 -o /tmp/ceil research/future-transform/straightline_ceiling.c && /tmp/ceil
 *
 * The point of the number is the pass probability: this rung's cases are
 * 4 hash-derived input bytes per case, 4 cases, and every one of the 16
 * emitted bytes must be exactly right, so a straight-line program passes an
 * epoch with probability (best/256)^16.
 */
#include <stdio.h>
#include <string.h>
#include <stdint.h>

static const int GEN[3][3] = {{1, 0, 0}, {1, 0, 2}, {2, 2, 1}};

/* a map is packed as g[0] + 3*g[1] + 9*g[2] */
static int compose(int f, int g) /* f after g */
{
    int gg[3] = {g % 3, (g / 3) % 3, (g / 9) % 3};
    int ff[3] = {f % 3, (f / 3) % 3, (f / 9) % 3};
    int r[3];
    for (int t = 0; t < 3; t++) r[t] = ff[gg[t]];
    return r[0] + 3 * r[1] + 9 * r[2];
}

static int maps_of_depth(int n, int *out)
{
    int cur[27], ncur = 1;
    cur[0] = 0 + 3 * 1 + 9 * 2; /* identity */
    for (int step = 0; step < n; step++) {
        int seen[27], nxt[27], nn = 0;
        memset(seen, 0, sizeof seen);
        for (int i = 0; i < ncur; i++)
            for (int g = 0; g < 3; g++) {
                int gp = GEN[g][0] + 3 * GEN[g][1] + 9 * GEN[g][2];
                int c = compose(gp, cur[i]);
                if (!seen[c]) { seen[c] = 1; nxt[nn++] = c; }
            }
        memcpy(cur, nxt, sizeof(int) * nn);
        ncur = nn;
    }
    memcpy(out, cur, sizeof(int) * ncur);
    return ncur;
}

static int P3[10];
static uint8_t trit[10][256];
static uint8_t target[256];

int main(void)
{
    P3[0] = 1;
    for (int i = 1; i < 10; i++) P3[i] = P3[i - 1] * 3;
    for (int b = 0; b < 256; b++) {
        int x = b;
        for (int i = 0; i < 10; i++) { trit[i][b] = x % 3; x /= 3; }
        target[b] = (uint8_t)(((b << 4) | (b >> 4)) & 0xFF);
    }

    int overall = 0, overall_n = -1, overall_shift = -1;
    for (int n = 0; n < 6; n++) {
        int maps[27], m = maps_of_depth(n, maps);
        for (int shift = 0; shift < 10; shift++) {
            int var_pos[10], nvar = 0, fix_pos[10], nfix = 0;
            for (int i = 0; i < 10; i++) {
                if ((i + shift) % 10 <= 5) var_pos[nvar++] = i; else fix_pos[nfix++] = i;
            }
            /* reachable K from the four constant positions */
            uint8_t allowed[256];
            memset(allowed, 0, sizeof allowed);
            int zvals[3], nz = 0, seenz[3] = {0, 0, 0};
            for (int i = 0; i < m; i++) { int z = maps[i] % 3; if (!seenz[z]) { seenz[z] = 1; zvals[nz++] = z; } }
            int combos = 1;
            for (int i = 0; i < nfix; i++) combos *= nz;
            for (int c = 0; c < combos; c++) {
                int k = 0, t = c;
                for (int i = 0; i < nfix; i++) { k += zvals[t % nz] * P3[fix_pos[i]]; t /= nz; }
                allowed[k & 255] = 1;
            }

            /* contribution table: contrib[level][map][b] */
            static uint8_t contrib[6][27][256];
            for (int l = 0; l < nvar; l++) {
                int i = var_pos[l], j = (i + shift) % 10;
                for (int gi = 0; gi < m; gi++) {
                    int g[3] = {maps[gi] % 3, (maps[gi] / 3) % 3, (maps[gi] / 9) % 3};
                    for (int b = 0; b < 256; b++)
                        contrib[l][gi][b] = (uint8_t)((g[trit[j][b]] * P3[i]) & 255);
                }
            }

            int best = -1;
            static uint8_t part[7][256];
            for (int b = 0; b < 256; b++) part[0][b] = 0;
            int idx[6] = {0, 0, 0, 0, 0, 0}, lvl = 0;
            /* iterative odometer over nvar levels */
            while (1) {
                if (lvl == nvar) {
                    int hist[256];
                    memset(hist, 0, sizeof hist);
                    for (int b = 0; b < 256; b++)
                        hist[(uint8_t)(target[b] - part[nvar][b])]++;
                    for (int k = 0; k < 256; k++)
                        if (allowed[k] && hist[k] > best) best = hist[k];
                    lvl--;
                    while (lvl >= 0 && ++idx[lvl] >= m) { idx[lvl] = 0; lvl--; }
                    if (lvl < 0) break;
                    const uint8_t *c = contrib[lvl][idx[lvl]];
                    for (int b = 0; b < 256; b++) part[lvl + 1][b] = part[lvl][b] + c[b];
                    lvl++;
                } else {
                    const uint8_t *c = contrib[lvl][idx[lvl]];
                    for (int b = 0; b < 256; b++) part[lvl + 1][b] = part[lvl][b] + c[b];
                    lvl++;
                }
            }
            if (nvar == 0) best = 0;
            printf("N=%d shift=%d |M_N|=%d best=%d\n", n, shift, m, best);
            fflush(stdout);
            if (best > overall) { overall = best; overall_n = n; overall_shift = shift; }
        }
    }
    printf("\nceiling over the whole straight-line family: %d/256 (N=%d, shift=%d)\n",
           overall, overall_n, overall_shift);
    return 0;
}
