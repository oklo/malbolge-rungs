/* Sweep the generalised table architecture for L2.FM2l.xor51-map12-low.
 *
 * cov48 fixed the dispatch at A = b + K0 with K0 a multiple of 729, because a
 * coverage rung needs all 256 inputs to index distinct table entries, and only
 * M1 = (1,0,2) is injective among the crazy rows, forcing identity on trits
 * 0..5.  This rung's twelve inputs are all < 81, so only trits 0..3 must be
 * preserved; trits 4..9 of every input are 0 and M[w2][M[w1][0]] can be made
 * 0, 1 or 2.  So the dispatch can realise A = b + K0 for ANY K0 that is a
 * multiple of 81 -- 50 offsets instead of 5.
 *
 * That matters because trits 5..9 of the accumulator are frozen after the
 * dispatch: table operands are printable bytes (< 243), so those trits only
 * ever see crazy_trit(t, 0) and their value after K layers is a function of K0
 * and the parity of K alone.  The high part H is therefore the same constant
 * for all twelve lanes, and each lane needs the exact low value
 * L*_b = (target_b - H) mod 256 with L* <= 242.
 *
 * usage: sweep [kmin kmax]   -- prints every (K0, K) with its live-lane count
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const int OPS[8] = {4, 5, 23, 39, 40, 62, 68, 81};
static const int INPUTS[12] = {0x08, 0x37, 0x35, 0x1a, 0x2a, 0x32,
                               0x38, 0x2f, 0x0d, 0x18, 0x3b, 0x14};

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
    int out = 0, f = 1;
    for (int i = 0; i < 10; i++) { out += crazy_trit(a % 3, d % 3) * f; a /= 3; d /= 3; f *= 3; }
    return out;
}

static int high_part(int K0, int K) {
    int H = 0, p3 = 243;
    for (int i = 5; i < 10; i++) {
        int t = (K0 / p3) % 3;
        for (int k = 0; k < K; k++) t = crazy_trit(t, 0);
        H += t * p3;
        p3 *= 3;
    }
    return H;
}

static int live_lanes(int K0, int K, int verbose) {
    int H = high_part(K0, K), ok = 0;
    for (int i = 0; i < 12; i++) {
        int b = INPUTS[i], need = (((b ^ 0x51) - H) % 256 + 256) % 256;
        if (need > 242) { if (verbose) printf("  in=%02x L*=%d OUT OF RANGE\n", b, need); continue; }
        unsigned char cur[243], nxt[243];
        memset(cur, 0, sizeof cur);
        cur[(b + K0) % 243] = 1;
        for (int k = 0; k < K; k++) {
            int addr = K0 + b + 1 + k;
            memset(nxt, 0, sizeof nxt);
            for (int a = 0; a < 243; a++) {
                if (!cur[a]) continue;
                for (int j = 0; j < 8; j++) nxt[crazy_word(a, legal_byte(addr, OPS[j])) % 243] = 1;
            }
            memcpy(cur, nxt, sizeof cur);
        }
        if (cur[need]) ok++;
        else if (verbose) printf("  in=%02x L*=%d unreachable\n", b, need);
    }
    return ok;
}

int main(int argc, char **argv) {
    int kmin = argc > 1 ? atoi(argv[1]) : 2, kmax = argc > 2 ? atoi(argv[2]) : 16;
    int best = -1, bK0 = 0, bK = 0;
    for (int K0 = 81; K0 + 59 + kmax < 4090; K0 += 81) {
        for (int K = kmin; K <= kmax; K++) {
            int n = live_lanes(K0, K, 0);
            if (n >= 10) printf("K0=%4d K=%2d  live=%2d/12  H=%d\n", K0, K, n, high_part(K0, K));
            if (n > best) { best = n; bK0 = K0; bK = K; }
        }
    }
    printf("best: K0=%d K=%d live=%d/12\n", bK0, bK, best);
    live_lanes(bK0, bK, 1);
    return 0;
}
