/* cov40: the identity-dispatch table architecture, scored exactly by DP.
 *
 * Two CRAZY layers with the SAME word W (trits 0..5 = 1 -> M1 o M1 = identity;
 * trits 6..9 chosen to add a constant K0) leave
 *      A = v = b + K0        (as a 10-trit word, positions 0..5 are b's)
 * and v parked in the cell the second CRAZY wrote.  One MOVD on that cell sets
 *      D = v + 1 = b + K0 + 1
 * so the input itself is the dispatch index: a 256-entry table with no per-entry
 * construction cost.  The table lives in the program's own bytes at addresses
 * K0+1 .. K0+256+k, past the code, never executed.
 *
 * Each table byte is constrained by Malbolge source validity: at address a the
 * byte must satisfy (val - 33 + a) mod 94 in {4,5,23,39,40,62,68,81}, i.e. it has
 * exactly EIGHT legal values.  Consecutive inputs share table cells when the tail
 * is k >= 2 layers deep, so the choices are coupled -- but only locally, along a
 * chain, so the exact optimum is a transfer-matrix DP over 8^(k-1) states.
 *
 * Reports the exact maximum hits for k = 1,2,3 and every reachable K0.
 */
#include <stdio.h>
#include <string.h>

static const int M[3][3]={{1,0,0},{1,0,2},{2,2,1}};
static const int OPS[8]={4,5,23,39,40,62,68,81};

static int crz(int a,int d){int r=0,p=1;for(int i=0;i<10;i++){r+=M[d%3][a%3]*p;p*=3;a/=3;d/=3;}return r;}

/* the eight source-valid byte values at address a */
static void legal(int a,int out[8]){
    for(int i=0;i<8;i++){
        int v = (((OPS[i] - a) % 94) + 94) % 94; if(v<33) v+=94;
        out[i]=v;
    }
}

int main(void){
    int TGT[256]; for(int b=0;b<256;b++) TGT[b]=b^0x51;
    int K0S[5]={729,1458,2187,2916,3645};

    for(int ki=0;ki<5;ki++){
        int K0=K0S[ki];
        for(int k=1;k<=3;k++){
            int base=K0+1;                 /* address of table cell for b = 0 */
            int NC=256+k-1;                /* cells used: base .. base+NC-1 */
            if(base+NC>4096) continue;
            int L[512][8];
            for(int c=0;c<NC;c++) legal(base+c,L[c]);

            /* state = tuple of the last (k-1) cell choices; DP left to right.
               When we fix cell index c (>= k-1), input b = c-(k-1) is fully
               determined by choices for cells c-k+1..c. */
            int S = 1; for(int i=1;i<k;i++) S*=8;
            static int dp[2][64], nd[64];
            for(int s=0;s<S;s++) dp[0][s]=-1;
            /* seed: choose the first k-1 cells */
            if(k==1){ dp[0][0]=0; }
            else {
                for(int s=0;s<S;s++) dp[0][s]=0;
            }
            int cur=0;
            for(int c=k-1;c<NC;c++){
                for(int s=0;s<S;s++) nd[s]=-1;
                for(int s=0;s<S;s++){
                    if(dp[cur][s]<0) continue;
                    for(int nx=0;nx<8;nx++){
                        /* reconstruct the k operands for input b = c-(k-1) */
                        int b=c-(k-1);
                        int ops[3]; int ss=s;
                        for(int i=0;i<k-1;i++){ ops[i]=L[c-(k-1)+i][ss%8]; ss/=8; }
                        ops[k-1]=L[c][nx];
                        int A=b+K0;
                        for(int i=0;i<k;i++) A=crz(A,ops[i]);
                        int hit = ((A&255)==TGT[b]);
                        int nstate = (k==1)?0:((s/8) + nx*(S/8));
                        int val=dp[cur][s]+hit;
                        if(val>nd[nstate]) nd[nstate]=val;
                    }
                }
                memcpy(dp[1-cur],nd,sizeof nd); cur=1-cur;
            }
            int best=0; for(int s=0;s<S;s++) if(dp[cur][s]>best) best=dp[cur][s];
            printf("K0=%-5d table@%-5d k=%d layers : %d / 256\n",K0,base,k,best);
            fflush(stdout);
        }
    }
    return 0;
}
