/* Exact overlap DP for repeated five-cell CRAZY/ROT sweeps.
 * The sixth source cell routes through a proven fixed-depth MOVD tree.
 * Its value is constrained but does not participate in the arithmetic.
 * Adjacent three-cell strides share three source bytes: 512 DP states.
 */
#define main old_main
#include "table_dp.c"
#undef main
static int mask[64],passes,first,core,retlen,retops[64];
static unsigned allowed[94];
static inline int circuit(int a,int v0,int v1,int v2,int v3,int v4){
 int m[5]={v0,v1,v2,v3,v4};
 for(int p=0;p<passes;p++)for(int i=0;i<5;i++)a=m[i]=(mask[p]&(1<<i))?rot(m[i]):cv(a,m[i]);
 return a;
}
/* CRAZY accepts manufactured intermediate words, so cache small per-trit
 * tables rather than pretending all subsequent operands remain printable. */
static uint16_t t5[243][243];
static inline int fastcr(int a,int d){return t5[a%243][d%243]+243*t5[a/243][d/243];}
static inline int fastcircuit(int a,int v0,int v1,int v2,int v3,int v4){
 int m[5]={v0,v1,v2,v3,v4};
 for(int p=0;p<passes;p++)for(int i=0;i<5;i++)if(!(mask[p]&(1<<(i+5))))a=m[i]=(mask[p]&(1<<i))?rot(m[i]):fastcr(a,m[i]);
 return a;
}
static const char enc[] = "5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";
static int score_low(const uint8_t *p,int n){
 uint16_t m[59049];int score=0;
 for(int b=0;b<first;b++){
  for(int i=0;i<n;i++)m[i]=p[i];
  for(int i=n;i<59049;i++)m[i]=fastcr(m[i-1],m[i-2]);
  int a=0,c=0,d=0,reads=0,out=-1;
  for(int step=0;step<2048;step++){
   int w=m[c];if(w<33||w>126)break;int op=(w+c)%94;
   if(op==81){if(out==(b^81))score++;break;}
   if(op==4)c=m[d];
   else if(op==5){if(out!=-1)break;out=a&255;}
   else if(op==23){if(reads++)break;a=b;}
   else if(op==39)a=m[d]=rot(m[d]);
   else if(op==40)d=m[d];
   else if(op==62)a=m[d]=fastcr(a,m[d]);
   if(m[c]<33||m[c]>126)break;
   m[c]=(unsigned char)enc[m[c]-33];c=(c+1)%59049;d=(d+1)%59049;
  }
 }
 return score;
}
int main(int argc,char**argv){
 if(argc<6)return 2;int phase=atoi(argv[1]),offset=atoi(argv[2]);FILE*cfg=fopen(argv[8],"r");fscanf(cfg,"%d%d%d",&first,&core,&retlen);for(int i=0;i<retlen;i++)fscanf(cfg,"%d",&retops[i]);fclose(cfg);FILE*f=fopen(argv[3],"r");for(int p=0;p<94;p++)fscanf(f,"%u",&allowed[p]);fclose(f);
 char*tok=strtok(argv[4],",");while(tok&&passes<64){mask[passes++]=atoi(tok);tok=strtok(0,",");}
 for(int a=0;a<243;a++)for(int d=0;d<243;d++)t5[a][d]=cv(a,d)%243;
 int dp[4096],next[4096];static uint16_t prev[256][4096];int poss=0;
 for(int s=0;s<4096;s++)dp[s]=0;
 for(int b=first;b<256;b++){
  int vals[7][8];for(int i=0;i<7;i++)for(int j=0;j<8;j++)vals[i][j]=byte(ops[j],offset+3*b+i);
  for(int ns=0;ns<4096;ns++)next[ns]=-10000;
  unsigned al=allowed[(offset+3*b+5)%94];int any=0;
  for(int s=0;s<4096;s++){
   if(dp[s]<0)continue;
   for(int p=0;p<8;p++){
    int a=fastcircuit(3*b+81,vals[0][s/512],vals[1][s/64%8],vals[2][s/8%8],vals[3][s%8],vals[4][p]);
    for(int j=0;j<8;j++)if(al&(1u<<j)){
     int aa=fastcr(a,vals[5][j]);
     for(int k=0;k<8;k++){
      int w=fastcr(aa,vals[6][k])&255,ok=w==(b^81),ns=((s%8)*64+p*8+j)*8+k;any|=ok;
      if(dp[s]+ok>next[ns]){next[ns]=dp[s]+ok;prev[b][ns]=s;}
     }
    }
   }
  }
  poss+=any;
  memcpy(dp,next,sizeof dp);
 }
 int best=0;for(int s=1;s<4096;s++)if(dp[s]>dp[best])best=s;
 uint8_t table[772]={0};int st=best;
 for(int b=255;b>=first;b--){int ps=prev[b][st];for(int i=0;i<4;i++){int div=i==0?512:i==1?64:i==2?8:1;table[3*b+i]=byte(ops[ps/div%8],offset+3*b+i);table[3*b+3+i]=byte(ops[st/div%8],offset+3*b+3+i);}st=ps;}
 if(strcmp(argv[5],"-")){f=fopen(argv[5],"wb");fwrite(table,1,772,f);fclose(f);}
 int lower=-1,end=0;
 if(argc>6){
  uint8_t p[2048];f=fopen(argv[6],"rb");fread(p,1,2048,f);fclose(f);memcpy(p+offset+3*first,table+3*first,772-3*first);end=core;
  for(int pass=0;pass<passes;pass++){
   if(pass){for(int j=0;j<retlen;j++){p[end]=byte(retops[j],end);end++;}}
   for(int j=0;j<5;j++){int op=(mask[pass]&(1<<(j+5)))?68:(mask[pass]&(1<<j))?39:62;p[end]=byte(op,end);end++;}
  }
  int tail[4]={62,62,5,81};for(int j=0;j<4;j++){p[end]=byte(tail[j],end);end++;}
  if(end<=1024)lower=score_low(p,end);
  if(argc>7){f=fopen(argv[7],"wb");fwrite(p,1,end,f);fclose(f);}
 }
 printf("{\"phase\":%d,\"offset\":%d,\"masks\":[",phase,offset);for(int i=0;i<passes;i++)printf("%s%d",i?",":"",mask[i]);printf("],\"reachable_under_pointer_constraints\":%d,\"upper_score\":%d,\"lower_single_read_score\":%d,\"single_read_score\":%d,\"source_bytes\":%d}\n",poss,dp[best],lower,dp[best]+(lower<0?0:lower),end);
}
