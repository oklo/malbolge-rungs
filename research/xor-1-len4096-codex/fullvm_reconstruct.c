/* Monotone reconstruction from an arbitrary prologue: execute the complete
 * VM from C=D=A=0 and synthesize only source cells actually reached. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#define M 59049
#define MAXN 4096
#define MAXCH 96
enum{JMP=4,OUT=5,IN=23,ROT=39,MOVD=40,CRZ=62,NOP=68,HLT=81};
static const int CODES[8]={JMP,OUT,IN,ROT,MOVD,CRZ,NOP,HLT};
static const int CT[3][3]={{1,0,0},{1,0,2},{2,2,1}};
static const char*XLAT2="5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";
static uint8_t prog[MAXN],x2[128],fixed[M],mut[M],asg[M],bestprog[MAXN];static uint16_t mem[M];static int N;
static int ua[16384],un;static uint16_t uv[16384];
static int target,order,ncur,found,ca[MAXCH];static uint8_t cv[MAXCH],bestv[MAXCH];static int besta[MAXCH],bestn;static long nodes,nodecap=30000000;
static int crazyw(int a,int d){int r=0,p=1;for(int i=0;i<10;i++){r+=CT[d%3][a%3]*p;a/=3;d/=3;p*=3;}return r;}static int rotr(int w){return w/3+(w%3)*19683;}static int byte_for(int op,int a){int v=(op-a)%94;if(v<0)v+=94;while(v<33)v+=94;return v;}
static void wr(int a,int v){if(un>=16384)return;ua[un]=a;uv[un]=mem[a];un++;mem[a]=v;}static void unwind(int n){while(un>n){--un;mem[ua[un]]=uv[un];}}
static void build(void){for(int a=0;a<N;a++)mem[a]=prog[a];for(int a=N;a<M;a++)mem[a]=crazyw(mem[a-1],mem[a-2]);un=0;}
static int run(int b,int mark){build();int A=0,C=0,D=0,ins=0,on=0,ob=-1;for(int s=0;s<4096;s++){int w=mem[C];if(C<N&&mark)fixed[C]=1;if(w<33||w>126)return 0;int op=(w+C)%94;if(op==HLT)return on==1&&ob==(b^0x51);if(op==JMP||op==ROT||op==MOVD||op==CRZ){if(D<N&&mark)fixed[D]=1;}if(op==JMP)C=mem[D];else if(op==OUT){if(on++)return 0;ob=A&255;}else if(op==IN){if(ins++)return 0;A=b;}else if(op==ROT){int v=rotr(mem[D]);wr(D,v);A=v;}else if(op==MOVD)D=mem[D];else if(op==CRZ){int v=crazyw(A,mem[D]);wr(D,v);A=v;}w=mem[C];if(C<N&&mark)fixed[C]=1;if(w<33||w>126)return 0;wr(C,x2[w]);C=(C+1)%M;D=(D+1)%M;}return 0;}
static int score(int sol[256]){int s=0;for(int b=0;b<256;b++){sol[b]=run(b,0);s+=sol[b];}return s;}
static int rec(int A,int C,int D,int ins,int on,int ob,int steps);
static int branch(int X,int A,int C,int D,int ins,int on,int ob,int steps){if(X<0||X>=N||ncur>=MAXCH)return 0;int z=un;for(int k=0;k<8&&!found;k++){int op=CODES[(k+order)&7],v=byte_for(op,X);if(v==prog[X])continue;wr(X,v);asg[X]=1;ca[ncur]=X;cv[ncur++]=v;rec(A,C,D,ins,on,ob,steps);--ncur;asg[X]=0;unwind(z);}return found;}
static int rec(int A,int C,int D,int ins,int on,int ob,int steps){if(found||++nodes>nodecap||steps>=512)return found;if(C<N&&mut[C]&&!asg[C])return branch(C,A,C,D,ins,on,ob,steps);int w=mem[C];if(w<33||w>126)return 0;int op=(w+C)%94;if(op==HLT){if(on==1&&ob==(target^0x51)){found=1;bestn=ncur;memcpy(besta,ca,sizeof(int)*ncur);memcpy(bestv,cv,ncur);}return found;}if(op==OUT&&(on||(A&255)!=(target^0x51)))return 0;if(op==IN&&ins)return 0;if((op==JMP||op==ROT||op==MOVD||op==CRZ)&&D<N&&mut[D]&&!asg[D])return branch(D,A,C,D,ins,on,ob,steps);int z=un;if(op==JMP)C=mem[D];else if(op==OUT){on=1;ob=A&255;}else if(op==IN){ins=1;A=target;}else if(op==ROT){int v=rotr(mem[D]);wr(D,v);A=v;}else if(op==MOVD)D=mem[D];else if(op==CRZ){int v=crazyw(A,mem[D]);wr(D,v);A=v;}w=mem[C];if(w<33||w>126){unwind(z);return 0;}wr(C,x2[w]);rec(A,(C+1)%M,(D+1)%M,ins,on,ob,steps+1);unwind(z);return found;}
static int solve(int b){target=b;nodes=0;found=0;ncur=0;memset(mut,0,sizeof(mut));memset(asg,0,sizeof(asg));for(int a=0;a<N-2;a++)if(!fixed[a])mut[a]=1;build();rec(0,0,0,0,0,-1,0);if(found)for(int i=0;i<bestn;i++)prog[besta[i]]=bestv[i];fprintf(stderr,"target=%d found=%d nodes=%ld changes=%d\n",b,found,nodes,bestn);return found;}
int main(int ac,char**av){const char*seed=0,*out=0;for(int i=1;i<ac;i++){if(!strcmp(av[i],"-s")&&i+1<ac)seed=av[++i];else if(!strcmp(av[i],"-o")&&i+1<ac)out=av[++i];else if(!strcmp(av[i],"-order")&&i+1<ac)order=atoi(av[++i])&7;else if(!strcmp(av[i],"-nodes")&&i+1<ac)nodecap=atol(av[++i]);else return 2;}if(!seed||!out)return 2;FILE*f=fopen(seed,"rb");if(!f)return 2;N=fread(prog,1,MAXN,f);fclose(f);for(int v=33;v<=126;v++)x2[v]=XLAT2[v-33];int sol[256],s=score(sol);fprintf(stderr,"start=%d\n",s);for(int pass=0;pass<3;pass++){int start=s;for(int b=255;b>=2;b--)if(!sol[b]){memset(fixed,0,sizeof(fixed));for(int x=0;x<256;x++)if(sol[x])run(x,1);uint8_t save[MAXN];memcpy(save,prog,N);if(solve(b)){int ns=score(sol);if(!sol[0]||!sol[1]||!sol[b]||ns<s){memcpy(prog,save,N);s=score(sol);}else{s=ns;memcpy(bestprog,prog,N);f=fopen(out,"wb");fwrite(prog,1,N,f);fclose(f);fprintf(stderr,"ACCEPT score=%d target=%d\n",s,b);}}}if(s==start)break;}f=fopen(out,"wb");fwrite(prog,1,N,f);fclose(f);fprintf(stderr,"final=%d misses:",s);for(int b=0;b<256;b++)if(!sol[b])fprintf(stderr," %d",b);fputc('\n',stderr);return 0;}
