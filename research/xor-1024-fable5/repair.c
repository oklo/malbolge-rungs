/* Fable 5 run-4: per-input escape repair for a compact-family candidate.
 * For each target input b, enumerate all 8^7 loader-legal choices of its
 * seven window cells under FULL native-semantics simulation (not the DP's
 * prescribed-path model): out-of-alphabet v5 values send D off the return
 * graph — through low memory or the implicit crazy fill — while C still walks
 * the fixed code. Any hit is re-simulated for the input's window neighbors
 * (b-2..b+2) before being accepted. The native Rust VM stays the judge.
 *
 * usage: repair <candidate.mal> <b1,b2,...> [maxhits]
 */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

static const int ops[8]={4,5,23,39,40,62,68,81};
static int ct[3][3]={{1,0,0},{1,0,2},{2,2,1}};
static int cv(int a,int d){int v=0,p=1;for(int i=0;i<10;i++,p*=3){v+=ct[d%3][a%3]*p;a/=3;d/=3;}return v;}
static int rot_(int a){return a/3+a%3*19683;}
static int byte_(int op,int addr){int v=(op-addr)%94;if(v<0)v+=94;while(v<33)v+=94;return v;}
static const char enc[]="5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";

static uint16_t t5[243][243];
static inline int fastcr(int a,int d){return t5[a%243][d%243]+243*t5[a/243][d/243];}

#define OFFSET 244
static uint8_t prog[2048]; static int n=1016;
static uint16_t fill0[59049];        /* pristine memory image */
static uint16_t mem[59049]; static unsigned stamp[59049]; static unsigned epoch_;
static inline int get(int a){return stamp[a]==epoch_?mem[a]:fill0[a];}
static inline void put(int a,int v){stamp[a]=epoch_;mem[a]=v;}

/* exact classic-51 semantics, single input byte; returns 1 iff clean halt with
 * exactly one output equal to b^0x51 */
static int simulate(int b){
 epoch_++;
 int a=0,c=0,d=0,reads=0,out=-1,nout=0;
 for(int step=0;step<2048;step++){
  int w=get(c);if(w<33||w>126)return 0;
  int op=(w+c)%94;
  if(op==81)return nout==1&&out==(b^81);
  if(op==4)c=get(d);
  else if(op==5){out=a&255;nout++;if(nout>1)return 0;}
  else if(op==23){if(reads++)return 0;a=b;}
  else if(op==39){a=rot_(get(d));put(d,a);}
  else if(op==40)d=get(d);
  else if(op==62){a=fastcr(a,get(d));put(d,a);}
  w=get(c);if(w<33||w>126)return 0;
  put(c,(unsigned char)enc[w-33]);
  c=(c+1)%59049;d=(d+1)%59049;
 }
 return 0;
}

int main(int argc,char**argv){
 for(int x=0;x<243;x++)for(int y=0;y<243;y++)t5[x][y]=cv(x,y)%243;
 FILE*f=fopen(argv[1],"rb");n=fread(prog,1,sizeof prog,f);fclose(f);
 for(int i=0;i<n;i++)fill0[i]=prog[i];
 for(int i=n;i<59049;i++)fill0[i]=fastcr(fill0[i-1],fill0[i-2]);
 int maxhits=argc>3?atoi(argv[3]):20;
 char*tok=strtok(argv[2],",");
 while(tok){
  int b=atoi(tok);tok=strtok(0,",");
  int w0=OFFSET+3*b;
  int legal[7][8];
  for(int i=0;i<7;i++)for(int j=0;j<8;j++)legal[i][j]=byte_(ops[j],w0+i);
  uint8_t save[7];for(int i=0;i<7;i++)save[i]=prog[w0+i];
  /* sanity: does the unmodified candidate fail b as expected? */
  int pre=simulate(b);
  fprintf(stderr,"input %d: baseline %s\n",b,pre?"PASS":"fail");
  long tried=0;int hits=0;
  for(long code=0;code<2097152&&hits<maxhits;code++){
   long cc=code;
   for(int i=0;i<7;i++){int j=cc&7;cc>>=3;fill0[w0+i]=legal[i][j];}
   tried++;
   if(!simulate(b))continue;
   /* neighbor check: b-2..b+2 must all still pass (or have failed before) */
   int ok=1;
   for(int nb=b-2;nb<=b+2&&ok;nb++){
    if(nb<0||nb>255||nb==b)continue;
    if(!simulate(nb))ok=0;
   }
   if(!ok)continue;
   printf("{\"b\":%d,\"bytes\":[",b);
   for(int i=0;i<7;i++)printf("%s%d",i?",":"",fill0[w0+i]);
   printf("],\"neighbors_ok\":true}\n");fflush(stdout);
   hits++;
  }
  for(int i=0;i<7;i++)fill0[w0+i]=save[i];
  fprintf(stderr,"input %d: tried %ld, hits with clean neighbors: %d\n",b,tried,hits);
 }
 return 0;
}
