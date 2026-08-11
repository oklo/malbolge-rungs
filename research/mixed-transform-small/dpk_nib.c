/* L2.R0.xor-1 (256-byte program cap): exact transfer-matrix DP over the
 * in-program operand table, with a free dispatch offset K0.
 *
 * Architecture (see docs/attempts/2026-08-11-claude-xor-1.md):
 *   IN                 A = b
 *   MOVD x3            D -> cell 71
 *   CRZ, CRZ           operands m[71] = m[72] = 121 = 11111_3
 *                      crazy(crazy(b,121),121) = b, so cell 72 now holds b
 *   MOVD x3            D -> m[72] + 1 = b + 1
 *   NOP x (K0-1)       every instruction post-increments D, so NOPs are a
 *                      free dispatch offset: D = b + K0
 *   CRZ x k            operands m[b+K0 .. b+K0+k-1]
 *   OUT, HALT          out = A mod 256, want b ^ 0x51
 *
 * Unlike the stride-9 layout of L2.R0d.xor-1-len4096, the 256-byte cap forces
 * stride 1, so adjacent inputs SHARE operand cells.  That sharing is what this
 * DP resolves exactly: the state is the choice made for the last k-1 cells.
 *
 * spec file, one line per address:
 *   <addr> F <value>   cell fixed at table-read time (code residue / pointer)
 *   <addr> X <value>   cell fixed AND input-dependent or code-corrupting:
 *                      any window touching it is unscoreable
 *   <addr> E           cell never executed and free: eight loader-valid bytes
 *
 * usage: dpk <spec> <k> <L> <K0> [emit]
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static const int OPS[8] = {4, 5, 23, 39, 40, 62, 68, 81};
static int crazy_trit(int a, int d) {
  static const int T[3][3] = {{1, 0, 0}, {1, 0, 2}, {2, 2, 1}};
  return T[d][a];
}
static unsigned crazy(unsigned a, unsigned d) {
  unsigned r = 0, f = 1;
  for (int i = 0; i < 10; i++) { r += (unsigned)crazy_trit(a % 3, d % 3) * f; a /= 3; d /= 3; f *= 3; }
  return r;
}
#define AMAX 700
static int NV[AMAX], VAL[AMAX][8], BAD[AMAX];
static unsigned *MEMO;
static inline unsigned cz(unsigned acc, int v) {
  if (v >= 33 && v <= 126) return MEMO[(v - 33) * 59049u + acc];
  return crazy(acc, (unsigned)v);
}
int main(int argc, char **argv) {
  if (argc < 5) { fprintf(stderr, "usage: dpk <spec> <k> <L> <K0> [emit]\n"); return 2; }
  FILE *f = fopen(argv[1], "r");
  if (!f) { perror("spec"); return 1; }
  int K = atoi(argv[2]), L = atoi(argv[3]), K0 = atoi(argv[4]);
  int emit = (argc > 5);
  for (int a = 0; a < AMAX; a++) { NV[a] = 1; VAL[a][0] = 33; BAD[a] = 1; }
  char kind[8]; int addr, val;
  while (fscanf(f, "%d %7s", &addr, kind) == 2) {
    if (addr < 0 || addr >= AMAX) { fprintf(stderr, "addr out of range\n"); return 1; }
    if (kind[0] == 'E') {
      int n = 0;
      for (int v = 33; v <= 126; v++) { int c = (v + addr) % 94; for (int i = 0; i < 8; i++) if (c == OPS[i]) { VAL[addr][n++] = v; break; } }
      NV[addr] = n; BAD[addr] = 0;
    } else {
      if (fscanf(f, "%d", &val) != 1) { fprintf(stderr, "bad spec\n"); return 1; }
      NV[addr] = 1; VAL[addr][0] = val; BAD[addr] = (kind[0] == 'X');
    }
  }
  fclose(f);
  MEMO = malloc(94ull * 59049 * sizeof(unsigned));
  for (int bi = 0; bi < 94; bi++) for (unsigned x = 0; x < 59049u; x++) MEMO[bi * 59049u + x] = crazy(x, (unsigned)(bi + 33));

  /* Cells at addresses >= L are the crazy fill; they are determined, not free. */
  int LAST = 255 + K0 + K - 1;
  if (LAST >= AMAX) { fprintf(stderr, "AMAX too small\n"); return 1; }

  long SW = 1; for (int i = 0; i < K - 1; i++) SW *= 8;
  int *dp = malloc(SW * sizeof(int)), *nd = malloc(SW * sizeof(int));
  unsigned char *par = calloc((size_t)AMAX * SW, 1);
  int *pst = malloc(sizeof(int) * (size_t)AMAX * SW);
  for (long i = 0; i < SW; i++) dp[i] = 0;

  /* Walk address a = the LAST cell of input b's window: a = b + K0 + K - 1.
   * Only addresses < L are choosable; the fill tail is handled after. */
  int amin = K0 + K - 1;                 /* a for b = 0 */
  for (int a = amin; a < L; a++) {
    for (long i = 0; i < SW; i++) nd[i] = -1;
    int b = a - (K0 + K - 1);
    int scor = (b >= 0 && b <= 255);
    for (int j = 0; j < K; j++) { int ad = b + K0 + j; if (ad < 0 || BAD[ad]) scor = 0; }
    for (long s = 0; s < SW; s++) {
      if (dp[s] < 0) continue;
      unsigned acc = (unsigned)(b < 0 ? 0 : b); long t = s; int ok = 1;
      for (int j = 0; j < K - 1; j++) {
        int ad = b + K0 + j, ix = t & 7; t >>= 3;
        if (ad < 0 || ix >= NV[ad]) { ok = 0; break; }
        acc = cz(acc, VAL[ad][ix]);
      }
      if (!ok) continue;
      for (int d = 0; d < NV[a]; d++) {
        unsigned r = cz(acc, VAL[a][d]);
        int sc = dp[s] + ((scor && (int)(r % 256) == (((b<<4)|(b>>4))&0xff)) ? 1 : 0);
        long ns = (s >> 3) | ((long)d << (3 * (K - 2)));
        if (sc > nd[ns]) { nd[ns] = sc; par[(size_t)a * SW + ns] = (unsigned char)d; pst[(size_t)a * SW + ns] = (int)s; }
      }
    }
    memcpy(dp, nd, SW * sizeof(int));
  }

  /* Tail: inputs whose window runs past L into the crazy fill. */
  int bestsc = -1; long bestst = 0;
  for (long s = 0; s < SW; s++) {
    if (dp[s] < 0) continue;
    unsigned cell[AMAX]; long t = s; int ok = 1;
    int base = L - (K - 1);
    for (int j = 0; j < K - 1; j++) { int ad = base + j, ix = t & 7; t >>= 3; if (ix >= NV[ad]) { ok = 0; break; } cell[ad] = (unsigned)VAL[ad][ix]; }
    if (!ok) continue;
    for (int i = L; i <= LAST; i++) cell[i] = crazy(cell[i - 1], cell[i - 2]);
    int sc = dp[s];
    for (int b = 0; b <= 255; b++) {
      if (b + K0 + K - 1 < L) continue;          /* already scored by the DP */
      int good = 1;
      for (int j = 0; j < K; j++) { int ad = b + K0 + j; if (ad < base || BAD[ad]) { good = 0; break; } }
      if (!good) continue;
      unsigned acc = (unsigned)b;
      for (int j = 0; j < K; j++) acc = cz(acc, cell[b + K0 + j]);
      if ((int)(acc % 256) == (((b<<4)|(b>>4))&0xff)) sc++;
    }
    if (sc > bestsc) { bestsc = sc; bestst = s; }
  }
  fprintf(stderr, "k=%d K0=%d L=%d best=%d/256\n", K, K0, L, bestsc);
  if (!emit) return 0;
  int ch[AMAX]; for (int i = 0; i < AMAX; i++) ch[i] = -1;
  long st = bestst;
  for (int a = L - 1; a >= amin; a--) { int d = par[(size_t)a * SW + st]; int ps = pst[(size_t)a * SW + st]; ch[a] = VAL[a][d]; st = ps; }
  /* st now encodes the choice made for cells amin-(K-1) .. amin-1 */
  { long t = st; for (int j = 0; j < K - 1; j++) { int ad = amin - (K - 1) + j; int ix = t & 7; t >>= 3; if (ad >= 0 && ix < NV[ad]) ch[ad] = VAL[ad][ix]; } }
  for (int a = 0; a < amin - (K - 1) && a < L; a++) ch[a] = VAL[a][0];
  for (int a = 0; a < L; a++) if (ch[a] < 33 || ch[a] > 126) ch[a] = VAL[a][0];
  for (int a = 0; a < L; a++) printf("%d %d\n", a, ch[a]);
  return 0;
}
