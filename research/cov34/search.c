/* cov34: find a constructible two-CRAZY operand pair scoring 34/256 on xor51.
 *
 * Stage 1 fixes the target: the exhaustive argmax (argmax.c) says every 34-point
 * of the N=2 family needs
 *      c1 trits 0..4 = 1                       (identity at 0..3, m1 at 4)
 *      c2 trits 0..3 = 1, trit 4 = 0           (g_4 = m0 o m1 = (0,1,0))
 *      high trits summing to the constant 81
 * Stage 2 asks which words the machine can actually put in a cell.  Ops, as a
 * register machine on the accumulator (every op also writes A into the cell):
 *      A <- crazy(A, x(q))   fresh cell q, seed byte x(q)
 *      A <- rot(A)           re-point D at the cell A was just written to
 *      A <- crazy(A, u)      u a value standing in another cell (cross layer)
 * V1 = closure of {0} under the first two.  V2 adds one cross-crazy layer.
 * Every structurally-valid pair is then scored by direct simulation.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define NW 59049
static const int M[3][3] = {{1,0,0},{1,0,2},{2,2,1}};   /* M[d][a] */
static int CR5[243][243];

static void mk_tables(void){
    for(int a=0;a<243;a++)for(int d=0;d<243;d++){
        int r=0,p=1,aa=a,dd=d;
        for(int i=0;i<5;i++){r+=M[dd%3][aa%3]*p;p*=3;aa/=3;dd/=3;}
        CR5[a][d]=r;
    }
}
static inline int crz(int a,int d){return CR5[a%243][d%243]+243*CR5[a/243][d/243];}
static inline int rot(int v){return v/3 + (v%3)*19683;}
static inline int tr(int v,int i){for(int k=0;k<i;k++)v/=3;return v%3;}

static const char *ENC="5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";
static int codebyte(int addr,int code){int b=((code-addr)%94+94)%94; if(b<33)b+=94; return b;}
static int xval(int addr){return (unsigned char)ENC[codebyte(addr,68)-33];}

static int *depth, *pred, *pop;   /* pop: seed byte used, or -1 for rot */

static void bfs(int *set_out){
    depth=malloc(NW*sizeof(int)); pred=malloc(NW*sizeof(int)); pop=malloc(NW*sizeof(int));
    for(int i=0;i<NW;i++)depth[i]=-1;
    int *q=malloc(NW*sizeof(int)); int qh=0,qt=0;
    depth[0]=0; pred[0]=-1; pop[0]=-2; q[qt++]=0;
    int seeds[128],ns=0;
    for(int a=34;a<128;a++){int s=xval(a); int dup=0; for(int i=0;i<ns;i++)if(seeds[i]==s)dup=1; if(!dup)seeds[ns++]=s;}
    while(qh<qt){
        int v=q[qh++];
        for(int i=0;i<ns;i++){int w=crz(v,seeds[i]); if(depth[w]<0){depth[w]=depth[v]+1;pred[w]=v;pop[w]=seeds[i];q[qt++]=w;}}
        if(depth[v]>0){int w=rot(v); if(depth[w]<0){depth[w]=depth[v]+1;pred[w]=v;pop[w]=-1;q[qt++]=w;}}
    }
    *set_out=qt;
    fprintf(stderr,"V1: %d reachable words (%d distinct seed bytes)\n",qt,ns);
}

static int score(int c1,int c2){
    int n=0;
    for(int b=0;b<256;b++){int a=crz(b,c1); a=crz(a,c2); if((a%256)==(b^0x51))n++;}
    return n;
}
static int ok1(int v){for(int i=0;i<5;i++)if(tr(v,i)!=1)return 0;return 1;}
static int ok2(int v){for(int i=0;i<4;i++)if(tr(v,i)!=1)return 0;return tr(v,4)==0;}

int main(void){
    mk_tables();
    int n; bfs(&n);
    int *A=malloc(NW*sizeof(int)),na=0,*B=malloc(NW*sizeof(int)),nb=0;
    for(int v=0;v<NW;v++){ if(depth[v]<0)continue; if(ok1(v))A[na++]=v; if(ok2(v))B[nb++]=v; }
    fprintf(stderr,"V1 candidates: c1-shaped %d, c2-shaped %d\n",na,nb);
    int found=0;
    for(int i=0;i<na;i++)for(int j=0;j<nb;j++){
        int s=score(A[i],B[j]);
        if(s>=34){printf("V1 PAIR score=%d c1=%d(d=%d) c2=%d(d=%d)\n",s,A[i],depth[A[i]],B[j],depth[B[j]]);found++;}
    }
    fprintf(stderr,"V1 pairs at 34: %d\n",found);
    if(found)return 0;

    /* cross layer: c2 = crazy(u,w), u,w in V1, then optional rot/seed-crazy tail */
    fprintf(stderr,"V1 empty on the c2 side or no pair; trying one cross-crazy layer\n");
    return 0;
}
