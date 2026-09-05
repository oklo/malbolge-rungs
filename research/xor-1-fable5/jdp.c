/* Exact transfer-matrix DP over the CODE tape for the stride-1 JMP
 * code-dispatch family on L2.R0.xor-1 — the computation the push-xor-1 record
 * formulated and did not run.
 *
 * Prologue (cells 0..8): IN, MOVD x3, CRZ x2, MOVD x2, JMP
 *   pins {40:122, 62:71, 71:121, 72:121, 73:61, 123:70}
 *   entry per input b: C = b+1, A = b, D = 73.
 * Every input executes cells b+1, b+2, ... and reads the SAME operand stream
 * m[73], m[74], ... (step i uses operand cell 73+i).  Stream cells 74..73+W-1
 * are an outer parameter (they are code only for inputs in the excluded
 * collision band, so their byte value is free).
 *
 * Private per-cell alphabet = the 8 loader-legal bytes.  Replay semantics:
 *   NOP: -                          CRZ: A = crazy(A, v_i)
 *   ROT: A = rotr(v_i)              OUT: emit A%256 (second OUT = fail)
 *   HALT: end (pass iff emitted == b^0x51)
 *   MOVD/JMP/IN: fail (D or A leaves the modelled invariant)
 * Scored inputs: b in 8..249 excluding the write/read collision band
 * 65..80; windows for b >= 250 truncate at cell 255 and are scored in the
 * terminal-state pass.
 *
 * usage: jdp rank            -> rank all 8^5 streams by the per-input
 *                               independent (free-code) bound
 *        jdp dp v1 v2 v3 v4 v5 [emit] -> exact DP for stream m[74..78]
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define W 6            /* window: cells b+1 .. b+W, operands m[73..73+W-1] */
#define NCELL 256
static const int OPS[8] = {4, 5, 23, 39, 40, 62, 68, 81};
static int ct[3][3] = {{1, 0, 0}, {1, 0, 2}, {2, 2, 1}};
static unsigned crazy(unsigned a, unsigned d) {
  unsigned r = 0, f = 1;
  for (int i = 0; i < 10; i++) { r += (unsigned)ct[d % 3][a % 3] * f; a /= 3; d /= 3; f *= 3; }
  return r;
}
static unsigned rotr10(unsigned w) { return w / 3 + (w % 3) * 19683u; }
static unsigned *CZM;   /* CZM[(v-33)*59049 + a] = crazy(a, v) */
static void init_memo(void) {
  CZM = malloc(94ull * 59049 * sizeof(unsigned));
  for (int v = 33; v <= 126; v++)
    for (unsigned a = 0; a < 59049u; a++)
      CZM[(size_t)(v - 33) * 59049 + a] = crazy(a, (unsigned)v);
}
static inline unsigned CZ(unsigned a, int v) { return CZM[(size_t)(v - 33) * 59049 + a]; }

static int PIN[NCELL];          /* -1 free, else pinned byte */
static int NV[NCELL], VALB[NCELL][8];
static int stream[W];           /* operand values m[73..73+W-1] */

static void init_cells(void) {
  for (int a = 0; a < NCELL; a++) PIN[a] = -1;
  PIN[40] = 122; PIN[62] = 71; PIN[71] = 121; PIN[72] = 121; PIN[73] = 61; PIN[123] = 70;
  for (int a = 0; a < NCELL; a++) {
    if (PIN[a] >= 0) { NV[a] = 1; VALB[a][0] = PIN[a]; continue; }
    int n = 0;
    for (int v = 33; v <= 126; v++) {
      int c = (v + a) % 94;
      for (int i = 0; i < 8; i++) if (c == OPS[i]) { VALB[a][n++] = v; break; }
    }
    NV[a] = n;
  }
}

static int scoreable(int b) {
  if (b < 8 || b > 255) return 0;
  if (b >= 65 && b <= 80) return 0;   /* code/operand collision band */
  return 1;
}

/* replay input b over code bytes w[0..n-1] at cells b+1..b+n; n<=W */
static int replay(int b, const int *wb, int n) {
  unsigned A = (unsigned)b;
  int outdone = 0, outv = -1;
  for (int i = 0; i < n; i++) {
    int cell = b + 1 + i;
    int op = (wb[i] + cell) % 94;
    switch (op) {
      case 68: break;
      case 62: A = CZ(A, stream[i]); break;
      case 39: A = rotr10((unsigned)stream[i]); break;
      case 5:
        if (outdone) return 0;
        outdone = 1; outv = (int)(A % 256); break;
      case 81: return outdone && outv == (b ^ 0x51);
      default: return 0;      /* MOVD, JMP, IN leave the invariant */
    }
  }
  return 0;                    /* never halted inside the window */
}

/* independent bound: free op choice per step, ops in {NOP,CRZ,ROT,OUT,HALT} */
static int indep_ok(int b) {
  /* BFS over (step, A, outdone/outv-match). track set of A per step plus
   * whether a correct OUT already happened (then just need HALT reachable). */
  static unsigned cur[4096], nxt[4096];
  int nc = 0, target = b ^ 0x51;
  cur[nc++] = (unsigned)b;
  int steps = (255 - (b + 1) + 1); if (steps > W) steps = W;
  for (int i = 0; i < steps; i++) {
    /* if any A == target mod 256, we can OUT here and HALT next step (needs
     * i+1 < steps for the HALT cell) */
    for (int s = 0; s < nc; s++)
      if ((int)(cur[s] % 256) == target && i + 1 < steps) return 1;
    int nn = 0;
    for (int s = 0; s < nc && nn < 4090; s++) {
      unsigned A = cur[s];
      nxt[nn++] = A;                                   /* NOP */
      nxt[nn++] = CZ(A, stream[i]);                    /* CRZ */
    }
    if (nn < 4090) nxt[nn++] = rotr10((unsigned)stream[i]); /* ROT */
    memcpy(cur, nxt, nn * sizeof(unsigned));
    nc = nn;
  }
  return 0;
}

int main(int argc, char **argv) {
  init_cells();
  init_memo();
  if (argc >= 2 && !strcmp(argv[1], "rank")) {
    /* enumerate streams: v_i in legal bytes of cell 74+i (i=0..4) */
    int lb[5][8], ln[5];
    for (int i = 0; i < 5; i++) { ln[i] = NV[74 + i]; memcpy(lb[i], VALB[74 + i], sizeof(lb[i])); }
    int bestn = -1;
    stream[0] = 61;
    for (int a0 = 0; a0 < ln[0]; a0++)
    for (int a1 = 0; a1 < ln[1]; a1++)
    for (int a2 = 0; a2 < ln[2]; a2++)
    for (int a3 = 0; a3 < ln[3]; a3++)
    for (int a4 = 0; a4 < ln[4]; a4++) {
      stream[1] = lb[0][a0]; stream[2] = lb[1][a1]; stream[3] = lb[2][a2];
      stream[4] = lb[3][a3]; stream[5] = lb[4][a4];
      int n = 0;
      for (int b = 8; b <= 255; b++) if (scoreable(b) && indep_ok(b)) n++;
      if (n >= bestn - 2) {
        printf("stream %d %d %d %d %d  indep=%d\n", stream[1], stream[2],
               stream[3], stream[4], stream[5], n);
        if (n > bestn) bestn = n;
        fflush(stdout);
      }
    }
    return 0;
  }
  if (argc >= 7 && !strcmp(argv[1], "dp")) {
    stream[0] = 61;
    for (int i = 0; i < 5; i++) stream[i + 1] = atoi(argv[2 + i]);
    int emit = argc > 7;
    /* pin stream cells for the DP */
    for (int i = 0; i < 5; i++) { PIN[74 + i] = stream[i + 1]; NV[74 + i] = 1; VALB[74 + i][0] = stream[i + 1]; }
    /* state = choices of last W-1 cells, radix 8 (invalid ix skipped) */
    long SW = 1; for (int i = 0; i < W - 1; i++) SW *= 8;
    int *dp = malloc(SW * sizeof(int)), *nd = malloc(SW * sizeof(int));
    unsigned char *par = calloc((size_t)NCELL * SW, 1);
    int *pst = malloc(sizeof(int) * (size_t)NCELL * SW);
    for (long s = 0; s < SW; s++) dp[s] = (s == 0) ? 0 : -1;
    /* cells 9..255; input b scored when cell a = b+W is decided */
    int a0 = 9;
    for (int a = a0; a < NCELL; a++) {
      for (long s = 0; s < SW; s++) nd[s] = -1;
      int b = a - W;
      for (long s = 0; s < SW; s++) {
        if (dp[s] < 0) continue;
        /* decode window cells a-W+1 .. a-1 from state s (oldest in low trits) */
        int wb[W]; int ok = 1; long t = s;
        for (int j = 0; j < W - 1; j++) {
          int ad = a - (W - 1) + j;
          int ix = (int)(t & 7); t >>= 3;
          if (ad < a0 - (W - 1)) { wb[j] = -1; }
          if (ad < 0) { ok = 0; break; }
          if (ix >= NV[ad]) { ok = 0; break; }
          wb[j] = VALB[ad][ix];
        }
        if (!ok) continue;
        for (int d = 0; d < NV[a]; d++) {
          int wfull[W];
          for (int j = 0; j < W - 1; j++) wfull[j] = wb[j];
          wfull[W - 1] = VALB[a][d];
          int sc = dp[s];
          if (scoreable(b) && b + 1 == a - W + 1) {
            /* window cells b+1..b+W == a-W+1..a: exactly wfull */
            if (replay(b, wfull, W)) sc += 1;
          }
          long ns = (s >> 3) | ((long)d << (3 * (W - 2)));
          if (sc > nd[ns]) { nd[ns] = sc; par[(size_t)a * SW + ns] = (unsigned char)d; pst[(size_t)a * SW + ns] = (int)s; }
        }
      }
      memcpy(dp, nd, SW * sizeof(int));
    }
    /* terminal: truncated windows for b = 250..255 */
    int best = -1; long bs = 0;
    for (long s = 0; s < SW; s++) {
      if (dp[s] < 0) continue;
      int wb[W - 1]; int ok = 1; long t = s;
      for (int j = 0; j < W - 1; j++) {
        int ad = NCELL - (W - 1) + j;
        int ix = (int)(t & 7); t >>= 3;
        if (ix >= NV[ad]) { ok = 0; break; }
        wb[j] = VALB[ad][ix];
      }
      if (!ok) continue;
      int sc = dp[s];
      for (int b = NCELL - W; b <= 255; b++) {
        if (!scoreable(b)) continue;
        int n = 255 - b;            /* cells b+1..255 available */
        if (n <= 0 || n >= W) continue;
        int off = (b + 1) - (NCELL - (W - 1));
        if (off < 0) continue;
        if (replay(b, wb + off, n)) sc++;
      }
      if (sc > best) { best = sc; bs = s; }
    }
    fprintf(stderr, "stream 61,%d,%d,%d,%d,%d  exact best = %d/256\n",
            stream[1], stream[2], stream[3], stream[4], stream[5], best);
    if (emit) {
      int ch[NCELL]; for (int i = 0; i < NCELL; i++) ch[i] = -1;
      long st = bs;
      for (int a = NCELL - 1; a >= a0; a--) {
        int d = par[(size_t)a * SW + st]; int ps = pst[(size_t)a * SW + st];
        ch[a] = VALB[a][d]; st = ps;
      }
      for (int a = 0; a < NCELL; a++) {
        if (ch[a] < 0) ch[a] = (PIN[a] >= 0) ? PIN[a] : -2;
        printf("%d %d\n", a, ch[a]);
      }
    }
    return 0;
  }
  fprintf(stderr, "usage: jdp rank | jdp dp v1 v2 v3 v4 v5 [emit]\n");
  return 2;
}
