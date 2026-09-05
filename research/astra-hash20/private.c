/* Independent direct-landing tail synthesis. Inspired by the prior XOR-256
 * independent-block search, with arbitrary input/target pairs and boundaries.
 * All cells outside this lane's block are fixed; other lanes' blocks cannot
 * be read. Thus independently obtained witnesses compose.
 */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
enum {N=2048,M=59049};
static const int ops[]={81,5,62,39,40,68,4,23};
static const int ct[3][3]={{1,0,0},{1,0,2},{2,2,1}};
static const char enc[]="5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";
static int tape[N],mem[M],set[N],choice[N],answer[N],owner[N],lane,lo,hi,target,depthcap;
static long nodes,cap=2000000;
static int exits[N];
static long suffix_nodes,total_nodes;
static int suffix_limit;
static int crz(int a,int d){int r=0,p=1;for(int i=0;i<10;i++,p*=3){r+=ct[d%3][a%3]*p;a/=3;d/=3;}return r;}
static int rot(int a){return a/3+(a%3)*19683;}
static int bytefor(int op,int c){int b=(op-c)%94;if(b<0)b+=94;if(b<33)b+=94;return b;}
static int dfs(int a,int c,int d,int on,int depth);
static int choose(int addr,int a,int c,int d,int on,int depth){
 int old=mem[addr];set[addr]=1;
 for(int k=0;k<8;k++){mem[addr]=choice[addr]=bytefor(ops[k],addr);if(dfs(a,c,d,on,depth))return 1;}
 mem[addr]=old;choice[addr]=-1;set[addr]=0;return 0;
}
static int dfs(int a,int c,int d,int on,int depth){
 if(++total_nodes>10000000||c<0||c>=N||d<0||d>=N)return 0;
 if(on==0){if(++nodes>cap||depth>=depthcap)return 0;}else{if(++suffix_nodes>20000||depth>=suffix_limit)return 0;}
 if(owner[c]!=lane){exits[c]=1;return 0;}
 if(!set[c])return choose(c,a,c,d,on,depth);
 int w=mem[c];if(w<33||w>126)return 0;int op=(w+c)%94;
 if(op==81){if(on!=2)return 0;for(int i=0;i<N;i++)if(owner[i]==lane)answer[i]=choice[i]<0?tape[i]:choice[i];return 1;}
 if(op==23)return 0;
 if(op==4||op==39||op==40||op==62){
  if(owner[d]>=0&&owner[d]!=lane)return 0;
  if(!set[d])return choose(d,a,c,d,on,depth);
 }
 int nc=c,nd=d,na=a,no=on,write=-1,old=0;
 if(op==5){if(on>=2||(a&255)!=((target>>(8*on))&255))return 0;no=on+1;}
 else if(op==4)nc=mem[d];
 else if(op==40)nd=mem[d];
 else if(op==39||op==62){write=d;old=mem[d];na=op==39?rot(old):crz(a,old);mem[d]=na;}
 if(nc<0||nc>=N){if(write>=0)mem[write]=old;return 0;}
 if(owner[nc]!=lane){exits[nc+1<N?nc+1:nc]=1;if(write>=0)mem[write]=old;return 0;}
 if(!set[nc]){if(write>=0)mem[write]=old;return choose(nc,a,c,d,on,depth);}
 w=mem[nc];if(w<33||w>126){if(write>=0)mem[write]=old;return 0;}
 mem[nc]=(unsigned char)enc[w-33];int ok=0;
 if(on==0&&no==1){for(suffix_limit=3;suffix_limit<=16&&!ok;suffix_limit++){suffix_nodes=0;ok=dfs(na,nc+1,nd+1,no,0);}}
 else ok=dfs(na,nc+1,nd+1,no,depth+1);mem[nc]=w;
 if(write>=0)mem[write]=old;return ok;
}
static int prologue(int input,int stop,int *a,int *d){
 int c=0;*a=*d=0;
 for(int i=0;i<N;i++)mem[i]=tape[i];
 for(int step=0;step<1000;step++){
  if(c==stop)return 1;
  if(c<0||c>=N||*d<0||*d>=N)return 0;
  int w=mem[c];if(w<33||w>126)return 0;int op=(w+c)%94;
  if(op==23)*a=input;
  else if(op==4)c=mem[*d];
  else if(op==40)*d=mem[*d];
  else if(op==62)*a=mem[*d]=crz(*a,mem[*d]);
  else if(op==39)*a=mem[*d]=rot(mem[*d]);
  else if(op==81||op==5)return 0;
  w=mem[c];if(w<33||w>126)return 0;mem[c]=(unsigned char)enc[w-33];c++;(*d)++;
 }return 0;
}
int main(int argc,char **argv){
 if(argc<4)return 2;
 FILE *f=fopen(argv[1],"rb");if(!f)return 2;
 for(int i=0;i<N;i++){int x=fgetc(f);if(x==EOF)return 2;tape[i]=x;}fclose(f);
 f=fopen(argv[2],"r");int count,ins[32],tgts[32],los[32],his[32];fscanf(f,"%d",&count);
 for(int i=0;i<N;i++)owner[i]=-1;
 for(int j=0;j<count;j++){fscanf(f,"%d%d%d%d",&ins[j],&tgts[j],&los[j],&his[j]);for(int i=los[j];i<his[j];i++)owner[i]=j;}fclose(f);
 if(argc>4)cap=atol(argv[4]);
 if(argc>5){f=fopen(argv[5],"r");int l,b,e;while(fscanf(f,"%d%d%d",&l,&b,&e)==3){for(int i=b;i<e;i++){if(owner[i]>=0)return 4;owner[i]=l;}}fclose(f);}
 int solved=0;
 for(lane=0;lane<count;lane++){
  lo=los[lane];hi=his[lane];target=tgts[lane];int found=0;long total=0;memset(exits,0,sizeof exits);
  for(depthcap=5;depthcap<=17;depthcap++){
   int a,d;if(!prologue(ins[lane],lo,&a,&d))return 3;
   for(int i=0;i<N;i++){set[i]=(owner[i]!=lane);choice[i]=-1;}
   nodes=total_nodes=0;found=dfs(a,lo,d,0,0);total+=total_nodes;if(found)break;
  }
  printf("lane=%d input=%d target=%d range=%d:%d found=%d nodes=%ld depth=%d\n",lane,ins[lane],target,lo,hi,found,total,depthcap);if(!found){printf("exits=");for(int i=0;i<N;i++)if(exits[i])printf("%d,",i);putchar(10);}fflush(stdout);
  if(found){solved++;for(int i=0;i<N;i++)if(owner[i]==lane)tape[i]=answer[i];}
 }
 f=fopen(argv[3],"wb");for(int i=0;i<N;i++)fputc(tape[i],f);fclose(f);
 return solved==count?0:1;
}
