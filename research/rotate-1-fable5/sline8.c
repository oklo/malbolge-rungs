/* L2.R2.rotate-1: search-best for the shared straight-line family — the rotl
 * analogue of the xor "branchless CRAZY/ROT = 34/256" result.
 *
 * Family: same op sequence for every input b (shared code, no b-indexed table).
 *   acc0 = rotr^j0(b); second source s = rotr^j1(b) (a second parked copy).
 *   ops: 0 acc=crazy(acc,c_i)   (constant word, ENVELOPE: any 0..59048,
 *        1 acc=crazy(c_i,acc)    i.e. assumes any constant is manufacturable)
 *        2 acc=rotr(acc)
 *        3 acc=crazy(acc,s)
 *        4 acc=crazy(s,acc)
 * Score = #{b in 0..255 : acc_final mod 256 == rotl(b,1)}.
 * Hill-climb with restarts; report search-best (NOT exact).
 * usage: sline <seed> <depth> <seconds>
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
static int ct[3][3] = {{1, 0, 0}, {1, 0, 2}, {2, 2, 1}}; /* ct[d][a] */
static unsigned crazy(unsigned a, unsigned d) {
  unsigned r = 0, f = 1;
  for (int i = 0; i < 10; i++) { r += (unsigned)ct[d % 3][a % 3] * f; a /= 3; d /= 3; f *= 3; }
  return r;
}
static unsigned rotr(unsigned w) { return w / 3 + (w % 3) * 19683u; }
#define DMAX 12
typedef struct { int j0, j1, n; int op[DMAX]; unsigned c[DMAX]; } G;
static unsigned R[10][256], CB121[256];
static unsigned CSET[3000]; static int NC;

static int cset_rots(unsigned c) { /* min rots to reach c from any byte 33..126 */
  for (int k = 0; k <= 9; k++) { unsigned w = c; int kk = k; unsigned x = w;
    /* invert: rotl word k times */ (void)kk; (void)x;
    ; }
  /* precomputed at init instead */ return 0; }
static int ROTS[59049];

static int genome_cost(const G *g) {
  int code = 6 + 8 + 2 + 4 + 3 * g->j0 + 2;
  for (int i = 0; i < g->n; i++) {
    int op = g->op[i];
    if (op == 0) { int r = ROTS[g->c[i]]; code += 1 + (r > 0 && r < 90 ? 3 * r + 3 : (r >= 90 ? 900 : 0)); }
    else if (op == 2) code += 3;
    else if (op == 1) { unsigned rc = (g->c[i] % 19683u) * 3u + g->c[i] / 19683u; int r = ROTS[rc]; code += 7 + (r < 90 ? 3 * r : 900); }
    else if (op == 3) code += 4;
    else if (op == 5) code += 5;
    else code += 999;
  }
  return code;
}

static int score(const G *g) {
  int sc = 0;
  for (int b = 0; b < 256; b++) {
    unsigned acc = R[g->j0][b], s = R[g->j0][b], t = CB121[b];
    for (int i = 0; i < g->n; i++) {
      switch (g->op[i]) {
        case 0: acc = crazy(acc, g->c[i]); break;
        case 1: acc = crazy(g->c[i], acc); break;
        case 2: acc = rotr(acc); break;
        case 3: acc = crazy(acc, s); break;
        case 4: acc = crazy(s, acc); break;
        case 5: acc = crazy(acc, (unsigned)b); break;
        case 6: acc = crazy(t, acc); break;
      }
    }
    if ((int)(acc % 256) == (((b << 1) | (b >> 7)) & 0xFF)) sc++;
  }
  return sc;
}
static unsigned rng_s;
static unsigned rnd(void) { rng_s ^= rng_s << 13; rng_s ^= rng_s >> 17; rng_s ^= rng_s << 5; return rng_s; }
int main(int argc, char **argv) {
  rng_s = argc > 1 ? (unsigned)atoi(argv[1]) : 1u;
  int depth = argc > 2 ? atoi(argv[2]) : 8;
  int secs = argc > 3 ? atoi(argv[3]) : 90;
  for (int b = 0; b < 256; b++) { unsigned w = (unsigned)b; for (int j = 0; j < 10; j++) { R[j][b] = w; w = rotr(w); } CB121[b] = crazy((unsigned)b, 121u); }
  for (int i = 0; i < 59049; i++) ROTS[i] = 99;
  for (int v = 33; v <= 126; v++) { unsigned w = (unsigned)v; for (int k = 0; k <= 9; k++) { if (k < ROTS[w]) ROTS[w] = k; w = rotr(w); } }
  for (int v = 33; v <= 126; v++) { unsigned w = crazy(0u, (unsigned)v); for (int k = 0; k <= 9; k++) { int cst = (k == 0) ? 1 : k + 1; if (cst < ROTS[w]) ROTS[w] = cst; w = rotr(w); } }
  NC = 0;
  for (int v = 33; v <= 126; v++) { unsigned w = (unsigned)v; for (int k = 0; k <= 9; k++) { CSET[NC++] = w; w = rotr(w); } }
  time_t t0 = time(NULL);
  G best; memset(&best, 0, sizeof best); int bestsc = -1;
  while (time(NULL) - t0 < secs) {
    G g; g.j0 = rnd() % 10; g.j1 = rnd() % 10; g.n = depth;
    for (int i = 0; i < depth; i++) { g.op[i] = rnd() % 7; g.c[i] = CSET[rnd() % NC]; }
    int sc = genome_cost(&g) <= 71 ? score(&g) : -1;
    for (int it = 0; it < 20000; it++) {
      G h = g; int m = rnd() % 3;
      int i = rnd() % depth;
      if (m == 0) h.op[i] = rnd() % 7;
      else if (m == 1) h.c[i] = CSET[rnd() % NC];
      else { h.j0 = rnd() % 10; h.j1 = rnd() % 10; }
      int hs = genome_cost(&h) <= 71 ? score(&h) : -1;
      if (hs >= sc) { g = h; sc = hs; }
    }
    if (sc > bestsc) {
      bestsc = sc; best = g;
      printf("best %d/256 cost=%d j0=%d j1=%d ops:", sc, genome_cost(&g), g.j0, g.j1);
      for (int i = 0; i < g.n; i++) printf(" %d(%u)", g.op[i], g.c[i]);
      printf("\n"); fflush(stdout);
    }
  }
  printf("FINAL %d/256 depth=%d\n", bestsc, depth);
  return 0;
}
