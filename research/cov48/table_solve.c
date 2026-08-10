/* cov48: exact transfer-matrix DP for one (K0,k), with the winning table extracted.
 * Same model as table_dp2.c; DFS over the 8^k operand combinations per cell reuses
 * CRAZY prefixes so k = 6 is tractable.  Prints "addr byte" for every table cell.
 */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
static const int M[3][3]={{1,0,0},{1,0,2},{2,2,1}};
static const int OPS[8]={4,5,23,39,40,62,68,81};
static int CR5[243][243];
static void mk(void){for(int a=0;a<243;a++)for(int d=0;d<243;d++){int r=0,p=1,aa=a,dd=d;for(int i=0;i<5;i++){r+=M[dd%3][aa%3]*p;p*=3;aa/=3;dd/=3;}CR5[a][d]=r;}}
static inline int crz(int a,int d){return CR5[a%243][d%243]+243*CR5[a/243][d/243];}
static void legal(int a,int out[8]){for(int i=0;i<8;i++){int b=((OPS[i]-a)%94+94)%94;if(b<33)b+=94;out[i]=b;}}
static int L[600][8],TGT[256],K0,k,S,SH;
static unsigned char *hitbuf;   /* indexed by combo = s + nx*S */
static int Lb[8][8];            /* legal bytes for cells b..b+k-1 */
static void dfs(int i,int A,int idx,int b){
    if(i==k){ hitbuf[idx]=((A&255)==TGT[b]); return; }
    for(int c=0;c<8;c++) dfs(i+1,crz(A,Lb[i][c]),idx+c*(1<<(3*i)),b);
}
int main(int argc,char**argv){
    mk(); for(int b=0;b<256;b++) TGT[b]=b^0x51;
    K0=atoi(argv[1]); k=atoi(argv[2]); int emit=argc>3;
    int base=K0+1,NC=256+k-1;
    if(base+NC>4096){fprintf(stderr,"too long\n");return 1;}
    for(int c=0;c<NC;c++) legal(base+c,L[c]);
    S=1<<(3*(k-1)); SH=S/8; hitbuf=malloc(1<<(3*k));
    int *dp=malloc(sizeof(int)*S),*nd=malloc(sizeof(int)*S);
    unsigned char *par=malloc((size_t)NC*S); int *pst=malloc(sizeof(int)*(size_t)NC*S);
    for(int s=0;s<S;s++) dp[s]=0;
    for(int c=k-1;c<NC;c++){
        int b=c-(k-1);
        for(int i=0;i<k;i++) memcpy(Lb[i],L[b+i],sizeof L[0]);
        dfs(0,b+K0,0,b);
        for(int s=0;s<S;s++) nd[s]=-1;
        for(int s=0;s<S;s++){ if(dp[s]<0) continue;
            for(int nx=0;nx<8;nx++){
                int val=dp[s]+hitbuf[s+nx*S];
                int nstate=(k==1)?0:((s>>3)+nx*SH);
                if(val>nd[nstate]){nd[nstate]=val;par[(size_t)c*S+nstate]=nx;pst[(size_t)c*S+nstate]=s;}
            }
        }
        memcpy(dp,nd,sizeof(int)*S);
    }
    int best=-1,bs=0; for(int s=0;s<S;s++) if(dp[s]>best){best=dp[s];bs=s;}
    fprintf(stderr,"K0=%d k=%d best=%d/256\n",K0,k,best);
    if(!emit) return 0;
    int *ch=malloc(sizeof(int)*NC),st=bs;
    for(int c=NC-1;c>=k-1;c--){int nx=par[(size_t)c*S+st];int ps=pst[(size_t)c*S+st];ch[c]=L[c][nx];st=ps;}
    for(int i=0;i<k-1;i++) ch[i]=L[i][(st>>(3*i))&7];
    for(int c=0;c<NC;c++) printf("%d %d\n",base+c,ch[c]);
    return 0;
}
