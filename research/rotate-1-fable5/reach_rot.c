/* Per-input reachability closure for L2.R2.rotate-1 — the "ROT in the walk" BFS
 * every xor record names and none has run (state = the 10-trit accumulator,
 * 59049 nodes).  For each input byte b, starting from acc = b (the parked
 * value the dispatch hands the walk), which accumulator values can ANY
 * stride-1 walk reach, and in particular some word == (((b << 1) | (b >> 7)) & 0xFF) mod 256?
 *
 * Edge sets, cumulative:
 *   A: acc -> crazy(acc, v), v in 33..126     (CRZ against a fresh table byte)
 *   B: A + acc -> rotr(acc)                   (ROT of a cell holding acc:
 *                                              write-then-rot, the record's
 *                                              re-entry gadget)
 *   C: B + acc -> crazy(v, acc), v in 33..126 (roles swapped: cell holds acc,
 *                                              A holds a table byte)
 *
 * This is an UPPER envelope on per-input reachability for every architecture
 * that carries per-input information only in A / cells written from A; it
 * ignores sharing, layout, and gadget cost entirely.  A target unreachable
 * here is unreachable for the whole family.  usage: reach [maxdepth]
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define M 59049
static int ct[3][3] = {{1, 0, 0}, {1, 0, 2}, {2, 2, 1}}; /* ct[d][a] */
static unsigned crazy(unsigned a, unsigned d) {
  unsigned r = 0, f = 1;
  for (int i = 0; i < 10; i++) { r += (unsigned)ct[d % 3][a % 3] * f; a /= 3; d /= 3; f *= 3; }
  return r;
}
static unsigned rotr(unsigned w) { return w / 3 + (w % 3) * 19683u; }

static unsigned *czAV, *czVA, *rt;
static int dist_[M];
static unsigned q[M];

static int bfs(int b, int variant, int maxd, int *mind) {
  memset(dist_, -1, sizeof(dist_));
  int head = 0, tail = 0, target = ((b << 1) | (b >> 7)) & 0xFF;
  dist_[b] = 0; q[tail++] = (unsigned)b;
  int found = -1;
  while (head < tail) {
    unsigned x = q[head++];
    int dx = dist_[x];
    if ((int)(x % 256) == target && dx > 0) { found = dx; break; }
    if (dx >= maxd) continue;
    for (int vi = 0; vi < 94; vi++) {
      unsigned y = czAV[(size_t)vi * M + x];
      if (dist_[y] < 0) { dist_[y] = dx + 1; q[tail++] = y; }
      if (variant == 2 || variant == 3) {
        y = czVA[(size_t)vi * M + x];
        if (dist_[y] < 0) { dist_[y] = dx + 1; q[tail++] = y; }
      }
    }
    if (variant == 1 || variant == 2) {
      unsigned y = rt[x];
      if (dist_[y] < 0) { dist_[y] = dx + 1; q[tail++] = y; }
    }
  }
  *mind = found;
  return found >= 0;
}

int main(int argc, char **argv) {
  int maxd = argc > 1 ? atoi(argv[1]) : 24;
  czAV = malloc(sizeof(unsigned) * 94 * M);
  czVA = malloc(sizeof(unsigned) * 94 * M);
  rt = malloc(sizeof(unsigned) * M);
  for (unsigned x = 0; x < M; x++) rt[x] = rotr(x);
  for (int vi = 0; vi < 94; vi++)
    for (unsigned x = 0; x < M; x++) {
      czAV[(size_t)vi * M + x] = crazy(x, (unsigned)(vi + 33));
      czVA[(size_t)vi * M + x] = crazy((unsigned)(vi + 33), x);
    }
  const char *names[4] = {"A: CRZ-only", "B: CRZ+ROT", "C: CRZ+ROT+swapped-CRZ", "D: CRZ+swapped-CRZ (no ROT)"};
  for (int variant = 0; variant < 4; variant++) {
    int n = 0, worst = 0, md;
    int miss[256], nm = 0;
    long sumd = 0;
    for (int b = 0; b < 256; b++) {
      if (bfs(b, variant, maxd, &md)) { n++; if (md > worst) worst = md; sumd += md; }
      else miss[nm++] = b;
    }
    printf("%-24s reachable %3d/256  worst min-depth %2d  mean %.2f  (cap %d)\n",
           names[variant], n, worst, n ? (double)sumd / n : 0.0, maxd);
    if (nm) {
      printf("  unreachable:");
      for (int i = 0; i < nm; i++) printf(" %d", miss[i]);
      printf("\n");
    }
    fflush(stdout);
  }
  return 0;
}
