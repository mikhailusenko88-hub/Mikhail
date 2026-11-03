// Honeycomb World — own path tracer. g++ -O3 -march=native -fopenmp pt.cpp -o pt
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <vector>
#include <algorithm>
#include <string>
#include <omp.h>

// ---------------- math ----------------
struct V { float x, y, z; V(float a=0,float b=0,float c=0):x(a),y(b),z(c){} };
inline V operator+(V a,V b){return V(a.x+b.x,a.y+b.y,a.z+b.z);} inline V operator-(V a,V b){return V(a.x-b.x,a.y-b.y,a.z-b.z);}
inline V operator*(V a,float s){return V(a.x*s,a.y*s,a.z*s);} inline V operator*(float s,V a){return a*s;} inline V operator*(V a,V b){return V(a.x*b.x,a.y*b.y,a.z*b.z);}
inline V operator/(V a,float s){return a*(1.f/s);} inline V operator-(V a){return V(-a.x,-a.y,-a.z);}
inline V& operator+=(V&a,V b){a=a+b;return a;} inline V& operator*=(V&a,float s){a=a*s;return a;} inline V& operator*=(V&a,V b){a=a*b;return a;}
inline float dot(V a,V b){return a.x*b.x+a.y*b.y+a.z*b.z;} inline V cross(V a,V b){return V(a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x);}
inline float len(V a){return sqrtf(dot(a,a));} inline V norm(V a){float l=len(a);return l>0?a/l:V(0,1,0);}
inline V vmin(V a,V b){return V(std::min(a.x,b.x),std::min(a.y,b.y),std::min(a.z,b.z));} inline V vmax(V a,V b){return V(std::max(a.x,b.x),std::max(a.y,b.y),std::max(a.z,b.z));}
inline float clampf(float x,float a,float b){return x<a?a:(x>b?b:x);} inline float lerpf(float a,float b,float t){return a+(b-a)*t;} inline V lerp(V a,V b,float t){return a+(b-a)*t;}
inline float smooth(float a,float b,float x){float t=clampf((x-a)/(b-a),0,1);return t*t*(3-2*t);}
inline float lum(V c){return 0.2126f*c.x+0.7152f*c.y+0.0722f*c.z;}
inline V expv(V a){return V(expf(a.x),expf(a.y),expf(a.z));}
const float PI=3.14159265f;
struct Rng { uint64_t s; Rng(uint64_t seed=1){s=seed*6364136223846793005ULL+1442695040888963407ULL; next();} inline uint32_t next(){ s=s*6364136223846793005ULL+1442695040888963407ULL; uint32_t x=((s>>18)^s)>>27; uint32_t r=s>>59; return (x>>r)|(x<<((-r)&31)); } inline float f(){ return (next()>>8)*(1.f/16777216.f);} };
inline void onb(V n,V&t,V&b){ float sg=n.z>=0?1.f:-1.f; float a=-1.f/(sg+n.z); float bb=n.x*n.y*a; t=V(1+sg*n.x*n.x*a, sg*bb, -sg*n.x); b=V(bb, sg+n.y*n.y*a, -n.y); }
inline V cosHemi(V n,float u1,float u2){ float r=sqrtf(u1), ph=2*PI*u2; V t,b; onb(n,t,b); return norm(t*(r*cosf(ph))+b*(r*sinf(ph))+n*sqrtf(std::max(0.f,1-u1))); }
inline V coneDir(V d,float cosMax,float u1,float u2){ float ct=1-u1*(1-cosMax); float st=sqrtf(std::max(0.f,1-ct*ct)); float ph=2*PI*u2; V t,b; onb(d,t,b); return norm(t*(st*cosf(ph))+b*(st*sinf(ph))+d*ct); }

// ---------------- geometry ----------------
enum { M_GRASS, M_SOIL, M_WAX, M_BARK, M_LEAF, M_GLASS, M_THINGLASS, M_EYE, M_EYEWHITE, M_POLLEN, M_DARKWAX, M_FLW, M_FLY, M_HONEYCORE, M_CHEEK, M_BEE_ABD, M_FUZZ, M_HEADB };
struct Tri { V p0,e1,e2; V n0,n1,n2; float u0,v0,u1,v1,u2,v2; int mat; float s0,s1,s2,k0,k1,k2; };
struct Node { V bmin; int left; V bmax; int count; }; // count>0: leaf, left=first index
struct TriHot { V p0; float pad0; V e1; float pad1; V e2; int id; };
struct Mesh { std::vector<Tri> tris; std::vector<Node> nodes; std::vector<int> idx; std::vector<TriHot> hot; V bmin,bmax; };
struct Xf { float m[12]; }; // row-major 3x4
inline V xp(const Xf&x,V p){return V(x.m[0]*p.x+x.m[1]*p.y+x.m[2]*p.z+x.m[3], x.m[4]*p.x+x.m[5]*p.y+x.m[6]*p.z+x.m[7], x.m[8]*p.x+x.m[9]*p.y+x.m[10]*p.z+x.m[11]);}
inline V xv(const Xf&x,V p){return V(x.m[0]*p.x+x.m[1]*p.y+x.m[2]*p.z, x.m[4]*p.x+x.m[5]*p.y+x.m[6]*p.z, x.m[8]*p.x+x.m[9]*p.y+x.m[10]*p.z);}
inline V xnT(const Xf&inv,V n){ // normal transform: transpose(inv) * n
  return V(inv.m[0]*n.x+inv.m[4]*n.y+inv.m[8]*n.z, inv.m[1]*n.x+inv.m[5]*n.y+inv.m[9]*n.z, inv.m[2]*n.x+inv.m[6]*n.y+inv.m[10]*n.z); }
Xf xfInverse(const Xf&a){ const float*m=a.m; float A=m[5]*m[10]-m[6]*m[9], B=m[6]*m[8]-m[4]*m[10], C=m[4]*m[9]-m[5]*m[8]; float det=m[0]*A+m[1]*B+m[2]*C; float id=1.f/det; Xf r;
  r.m[0]=A*id; r.m[1]=(m[2]*m[9]-m[1]*m[10])*id; r.m[2]=(m[1]*m[6]-m[2]*m[5])*id;
  r.m[4]=B*id; r.m[5]=(m[0]*m[10]-m[2]*m[8])*id; r.m[6]=(m[2]*m[4]-m[0]*m[6])*id;
  r.m[8]=C*id; r.m[9]=(m[1]*m[8]-m[0]*m[9])*id; r.m[10]=(m[0]*m[5]-m[1]*m[4])*id;
  V t(m[3],m[7],m[11]); V it=xv(r,t); r.m[3]=-it.x; r.m[7]=-it.y; r.m[11]=-it.z; return r; }
Xf xfMake(V pos, float tx, float tz, V scale){ // translate * rotX(tz) * rotZ(-tx) * scale ; tilt: lean top toward +x by tx, +z by tz
  float cz=cosf(-tx), sz=sinf(-tx), cx=cosf(tz), sx=sinf(tz);
  // Rz(-tx): [cz -sz 0; sz cz 0; 0 0 1]  Rx(tz): [1 0 0; 0 cx -sx; 0 sx cx]
  float R[9]={ cz, -sz, 0,  cx*sz, cx*cz, -sx,  sx*sz, sx*cz, cx };
  Xf x; x.m[0]=R[0]*scale.x; x.m[1]=R[1]*scale.y; x.m[2]=R[2]*scale.z; x.m[3]=pos.x;
  x.m[4]=R[3]*scale.x; x.m[5]=R[4]*scale.y; x.m[6]=R[5]*scale.z; x.m[7]=pos.y;
  x.m[8]=R[6]*scale.x; x.m[9]=R[7]*scale.y; x.m[10]=R[8]*scale.z; x.m[11]=pos.z; return x; }
Xf xfYaw(V pos,float yaw,V scale){ float c=cosf(yaw),s=sinf(yaw); Xf x; x.m[0]=c*scale.x;x.m[1]=0;x.m[2]=-s*scale.z;x.m[3]=pos.x; x.m[4]=0;x.m[5]=scale.y;x.m[6]=0;x.m[7]=pos.y; x.m[8]=s*scale.x;x.m[9]=0;x.m[10]=c*scale.z;x.m[11]=pos.z; return x; }
Xf xfMul(const Xf&a,const Xf&b){ Xf r; for(int i=0;i<3;i++) for(int j=0;j<4;j++){ float s=0; for(int k=0;k<3;k++) s+=a.m[i*4+k]*b.m[k*4+j]; if(j==3) s+=a.m[i*4+3]; r.m[i*4+j]=s;} return r; }
struct Inst { int mesh; Xf xf, inv; V bmin,bmax; int matOverride; V tint; };

// generic BVH build over boxes
struct BItem { V bmin,bmax,c; int id; };
static void buildBVH(std::vector<BItem>&items, std::vector<Node>&nodes, std::vector<int>&idx, int leafSize){
  nodes.clear(); idx.clear(); idx.reserve(items.size()); nodes.reserve(items.size()*2);
  struct Task{int node,start,end;}; std::vector<Task> st; nodes.push_back(Node()); st.push_back({0,0,(int)items.size()});
  while(!st.empty()){ Task t=st.back(); st.pop_back(); V bmin(1e30f,1e30f,1e30f), bmax(-1e30f,-1e30f,-1e30f), cmin=bmin, cmax=bmax;
    for(int i=t.start;i<t.end;i++){ bmin=vmin(bmin,items[i].bmin); bmax=vmax(bmax,items[i].bmax); cmin=vmin(cmin,items[i].c); cmax=vmax(cmax,items[i].c); }
    Node&n=nodes[t.node]; n.bmin=bmin; n.bmax=bmax; int cnt=t.end-t.start;
    if(cnt<=leafSize){ n.left=(int)idx.size(); n.count=cnt; for(int i=t.start;i<t.end;i++) idx.push_back(items[i].id); continue; }
    // binned SAH
    const int NB=12; float bestCost=1e30f; int bestAxis=-1, bestBin=-1; V ext=cmax-cmin;
    for(int ax=0;ax<3;ax++){ float e=ax==0?ext.x:ax==1?ext.y:ext.z; if(e<=1e-7f) continue; float lo=ax==0?cmin.x:ax==1?cmin.y:cmin.z; float sc=NB/e;
      int bc[NB]={0}; V bbl[NB], bbh[NB]; for(int b=0;b<NB;b++){bbl[b]=V(1e30f,1e30f,1e30f);bbh[b]=V(-1e30f,-1e30f,-1e30f);}
      for(int i=t.start;i<t.end;i++){ float c=ax==0?items[i].c.x:ax==1?items[i].c.y:items[i].c.z; int b=std::min(NB-1,(int)((c-lo)*sc)); bc[b]++; bbl[b]=vmin(bbl[b],items[i].bmin); bbh[b]=vmax(bbh[b],items[i].bmax); }
      float la[NB], ra[NB]; int lc[NB], rc[NB]; V l0(1e30f,1e30f,1e30f),l1(-1e30f,-1e30f,-1e30f); int c0=0;
      for(int b=0;b<NB-1;b++){ l0=vmin(l0,bbl[b]); l1=vmax(l1,bbh[b]); c0+=bc[b]; V d=l1-l0; la[b]=c0?2*(d.x*d.y+d.y*d.z+d.z*d.x):0; lc[b]=c0; }
      V r0(1e30f,1e30f,1e30f),r1(-1e30f,-1e30f,-1e30f); int c1=0;
      for(int b=NB-1;b>0;b--){ r0=vmin(r0,bbl[b]); r1=vmax(r1,bbh[b]); c1+=bc[b]; V d=r1-r0; ra[b-1]=c1?2*(d.x*d.y+d.y*d.z+d.z*d.x):0; rc[b-1]=c1; }
      for(int b=0;b<NB-1;b++){ if(lc[b]==0||rc[b]==0) continue; float cost=la[b]*lc[b]+ra[b]*rc[b]; if(cost<bestCost){bestCost=cost;bestAxis=ax;bestBin=b;} } }
    int mid;
    if(bestAxis<0){ mid=(t.start+t.end)/2; int ax = ext.x>ext.y&&ext.x>ext.z?0:(ext.y>ext.z?1:2); std::nth_element(items.begin()+t.start, items.begin()+mid, items.begin()+t.end, [ax](const BItem&a,const BItem&b){ return (ax==0?a.c.x:ax==1?a.c.y:a.c.z) < (ax==0?b.c.x:ax==1?b.c.y:b.c.z); }); }
    else { float e=bestAxis==0?ext.x:bestAxis==1?ext.y:ext.z; float lo=bestAxis==0?cmin.x:bestAxis==1?cmin.y:cmin.z; float split=lo+(bestBin+1)*e/NB; int ax=bestAxis;
      auto it=std::partition(items.begin()+t.start, items.begin()+t.end, [&](const BItem&a){ return (ax==0?a.c.x:ax==1?a.c.y:a.c.z) < split; }); mid=(int)(it-items.begin()); if(mid==t.start||mid==t.end) mid=(t.start+t.end)/2; }
    int l=(int)nodes.size(); nodes.push_back(Node()); nodes.push_back(Node()); nodes[t.node].left=l; nodes[t.node].count=0;
    st.push_back({l,t.start,mid}); st.push_back({l+1,mid,t.end}); }
}
static void buildMesh(Mesh&m){ std::vector<BItem> it(m.tris.size()); for(size_t i=0;i<m.tris.size();i++){ const Tri&t=m.tris[i]; V p1=t.p0+t.e1, p2=t.p0+t.e2; it[i].bmin=vmin(t.p0,vmin(p1,p2))-V(1e-4f,1e-4f,1e-4f); it[i].bmax=vmax(t.p0,vmax(p1,p2))+V(1e-4f,1e-4f,1e-4f); it[i].c=(t.p0+p1+p2)/3; it[i].id=(int)i; }
  buildBVH(it,m.nodes,m.idx,LEAFN); m.bmin=m.nodes[0].bmin; m.bmax=m.nodes[0].bmax; m.hot.resize(m.idx.size()); for(size_t k=0;k<m.idx.size();k++){ const Tri&t=m.tris[m.idx[k]]; TriHot&h=m.hot[k]; h.p0=t.p0; h.e1=t.e1; h.e2=t.e2; h.id=m.idx[k]; h.pad0=h.pad1=0; } }

struct Hit { float t; float u,v; int tri; int inst; };
#ifdef STATS
static thread_local long ST_node=0, ST_tri=0, ST_inst=0, ST_ray=0; long ST_tot[4]={0,0,0,0};
#define STAT(x) (x)++
#else
#define STAT(x)
#endif
inline bool boxHit(const Node&n, V o, V id, float tmax, float&tn){ float tx1=(n.bmin.x-o.x)*id.x, tx2=(n.bmax.x-o.x)*id.x; float tmin=std::min(tx1,tx2), tm=std::max(tx1,tx2);
  float ty1=(n.bmin.y-o.y)*id.y, ty2=(n.bmax.y-o.y)*id.y; tmin=std::max(tmin,std::min(ty1,ty2)); tm=std::min(tm,std::max(ty1,ty2));
  float tz1=(n.bmin.z-o.z)*id.z, tz2=(n.bmax.z-o.z)*id.z; tmin=std::max(tmin,std::min(tz1,tz2)); tm=std::min(tm,std::max(tz1,tz2)); tn=std::max(tmin,0.f); return tm>=tn && tmin<tmax; }
inline bool triHit(const TriHot&t, V o, V d, float&tt, float&u, float&v){ V p=cross(d,t.e2); float det=dot(t.e1,p); if(fabsf(det)<1e-9f) return false; float inv=1.f/det; V s=o-t.p0; u=dot(s,p)*inv; if(u<0||u>1) return false; V q=cross(s,t.e1); v=dot(d,q)*inv; if(v<0||u+v>1) return false; float tc=dot(t.e2,q)*inv; if(tc<=1e-5f||tc>=tt) return false; tt=tc; return true; }
static void meshHit(const Mesh&m, V o, V d, Hit&h){ V id(1.f/d.x,1.f/d.y,1.f/d.z); int stack[64]; int sp=0; stack[sp++]=0;
  while(sp){ const Node&n=m.nodes[stack[--sp]]; float tn; STAT(ST_node); if(!boxHit(n,o,id,h.t,tn)) continue;
    if(n.count){ STAT(ST_tri); const TriHot*th=&m.hot[n.left]; for(int i=0;i<n.count;i++){ float u,v; if(triHit(th[i],o,d,h.t,u,v)){ h.u=u;h.v=v;h.tri=th[i].id; } } }
    else { float ta,tb; const Node&a=m.nodes[n.left]; const Node&b=m.nodes[n.left+1]; bool ha=boxHit(a,o,id,h.t,ta), hb=boxHit(b,o,id,h.t,tb);
      if(ha&&hb){ if(ta<tb){ stack[sp++]=n.left+1; stack[sp++]=n.left; } else { stack[sp++]=n.left; stack[sp++]=n.left+1; } } else if(ha) stack[sp++]=n.left; else if(hb) stack[sp++]=n.left+1; } } }

struct Scene { std::vector<Mesh> meshes; std::vector<Inst> insts; std::vector<Node> tnodes; std::vector<int> tidx; };
static void buildTLAS(Scene&s){ std::vector<BItem> it(s.insts.size()); for(size_t i=0;i<s.insts.size();i++){ Inst&in=s.insts[i]; const Mesh&m=s.meshes[in.mesh]; V bmin(1e30f,1e30f,1e30f),bmax(-1e30f,-1e30f,-1e30f);
    for(int c=0;c<8;c++){ V p((c&1)?m.bmax.x:m.bmin.x,(c&2)?m.bmax.y:m.bmin.y,(c&4)?m.bmax.z:m.bmin.z); V w=xp(in.xf,p); bmin=vmin(bmin,w); bmax=vmax(bmax,w);} in.bmin=bmin; in.bmax=bmax; it[i].bmin=bmin; it[i].bmax=bmax; it[i].c=(bmin+bmax)*0.5f; it[i].id=(int)i; }
  buildBVH(it,s.tnodes,s.tidx,2); }
static bool sceneHit(const Scene&s, V o, V d, Hit&h){ STAT(ST_ray); h.tri=-1; h.inst=-1; V id(1.f/d.x,1.f/d.y,1.f/d.z); int stack[64]; int sp=0; stack[sp++]=0;
  while(sp){ const Node&n=s.tnodes[stack[--sp]]; float tn; if(!boxHit(n,o,id,h.t,tn)) continue;
    if(n.count){ for(int i=0;i<n.count;i++){ int ii=s.tidx[n.left+i]; const Inst&in=s.insts[ii]; if(n.count>1){ Node ib; ib.bmin=in.bmin; ib.bmax=in.bmax; float tq; if(!boxHit(ib,o,id,h.t,tq)) continue; } V lo=xp(in.inv,o), ld=xv(in.inv,d); int before=h.tri; int tb=h.tri; (void)tb;
        STAT(ST_inst); Hit hh=h; hh.tri=-1; meshHit(s.meshes[in.mesh],lo,ld,hh); if(hh.tri>=0){ h=hh; h.inst=ii; } (void)before; } }
    else { float ta,tb; const Node&a=s.tnodes[n.left]; const Node&b=s.tnodes[n.left+1]; bool ha=boxHit(a,o,id,h.t,ta), hb=boxHit(b,o,id,h.t,tb);
      if(ha&&hb){ if(ta<tb){ stack[sp++]=n.left+1; stack[sp++]=n.left; } else { stack[sp++]=n.left; stack[sp++]=n.left+1; } } else if(ha) stack[sp++]=n.left; else if(hb) stack[sp++]=n.left+1; } }
  return h.tri>=0; }

// ---------------- mesh generators ----------------
static void addTri(Mesh&m, V a, V b, V c, V na, V nb, V nc, float ua,float va,float ub,float vb,float uc,float vc, int mat, float sa=-1,float sb=-1,float sc=-1,float ka=1,float kb=1,float kc=1){ Tri t; t.p0=a; t.e1=b-a; t.e2=c-a; t.n0=na;t.n1=nb;t.n2=nc; t.u0=ua;t.v0=va;t.u1=ub;t.v1=vb;t.u2=uc;t.v2=vc; t.mat=mat; t.s0=sa;t.s1=sb;t.s2=sc;t.k0=ka;t.k1=kb;t.k2=kc; m.tris.push_back(t); }
static void addQuad(Mesh&m, V a,V b,V c,V d, int mat, float u=0){ V n=norm(cross(b-a,d-a)); addTri(m,a,b,c,n,n,n,u,0,u,0,u,1,mat); addTri(m,a,c,d,n,n,n,u,0,u,1,u,1,mat); }
// hex prism (pointy-top), circumradius 1, height 1, with bevel
static Mesh hexPrism(int sideMat, int topMat, float bevel=0.08f){ Mesh m; V bot[6],ot[6],in[6]; for(int k=0;k<6;k++){ float a=PI/6+k*PI/3; bot[k]=V(cosf(a),0,sinf(a)); ot[k]=V(cosf(a),1-bevel,sinf(a)); in[k]=V(cosf(a)*(1-bevel*1.5f),1,sinf(a)*(1-bevel*1.5f)); }
  for(int k=0;k<6;k++){ int k2=(k+1)%6; addQuad(m,bot[k],ot[k],ot[k2],bot[k2],sideMat); addQuad(m,ot[k],in[k],in[k2],ot[k2],sideMat); }
  V n(0,1,0); for(int k=1;k<5;k++) addTri(m,in[0],in[k+1],in[k],n,n,n,0,1,0,1,0,1,topMat);
  // bottom cap (for glass cells)
  V nb(0,-1,0); for(int k=1;k<5;k++) addTri(m,bot[0],bot[k],bot[k+1],nb,nb,nb,0,0,0,0,0,0,sideMat);
  buildMesh(m); return m; }
static Mesh sphere(int mat, int nu=20, int nv=12){ Mesh m; for(int j=0;j<nv;j++){ float t0=PI*j/nv, t1=PI*(j+1)/nv; for(int i=0;i<nu;i++){ float p0=2*PI*i/nu, p1=2*PI*(i+1)/nu;
  auto P=[&](float t,float p){ return V(sinf(t)*cosf(p), cosf(t), sinf(t)*sinf(p)); }; V a=P(t0,p0),b=P(t0,p1),c=P(t1,p1),d=P(t1,p0);
  float v0=t0/PI, v1=t1/PI, uu0=p0/(2*PI), uu1=p1/(2*PI); addTri(m,a,c,b,a,c,b,uu0,v0,uu1,v1,uu1,v0,mat); addTri(m,a,d,c,a,d,c,uu0,v0,uu0,v1,uu1,v1,mat); } } buildMesh(m); return m; }
static Mesh cylinderMesh(int mat, int seg=8){ Mesh m; for(int i=0;i<seg;i++){ float p0=2*PI*i/seg,p1=2*PI*(i+1)/seg; V d0(cosf(p0),0,sinf(p0)), d1(cosf(p1),0,sinf(p1)); addTri(m,d0,d0+V(0,1,0),d1+V(0,1,0),d0,d0,d1,0,0,0,1,0,1,mat); addTri(m,d0,d1+V(0,1,0),d1,d0,d1,d1,0,0,0,1,0,0,mat); } buildMesh(m); return m; }
static Xf xfAxes(V o, V ax, V ay, V az){ Xf x; x.m[0]=ax.x;x.m[1]=ay.x;x.m[2]=az.x;x.m[3]=o.x; x.m[4]=ax.y;x.m[5]=ay.y;x.m[6]=az.y;x.m[7]=o.y; x.m[8]=ax.z;x.m[9]=ay.z;x.m[10]=az.z;x.m[11]=o.z; return x; }

static float hstat(float x,float z){ return 0.35f*sinf(0.07f*x+0.3f)*cosf(0.055f*z) + 0.18f*sinf(0.13f*x-0.09f*z+1.0f) + 0.09f*sinf(0.25f*x+0.19f*z+2.0f) + 0.0016f*std::max(0.f,-z-18)*std::max(0.f,-z-18); }
struct Rip { float x,z,t,speed,amp,decay,width; };
std::vector<Rip> RIPS;
static float hdyn(float x,float z,float t){ float w=0.07f*sinf(0.3f*x-1.4f*t+0.8f*sinf(0.22f*z+0.5f*t))+0.04f*sinf(0.4f*z+0.9f*t+0.5f*x);
  for(const Rip&r:RIPS){ float a=t-r.t; if(a<=0) continue; float d=sqrtf((x-r.x)*(x-r.x)+(z-r.z)*(z-r.z)); float rr=a*r.speed; float amp=r.amp*expf(-a*r.decay)/(1+0.12f*rr); float xx=(d-rr)*r.width; w+=amp*(expf(-xx*xx)-0.45f*expf(-(xx+1.3f)*(xx+1.3f))); } return w; }

// grass patch inside hexagon of circumradius R
struct Blade { float x,z,h,w,yaw,bend,phase,rnd; float sv[5], kv[5]; };
static const float BS[5]={0,0.3f,0.58f,0.82f,1.0f};
static inline void bladePts(const Blade&b, V base, V dir, float wind, V dd, V P[5]){ V wdir(0.8f,0,0.6f); for(int i=0;i<5;i++){ float s=BS[i]; float bend=b.bend*s*s; P[i]=base + V(0,1,0)*(b.h*s*(1-0.28f*b.bend*s*s)) + dir*(b.h*bend*0.55f) + wdir*(wind*b.h*s*s) + dd*(s*s); } }
struct Patch { std::vector<Blade> blades; struct Fl{float x,z,h,yaw; int kind;}; std::vector<Fl> flowers; };
static Patch makePatch(uint64_t seed, float R, int n, bool flowers, float hmul=1.f){ Rng r(seed); Patch p; while((int)p.blades.size()<n){ float x=(r.f()*2-1)*R*1.06f, z=(r.f()*2-1)*R*1.06f; float ax=fabsf(x), az=fabsf(z); if(az>R*0.866f*1.05f || ax*0.866f+az*0.5f>R*0.866f*1.05f) continue;
    Blade b; b.x=x;b.z=z; float cl=r.f(); b.h=(0.16f+0.26f*powf(r.f(),0.8f)+(cl<0.2f?0.12f:0))*hmul; b.w=0.009f+0.008f*r.f(); b.yaw=r.f()*2*PI; b.bend=0.25f+0.7f*r.f(); b.phase=r.f()*2*PI; b.rnd=r.f(); for(int q=0;q<5;q++){b.sv[q]=1;b.kv[q]=1;} p.blades.push_back(b); }
  if(flowers){ int nf=6+(int)(r.f()*8); for(int i=0;i<nf;i++){ float x=(r.f()*2-1)*R*0.8f, z=(r.f()*2-1)*R*0.8f; if(fabsf(z)>R*0.8f||fabsf(x)*0.866f+fabsf(z)*0.5f>R*0.8f) continue; p.flowers.push_back({x,z,0.22f+0.18f*r.f(),r.f()*6.28f,(int)(r.f()*3)}); } }
  return p; }
struct Deform { float t; V hero; bool heroDown; };
static V dispAt(float wx,float wz,const Deform&D){ V disp(0,0,0); for(const Rip&r:RIPS){ float a=D.t-r.t; if(a<=0) continue; float dx=wx-r.x, dz=wz-r.z; float d=sqrtf(dx*dx+dz*dz)+1e-4f; float rr=a*r.speed; float g=r.amp*expf(-a*r.decay)/(1+0.12f*rr); if(g<0.003f) continue; float xx=(d-rr)*r.width; g*=expf(-xx*xx); if(g<0.002f) continue; disp+=V(dx/d*g*1.3f,-g*0.8f,dz/d*g*1.3f); }
  if(D.heroDown){ float dx=wx-D.hero.x, dz=wz-D.hero.z; float d=sqrtf(dx*dx+dz*dz)+1e-4f; if(d<0.5f){ float k=(0.5f-d)/0.5f; k=k*k; disp+=V(dx/d*k*0.25f,-k*0.3f,dz/d*k*0.25f); } } return disp; }
static void buildGrassMesh(Mesh&m, const Patch&p, float t, float windAmp, float yaw=0, V off=V(0,0,0), const Deform*D=nullptr){ m.tris.clear(); m.tris.reserve(p.blades.size()*7+p.flowers.size()*24); float cy=cosf(yaw), sy=sinf(yaw);
  for(const Blade&b:p.blades){ V base(off.x+b.x*cy-b.z*sy,off.y,off.z+b.x*sy+b.z*cy); V dir(cosf(b.yaw+yaw),0,sinf(b.yaw+yaw)); V side(-dir.z,0,dir.x); V dd(0,0,0); if(D){ dd=dispAt(base.x,base.z,*D); float l=len(dd); if(l>0.85f*b.h) dd=dd*(0.85f*b.h/l); }
    float wind = windAmp*(sinf(1.7f*t+b.phase+b.x*0.9f+b.z*0.5f) + 0.5f*sinf(3.1f*t+1.3f*b.phase) + 0.6f);
    const float S[5]={0,0.3f,0.58f,0.82f,1.0f}; V P[5]; V T[5]; bladePts(b,base,dir,wind,dd,P);
    for(int i=0;i<5;i++){ T[i]=norm(P[std::min(i+1,4)]-P[std::max(i-1,0)]); }
    for(int i=0;i<4;i++){ float w0=b.w*powf(1-S[i],0.6f), w1=b.w*powf(1-S[i+1],0.6f); V n0=norm(cross(side,T[i])), n1=norm(cross(side,T[i+1]));
      V a=P[i]-side*w0, bb=P[i]+side*w0, c=P[i+1]+side*w1, d=P[i+1]-side*w1;
      if(i<3){ addTri(m,a,bb,c,n0,n0,n1,b.rnd,S[i],b.rnd,S[i],b.rnd,S[i+1],M_GRASS,b.sv[i],b.sv[i],b.sv[i+1],b.kv[i],b.kv[i],b.kv[i+1]); addTri(m,a,c,d,n0,n1,n1,b.rnd,S[i],b.rnd,S[i+1],b.rnd,S[i+1],M_GRASS,b.sv[i],b.sv[i+1],b.sv[i+1],b.kv[i],b.kv[i+1],b.kv[i+1]); }
      else { addTri(m,a,bb,P[4],n0,n0,n1,b.rnd,S[i],b.rnd,S[i],b.rnd,1,M_GRASS,b.sv[3],b.sv[3],b.sv[4],b.kv[3],b.kv[3],b.kv[4]); } } }
  for(const auto&f:p.flowers){ V base(off.x+f.x*cy-f.z*sy,off.y,off.z+f.x*sy+f.z*cy); float w=windAmp*0.5f*sinf(1.7f*t+f.yaw*3); V top=base+V(w*0.3f,f.h,0); // stem
    V sd(0.003f,0,0); { V n=norm(cross(top-base,V(0,0,1))); addTri(m,base-sd,base+sd,top+sd,n,n,n,0.3f,0,0.3f,0,0.3f,1,M_GRASS,0.5f,0.5f,0.8f,0.5f,0.5f,0.8f); addTri(m,base-sd,top+sd,top-sd,n,n,n,0.3f,0,0.3f,1,0.3f,1,M_GRASS,0.5f,0.8f,0.8f,0.5f,0.8f,0.8f); }
    int pm = f.kind==0?M_FLW:(f.kind==1?M_FLY:M_FLW); int np=f.kind==2?6:5; float pr=f.kind==2?0.025f:0.02f;
    for(int k=0;k<np;k++){ float a=f.yaw+k*2*PI/np; V d(cosf(a),0.25f,sinf(a)); V s2=norm(cross(d,V(0,1,0)))*pr*0.55f; V tip=top+norm(d)*pr*2.2f; V mid=top+norm(d)*pr*1.1f; addTri(m,top,mid+s2,tip,V(0,1,0),V(0,1,0),V(0,1,0),0,0,0,0,0,0,pm,0.85f,0.85f,0.85f,0.7f,0.7f,0.7f); addTri(m,top,tip,mid-s2,V(0,1,0),V(0,1,0),V(0,1,0),0,0,0,0,0,0,pm,0.85f,0.85f,0.85f,0.7f,0.7f,0.7f); }
    float cr=pr*0.7f; for(int k=0;k<6;k++){ float a0=k*PI/3,a1=(k+1)*PI/3; addTri(m,top+V(0,0.004f,0),top+V(cosf(a1)*cr,0.004f,sinf(a1)*cr),top+V(cosf(a0)*cr,0.004f,sinf(a0)*cr),V(0,1,0),V(0,1,0),V(0,1,0),0,0,0,0,0,0,f.kind==1?M_DARKWAX:M_FLY,0.85f,0.85f,0.85f,0.7f,0.7f,0.7f); } }
  buildMesh(m); }

// tree
struct Leaf { V p; V n; float s; float rnd; float sv,kv; };
struct TreeDef { std::vector<Leaf> leaves; Mesh trunk; float h; };
static TreeDef makeTree(uint64_t seed){ Rng r(seed); TreeDef T; float h=5.5f+3.5f*r.f(); T.h=h; Mesh&m=T.trunk;
  auto cyl=[&](V a, V b, float ra, float rb, int seg){ V ax=norm(b-a); V t,bb; onb(ax,t,bb); for(int i=0;i<seg;i++){ float p0=2*PI*i/seg,p1=2*PI*(i+1)/seg; V d0=t*cosf(p0)+bb*sinf(p0), d1=t*cosf(p1)+bb*sinf(p1);
    addTri(m,a+d0*ra,b+d0*rb,b+d1*rb,d0,d0,d1,0,0,0,1,0,1,M_BARK); addTri(m,a+d0*ra,b+d1*rb,a+d1*ra,d0,d1,d1,0,0,0,1,0,0,M_BARK); } };
  V p(0,0,0); float rad=0.16f+0.08f*r.f(); int nseg=6; V lean((r.f()-0.5f)*0.12f,1,(r.f()-0.5f)*0.12f);
  for(int i=0;i<nseg;i++){ V q=p+norm(lean+V((r.f()-0.5f)*0.15f,0,(r.f()-0.5f)*0.15f))*(h*0.75f/nseg); cyl(p,q,rad*(1-0.1f*i),rad*(1-0.1f*(i+1)),10); p=q; }
  V topc=p; int nb=4+(int)(r.f()*3); for(int k=0;k<nb;k++){ float a=r.f()*2*PI; V d=norm(V(cosf(a),0.7f+0.6f*r.f(),sinf(a))); V s=topc-V(0,h*0.15f*r.f(),0); V e=s+d*(1.6f+1.4f*r.f()); cyl(s,e,rad*0.45f,rad*0.12f,7); }
  buildMesh(m);
  int nl=1100+(int)(r.f()*500); float cr=1.9f+1.1f*r.f(); V cc=topc+V(0,cr*0.55f,0);
  for(int i=0;i<nl;i++){ float u=r.f(),v=r.f(),w=r.f(); float th=acosf(2*u-1), ph=2*PI*v; float rr=cr*powf(w,0.3f); V d(sinf(th)*cosf(ph),cosf(th)*0.8f,sinf(th)*sinf(ph)); Leaf L; L.p=cc+d*rr; if(L.p.y<topc.y-0.5f) continue; L.n=norm(V(r.f()-0.5f,r.f()*0.6f,r.f()-0.5f)+d*0.6f); L.s=0.07f+0.06f*r.f(); L.rnd=r.f(); L.sv=1; L.kv=1; T.leaves.push_back(L); }
  return T; }
static void buildTreeLeaves(Mesh&m, const TreeDef&T, float t, float ph){ m.tris.clear(); for(const Leaf&L:T.leaves){ V n=L.n; V tt,bb; onb(n,tt,bb); V p=L.p+V(sinf(1.3f*t+ph+L.p.y*0.5f)*0.05f,0,cosf(0.9f*t+ph)*0.04f); float a=L.rnd*6.28f; V e1=(tt*cosf(a)+bb*sinf(a))*L.s, e2=(bb*cosf(a)-tt*sinf(a))*L.s*0.6f;
    addTri(m,p-e1,p+e2,p+e1,n,n,n,L.rnd,0,L.rnd,0,L.rnd,1,M_LEAF,L.sv,L.sv,L.sv,L.kv,L.kv,L.kv); addTri(m,p-e1,p-e2,p+e2,n,n,n,L.rnd,0,L.rnd,1,L.rnd,0,M_LEAF,L.sv,L.sv,L.sv,L.kv,L.kv,L.kv); } buildMesh(m); }


static bool meshAny(const Mesh&m, V o, V d, float tmax, V&tr);
static bool sceneAny(const Scene&s, V o, V d, float tmax){ V id(1.f/d.x,1.f/d.y,1.f/d.z); int stack[64]; int sp=0; stack[sp++]=0;
  while(sp){ const Node&n=s.tnodes[stack[--sp]]; float tn; if(!boxHit(n,o,id,tmax,tn)) continue;
    if(n.count){ for(int i=0;i<n.count;i++){ int ii=s.tidx[n.left+i]; const Inst&in=s.insts[ii]; V lo=xp(in.inv,o), ld=xv(in.inv,d); V tr(1,1,1); if(meshAny(s.meshes[in.mesh],lo,ld,tmax,tr)) return true; } }
    else { stack[sp++]=n.left; stack[sp++]=n.left+1; } } return false; }
extern V SUN; extern float SUN_COS;
static void bakePatch(Patch&p, float TR, float windAmp){ Scene bs; Mesh gm; buildGrassMesh(gm,p,0,windAmp); bs.meshes.push_back(gm);
  Mesh g; addQuad(g,V(-30,0,-30),V(-30,0,30),V(30,0,30),V(30,0,-30),M_SOIL); buildMesh(g); bs.meshes.push_back(g);
  float HX=sqrtf(3.f)*TR, HZ=1.5f*TR; float offs[7][2]={{0,0},{HX,0},{-HX,0},{HX/2,HZ},{-HX/2,HZ},{HX/2,-HZ},{-HX/2,-HZ}};
  for(int k=0;k<7;k++){ Inst in; in.mesh=0; in.xf=xfMake(V(offs[k][0],0,offs[k][1]),0,0,V(1,1,1)); in.inv=xfInverse(in.xf); in.matOverride=-1; in.tint=V(-1,-1,-1); bs.insts.push_back(in); }
  { Inst in; in.mesh=1; in.xf=xfMake(V(0,0,0),0,0,V(1,1,1)); in.inv=in.xf; in.matOverride=-1; in.tint=V(-1,-1,-1); bs.insts.push_back(in); }
  buildTLAS(bs); const int NS=20, NK=20;
  #pragma omp parallel for schedule(dynamic,32)
  for(int bi=0;bi<(int)p.blades.size();bi++){ Blade&b=p.blades[bi]; Rng rng(bi*77+5); V P[5]; V dir(cosf(b.yaw),0,sinf(b.yaw)); bladePts(b,V(b.x,0,b.z),dir,windAmp*0.6f,V(0,0,0),P);
    for(int i=0;i<5;i++){ int vs=0,vk=0; for(int k=0;k<NS;k++){ V d=coneDir(SUN,SUN_COS,rng.f(),rng.f()); if(!sceneAny(bs,P[i]+d*0.012f,d,1e30f)) vs++; }
      for(int k=0;k<NK;k++){ V d=cosHemi(V(0,1,0),rng.f(),rng.f()); if(!sceneAny(bs,P[i]+V(0,0.006f,0)+d*0.006f,d,1e30f)) vk++; }
      b.sv[i]=vs/(float)NS; b.kv[i]=vk/(float)NK; } } }
static void bakeTree(TreeDef&T){ Scene bs; bs.meshes.push_back(T.trunk); Mesh lm; buildTreeLeaves(lm,T,0,0); bs.meshes.push_back(lm);
  for(int k=0;k<2;k++){ Inst in; in.mesh=k; in.xf=xfMake(V(0,0,0),0,0,V(1,1,1)); in.inv=in.xf; in.matOverride=-1; in.tint=V(-1,-1,-1); bs.insts.push_back(in); } buildTLAS(bs); const int NS=16;
  #pragma omp parallel for schedule(dynamic,32)
  for(int li=0;li<(int)T.leaves.size();li++){ Leaf&L=T.leaves[li]; Rng rng(li*31+3); int vs=0,vk=0; for(int k=0;k<NS;k++){ V d=coneDir(SUN,SUN_COS,rng.f(),rng.f()); if(!sceneAny(bs,L.p+d*0.05f,d,1e30f)) vs++; V d2=cosHemi(V(0,1,0),rng.f(),rng.f()); if(!sceneAny(bs,L.p+V(0,0.03f,0)+d2*0.03f,d2,1e30f)) vk++; }
    L.sv=0.25f+0.75f*vs/(float)NS; L.kv=0.3f+0.7f*vk/(float)NS; } }
// ---------------- materials / shading ----------------
struct MatEval { V albedo; V trans; float rough; float f0; int type; float sheen; };
static MatEval evalMat(int mat, float u, float v, V tint){ MatEval e; e.trans=V(0,0,0); e.rough=0.5f; e.f0=0.04f; e.type=mat; e.sheen=0;
  switch(mat){
    case M_GRASS: { float g=powf(clampf(v,0,1),1.2f); V dark(0.04f,0.095f,0.02f), light(0.27f,0.39f,0.09f); V c=lerp(dark,light,g); c=c*(0.65f+0.7f*u); if(u>0.85f) c=c*V(1.15f,1.0f,0.7f); e.albedo=c; e.trans=c*V(1.4f,1.5f,0.9f); e.rough=0.32f; e.f0=0.035f; } break;
    case M_SOIL: e.albedo=V(0.085f,0.062f,0.038f)*(0.7f+0.6f*u); e.rough=0.9f; e.f0=0.02f; break;
    case M_WAX: e.albedo=V(0.85f,0.55f,0.16f); e.rough=0.28f; e.f0=0.04f; break;
    case M_DARKWAX: e.albedo=V(0.12f,0.07f,0.035f); e.rough=0.25f; e.f0=0.045f; break;
    case M_BARK: e.albedo=V(0.16f,0.11f,0.07f)*(0.7f+0.6f*fabsf(sinf(v*40))); e.rough=0.85f; e.f0=0.02f; break;
    case M_LEAF: { V c=lerp(V(0.06f,0.16f,0.03f),V(0.3f,0.42f,0.07f),u); if(u>0.9f) c=V(0.6f,0.35f,0.06f); e.albedo=c; e.trans=c*1.3f; e.rough=0.4f; e.f0=0.03f; } break;
    case M_EYE: e.albedo=V(0.01f,0.008f,0.006f); e.rough=0.08f; e.f0=0.05f; break;
    case M_EYEWHITE: e.albedo=V(0.9f,0.9f,0.88f); e.rough=0.12f; e.f0=0.04f; break;
    case M_POLLEN: e.albedo=V(1.0f,0.92f,0.6f); e.rough=0.6f; e.f0=0.03f; break;
    case M_FLW: e.albedo=V(0.95f,0.95f,0.92f); e.trans=V(0.6f,0.6f,0.55f); e.rough=0.5f; break;
    case M_FLY: e.albedo=V(0.98f,0.75f,0.12f); e.trans=V(0.5f,0.35f,0.05f); e.rough=0.5f; break;
    case M_HONEYCORE: e.albedo=V(0.92f,0.58f,0.1f); e.rough=0.22f; e.f0=0.045f; break;
    case M_CHEEK: e.albedo=V(0.95f,0.45f,0.4f); e.rough=0.3f; break;
    case M_BEE_ABD: { float sb=v*5.2f-0.25f; float fr=sb-floorf(sb); int band=(int)floorf(sb); float edge=smooth(0.0f,0.12f,fr)*(1-smooth(0.88f,1.0f,fr)); V yel(0.9f,0.62f,0.1f), drk(0.07f,0.05f,0.035f); V c=(band&1)?drk:yel; V other=(band&1)?yel:drk; c=lerp(other,c,edge); if(v>0.93f) c=drk; e.albedo=c; e.rough=0.55f; e.f0=0.035f; e.sheen=0.35f; } break;
    case M_FUZZ: e.albedo=V(0.9f,0.62f,0.14f); e.rough=0.75f; e.f0=0.03f; e.sheen=0.7f; break;
    case M_HEADB: e.albedo=V(0.1f,0.07f,0.045f); e.rough=0.6f; e.f0=0.035f; e.sheen=0.35f; break;
    default: e.albedo=V(0.5f,0.5f,0.5f); }
  if(tint.x>=0) e.albedo=e.albedo*tint;
  return e; }
inline float ggxD(float nh,float a){ float a2=a*a; float d=nh*nh*(a2-1)+1; return a2/(PI*d*d+1e-9f); }
inline float ggxG1(float nv,float a){ float k=a*a/2; return nv/(nv*(1-k)+k+1e-9f); }
inline V fresnel(float vh,float f0){ float f=powf(1-vh,5); return V(f0+(1-f0)*f,f0+(1-f0)*f,f0+(1-f0)*f); }
inline float fresnelDiel(float cosi, float eta){ // eta = n_t/n_i
  float sint2=(1-cosi*cosi)/(eta*eta); if(sint2>=1) return 1.f; float cost=sqrtf(1-sint2); float rs=(cosi-eta*cost)/(cosi+eta*cost), rp=(eta*cosi-cost)/(eta*cosi+cost); return 0.5f*(rs*rs+rp*rp); }

// ---------------- sky / sun ----------------
V SUN; V SUNCOL(1.0f,0.80f,0.55f); float SUNRAD=11.0f; float SUN_COS=cosf(0.0075f); float EXPOSURE=0.7f;
static V sky(V d, bool withSun){ float y=d.y; V zen(0.17f,0.36f,0.78f), hor(1.0f,0.8f,0.58f); V c; if(y>=0) c=lerp(hor,zen,powf(y,0.42f)); else c=lerp(hor,V(0.35f,0.3f,0.22f),clampf(-y*8,0,1));
  float s=std::max(0.f,dot(d,SUN)); c+=SUNCOL*(0.10f*powf(s,6)+0.5f*powf(s,80)+0.9f*powf(s,500)); c*=0.85f;
  if(withSun && s>SUN_COS) c+=SUNCOL*220.f; return c; }

// ---------------- integrator ----------------
Scene SC;
struct Shade { V ng, ns, p; MatEval m; bool frontFace; float sv,kv; };
static void getShade(const Hit&h, V o, V d, Shade&s){ const Inst&in=SC.insts[h.inst]; const Tri&t=SC.meshes[in.mesh].tris[h.tri]; float w=1-h.u-h.v;
  V nl=norm(t.n0*w+t.n1*h.u+t.n2*h.v); V ngl=cross(t.e1,t.e2); s.ng=norm(xnT(in.inv,ngl)); s.ns=norm(xnT(in.inv,nl)); if(dot(s.ns,s.ng)<0) s.ns=-s.ns;
  s.p=o+d*h.t; float u=t.u0*w+t.u1*h.u+t.u2*h.v, v=t.v0*w+t.v1*h.u+t.v2*h.v; int mat=in.matOverride>=0?in.matOverride:t.mat; s.m=evalMat(mat,u,v,in.tint); s.sv=t.s0*w+t.s1*h.u+t.s2*h.v; s.kv=t.k0*w+t.k1*h.u+t.k2*h.v;
  s.frontFace=dot(d,s.ng)<0; if(!s.frontFace && mat!=M_GLASS){ s.ng=-s.ng; s.ns=-s.ns; } }
static bool meshAny(const Mesh&m, V o, V d, float tmax, V&tr){ V id(1.f/d.x,1.f/d.y,1.f/d.z); int stack[64]; int sp=0; stack[sp++]=0;
  while(sp){ const Node&n=m.nodes[stack[--sp]]; float tn; if(!boxHit(n,o,id,tmax,tn)) continue;
    if(n.count){ for(int i=0;i<n.count;i++){ int ti=m.idx[n.left+i]; float tt=tmax,u,v; if(triHit(m.hot[n.left+i],o,d,tt,u,v)){ int mat=m.tris[ti].mat; if(mat==M_GLASS) tr*=V(0.8f,0.6f,0.3f); else if(mat==M_THINGLASS) tr*=0.85f; else return true; } } }
    else { stack[sp++]=n.left; stack[sp++]=n.left+1; } } return false; }
static V shadowTrans(V o, V d, float tmax){ V tr(1,1,1); V id(1.f/d.x,1.f/d.y,1.f/d.z); int stack[64]; int sp=0; stack[sp++]=0;
  while(sp){ const Node&n=SC.tnodes[stack[--sp]]; float tn; if(!boxHit(n,o,id,tmax,tn)) continue;
    if(n.count){ for(int i=0;i<n.count;i++){ int ii=SC.tidx[n.left+i]; const Inst&in=SC.insts[ii]; V lo=xp(in.inv,o), ld=xv(in.inv,d); if(in.matOverride==M_GLASS){ Hit hh; hh.t=tmax; hh.tri=-1; meshHit(SC.meshes[in.mesh],lo,ld,hh); if(hh.tri>=0) tr*=V(0.8f,0.6f,0.3f); continue; }
        if(meshAny(SC.meshes[in.mesh],lo,ld,tmax,tr)) return V(0,0,0); } }
    else { stack[sp++]=n.left; stack[sp++]=n.left+1; } } return tr; }
int HERO_I0=0, HERO_I1=0; V HERO_C; float HERO_R=0.5f;
static float heroShadow(V o, V d){ // 1 = unshadowed by hero
  V oc=HERO_C-o; float tc=dot(oc,d); if(tc<0) return 1.f; float d2=dot(oc,oc)-tc*tc; if(d2>HERO_R*HERO_R) return 1.f;
  V id(1.f/d.x,1.f/d.y,1.f/d.z); for(int i=HERO_I0;i<HERO_I1;i++){ const Inst&in=SC.insts[i]; Node nb; nb.bmin=in.bmin; nb.bmax=in.bmax; float tn; if(!boxHit(nb,o,id,1e30f,tn)) continue; V lo=xp(in.inv,o), ld=xv(in.inv,d); Hit hh; hh.t=1e30f; hh.tri=-1; meshHit(SC.meshes[in.mesh],lo,ld,hh); if(hh.tri>=0){ int mat=SC.meshes[in.mesh].tris[hh.tri].mat; if(mat==M_THINGLASS) continue; return 0.f; } } return 1.f; }
static V ambientSky(V n){ return lerp(V(0.17f,0.26f,0.06f), V(0.45f,0.48f,0.6f), 0.5f+0.5f*n.y); }
struct Aov { V albedo, normal; float depth; };
static V trace(V o, V d, Rng&rng, Aov&aov){ V L(0,0,0), beta(1,1,1); bool specular=true; aov.depth=1e9f; aov.albedo=V(1,1,1); aov.normal=V(0,0,0); bool aovSet=false; float sumT=0;
  for(int depth=0;depth<8;depth++){ if(depth>=5 && !specular) break; Hit h; h.t=1e30f; if(!sceneHit(SC,o,d,h)){ L+=beta*sky(d,specular); break; }
    Shade s; getShade(h,o,d,s); sumT+=h.t;
    if(!aovSet && s.m.type!=M_GLASS && s.m.type!=M_THINGLASS){ aov.albedo=s.m.albedo; aov.normal=s.ns; aov.depth=sumT; aovSet=true; }
    if(s.m.type==M_GLASS){ float eta=1.47f; bool entering=s.frontFace; V n=entering?s.ns:-s.ns; float cosi=clampf(-dot(d,n),0,1); float e=entering?1.f/eta:eta; float F=fresnelDiel(cosi, 1.f/e);
      if(!entering){ V ab(0.35f,1.1f,3.5f); beta*=expv(-ab*h.t); } // Beer inside honey
      if(rng.f()<F){ d=norm(d+n*(2*cosi)); o=s.p+n*1e-4f; } else { float k=1-e*e*(1-cosi*cosi); if(k<0){ d=norm(d+n*(2*cosi)); o=s.p+n*1e-4f; } else { d=norm(d*e+n*(e*cosi-sqrtf(k))); o=s.p-n*1e-4f; } }
      specular=true; continue; }
    if(s.m.type==M_THINGLASS){ V n=s.ns; float cosi=clampf(-dot(d,n),0,1); float F=fresnelDiel(cosi,1.4f)*0.9f; V rd=norm(d+n*(2*cosi)); L+=beta*F*(sky(rd,false)*0.9f+SUNCOL*SUNRAD*0.02f*powf(std::max(0.f,dot(rd,SUN)),30.f)); beta*=(1-F)*V(0.9f,0.96f,1.0f); o=s.p+d*1e-4f; specular=true; continue; }
    if(s.sv>=0.f){ // baked lighting: no secondary rays
      V nsh=s.ns; V wo=-d; V ld=SUN; float ndl=dot(nsh,ld); float sunv=s.sv*heroShadow(s.p+s.ng*1e-3f, ld); V sunL=SUNCOL*SUNRAD*sunv;
      if(ndl>0){ V f=s.m.albedo*(1.f/PI); V hv=norm(wo+ld); float nh=std::max(0.f,dot(nsh,hv)), nv=std::max(1e-4f,dot(nsh,wo)), vh=std::max(0.f,dot(wo,hv)); float a=std::max(0.03f,s.m.rough*s.m.rough);
        V spec=fresnel(vh,s.m.f0)*(ggxD(nh,a)*ggxG1(nv,a)*ggxG1(ndl,a)/(4*nv*ndl+1e-6f)); L+=beta*sunL*(f+spec*0.6f)*ndl; }
      else { L+=beta*sunL*s.m.trans*(1.f/PI)*(-ndl)*0.8f; }
      float nv=std::max(0.f,dot(nsh,wo)); L+=beta*s.m.albedo*ambientSky(nsh)*s.kv*(1.0f+0.15f*powf(1-nv,2));
      L+=beta*s.m.trans*V(0.17f,0.26f,0.06f)*0.35f*s.kv; // light through neighbours
      break; }
    if(s.m.type==M_SOIL){ V nsh=s.ns; V ld=coneDir(SUN, SUN_COS, rng.f(), rng.f()); float ndl=dot(nsh,ld); V vis=shadowTrans(s.p+s.ng*2e-4f, ld, 1e30f);
      if(ndl>0) L+=beta*SUNCOL*SUNRAD*vis*s.m.albedo*(1.f/PI)*ndl; L+=beta*s.m.albedo*ambientSky(nsh)*0.35f; break; }
    // direct sun
    V nsh=s.ns; V wo=-d; { V ld=coneDir(SUN, SUN_COS, rng.f(), rng.f()); float ndl=dot(nsh,ld); float ngl=dot(s.ng,ld);
      V vis=shadowTrans(s.p+s.ng*2e-4f*(ngl>0?1:-1), ld, 1e30f); if(vis.x+vis.y+vis.z>0){ V sunL=SUNCOL*SUNRAD*vis;
        if(ndl>0 && ngl>0){ V f=s.m.albedo*(1.f/PI); V hv=norm(wo+ld); float nh=std::max(0.f,dot(nsh,hv)), nv=std::max(1e-4f,dot(nsh,wo)), vh=std::max(0.f,dot(wo,hv)); float a=std::max(0.03f,s.m.rough*s.m.rough);
          V spec=fresnel(vh,s.m.f0)*(ggxD(nh,a)*ggxG1(nv,a)*ggxG1(ndl,a)/(4*nv*ndl+1e-6f)); L+=beta*sunL*(f+spec)*ndl; if(s.m.sheen>0){ float rim=powf(1-nv,3); L+=beta*sunL*(s.m.albedo*0.8f+V(0.25f,0.22f,0.18f))*s.m.sheen*rim*ndl*0.9f; } }
        else if(ndl<0 && s.m.trans.x+s.m.trans.y+s.m.trans.z>0){ L+=beta*sunL*s.m.trans*(1.f/PI)*(-ndl)*0.8f; }
        else if(ndl<0 && s.m.sheen>0){ float nv=std::max(0.f,dot(nsh,wo)); float rim=powf(1-nv,2.5f); L+=beta*sunL*(s.m.albedo*0.6f+V(0.3f,0.26f,0.2f))*s.m.sheen*rim*(-ndl)*0.7f; } } }
    // bounce
    float pt = (s.m.trans.x+s.m.trans.y+s.m.trans.z)>0 ? 0.22f : 0.f; float ps = 0.25f; float r=rng.f();
    if(r<pt){ V nd=cosHemi(-nsh,rng.f(),rng.f()); beta*=s.m.trans*(0.8f/pt); o=s.p-s.ng*2e-4f; d=nd; specular=false; }
    else if(r<pt+ps){ V hv; float a=std::max(0.03f,s.m.rough*s.m.rough); float u1=rng.f(),u2=rng.f(); float ct=sqrtf((1-u1)/(1+(a*a-1)*u1)); float st=sqrtf(1-ct*ct); float ph=2*PI*u2; V t,b; onb(nsh,t,b); hv=norm(t*(st*cosf(ph))+b*(st*sinf(ph))+nsh*ct);
      V nd=norm(hv*(2*dot(wo,hv))-wo); float ndl=dot(nsh,nd); if(ndl<=0||dot(s.ng,nd)<=0) break; float nv=std::max(1e-4f,dot(nsh,wo)), vh=std::max(1e-4f,dot(wo,hv)), nh=std::max(1e-4f,dot(nsh,hv));
      V F=fresnel(vh,s.m.f0); float G=ggxG1(nv,a)*ggxG1(ndl,a); V w=F*(G*vh/(nv*nh+1e-6f)); beta*=w*(1.f/ps); o=s.p+s.ng*2e-4f; d=nd; specular=s.m.rough<0.15f; }
    else { V nd=cosHemi(nsh,rng.f(),rng.f()); if(dot(s.ng,nd)<=0) break; beta*=s.m.albedo*(1.f/(1-pt-ps)); o=s.p+s.ng*2e-4f; d=nd; specular=false; }
    if(depth>=1){ float q=std::min(0.85f,std::max(beta.x,std::max(beta.y,beta.z))); if(rng.f()>q) break; beta*=1.f/q; }
    if(depth>=4 && !specular) { /* keep going a bit */ }
  }
  float m=std::max(L.x,std::max(L.y,L.z)); if(m>40.f) L*=40.f/m;
  return L; }


// ---------------- hero (smooth bee) ----------------
struct Hop { float t0,dur,h,v; };
std::vector<Hop> HOPS; V HSTART(-6.0f,0,-1.0f); float YAW=-0.3f; V FD;
struct HeroState { float x,z,s,hop; bool inAir,big; float vfrac,since,sinceBig; };
static HeroState heroState(float t){ HeroState H; float s=0; H.hop=0; H.inAir=false; H.big=false; H.vfrac=0;
  for(const Hop&h:HOPS){ if(t>=h.t0+h.dur) s+=h.v*h.dur; else if(t>=h.t0){ float p=(t-h.t0)/h.dur; s+=h.v*(t-h.t0); H.hop=h.h*4*p*(1-p); H.inAir=true; H.vfrac=1-2*p; H.big=h.h>0.7f; break; } else break; }
  H.x=HSTART.x+FD.x*s; H.z=HSTART.z+FD.z*s; H.s=s; H.since=99; H.sinceBig=99; for(const Hop&h:HOPS){ float lt=h.t0+h.dur; if(t>=lt){ H.since=std::min(H.since,t-lt); if(h.h>0.7f) H.sinceBig=t-lt; } } return H; }
int MESH_SPH_ABD, MESH_SPH_FUZZ, MESH_SPH_HEAD, MESH_SPH_EYE, MESH_SPH_TIP, MESH_SPH_WING, MESH_SPH_POLLEN, MESH_CYL_DARK;
static void addPart(std::vector<Inst>&out, int mesh, const Xf&base, V c, V ex, V ey, V ez, int matOv=-1){ Inst in; in.mesh=mesh; in.xf=xfMul(base, xfAxes(c,ex,ey,ez)); in.inv=xfInverse(in.xf); in.matOverride=matOv; in.tint=V(-1,-1,-1); out.push_back(in); }
static void addSph(std::vector<Inst>&out, int mesh, V pos, float r, int matOv=-1){ Inst in; in.mesh=mesh; in.xf=xfMake(pos,0,0,V(r,r,r)); in.inv=xfInverse(in.xf); in.matOverride=matOv; in.tint=V(-1,-1,-1); out.push_back(in); }
static V heroPos; static float heroGround; static bool heroDown;
static void addSeg(std::vector<Inst>&out, const Xf&base, V a, V b, float r){ V d=b-a; V t,bb; onb(norm(d),t,bb); addPart(out,MESH_CYL_DARK,base,a,t*r,d,bb*r); }
static void buildHero(std::vector<Inst>&out, float t){ HeroState H=heroState(t); float gy=hstat(H.x,H.z);
  float sy=1, sxz=1; if(H.inAir) sy=1+0.14f*fabsf(H.vfrac)*(H.big?1.4f:1);
  if(H.since<0.22f){ float k=H.since/0.22f; sy=lerpf(0.72f,1.07f,smooth(0,1,k)); if(H.sinceBig<0.5f) sy=lerpf(0.6f,1.08f,smooth(0,0.5f,H.sinceBig)); } else if(H.since<0.4f) sy=lerpf(1.07f,1.0f,(H.since-0.22f)/0.18f);
  sxz=1/sqrtf(sy); float pitch=H.inAir?(H.big?0.4f:0.3f)*H.vfrac:(H.since<0.2f?-0.1f*(1-H.since/0.2f):0.f); float idle=sinf(t*2.2f)*0.02f; pitch+=idle;
  V origin(H.x, gy+H.hop, H.z); heroPos=origin; heroGround=gy; heroDown=!H.inAir;
  V fwd=FD, up(0,1,0), side(-FD.z,0,FD.x); V f2=fwd*cosf(pitch)+up*sinf(pitch), u2=up*cosf(pitch)-fwd*sinf(pitch);
  Xf base=xfAxes(origin, f2*sxz, u2*sy, side*sxz);
  V X(1,0,0),Y(0,1,0),Z(0,0,1);
  // abdomen: ellipsoid, sphere polar axis along body x (tilted down at back)
  { float a=-0.3f; V ax=V(cosf(a),sinf(a),0), ay=V(-sinf(a),cosf(a),0); addPart(out,MESH_SPH_ABD,base,V(-0.13f,0.27f,0), ay*0.15f, ax*0.2f, Z*0.15f); }
  addPart(out,MESH_SPH_FUZZ,base,V(0.11f,0.31f,0), X*0.14f, Y*0.135f, Z*0.14f);
  V hc(0.29f,0.32f,0); addPart(out,MESH_SPH_HEAD,base,hc, X*0.1f, Y*0.1f, Z*0.1f);
  for(int sg=-1;sg<=1;sg+=2){ V e=hc+V(0.065f,0.03f,sg*0.06f); float blink=(fmodf(t+1.3f,3.4f)<0.1f)?0.25f:1.f; V d=norm(e-hc); V tt,bb; onb(d,tt,bb); addPart(out,MESH_SPH_EYE,base,e, tt*0.04f*blink, d*0.03f, bb*0.045f);
    // antenna
    V a0=hc+V(0.03f,0.095f,sg*0.03f); float bob=sinf(t*9)*0.1f*(H.inAir?1:0.4f); V a1=a0+V(0.09f+bob*0.3f,0.12f,sg*0.06f); addSeg(out,base,a0,a1,0.006f); addSph(out,MESH_SPH_TIP,xp(base,a1),0.012f); }
  // legs: 3 pairs
  for(int sg=-1;sg<=1;sg+=2) for(int k=0;k<3;k++){ float ax=0.17f-k*0.12f; V att(ax,0.22f,sg*0.1f); float tuck=H.inAir?0.08f:0; V knee(ax+0.02f-k*0.01f,0.17f+tuck*0.5f,sg*(0.2f+0.02f*k)); V foot(ax+0.05f-k*0.03f,0.0f+tuck,sg*(0.24f+0.03f*k));
    if(H.inAir) knee.y+=0.03f; addSeg(out,base,att,knee,0.009f); addSeg(out,base,knee,foot,0.007f); addSph(out,MESH_SPH_TIP,xp(base,foot),0.009f,M_HEADB); }
  // wings
  float flap=sinf(t*2*PI*9)*(H.inAir?0.7f:0.2f)+0.3f; for(int sg=-1;sg<=1;sg+=2){ float a=flap*sg; V wz=V(0,sinf(a)*sg,cosf(a))*sg; V wc=V(0.1f,0.42f,0)+wz*0.17f; V wx=V(1,0,0); V wy=cross(wz,wx); addPart(out,MESH_SPH_WING,base,wc, wx*0.1f, wy*0.003f, wz*0.18f); }
}

// ---------------- camera ----------------
struct Cam { V eye, look; float fov, aperture, focus; };
static Cam cameraFor(float t){ Cam c; float k1=smooth(7.2f,8.8f,t); float u=clampf(t/7,0,1);
  V off0(lerpf(2.4f,2.1f,u), lerpf(0.6f,0.85f,u), lerpf(1.55f,1.7f,u)); V off1(3.4f,1.8f,3.6f); V off=lerp(off0,off1,k1);
  HeroState H=heroState(t); float gy=hstat(H.x,H.z);
  c.look=V(H.x+FD.x*lerpf(0.25f,0.8f,k1), gy+lerpf(0.32f,0.25f,k1)+H.hop*0.5f, H.z+FD.z*lerpf(0.25f,0.8f,k1));
  c.eye=V(H.x+off.x, gy+off.y+H.hop*0.15f, H.z+off.z); c.fov=lerpf(38,42,k1)*PI/180; c.focus=len(V(H.x,gy+0.35f+H.hop,H.z)-c.eye); c.aperture=lerpf(0.016f,0.008f,k1); return c; }

// ---------------- post ----------------
static void atrous(std::vector<V>&col, const std::vector<V>&alb, const std::vector<V>&nrm, const std::vector<float>&dep, int W,int H){
  std::vector<V> dem(W*H); for(int i=0;i<W*H;i++){ V a=alb[i]; dem[i]=V(col[i].x/(a.x+0.02f),col[i].y/(a.y+0.02f),col[i].z/(a.z+0.02f)); }
  std::vector<V> tmp(W*H); const float k[3]={3.f/8,1.f/4,1.f/16};
  for(int it=0;it<4;it++){ int step=1<<it; float sigL=0.9f*(it+1);
    #pragma omp parallel for schedule(dynamic,8)
    for(int y=0;y<H;y++) for(int x=0;x<W;x++){ int i=y*W+x; V c0=dem[i]; V n0=nrm[i]; float d0=dep[i]; V sum(0,0,0); float ws=0; float l0=lum(c0);
      for(int dy=-2;dy<=2;dy++) for(int dx=-2;dx<=2;dx++){ int xx=x+dx*step, yy=y+dy*step; if(xx<0||yy<0||xx>=W||yy>=H) continue; int j=yy*W+xx; float w=k[abs(dx)]*k[abs(dy)];
        float wn=powf(std::max(0.f,dot(n0,nrm[j])),3); float wd=expf(-fabsf(d0-dep[j])/(0.05f*d0+0.08f)); float wl=expf(-fabsf(l0-lum(dem[j]))/sigL); w*=wn*wd*wl; sum+=dem[j]*w; ws+=w; }
      tmp[i]=ws>0?sum/ws:c0; }
    std::swap(dem,tmp); }
  for(int i=0;i<W*H;i++){ V a=alb[i]; col[i]=V(dem[i].x*(a.x+0.02f),dem[i].y*(a.y+0.02f),dem[i].z*(a.z+0.02f)); } }
static V aces(V x){ auto f=[](float v){ return clampf((v*(2.51f*v+0.03f))/(v*(2.43f*v+0.59f)+0.14f),0,1); }; return V(f(x.x),f(x.y),f(x.z)); }

int main(int argc,char**argv){ int f0=atoi(argv[1]), f1=atoi(argv[2]); int W=atoi(argv[3]), H=atoi(argv[4]); int SPP=atoi(argv[5]); const char*outdir=argv[6]; int FPS=24;
  SUN=norm(V(0.62f,0.32f,-0.73f)); FD=V(cosf(YAW),0,sinf(YAW));
  { float t=0.15f; while(t<7.0f){ HOPS.push_back({t,0.56f,0.36f,1.05f}); t+=0.68f; } HOPS.push_back({7.3f,1.15f,1.05f,1.3f}); }
  { float s=0; for(const Hop&h:HOPS){ s+=h.v*h.dur; bool big=h.h>0.7f; RIPS.push_back({HSTART.x+FD.x*s, HSTART.z+FD.z*s, h.t0+h.dur, big?3.0f:1.6f, big?0.55f:0.09f, big?0.5f:1.4f, big?1.3f:3.0f}); } }
  // meshes
  SC.meshes.push_back(sphere(M_BEE_ABD,28,18)); MESH_SPH_ABD=0;
  SC.meshes.push_back(sphere(M_FUZZ,24,16)); MESH_SPH_FUZZ=1;
  SC.meshes.push_back(sphere(M_FUZZ,24,16)); MESH_SPH_HEAD=2;
  SC.meshes.push_back(sphere(M_EYE,16,12)); MESH_SPH_EYE=3;
  SC.meshes.push_back(sphere(M_HEADB,10,8)); MESH_SPH_TIP=4;
  SC.meshes.push_back(sphere(M_THINGLASS,24,12)); MESH_SPH_WING=5;
  SC.meshes.push_back(sphere(M_POLLEN,8,6)); MESH_SPH_POLLEN=6;
  SC.meshes.push_back(cylinderMesh(M_HEADB,8)); MESH_CYL_DARK=7;
  // ground heightfield (one continuous mesh)
  int MESH_GROUND=(int)SC.meshes.size(); { Mesh g; Rng gr(5); const float X0=-45,X1=65,Z0=-80,Z1=30; const float st=1.0f; int nx=(int)((X1-X0)/st), nz=(int)((Z1-Z0)/st);
    auto P=[&](int i,int j){ float x=X0+i*st, z=Z0+j*st; return V(x,hstat(x,z)-0.01f,z); }; auto N=[&](int i,int j){ V a=P(i+1,j)-P(i-1,j), b=P(i,j+1)-P(i,j-1); return norm(cross(b,a)); };
    for(int j=0;j<nz;j++) for(int i=0;i<nx;i++){ V p00=P(i,j),p10=P(i+1,j),p01=P(i,j+1),p11=P(i+1,j+1); V n00=N(i,j),n10=N(i+1,j),n01=N(i,j+1),n11=N(i+1,j+1); float u0=gr.f(),u1=gr.f(),u2=gr.f(),u3=gr.f();
      addTri(g,p00,p01,p11,n00,n01,n11,u0,0,u1,0,u2,0,M_SOIL); addTri(g,p00,p11,p10,n00,n11,n10,u0,0,u2,0,u3,0,M_SOIL); } buildMesh(g); SC.meshes.push_back(g); }
  // grass patch variants: 0-5 meadow, 6-7 short (path), 8-9 far (coarse)
  const int NP=10; std::vector<Patch> patches; const float TR=1.6f;
  for(int i=0;i<NP;i++){ int n = i>=8?650:(i>=6?3000:(i<2?2600:1800)); float hm = i>=8?1.15f:(i==6?0.45f:(i==7?0.7f:1.f)); patches.push_back(makePatch(100+i,TR*1.0f, n, (i%2==0)&&i<6, hm)); if(i>=8) for(auto&bl:patches[i].blades) bl.w*=2.2f; }
  { double tb=omp_get_wtime(); for(int i=0;i<NP;i++) bakePatch(patches[i], TR, (i>=6&&i<8)?0.03f:0.05f+0.02f*(i%6)); fprintf(stderr,"baked grass %.1fs\n",omp_get_wtime()-tb); }
  int MESH_GRASS0=(int)SC.meshes.size(); for(int i=0;i<NP;i++) SC.meshes.push_back(Mesh());
  const int NT=3; std::vector<TreeDef> trees; for(int i=0;i<NT;i++){ trees.push_back(makeTree(500+i)); bakeTree(trees.back()); } int MESH_TRUNK0=(int)SC.meshes.size(); for(int i=0;i<NT;i++) SC.meshes.push_back(trees[i].trunk); int MESH_LEAF0=(int)SC.meshes.size(); for(int i=0;i<NT;i++) SC.meshes.push_back(Mesh());
  const int MAXU=90; int MESH_UNIQ0=(int)SC.meshes.size(); for(int i=0;i<MAXU;i++) SC.meshes.push_back(Mesh());
  // static layout of hex cells
  struct TileI{float x,z; int patch; float yaw;}; std::vector<TileI> tiles; Rng r(77); float HX=sqrtf(3.f)*TR, HZ=1.5f*TR;
  for(int row=-34; row<=12; row++) for(int col=-16; col<=24; col++){ float x=col*HX+((row&1)?HX/2:0), z=row*HZ; float px=x-HSTART.x, pz=z-HSTART.z; float along=px*FD.x+pz*FD.z, side=-px*FD.z+pz*FD.x; int pi=(int)(r.f()*6);
    if(along>-5&&along<22&&fabsf(side)<2.0f) pi=6; else if(along>-6&&along<23&&fabsf(side)<3.6f) pi=7; else if(along<-9||along>24||fabsf(side)>8.5f) pi=8+(int)(r.f()*2); tiles.push_back({x,z,pi,0.f}); }
  auto nearPath=[&](float x,float z){ float px=x-HSTART.x, pz=z-HSTART.z; float along=px*FD.x+pz*FD.z; float side=-px*FD.z+pz*FD.x; if(along>-4&&along<20&&fabsf(side)<2.6f) return true; for(int k=0;k<4;k++){ float ox[4]={2.1f,2.6f,3.2f,1.2f}, oz[4]={1.35f,2.4f,3.4f,0.8f}; float cs=-ox[k]*FD.z+oz[k]*FD.x, ca=ox[k]*FD.x+oz[k]*FD.z; if(along>ca-4&&along<ca+20&&fabsf(side-cs)<3.0f) return true;} return false; };
  struct TreeI{float x,z,yaw,sc,ph; int v;}; std::vector<TreeI> treeI; for(int i=0;i<260;i++){ float x=-28+70*r.f(), z=-62+36*r.f(); if(nearPath(x,z)) continue; treeI.push_back({x,z,r.f()*6.28f,0.8f+0.5f*r.f(),r.f()*6.28f,(int)(r.f()*NT)}); }
  for(int i=0;i<16;i++){ float x=-14+34*r.f(), z=-24+30*r.f(); if(nearPath(x,z)) continue; { float px=x-HSTART.x, pz=z-HSTART.z; float along=px*FD.x+pz*FD.z, side=-px*FD.z+pz*FD.x; if(along>-8&&along<26&&fabsf(side)<7) continue; } treeI.push_back({x,z,r.f()*6.28f,0.7f+0.4f*r.f(),r.f()*6.28f,(int)(r.f()*NT)}); }
  struct Pol{float x,y,z,ph;}; std::vector<Pol> pol; for(int i=0;i<500;i++){ float x=-10+26*r.f(), z=-14+16*r.f(); pol.push_back({x,hstat(x,z)+0.15f+1.4f*powf(r.f(),1.5f),z,r.f()*6.28f}); }
  fprintf(stderr,"tiles %zu trees %zu\n",tiles.size(),treeI.size());
  std::vector<V> col(W*H), alb(W*H), nrm(W*H); std::vector<float> dep(W*H); std::vector<unsigned char> img(W*H*3);
  for(int f=f0; f<f1; f++){ float t=f/(float)FPS; double T0=omp_get_wtime();
    for(int i=0;i<NP;i++) buildGrassMesh(SC.meshes[MESH_GRASS0+i], patches[i], t, i>=6&&i<8?0.03f:0.05f+0.02f*(i%6));
    for(int i=0;i<NT;i++) buildTreeLeaves(SC.meshes[MESH_LEAF0+i], trees[i], t, i*2.1f);
    SC.insts.clear();
    { Inst g; g.mesh=MESH_GROUND; Xf id=xfMake(V(0,0,0),0,0,V(1,1,1)); g.xf=id; g.inv=id; g.matOverride=-1; g.tint=V(-1,-1,-1); SC.insts.push_back(g); }
    HeroState HS=heroState(t); Deform D; D.t=t; D.hero=V(HS.x,0,HS.z); D.heroDown=!HS.inAir; int nu=0;
    for(const TileI&ti:tiles){ float y=hstat(ti.x,ti.z);
      // affected by ripple / hero?
      bool aff=false; for(const Rip&rp:RIPS){ float a=t-rp.t; if(a<=0) continue; float g=rp.amp*expf(-a*rp.decay); if(g<0.004f) continue; float d=sqrtf((ti.x-rp.x)*(ti.x-rp.x)+(ti.z-rp.z)*(ti.z-rp.z)); float rr=a*rp.speed; if(fabsf(d-rr)<TR+2.5f/rp.width){ aff=true; break; } }
      if(!aff && D.heroDown){ float d=sqrtf((ti.x-HS.x)*(ti.x-HS.x)+(ti.z-HS.z)*(ti.z-HS.z)); if(d<TR+0.6f) aff=true; }
      Inst g; g.matOverride=-1; g.tint=V(-1,-1,-1);
      if(aff && nu<MAXU){ buildGrassMesh(SC.meshes[MESH_UNIQ0+nu], patches[ti.patch], t, ti.patch>=6&&ti.patch<8?0.03f:0.06f, ti.yaw, V(ti.x,y,ti.z), &D); g.mesh=MESH_UNIQ0+nu; Xf id=xfMake(V(0,0,0),0,0,V(1,1,1)); g.xf=id; g.inv=id; nu++; }
      else { g.mesh=MESH_GRASS0+ti.patch; g.xf=xfYaw(V(ti.x,y,ti.z),ti.yaw,V(1,1,1)); g.inv=xfInverse(g.xf); }
      SC.insts.push_back(g); }
    for(const TreeI&tr:treeI){ float y=hstat(tr.x,tr.z); Xf x=xfYaw(V(tr.x,y-0.1f,tr.z),tr.yaw,V(tr.sc,tr.sc,tr.sc)); Inst a; a.mesh=MESH_TRUNK0+tr.v; a.xf=x; a.inv=xfInverse(x); a.matOverride=-1; a.tint=V(-1,-1,-1); SC.insts.push_back(a); Inst b=a; b.mesh=MESH_LEAF0+tr.v; SC.insts.push_back(b); }
    for(const Pol&p:pol){ addSph(SC.insts,MESH_SPH_POLLEN,V(p.x+0.25f*t+0.1f*sinf(t+p.ph), p.y+0.08f*sinf(1.2f*t+p.ph), p.z+0.08f*sinf(0.8f*t+p.ph*2)), 0.003f); }
    HERO_I0=(int)SC.insts.size(); buildHero(SC.insts,t); HERO_I1=(int)SC.insts.size(); HERO_C=heroPos+V(0.08f,0.3f,0); HERO_R=0.6f;
    buildTLAS(SC); { V bmin(1e30f,1e30f,1e30f),bmax(-1e30f,-1e30f,-1e30f); for(int i=HERO_I0;i<HERO_I1;i++){ bmin=vmin(bmin,SC.insts[i].bmin); bmax=vmax(bmax,SC.insts[i].bmax);} HERO_C=(bmin+bmax)*0.5f; HERO_R=len(bmax-bmin)*0.5f+0.02f; }
    Cam cam=cameraFor(t); V cf=norm(cam.look-cam.eye), cr=norm(cross(cf,V(0,1,0))), cu=cross(cr,cf); float tanF=tanf(cam.fov/2), asp=(float)W/H;
    double T1=omp_get_wtime();
    int Ysub=(int)(H*0.72f);
    #pragma omp parallel for schedule(dynamic,4)
    for(int y=0;y<H;y++){ for(int x=0;x<W;x++){ if(y>=Ysub && ((y&1)||(x&1))) continue; Rng rng(((uint64_t)f*W*H+y*W+x)*7919ULL+13); V acc(0,0,0), aa(0,0,0), an(0,0,0); float ad=0; int nd=0;
        int ns=0; float l1=0,l2=0; bool sub=(y>=Ysub); int maxS=sub?SPP+3:SPP; int minS=sub?5:3;
        for(int s=0;s<maxS;s++){ float px=(x+rng.f())/W*2-1, py=1-(y+rng.f())/H*2; V d=norm(cf+cr*(px*tanF*asp)+cu*(py*tanF));
          V fp=cam.eye+d*(cam.focus/dot(d,cf)); float r1=sqrtf(rng.f()), r2=2*PI*rng.f(); V o=cam.eye+(cr*cosf(r2)+cu*sinf(r2))*(r1*cam.aperture); d=norm(fp-o);
          Aov aov; V L=trace(o,d,rng,aov); acc+=L; aa+=aov.albedo; an+=aov.normal; if(aov.depth<1e8f){ ad+=aov.depth; nd++; } ns++;
          float lu=lum(L); if(s==0) l1=lu; else if(s==1){ l2=lu; if(nd==0) break; /* sky: 2 samples enough */ }
          else if(s==minS-1){ float m=lum(acc)/ns; float dev=fabsf(l1-m)+fabsf(l2-m)+fabsf(lu-m); if(dev<0.18f*(m+0.03f)*3) break; } }
        int i=y*W+x; col[i]=acc/(float)ns; alb[i]=aa/(float)ns; nrm[i]=norm(an); dep[i]=nd?ad/nd:1e6f; } }
    // fill subsampled region
    for(int y=Ysub;y<H;y++) for(int x=0;x<W;x++){ if(!((y&1)||(x&1))) continue; int x0=x&~1, y0=y&~1; int x1=std::min(W-2,x0+2), y1=std::min(H-2,y0+2); if(y0<Ysub) y0=Ysub+ (Ysub&1); float fx=(x&1)?0.5f:0.f, fy=(y&1)?0.5f:0.f;
      auto I=[&](const std::vector<V>&a){ return lerp(lerp(a[y0*W+x0],a[y0*W+x1],fx),lerp(a[y1*W+x0],a[y1*W+x1],fx),fy); };
      int i=y*W+x; col[i]=I(col); alb[i]=I(alb); nrm[i]=norm(I(nrm)); dep[i]=lerpf(lerpf(dep[y0*W+x0],dep[y0*W+x1],fx),lerpf(dep[y1*W+x0],dep[y1*W+x1],fx),fy); }
    double T2=omp_get_wtime();
#ifdef STATS
    { long a=0,b=0,c=0,r=0;
      #pragma omp parallel reduction(+:a,b,c,r)
      { a+=ST_node; b+=ST_tri; c+=ST_inst; r+=ST_ray; ST_node=ST_tri=ST_inst=ST_ray=0; }
      fprintf(stderr,"rays %ld  inst/ray %.1f  nodes/ray %.1f  leaves/ray %.1f\n",r,c/(double)r,a/(double)r,b/(double)r); }
#endif
    atrous(col,alb,nrm,dep,W,H);
    // fog (aerial perspective) + bloom + tonemap
    for(int y=0;y<H;y++) for(int x=0;x<W;x++){ int i=y*W+x; float d=dep[i]; if(d<1e5f){ float px=(x+0.5f)/W*2-1, py=1-(y+0.5f)/H*2; V dir=norm(cf+cr*(px*tanF*asp)+cu*(py*tanF)); float fg=1-expf(-d*0.022f); V fc=lerp(V(0.9f,0.72f,0.55f),SUNCOL*1.3f,powf(std::max(0.f,dot(dir,SUN)),4)*0.7f)*0.75f; col[i]=lerp(col[i],fc,fg*0.9f); } }
    int BW=W/4,BH=H/4; std::vector<V> b0(BW*BH),b1(BW*BH); for(int y=0;y<BH;y++) for(int x=0;x<BW;x++){ V s(0,0,0); for(int j=0;j<4;j++) for(int i=0;i<4;i++) s+=col[(y*4+j)*W+x*4+i]; s=s/16; float l=lum(s)*EXPOSURE; b0[y*BW+x]=s*smooth(0.9f,2.5f,l); }
    const int R=14; std::vector<float> gk(2*R+1); float gs=0; for(int i=-R;i<=R;i++){ gk[i+R]=expf(-i*i/(2.f*5.5f*5.5f)); gs+=gk[i+R]; } for(auto&g:gk) g/=gs;
    for(int y=0;y<BH;y++) for(int x=0;x<BW;x++){ V s(0,0,0); for(int i=-R;i<=R;i++){ int xx=std::min(BW-1,std::max(0,x+i)); s+=b0[y*BW+xx]*gk[i+R]; } b1[y*BW+x]=s; }
    for(int y=0;y<BH;y++) for(int x=0;x<BW;x++){ V s(0,0,0); for(int i=-R;i<=R;i++){ int yy=std::min(BH-1,std::max(0,y+i)); s+=b1[yy*BW+x]*gk[i+R]; } b0[y*BW+x]=s; }
    Rng gr(f*31+7);
    for(int y=0;y<H;y++) for(int x=0;x<W;x++){ int i=y*W+x; float bx=(x+0.5f)/4-0.5f, by=(y+0.5f)/4-0.5f; int x0=std::max(0,std::min(BW-2,(int)bx)), y0=std::max(0,std::min(BH-2,(int)by)); float fx=clampf(bx-x0,0,1), fy=clampf(by-y0,0,1);
      V bl=lerp(lerp(b0[y0*BW+x0],b0[y0*BW+x0+1],fx),lerp(b0[(y0+1)*BW+x0],b0[(y0+1)*BW+x0+1],fx),fy);
      V c=(col[i]+bl*0.22f)*EXPOSURE; float u=(x+0.5f)/W-0.5f, v=(y+0.5f)/H-0.5f; c*=1-0.45f*(u*u+v*v)*2.2f; c=aces(c); float g=(gr.f()-0.5f)*0.012f; c+=V(g,g,g);
      c=V(powf(clampf(c.x,0,1),1/2.2f),powf(clampf(c.y,0,1),1/2.2f),powf(clampf(c.z,0,1),1/2.2f)); img[i*3]=(unsigned char)(c.x*255+0.5f); img[i*3+1]=(unsigned char)(c.y*255+0.5f); img[i*3+2]=(unsigned char)(c.z*255+0.5f); }
    char fn[512]; snprintf(fn,512,"%s/f_%04d.ppm",outdir,f); char tmpn[520]; snprintf(tmpn,520,"%s.tmp",fn); FILE*fp=fopen(tmpn,"wb"); fprintf(fp,"P6\n%d %d\n255\n",W,H); fwrite(img.data(),1,img.size(),fp); fclose(fp); rename(tmpn,fn);
    fprintf(stderr,"frame %d: build %.1fs render %.1fs post %.1fs uniq=%d insts=%zu\n",f,T1-T0,T2-T1,omp_get_wtime()-T2,nu,SC.insts.size()); }
  return 0; }
