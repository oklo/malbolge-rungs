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
static unsigned R[10][256];
static int score(const G *g) {
  int sc = 0;
  for (int b = 0; b < 256; b++) {
    unsigned acc = R[g->j0][b], s = R[g->j1][b];
    for (int i = 0; i < g->n; i++) {
      switch (g->op[i]) {
        case 0: acc = crazy(acc, g->c[i]); break;
        case 1: acc = crazy(g->c[i], acc); break;
        case 2: acc = rotr(acc); break;
        case 3: acc = crazy(acc, s); break;
        case 4: acc = crazy(s, acc); break;
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
  for (int b = 0; b < 256; b++) { unsigned w = (unsigned)b; for (int j = 0; j < 10; j++) { R[j][b] = w; w = rotr(w); } }
  time_t t0 = time(NULL);
  G best; memset(&best, 0, sizeof best); int bestsc = -1;
  while (time(NULL) - t0 < secs) {
    G g; g.j0 = rnd() % 10; g.j1 = rnd() % 10; g.n = depth;
    for (int i = 0; i < depth; i++) { g.op[i] = rnd() % 5; g.c[i] = rnd() % 59049u; }
    int sc = score(&g);
    for (int it = 0; it < 20000; it++) {
      G h = g; int m = rnd() % 3;
      int i = rnd() % depth;
      if (m == 0) h.op[i] = rnd() % 5;
      else if (m == 1) h.c[i] = rnd() % 59049u;
      else { h.j0 = rnd() % 10; h.j1 = rnd() % 10; }
      int hs = score(&h);
      if (hs >= sc) { g = h; sc = hs; }
    }
    if (sc > bestsc) {
      bestsc = sc; best = g;
      printf("best %d/256  j0=%d j1=%d ops:", sc, g.j0, g.j1);
      for (int i = 0; i < g.n; i++) printf(" %d(%u)", g.op[i], g.c[i]);
      printf("\n"); fflush(stdout);
    }
  }
  printf("FINAL %d/256 depth=%d\n", bestsc, depth);
  return 0;
}
