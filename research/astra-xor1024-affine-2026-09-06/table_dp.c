/* GPT-6 Astra: shared five-CRAZY data table, stride three.
 * Each input b reads five loader-legal source cells at 3*(b+81)+1.
 * Adjacent inputs overlap in two source cells. Exact max-sum DP has
 * 64 states (their opcode indices) and 512 extensions per input.
 * This is a circuit/layout diagnostic; the Rust VM remains the judge.
 */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
static const int ops[8]={4,5,23,39,40,62,68,81};
static uint16_t cr[59049][127];
static int ct[3][3]={{1,0,0},{1,0,2},{2,2,1}};
static int cv(int a,int d){int v=0,p=1;for(int i=0;i<10;i++,p*=3){v+=ct[d%3][a%3]*p;a/=3;d/=3;}return v;}
static int rot(int a){return a/3+a%3*19683;}
static int byte(int op,int addr){int v=(op-addr)%94;if(v<0)v+=94;while(v<33)v+=94;return v;}
static int acc(int b,int phase){
 int x=9*b,y=27*b,a=cv(x,52496),r=cv(y,54683),c=cv(r,3645),d=cv(a,c),e=cv(d,x);
 switch(phase){case 0:return 3*(b+81);case 1:return 9*b;case 2:return 27*b;case 3:return b;case 4:return a;case 5:return r;case 6:return c;case 7:return d;case 8:return e;case 9:return 9*(b+81);case 10:return 3*b;default:return phase-10;}
}
int main(int argc,char**argv){
 int phase=argc>1?atoi(argv[1]):0,ro=argc>2?atoi(argv[2]):-1,offset=argc>3?atoi(argv[3]):244;
 for(int a=0;a<59049;a++)for(int d=33;d<127;d++)cr[a][d]=cv(a,d);
 int dp[64],next[64];uint16_t prev[256][64];uint8_t mid[256][64];
 for(int s=0;s<64;s++)dp[s]=0;
 int poss=0;
 for(int b=0;b<256;b++){
  int vals[5][8];for(int i=0;i<5;i++)for(int j=0;j<8;j++)vals[i][j]=byte(ops[j],offset+3*b+i);
  for(int s=0;s<64;s++)next[s]=-10000;
  int any=0;
  for(int s=0;s<64;s++){
   int a=acc(b,phase);a=ro==0?rot(vals[0][s/8]):cr[a][vals[0][s/8]];a=ro==1?rot(vals[1][s%8]):cr[a][vals[1][s%8]];
   for(int m=0;m<8;m++){
    int z=ro==2?rot(vals[2][m]):cr[a][vals[2][m]];
    for(int j=0;j<8;j++){
     int t=ro==3?rot(vals[3][j]):cr[z][vals[3][j]];
     for(int k=0;k<8;k++){
      int w=ro==4?rot(vals[4][k]):cr[t][vals[4][k]],ns=8*j+k,ok=((w&255)==(b^81));any|=ok;
      int v=dp[s]+ok;if(v>next[ns]){next[ns]=v;prev[b][ns]=s;mid[b][ns]=m;}
     }
    }
   }
  }
  poss+=any;memcpy(dp,next,sizeof dp);
 }
 int best=0;for(int s=1;s<64;s++)if(dp[s]>dp[best])best=s;
 printf("{\"phase\":%d,\"rotate_at\":%d,\"offset\":%d,\"independent_reachable\":%d,\"joint_score\":%d}\n",phase,ro,offset,poss,dp[best]);
 if(argc>4){uint8_t table[770];int st=best;for(int b=255;b>=0;b--){int ps=prev[b][st];table[3*b]=byte(ops[ps/8],offset+3*b);table[3*b+1]=byte(ops[ps%8],offset+3*b+1);table[3*b+2]=byte(ops[mid[b][st]],offset+3*b+2);table[3*b+3]=byte(ops[st/8],offset+3*b+3);table[3*b+4]=byte(ops[st%8],offset+3*b+4);st=ps;}FILE*f=fopen(argv[4],"wb");fwrite(table,1,770,f);fclose(f);}
 return 0;
}
