/* map16 (adapted from research/map12-low/chain.c): find a buildable dispatch
 * operand pair (W1,W2) with crazy(crazy(b,W1),W2) = (b mod 243) + K0 for the
 * sixteen rung inputs.  Trits 0..4 must survive (identity, w1=w2=1); trit 5
 * is crushed to a constant because 0xf6 = 246 is the only input >= 243 and the
 * sixteen inputs stay distinct mod 243; trits 6..9 are free constants.
 * So K0 is any multiple of 243.  Original header follows.
 *
 * map12-low: find a buildable dispatch operand pair (W1,W2) with
 * crazy(crazy(b,W1),W2) = b + K0 for the twelve rung inputs only.
 *
 * Derived from research/cov48/chain2.c.  The one change that matters: cov48
 * needed the identity on trits 0..5 (all 256 inputs must index distinct table
 * entries), which forces K0 to be a multiple of 729.  Every input of
 * L2.FM2l.xor51-map12-low is < 81, so only trits 0..3 must survive and trits
 * 4..9 of the input are 0 -- M[w2][M[w1][0]] can be made 0, 1 or 2, so K0 may
 * be any multiple of 81.  That widens the reachable high-part constant H (see
 * research/map12-low/sweep.c) from 10 values to 32.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define NW 59049
static const int M[3][3]={{1,0,0},{1,0,2},{2,2,1}};
static int CR5[243][243];
static void mk(void){for(int a=0;a<243;a++)for(int d=0;d<243;d++){int r=0,p=1,aa=a,dd=d;for(int i=0;i<5;i++){r+=M[dd%3][aa%3]*p;p*=3;aa/=3;dd/=3;}CR5[a][d]=r;}}
static inline int crz(int a,int d){return CR5[a%243][d%243]+243*CR5[a/243][d/243];}
static inline int rot(int v){return v/3+(v%3)*19683;}
static inline int tr(int v,int i){for(int k=0;k<i;k++)v/=3;return v%3;}
static const char*ENC="5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";
static int codebyte(int a,int c){int b=((c-a)%94+94)%94;if(b<33)b+=94;return b;}
static int xval(int a){return (unsigned char)ENC[codebyte(a,68)-33];}
static int seeds[128],ns=0,cellof[256];
static int dep[NW],pre[NW],pop_[NW],forbid[256];
static void bfs(int start,int forceCrazyFirst){
    for(int i=0;i<NW;i++)dep[i]=-1;
    int*q=malloc(NW*sizeof(int));int qh=0,qt=0;dep[start]=0;pre[start]=-1;pop_[start]=-2;q[qt++]=start;
    while(qh<qt){int v=q[qh++];
        for(int i=0;i<ns;i++){if(forbid[seeds[i]])continue;int w=crz(v,seeds[i]);if(dep[w]<0){dep[w]=dep[v]+1;pre[w]=v;pop_[w]=seeds[i];q[qt++]=w;}}
        if(!(forceCrazyFirst&&dep[v]==0)){int w=rot(v);if(dep[w]<0){dep[w]=dep[v]+1;pre[w]=v;pop_[w]=-1;q[qt++]=w;}}}
    free(q);
}
static void bfs2(int start){
    for(int i=0;i<NW;i++)dep[i]=-1;
    int*q=malloc(NW*sizeof(int));int qh=0,qt=0;
    for(int i=0;i<ns;i++){if(forbid[seeds[i]])continue;int w=crz(start,seeds[i]);
        if(dep[w]<0){dep[w]=1;pre[w]=start;pop_[w]=seeds[i];q[qt++]=w;}}
    while(qh<qt){int v=q[qh++];
        for(int i=0;i<ns;i++){if(forbid[seeds[i]])continue;int w=crz(v,seeds[i]);if(dep[w]<0){dep[w]=dep[v]+1;pre[w]=v;pop_[w]=seeds[i];q[qt++]=w;}}
        {int w=rot(v);if(dep[w]<0){dep[w]=dep[v]+1;pre[w]=v;pop_[w]=-1;q[qt++]=w;}}}
    free(q);
}
static int path(int start,int end,int*ops){int n=0,v=end;while(v!=start){ops[n++]=pop_[v];v=pre[v];}
    for(int i=0;i<n/2;i++){int t=ops[i];ops[i]=ops[n-1-i];ops[n-1-i]=t;}return n;}
static int K0;
static const int INPUTS[16]={0x02,0x06,0x09,0x30,0x82,0x6f,0xa7,0xc0,0xc5,0xf6,0x1c,0x87,0xf0,0x2d,0x4a,0x85};
static int good(int w1,int w2){for(int i=0;i<16;i++){int b=INPUTS[i]; if(crz(crz(b,w1),w2)!=(b%243)+K0) return 0;} return 1;}

int main(int argc,char**argv){
    K0=argc>1?atoi(argv[1]):2916;
    mk();
    for(int a=34;a<128;a++){int s=xval(a);int d=0;for(int i=0;i<ns;i++)if(seeds[i]==s)d=1;if(!d){cellof[s]=a;seeds[ns++]=s;}}
    /* candidate words: trits 0..5 = 1, trits 6,7 forced, 8,9 free */
    int cand[1024],nc=0;
    for(int t5=0;t5<3;t5++)for(int t6=0;t6<3;t6++)for(int t7=0;t7<3;t7++)
    for(int t8=0;t8<3;t8++)for(int t9=0;t9<3;t9++){
        int w=121+t5*243+t6*729+t7*2187+t8*6561+t9*19683; cand[nc++]=w; }
    memset(forbid,0,sizeof forbid);
    bfs(0,0);
    static int d0[NW],p0[NW],o0[NW];
    memcpy(d0,dep,sizeof d0); memcpy(p0,pre,sizeof p0); memcpy(o0,pop_,sizeof o0);
    int best=1<<30,bW1=-1,bW2=-1,bo1[64],bn1=0,bo2[64],bn2=0;
    for(int i=0;i<nc;i++){
        int W1=cand[i]; if(d0[W1]<0||d0[W1]>10) continue;
        memcpy(dep,d0,sizeof d0);memcpy(pre,p0,sizeof p0);memcpy(pop_,o0,sizeof o0);
        int o1[64],k1=path(0,W1,o1);
        memset(forbid,0,sizeof forbid);
        for(int t=0;t<k1;t++) if(o1[t]>=0) forbid[o1[t]]=1;
        /* leg2 must be NON-EMPTY even when W2 == W1: the first CRAZY overwrites
           W1's cell, so the second operand needs its own cell.  Seed the BFS at
           depth 1 with every fresh-cell CRAZY successor of W1 instead of at W1. */
        bfs2(W1);
        for(int j=0;j<nc;j++){
            int W2=cand[j]; if(dep[W2]<0) continue;
            if(!good(W1,W2)) continue;
            int o2[64],k2=path(W1,W2,o2);
            /* W2 must end up parked IN a cell: the last leg2 op has to be a
               CRAZY (ROT touches only the accumulator, never memory). */
            if(k2<1||o2[k2-1]<0) continue;
            /* a seed may be spent once: each CRAZY consumes the cell it writes */
            int u[256]; memset(u,0,sizeof u); int dup=0;
            for(int t=0;t<k1;t++) if(o1[t]>=0 && u[o1[t]]++) dup=1;
            for(int t=0;t<k2;t++) if(o2[t]>=0 && u[o2[t]]++) dup=1;
            if(dup) continue;
            int tot=k1+k2;
            if(tot<best){best=tot;bW1=W1;bW2=W2;bn1=k1;memcpy(bo1,o1,sizeof o1);bn2=k2;memcpy(bo2,o2,sizeof o2);}
        }
    }
    if(bW1<0){printf("K0=%d: NO buildable pair\n",K0);return 1;}
    printf("K0=%d  W1=%d W2=%d  total ops=%d\n",K0,bW1,bW2,best);
    printf("leg1 (0->W1):"); for(int i=0;i<bn1;i++) bo1[i]<0?printf(" ROT"):printf(" CRZ(%d)",cellof[bo1[i]]); printf("\n");
    printf("leg2 (W1->W2):"); for(int i=0;i<bn2;i++) bo2[i]<0?printf(" ROT"):printf(" CRZ(%d)",cellof[bo2[i]]); printf("\n");
    printf("PY_CHAIN=[");
    for(int i=0;i<bn1;i++) printf("%s(\"%s\",%d)",i?",":"",bo1[i]<0?"rot":"crz",bo1[i]<0?-1:cellof[bo1[i]]);
    printf("]\nPY_CHAIN2=[");
    for(int i=0;i<bn2;i++) printf("%s(\"%s\",%d)",i?",":"",bo2[i]<0?"rot":"crz",bo2[i]<0?-1:cellof[bo2[i]]);
    printf("]\n");
    int used[256]; memset(used,0,sizeof used); int dup=0;
    for(int i=0;i<bn1;i++) if(bo1[i]>=0){ if(used[bo1[i]]++) dup=1; }
    for(int i=0;i<bn2;i++) if(bo2[i]>=0){ if(used[bo2[i]]++) dup=1; }
    printf("seed reuse: %s\n",dup?"YES (bad)":"none");
    return 0;
}
