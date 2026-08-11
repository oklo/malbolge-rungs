// DP over the free-table dispatch architecture for L2.R2.rotate-1.
//
// Architecture (K0 = 0 variant of the cov40/cov48 table dispatch):
//   IN            A = b
//   CRZ W1, CRZ W2 with W1 = W2 = 364 (mod 729)  ->  A = b exactly, parked in a cell
//   MOVD on that cell -> D = b, post-increment -> D = b+1
//   CRZ x k       A = crazy(...crazy(b, m[b+1])..., m[b+k])
//   OUT           emits A % 256, must equal rotl(b,1)
//
// Because max_program_len = 256 on this rung, the table addresses b+1..b+k lie
// INSIDE the program (addresses 1..255) and are therefore freely choosable,
// 8 loader-valid bytes per address -- unlike the coverage rungs, where K0 had to
// be a multiple of 729 and the alphabet was fixed by address mod 94.
// Addresses >= 256 are not choosable: they are the crazy-fill tail
// m[i] = crazy(m[i-1], m[i-2]), so the last k inputs run off a forced ending.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const int OPS[8] = {4,5,23,39,40,62,68,81};
static unsigned short CR[59049u]; // not used; placeholder

static int crazy_trit(int a,int d){
  static const int T[3][3] = {{1,0,0},{1,0,2},{2,2,1}}; // T[d][a]
  return T[d][a];
}
static unsigned crazy(unsigned a, unsigned d){
  unsigned r=0,f=1;
  for(int i=0;i<10;i++){ r += (unsigned)crazy_trit(a%3,d%3)*f; a/=3; d/=3; f*=3; }
  return r;
}
static int legal_at(int addr, int out[8]){
  int n=0;
  for(int v=33;v<=126;v++){
    int code=(v+addr)%94;
    for(int i=0;i<8;i++) if(code==OPS[i]){ out[n++]=v; break; }
  }
  return n;
}
static int TAB[300][8];

int main(int argc,char**argv){
  int K = argc>1?atoi(argv[1]):6;
  for(int a=0;a<300;a++){ int n=legal_at(a,TAB[a]); if(n!=8){fprintf(stderr,"addr %d has %d\n",a,n); return 1;} }
  int SW = 1; for(int i=0;i<K-1;i++) SW*=8;           // number of states
  signed char *best = malloc(SW*sizeof(signed char));
  int *dp = malloc(SW*sizeof(int)), *nd = malloc(SW*sizeof(int));
  unsigned char *par = malloc((size_t)SW*256);        // parent state per address step
  unsigned char *ch  = malloc((size_t)SW*256);        // chosen digit per address step
  for(int i=0;i<SW;i++) dp[i]=-1;
  // enumerate initial window: addresses 1..K-1
  for(int s=0;s<SW;s++) dp[s]=0;                      // all initial windows reachable, score 0
  // step: choose t[a] for a = K .. 255, completing input b = a-K
  for(int a=K;a<=255;a++){
    for(int i=0;i<SW;i++) nd[i]=-1;
    for(int s=0;s<SW;s++){
      if(dp[s]<0) continue;
      // decode window cells for addresses a-K+1 .. a-1
      int cells[16]; int t=s;
      for(int j=0;j<K-1;j++){ cells[j]=TAB[a-K+1+j][t&7]; t>>=3; }
      int b=a-K;
      for(int d=0;d<8;d++){
        int last=TAB[a][d];
        unsigned acc=(unsigned)b;
        for(int j=0;j<K-1;j++) acc=crazy(acc,(unsigned)cells[j]);
        acc=crazy(acc,(unsigned)last);
        int sc=dp[s] + (((acc%256)==(unsigned)(((b<<1)|(b>>7))&255))?1:0);
        int ns=(s>>3) | (d<<(3*(K-2)));
        if(sc>nd[ns]){ nd[ns]=sc; par[(size_t)(a-K)*SW+ns]=0; ch[(size_t)(a-K)*SW+ns]=0; }
      }
    }
    memcpy(dp,nd,SW*sizeof(int));
  }
  // terminal: state holds addresses 257-K .. 255; forced tail 256..255+K
  int bestscore=-1;
  for(int s=0;s<SW;s++){
    if(dp[s]<0) continue;
    int cells[16]; int t=s;
    for(int j=0;j<K-1;j++){ cells[j]=TAB[257-K+j][t&7]; t>>=3; }
    unsigned tail[32];
    for(int j=0;j<K-1;j++) tail[j]=(unsigned)cells[j];
    // extend: tail index maps address 257-K+j
    int n=K-1;
    while(n < (K-1)+K+1){ tail[n]=crazy(tail[n-1],tail[n-2]); n++; }
    int sc=dp[s];
    for(int b=256-K;b<=255;b++){
      unsigned acc=(unsigned)b;
      for(int j=1;j<=K;j++){
        int addr=b+j; int idx=addr-(257-K);
        acc=crazy(acc,tail[idx]);
      }
      if((acc%256)==(unsigned)(((b<<1)|(b>>7))&255)) sc++;
    }
    if(sc>bestscore) bestscore=sc;
  }
  printf("k=%d  best=%d/256\n",K,bestscore);
  (void)best; (void)CR;
  return 0;
}
