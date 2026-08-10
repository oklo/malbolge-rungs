/* Exhaustive argmax over the N=2, shift-0 straight-line CRAZY family on xor51.
 *
 * A two-CRAZY straight line computes, per trit position i,
 *     g_i = m_{c2_i} o m_{c1_i},   m0=(1,0,0) m1=(1,0,2) m2=(2,2,1)
 * where c1 is the first CRAZY operand's trit at i and c2 the second's.  A byte
 * has trits 6..9 = 0, so those four positions contribute a constant K.
 *     out(b) = ( sum_{i=0..5} g_i(trit_i(b)) * 3^i + K ) mod 256
 * We enumerate every (c1_i,c2_i) for i=0..5 (9^6) and every K in 0..255, and
 * print every configuration scoring >= THRESH against b XOR 0x51.
 */
#include <stdio.h>
#include <string.h>

static const int M[3][3] = {{1,0,0},{1,0,2},{2,2,1}};
static const int P3[6] = {1,3,9,27,81,243};
#define THRESH 34

int main(void) {
    int g[9][3], gc1[9], gc2[9];
    for (int a = 0; a < 3; a++) for (int c = 0; c < 3; c++) {
        int k = a*3+c; gc1[k]=a; gc2[k]=c;
        for (int t = 0; t < 3; t++) g[k][t] = M[c][M[a][t]];
    }
    int trit[256][6];
    for (int b = 0; b < 256; b++) { int x=b; for (int i=0;i<6;i++){trit[b][i]=x%3;x/=3;} }

    /* contribution of position i with pair index k, per input byte */
    static unsigned char contrib[6][9][256];
    for (int i=0;i<6;i++) for (int k=0;k<9;k++) for (int b=0;b<256;b++)
        contrib[i][k][b] = (unsigned char)((g[k][trit[b][i]] * P3[i]) % 256);

    static unsigned char lo[729][256], hi[729][256];
    for (int u=0;u<729;u++) {
        int a=u%9,bb=(u/9)%9,c=u/81;
        for (int b=0;b<256;b++) lo[u][b]=(unsigned char)(contrib[0][a][b]+contrib[1][bb][b]+contrib[2][c][b]);
        for (int b=0;b<256;b++) hi[u][b]=(unsigned char)(contrib[3][a][b]+contrib[4][bb][b]+contrib[5][c][b]);
    }
    unsigned char tgt[256];
    for (int b=0;b<256;b++) tgt[b]=(unsigned char)(b^0x51);

    int best=0; long nhit=0;
    for (int u=0;u<729;u++) for (int v=0;v<729;v++) {
        int cnt[256]; memset(cnt,0,sizeof cnt);
        const unsigned char *L=lo[u], *H=hi[v];
        for (int b=0;b<256;b++) cnt[(unsigned char)(tgt[b]-L[b]-H[b])]++;
        for (int K=0;K<256;K++) {
            if (cnt[K]>best) best=cnt[K];
            if (cnt[K]>=THRESH) {
                nhit++;
                int p[6]={u%9,(u/9)%9,u/81,v%9,(v/9)%9,v/81};
                printf("score=%d K=%d c1=", cnt[K], K);
                for (int i=5;i>=0;i--) printf("%d", gc1[p[i]]);
                printf(" c2=");
                for (int i=5;i>=0;i--) printf("%d", gc2[p[i]]);
                printf("\n");
            }
        }
    }
    fprintf(stderr, "max=%d  configs>=%d: %ld\n", best, THRESH, nhit);
    return 0;
}
