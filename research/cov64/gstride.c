/* gstride.c -- stride table-dispatch solver for ANY stride s in 1..256.
 *
 * Extends research/cov64/stride_solve.c, which hard-codes s = 128 ("class size 2
 * only").  With s > 128 the residue classes are no longer all pairs: residues
 * r < 256-s hold the pair {r, r+s}, residues r >= 256-s hold the SINGLETON {r}.
 * A singleton owns k private cells and is solvable whenever any of the 8^k byte
 * choices lands its target byte, which at k = 6 is 262144 tries for a 1-in-256
 * target -- essentially always.  So the score climbs roughly linearly in s:
 * every extra unit of stride converts one coupled pair into two free singletons.
 *
 * What stops it is not the table (256 + (k-1)s cells) but the CHAIN: D advances
 * one cell per instruction, so the walk is (k-1)s + 1 instructions and every one
 * of them is a step.  The rung allows 2048 steps per case, and the prefix plus
 * dispatch already costs ~600-900.  That is the real ceiling on s, not 4096.
 *
 * Usage: gstride K0 s k [emit]
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static const int M[3][3] = {{1,0,0},{1,0,2},{2,2,1}};
static const int OPS[8] = {4,5,23,39,40,62,68,81};
static int CR5[243][243];
static void mk(void){for(int a=0;a<243;a++)for(int d=0;d<243;d++){int r=0,p=1,aa=a,dd=d;
  for(int i=0;i<5;i++){r+=M[dd%3][aa%3]*p;p*=3;aa/=3;dd/=3;}CR5[a][d]=r;}}
static inline int crz(int a,int d){return CR5[a%243][d%243]+243*CR5[a/243][d/243];}
static void legal(int a,int out[8]){for(int i=0;i<8;i++){int b=((OPS[i]-a)%94+94)%94;if(b<33)b+=94;out[i]=b;}}

static int K0,s,k,NP,TGT[256];
static int LB[16][8], bestc[16], curc[16], bh, m0, m1, npair;

/* pattern cell i is used by member0 when i < k, by member1 when i > 0 */
static void dfs(int i,int A0,int A1){
  if(i==NP){
    int h=((A0&255)==TGT[m0]) + (npair ? ((A1&255)==TGT[m1]) : 0);
    if(h>bh){bh=h;memcpy(bestc,curc,sizeof curc);}
    return;
  }
  for(int c=0;c<8;c++){
    curc[i]=c; int d=LB[i][c];
    dfs(i+1, i<k?crz(A0,d):A0, (npair&&i>0)?crz(A1,d):A1);
    if(bh==1+npair) return;
  }
}

int main(int argc,char**argv){
  mk(); for(int b=0;b<256;b++) TGT[b]=b^0x51;
  K0=atoi(argv[1]); s=atoi(argv[2]); k=atoi(argv[3]); int emit=argc>4;
  if(s<1||s>256){fprintf(stderr,"stride out of range\n");return 1;}
  int NCELL=256+(k-1)*s;
  if(K0+1+NCELL>4096){fprintf(stderr,"K0=%d s=%d k=%d : table overruns 4096 (%d cells)\n",K0,s,k,NCELL);return 1;}
  if(256>2*s && s!=256){/* classes of size >2 unsupported */
    fprintf(stderr,"s=%d gives classes of size %d; this solver handles 1 and 2\n",s,(255-0)/s+1);return 1;}
  int *cell=malloc(sizeof(int)*NCELL); for(int i=0;i<NCELL;i++) cell[i]=-1;
  int tot=0,full=0,nsing=0;
  for(int r=0;r<s && r<256;r++){
    m0=r; m1=r+s; npair=(m1<256);
    NP = npair ? k+1 : k;
    if(!npair) nsing++;
    for(int i=0;i<NP;i++) legal(K0+1+r+i*s,LB[i]);
    bh=-1; dfs(0,m0+K0,npair?m1+K0:0);
    tot+=bh; full+=(bh==1+npair);
    for(int i=0;i<NP;i++) cell[r+i*s]=LB[i][bestc[i]];
  }
  fprintf(stderr,"K0=%d s=%d k=%d cells=%d chain=%d : %d/256 (%d/%d classes full, %d singletons)\n",
          K0,s,k,NCELL,(k-1)*s+1,tot,full,(s<256?s:256),nsing);
  if(emit) for(int i=0;i<NCELL;i++) printf("%d %d\n",K0+1+i,cell[i]<0?68:cell[i]);
  return 0;
}
