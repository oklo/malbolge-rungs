// Exact ceiling for the K0=0 table-dispatch family on transform xor 0x51,
// under L2.R3.xor-2-multicase's 384-byte program cap.
//
// Architecture (identical to research/rotate-1/dp.c, target changed):
//   a = b ; d = b+1 ; k CRZs walk d over cells b+1..b+k ; OUT a%256.
// Cell b+i is a program byte at address b+i, so it has exactly 8 loader-valid
// values (33..126 whose (v+addr)%94 is an opcode) -> 3 bits of freedom, shared
// by k consecutive inputs.  Transfer-matrix DP over the last k-1 cell choices
// gives the exact maximum coverage over ALL tables.  Addresses >= 256+k are the
// crazy-fill (not choosable); the terminal states are scored against the forced
// continuation exactly.
//
// This is an UPPER bound for the rung: it ignores that ~13 low addresses are
// pinned by the dispatch code itself.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static const int OPS[8]={4,5,23,39,40,62,68,81};
static int crazy_trit(int a,int d){static const int T[3][3]={{1,0,0},{1,0,2},{2,2,1}};return T[d][a];}
static unsigned crazy(unsigned a,unsigned d){unsigned r=0,f=1;for(int i=0;i<10;i++){r+=(unsigned)crazy_trit(a%3,d%3)*f;a/=3;d/=3;f*=3;}return r;}
static int TAB[300][8];
static unsigned short M[94][59049];
int main(int argc,char**argv){
  int K=argc>1?atoi(argv[1]):7;
  for(int a=0;a<300;a++){int n=0;for(int v=33;v<=126;v++){int c=(v+a)%94;for(int i=0;i<8;i++)if(c==OPS[i]){TAB[a][n++]=v;break;}}}
  for(int bi=0;bi<94;bi++) for(unsigned x=0;x<59049u;x++) M[bi][x]=(unsigned short)crazy(x,(unsigned)(bi+33));
  long SW=1;for(int i=0;i<K-1;i++)SW*=8;
  int *dp=malloc(SW*sizeof(int)),*nd=malloc(SW*sizeof(int));
  for(long i=0;i<SW;i++)dp[i]=0;
  for(int a=K;a<=255;a++){
    for(long i=0;i<SW;i++)nd[i]=-1;
    int b=a-K;
    for(long s=0;s<SW;s++){
      if(dp[s]<0)continue;
      unsigned acc=(unsigned)b; long t=s;
      for(int j=0;j<K-1;j++){int cell=TAB[a-K+1+j][t&7];t>>=3;acc=M[cell-33][acc];}
      int want=b^0x51;
      for(int d=0;d<8;d++){
        unsigned r=M[TAB[a][d]-33][acc];
        int sc=dp[s]+(((int)(r%256)==want)?1:0);
        long ns=(s>>3)|((long)d<<(3*(K-2)));
        if(sc>nd[ns])nd[ns]=sc;
      }
    }
    memcpy(dp,nd,SW*sizeof(int));
  }
  int best=-1;
  for(long s=0;s<SW;s++){
    if(dp[s]<0)continue;
    unsigned tail[64];long t=s;
    for(int j=0;j<K-1;j++){tail[j]=(unsigned)TAB[257-K+j][t&7];t>>=3;}
    for(int n=K-1;n<(K-1)+K+1;n++)tail[n]=crazy(tail[n-1],tail[n-2]);
    int sc=dp[s];
    for(int b=256-K;b<=255;b++){
      unsigned acc=(unsigned)b;
      for(int j=1;j<=K;j++)acc=crazy(acc,tail[b+j-(257-K)]);
      if((int)(acc%256)==(b^0x51))sc++;
    }
    if(sc>best)best=sc;
  }
  printf("k=%d best=%d/256\n",K,best);
  return 0;
}
