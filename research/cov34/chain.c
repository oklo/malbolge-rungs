/* cov34 stage 3: pick the cheapest constructible operand pair and emit its op chain.
 *
 * A build is a single chain from A = 0:
 *      A <- crazy(A, x(q))   fresh cell q   (writes A into q)
 *      A <- rot(A)           re-point D at the cell A was just written to
 * The chain is cut at one point: the word standing there is operand #1 and stays
 * in its cell, so the continuation's first op must be a CRAZY on a fresh cell
 * (a ROT would rotate operand #1's cell and destroy it).  No accumulator reset
 * is needed -- the second operand is built starting from the first.
 * Every CRAZY consumes a distinct cell, and x() is injective on 34..127, so all
 * seed bytes in the whole chain must be distinct.
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
static int dep[NW],pre[NW],pop_[NW];
/* BFS from `start`; if forceCrazyFirst, the first op may not be a ROT. */
static int forbid[256];
static void bfs(int start,int forceCrazyFirst){
    for(int i=0;i<NW;i++)dep[i]=-1;
    int*q=malloc(NW*sizeof(int));int qh=0,qt=0;dep[start]=0;pre[start]=-1;pop_[start]=-2;q[qt++]=start;
    while(qh<qt){int v=q[qh++];
        for(int i=0;i<ns;i++){if(forbid[seeds[i]])continue;int w=crz(v,seeds[i]);if(dep[w]<0){dep[w]=dep[v]+1;pre[w]=v;pop_[w]=seeds[i];q[qt++]=w;}}
        if(!(forceCrazyFirst&&dep[v]==0)){int w=rot(v);if(dep[w]<0){dep[w]=dep[v]+1;pre[w]=v;pop_[w]=-1;q[qt++]=w;}}}
    free(q);
}
static int score(int c1,int c2){int n=0;for(int b=0;b<256;b++){int a=crz(crz(b,c1),c2);if((a%256)==(b^0x51))n++;}return n;}
static int ok1(int v){for(int i=0;i<5;i++)if(tr(v,i)!=1)return 0;return 1;}
static int ok2(int v){for(int i=0;i<4;i++)if(tr(v,i)!=1)return 0;return tr(v,4)==0;}
static int path(int start,int end,int*ops){int n=0,v=end;while(v!=start){ops[n++]=pop_[v];v=pre[v];}
    for(int i=0;i<n/2;i++){int t=ops[i];ops[i]=ops[n-1-i];ops[n-1-i]=t;}return n;}

int main(void){
    mk();
    for(int a=34;a<128;a++){int s=xval(a);int d=0;for(int i=0;i<ns;i++)if(seeds[i]==s)d=1;if(!d){cellof[s]=a;seeds[ns++]=s;}}
    int *C1=malloc(NW*4),n1=0,*C2=malloc(NW*4),n2=0;
    bfs(0,0);
    int *d0=malloc(NW*4); memcpy(d0,dep,NW*4);
    for(int v=0;v<NW;v++){if(d0[v]<0)continue;if(ok1(v))C1[n1++]=v;if(ok2(v))C2[n2++]=v;}
    int best=1<<30,bP=-1,bQ=-1,bFirstIsC1=0,bops1[64],bn1=0,bops2[64],bn2=0;
    for(int pass=0;pass<2;pass++){
        int *F=pass?C2:C1,nf=pass?n2:n1,*S=pass?C1:C2,nsS=pass?n1:n2;
        for(int i=0;i<nf;i++){
            int P=F[i]; if(d0[P]<0||d0[P]>8) continue;
            memset(forbid,0,sizeof forbid); bfs(0,0);
            int o1[64],k1=path(0,P,o1);
            memset(forbid,0,sizeof forbid);
            for(int t=0;t<k1;t++) if(o1[t]>=0) forbid[o1[t]]=1;   /* leg1 cells are consumed */
            bfs(P,1);
            for(int j=0;j<nsS;j++){int Q=S[j];if(dep[Q]<0)continue;
                int c1=pass?Q:P,c2=pass?P:Q;
                if(score(c1,c2)<34)continue;
                int tot=k1+dep[Q];
                if(tot<best){best=tot;bP=P;bQ=Q;bFirstIsC1=!pass;
                    bn1=k1;memcpy(bops1,o1,sizeof o1);bn2=path(P,Q,bops2);}}
        }
    }
    printf("best total ops = %d  first=%d second=%d  (first is %s)\n",best,bP,bQ,bFirstIsC1?"c1":"c2");
    int *ops1=bops1,*ops2=bops2,n_1=bn1,n_2=bn2;
    printf("leg1 (0 -> %d):",bP); for(int i=0;i<n_1;i++) ops1[i]<0?printf(" ROT"):printf(" CRZ(seed=%d,cell=%d)",ops1[i],cellof[ops1[i]]); printf("\n");
    printf("leg2 (%d -> %d):",bP,bQ); for(int i=0;i<n_2;i++) ops2[i]<0?printf(" ROT"):printf(" CRZ(seed=%d,cell=%d)",ops2[i],cellof[ops2[i]]); printf("\n");
    int c1=bFirstIsC1?bP:bQ, c2=bFirstIsC1?bQ:bP;
    printf("c1=%d c2=%d score=%d\n",c1,c2,score(c1,c2));
    printf("c1 trits(0..9):"); for(int i=0;i<10;i++)printf(" %d",tr(c1,i)); printf("\n");
    printf("c2 trits(0..9):"); for(int i=0;i<10;i++)printf(" %d",tr(c2,i)); printf("\n");
    /* seed distinctness across both legs */
    int used[256]; memset(used,0,sizeof used); int dup=0;
    for(int i=0;i<n_1;i++) if(ops1[i]>=0){ if(used[ops1[i]]++) dup=1; }
    for(int i=0;i<n_2;i++) if(ops2[i]>=0){ if(used[ops2[i]]++) dup=1; }
    printf("seed reuse across chain: %s\n", dup?"YES (needs fixing)":"none");
    return 0;
}
