/* cov48: exact DP over the identity-dispatch table architecture.
 *
 * Architecture (same as research/cov40/table_dp.c, corrected and extended):
 *   IN                        A = b
 *   CRAZY W1, CRAZY W2        A = v = b + K0   (low 6 trits = b, high trits = K0/729)
 *                             v parked in the cell the 2nd CRAZY wrote
 *   MOVD chain                D = v + 1
 *   k x CRAZY                 A = crazy^k(v, mem[v+1..v+k])
 *   OUT, HALT                 out = A mod 256, target = b ^ 0x51
 *
 * CORRECTION vs research/cov40/table_dp.c: that file's legal() returned
 *     33 + ((op + 33 - a) mod 94)
 * The loader (crates/classic_malbolge, crates/harness/src/dispatch.rs) requires
 *     (byte + address) mod 94 in {4,5,23,39,40,62,68,81},  byte in 33..126
 * so the legal byte is ((op - a) mod 94), bumped by +94 when below 33.  The two
 * differ for every address, so cov40's per-k numbers are for the wrong byte set.
 *
 * Consecutive inputs share table cells for k >= 2, so cell choices are coupled
 * along a chain: exact optimum by transfer-matrix DP over 8^(k-1) states.
 */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static const int M[3][3]={{1,0,0},{1,0,2},{2,2,1}};
static const int OPS[8]={4,5,23,39,40,62,68,81};

static int crz(int a,int d){int r=0,p=1;for(int i=0;i<10;i++){r+=M[d%3][a%3]*p;p*=3;a/=3;d/=3;}return r;}

static void legal(int a,int out[8]){
    for(int i=0;i<8;i++){
        int b=((OPS[i]-a)%94+94)%94;
        if(b<33) b+=94;
        out[i]=b;
    }
}

int TGT[256];
static int L[600][8];

/* returns best hits; if choice != NULL, fills choice[0..NC-1] with byte values */
static int run(int K0,int k,int *choice){
    int base=K0+1, NC=256+k-1;
    if(base+NC>4096) return -1;
    for(int c=0;c<NC;c++) legal(base+c,L[c]);
    int S=1; for(int i=1;i<k;i++) S*=8;
    int *dp=malloc(sizeof(int)*S), *nd=malloc(sizeof(int)*S);
    unsigned char *par=NULL; int *pst=NULL;
    if(choice){ par=malloc((size_t)NC*S); pst=malloc(sizeof(int)*(size_t)NC*S); }
    for(int s=0;s<S;s++) dp[s]=0;      /* first k-1 cells free, all states seeded */
    for(int c=k-1;c<NC;c++){
        for(int s=0;s<S;s++) nd[s]=-1;
        int b=c-(k-1);
        for(int s=0;s<S;s++){
            if(dp[s]<0) continue;
            for(int nx=0;nx<8;nx++){
                int ops[8]; int ss=s;
                for(int i=0;i<k-1;i++){ ops[i]=L[b+i][ss%8]; ss/=8; }
                ops[k-1]=L[c][nx];
                int A=b+K0;
                for(int i=0;i<k;i++) A=crz(A,ops[i]);
                int hit=((A&255)==TGT[b]);
                int nstate=(k==1)?0:((s/8)+nx*(S/8));
                int val=dp[s]+hit;
                if(val>nd[nstate]){ nd[nstate]=val;
                    if(choice){ par[(size_t)c*S+nstate]=(unsigned char)nx; pst[(size_t)c*S+nstate]=s; } }
            }
        }
        memcpy(dp,nd,sizeof(int)*S);
    }
    int best=-1,bs=0; for(int s=0;s<S;s++) if(dp[s]>best){best=dp[s];bs=s;}
    if(choice){
        int st=bs;
        for(int c=NC-1;c>=k-1;c--){
            int nx=par[(size_t)c*S+st]; int ps=pst[(size_t)c*S+st];
            choice[c]=L[c][nx]; st=ps;
        }
        int ss=st; for(int i=0;i<k-1;i++){ choice[i]=L[i][ss%8]; ss/=8; }
        free(par); free(pst);
    }
    free(dp); free(nd);
    return best;
}

int main(int argc,char**argv){
    for(int b=0;b<256;b++) TGT[b]=b^0x51;
    if(argc>=3){
        int K0=atoi(argv[1]),k=atoi(argv[2]);
        int NC=256+k-1; int *ch=malloc(sizeof(int)*NC);
        int r=run(K0,k,ch);
        fprintf(stderr,"K0=%d k=%d best=%d\n",K0,k,r);
        for(int c=0;c<NC;c++) printf("%d %d\n",K0+1+c,ch[c]);
        return 0;
    }
    for(int m=1;m<=5;m++){
        int K0=729*m;
        for(int k=1;k<=6;k++){
            int r=run(K0,k,NULL);
            if(r>=0) printf("K0=%-5d table@%-5d k=%d : %3d / 256\n",K0,K0+1,k,r);
            fflush(stdout);
        }
    }
    return 0;
}
