// Neon world — «завод»: прошивает диоды (свечение травы, листвы, земли считается один раз
// тем же трассировщиком pt.cpp) и выгружает их для «проектора» (WebGL-страница на телефоне).
// pt.cpp подключается как есть, без единого изменения.
//   g++ -O3 -march=native -ffast-math -fopenmp -DLEAFN=6 -o neon_bake neon_bake.cpp
//   ./neon_bake out_dir            -> out_dir/scene.bin, out_dir/frames.bin
#define main pt_main
#include "pt.cpp"
#undef main

#include <cstdint>
#include <string>

// ---------- бинарный писатель ----------
struct Buf { std::vector<uint8_t> d; size_t pos(){return d.size();}
  void u8(uint8_t v){d.push_back(v);} void i8(int8_t v){d.push_back((uint8_t)v);}
  void i16(int16_t v){d.push_back(v&255);d.push_back((v>>8)&255);} void u16(uint16_t v){d.push_back(v&255);d.push_back((v>>8)&255);}
  void u32(uint32_t v){for(int i=0;i<4;i++)d.push_back((v>>(8*i))&255);} void f32(float f){uint32_t v;memcpy(&v,&f,4);u32(v);}
  void align4(){while(d.size()%4)d.push_back(0);} };
static inline uint8_t q8(float v){ return (uint8_t)clampf(v*255.f+0.5f,0,255); }
static inline int16_t q16(float v,float scale){ return (int16_t)clampf(roundf(v/scale),-32767,32767); }
// oct-encode normal -> 2 x snorm8
static void octEnc(V n, int8_t&ox, int8_t&oy){ n=norm(n); float l=fabsf(n.x)+fabsf(n.y)+fabsf(n.z); float px=n.x/l, py=n.y/l;
  if(n.z<0){ float qx=(1-fabsf(py))*(px>=0?1:-1), qy=(1-fabsf(px))*(py>=0?1:-1); px=qx; py=qy; }
  ox=(int8_t)clampf(roundf(px*127),-127,127); oy=(int8_t)clampf(roundf(py*127),-127,127); }

// «диод»: 16 байт. pos int16x3 (scale) | normal oct int8x2 | albedo u8x3 | sunD u8 (|n·sun|*vis) | kv u8 | s u8 (доля высоты) | flags u8
// flags: bit0 = знак стороны (для расширения травинки), bit1 = солнце со стороны +n, bits2..7 = фаза ветра (64 ступени)
static void diode(Buf&b, V p, float scale, V n, V alb, float sunVis, float kv, float s, int sideSign, float phase){
  b.i16(q16(p.x,scale)); b.i16(q16(p.y,scale)); b.i16(q16(p.z,scale));
  int8_t ox,oy; octEnc(n,ox,oy); b.i8(ox); b.i8(oy);
  b.u8(q8(alb.x)); b.u8(q8(alb.y)); b.u8(q8(alb.z));
  float ndl=dot(norm(n),SUN); b.u8(q8(fabsf(ndl)*sunVis)); b.u8(q8(kv)); b.u8(q8(s));
  int ph=(int)(fmodf(phase,2*PI)/(2*PI)*64)&63; b.u8((sideSign>0?1:0)|(ndl>0?2:0)|(ph<<2)); b.u8(0); }
// то же, но позиции float32 (земля): 24 байта
static void diodeF(Buf&b, V p, V n, V alb, float sunVis, float kv){
  b.f32(p.x); b.f32(p.y); b.f32(p.z); int8_t ox,oy; octEnc(n,ox,oy); b.i8(ox); b.i8(oy);
  b.u8(q8(alb.x)); b.u8(q8(alb.y)); b.u8(q8(alb.z)); float ndl=dot(norm(n),SUN); b.u8(q8(fabsf(ndl)*sunVis)); b.u8(q8(kv)); b.u8(0); b.u8(ndl>0?2:0); b.u8(0);b.u8(0);b.u8(0); }

// семь соседних ячеек + земля — та же сцена, что в bakePatch (для света на земле)
static void patchScene(Scene&bs, const Patch&p, float TR, float windAmp){ Mesh gm; buildGrassMesh(gm,p,0,windAmp); bs.meshes.push_back(gm);
  Mesh g; addQuad(g,V(-30,0,-30),V(-30,0,30),V(30,0,30),V(30,0,-30),M_SOIL); buildMesh(g); bs.meshes.push_back(g);
  float HX=sqrtf(3.f)*TR, HZ=1.5f*TR; float offs[7][2]={{0,0},{HX,0},{-HX,0},{HX/2,HZ},{-HX/2,HZ},{HX/2,-HZ},{-HX/2,-HZ}};
  for(int k=0;k<7;k++){ Inst in; in.mesh=0; in.xf=xfMake(V(offs[k][0],0,offs[k][1]),0,0,V(1,1,1)); in.inv=xfInverse(in.xf); in.matOverride=-1; in.tint=V(-1,-1,-1); bs.insts.push_back(in); }
  { Inst in; in.mesh=1; in.xf=xfMake(V(0,0,0),0,0,V(1,1,1)); in.inv=in.xf; in.matOverride=-1; in.tint=V(-1,-1,-1); bs.insts.push_back(in); }
  buildTLAS(bs); }

int main(int argc,char**argv){ const char*outdir=argc>1?argv[1]:"web"; int FPS=24, NF=240;
  SUN=norm(V(0.62f,0.32f,-0.73f)); FD=V(cosf(YAW),0,sinf(YAW));
  { float t=0.15f; while(t<7.0f){ HOPS.push_back({t,0.56f,0.36f,1.05f}); t+=0.68f; } HOPS.push_back({7.3f,1.15f,1.05f,1.3f}); }
  { float s=0; for(const Hop&h:HOPS){ s+=h.v*h.dur; bool big=h.h>0.7f; RIPS.push_back({HSTART.x+FD.x*s, HSTART.z+FD.z*s, h.t0+h.dur, big?3.0f:1.6f, big?0.55f:0.09f, big?0.5f:1.4f, big?1.3f:3.0f}); } }
  // герой — те же меши, что в pt.cpp
  SC.meshes.push_back(sphere(M_BEE_ABD,28,18)); MESH_SPH_ABD=0;
  SC.meshes.push_back(sphere(M_FUZZ,24,16)); MESH_SPH_FUZZ=1;
  SC.meshes.push_back(sphere(M_FUZZ,24,16)); MESH_SPH_HEAD=2;
  SC.meshes.push_back(sphere(M_EYE,16,12)); MESH_SPH_EYE=3;
  SC.meshes.push_back(sphere(M_HEADB,10,8)); MESH_SPH_TIP=4;
  SC.meshes.push_back(sphere(M_THINGLASS,24,12)); MESH_SPH_WING=5;
  SC.meshes.push_back(sphere(M_POLLEN,8,6)); MESH_SPH_POLLEN=6;
  SC.meshes.push_back(cylinderMesh(M_HEADB,8)); MESH_CYL_DARK=7;
  // образцы травы и их прошивка — ровно как в pt.cpp
  const int NP=10; std::vector<Patch> patches; const float TR=1.6f;
  for(int i=0;i<NP;i++){ bool catM=argc>2&&std::string(argv[2])=="cat"; int n = i>=8?650:(i>=6?(catM?4500:3000):(i<2?2600:1800)); float hm = i>=8?1.15f:(i==6?(catM?0.2f:0.45f):(i==7?(catM?0.4f:0.7f):1.f)); patches.push_back(makePatch(100+i,TR*1.0f, n, (i%2==0)&&i<6, hm)); if(i>=8) for(auto&bl:patches[i].blades) bl.w*=2.2f; if(catM&&i>=6&&i<8) for(auto&bl:patches[i].blades){ bl.w*=0.6f; bl.bend*=0.7f; } }
  float windA[NP]; for(int i=0;i<NP;i++) windA[i]=(i>=6&&i<8)?0.03f:0.05f+0.02f*(i%6);
  { double tb=omp_get_wtime(); for(int i=0;i<NP;i++) bakePatch(patches[i], TR, windA[i]); fprintf(stderr,"baked grass %.1fs\n",omp_get_wtime()-tb); }
  // свет на земле под каждым образцом (среднее по ячейке)
  float gsv[NP], gkv[NP];
  for(int i=0;i<NP;i++){ Scene bs; patchScene(bs,patches[i],TR,windA[i]); Rng rng(900+i); double svs=0,kvs=0; int n=0;
    for(int k=0;k<120;k++){ float x=(rng.f()*2-1)*TR*0.8f, z=(rng.f()*2-1)*TR*0.8f; if(fabsf(z)>TR*0.8f||fabsf(x)*0.866f+fabsf(z)*0.5f>TR*0.8f) continue; V P(x,0.004f,z); int vs=0,vk=0;
      for(int q=0;q<12;q++){ V d=coneDir(SUN,SUN_COS,rng.f(),rng.f()); if(!sceneAny(bs,P,d,1e30f)) vs++; V d2=cosHemi(V(0,1,0),rng.f(),rng.f()); if(!sceneAny(bs,P,d2,1e30f)) vk++; }
      svs+=vs/12.0; kvs+=vk/12.0; n++; }
    gsv[i]=(float)(svs/n); gkv[i]=(float)(kvs/n); fprintf(stderr,"ground patch %d: sun %.2f sky %.2f\n",i,gsv[i],gkv[i]); }
  const int NT=3; std::vector<TreeDef> trees; for(int i=0;i<NT;i++){ trees.push_back(makeTree(500+i)); bakeTree(trees.back()); }
  // раскладка ячеек, деревьев, пыльцы — тот же генератор и та же последовательность случайных чисел, что в pt.cpp
  struct TileI{float x,z; int patch; float yaw;}; std::vector<TileI> tiles; Rng r(77); float HX=sqrtf(3.f)*TR, HZ=1.5f*TR;
  for(int row=-34; row<=12; row++) for(int col=-16; col<=24; col++){ float x=col*HX+((row&1)?HX/2:0), z=row*HZ; float px=x-HSTART.x, pz=z-HSTART.z; float along=px*FD.x+pz*FD.z, side=-px*FD.z+pz*FD.x; int pi=(int)(r.f()*6);
    if(along>-5&&along<22&&fabsf(side)<2.0f) pi=6; else if(along>-6&&along<23&&fabsf(side)<3.6f) pi=7; else if(along<-9||along>24||fabsf(side)>8.5f) pi=8+(int)(r.f()*2); tiles.push_back({x,z,pi,0.f}); }
  auto nearPath=[&](float x,float z){ float px=x-HSTART.x, pz=z-HSTART.z; float along=px*FD.x+pz*FD.z; float side=-px*FD.z+pz*FD.x; if(along>-4&&along<20&&fabsf(side)<2.6f) return true; for(int k=0;k<4;k++){ float ox[4]={2.1f,2.6f,3.2f,1.2f}, oz[4]={1.35f,2.4f,3.4f,0.8f}; float cs=-ox[k]*FD.z+oz[k]*FD.x, ca=ox[k]*FD.x+oz[k]*FD.z; if(along>ca-4&&along<ca+20&&fabsf(side-cs)<3.0f) return true;} return false; };
  struct TreeI{float x,z,yaw,sc,ph; int v;}; std::vector<TreeI> treeI; for(int i=0;i<260;i++){ float x=-28+70*r.f(), z=-62+36*r.f(); if(nearPath(x,z)) continue; treeI.push_back({x,z,r.f()*6.28f,0.8f+0.5f*r.f(),r.f()*6.28f,(int)(r.f()*NT)}); }
  for(int i=0;i<16;i++){ float x=-14+34*r.f(), z=-24+30*r.f(); if(nearPath(x,z)) continue; { float px=x-HSTART.x, pz=z-HSTART.z; float along=px*FD.x+pz*FD.z, side=-px*FD.z+pz*FD.x; if(along>-8&&along<26&&fabsf(side)<7) continue; } treeI.push_back({x,z,r.f()*6.28f,0.7f+0.4f*r.f(),r.f()*6.28f,(int)(r.f()*NT)}); }
  struct Pol{float x,y,z,ph;}; std::vector<Pol> pol; for(int i=0;i<500;i++){ float x=-10+26*r.f(), z=-14+16*r.f(); pol.push_back({x,hstat(x,z)+0.15f+1.4f*powf(r.f(),1.5f),z,r.f()*6.28f}); }
  // режим «кот в лесу»: тропа с короткой травой на x=CX, z от CZ0 до CZ1, луг вокруг, деревья с тропы убрать
  bool catMode = argc>2 && std::string(argv[2])=="cat"; const float CX=6.0f, CZ0=-29.0f, CZ1=-45.0f;
  auto segDist=[&](float x,float z){ float zz=clampf(z,CZ1,CZ0); float dx=x-CX, dz=z-zz; return sqrtf(dx*dx+dz*dz); };
  if(catMode){ Rng rc(4242); for(auto&t:tiles){ float d=segDist(t.x,t.z); if(d<1.7f) t.patch=6; else if(d<3.4f) t.patch=7; else if(d<18.f && t.patch>=8) t.patch=(int)(rc.f()*6); }
    std::vector<TreeI> keep; for(const TreeI&t:treeI){ if(segDist(t.x,t.z)<1.6f) continue; keep.push_back(t); } treeI.swap(keep);
    // несколько деревьев ближе к тропе, чтобы лес обступал
    float extra[][2]={{3.2f,-33.f},{9.1f,-36.5f},{2.9f,-40.f},{9.4f,-42.5f},{3.6f,-46.f},{8.7f,-30.5f},{10.2f,-47.5f},{2.2f,-27.f}};
    for(auto&e:extra) treeI.push_back({e[0],e[1],rc.f()*6.28f,0.85f+0.4f*rc.f(),rc.f()*6.28f,(int)(rc.f()*NT)});
    // толстые старые деревья рядом с тропой — как в Blender-кадре
    float big[][3]={{1.4f,-36.2f,2.0f},{11.3f,-40.8f,2.2f},{0.6f,-44.8f,1.8f},{11.8f,-31.2f,1.9f},{12.2f,-47.0f,2.1f},{0.2f,-28.6f,1.9f}};
    for(auto&e:big) treeI.push_back({e[0],e[1],rc.f()*6.28f,e[2],rc.f()*6.28f,(int)(rc.f()*NT)}); }
  fprintf(stderr,"tiles %zu trees %zu%s\n",tiles.size(),treeI.size(),catMode?" (cat)":"");

  // ---------- scene.bin ----------
  Buf bin; std::string hdr="{"; char tmp[512];
  snprintf(tmp,512,"\"sun\":[%g,%g,%g],\"suncol\":[%g,%g,%g],\"sunrad\":%g,\"exposure\":%g,\"TR\":%g,\"grassScale\":%g,\"treeScale\":%g,",SUN.x,SUN.y,SUN.z,SUNCOL.x,SUNCOL.y,SUNCOL.z,SUNRAD,EXPOSURE,TR,1.f/16000,1.f/2500); hdr+=tmp;
  const float GS=1.f/16000, TS=1.f/2500;
  // --- образцы травы ---
  hdr+="\"patches\":[";
  for(int i=0;i<NP;i++){ const Patch&p=patches[i]; float windAmp=windA[i]; Buf vb, ib; int nv=0;
    for(const Blade&b:p.blades){ V base(b.x,0,b.z); V dir(cosf(b.yaw),0,sinf(b.yaw)); V side(-dir.z,0,dir.x); V P[5],T[5]; bladePts(b,base,dir,windAmp*0.6f,V(0,0,0),P);
      for(int k=0;k<5;k++) T[k]=norm(P[std::min(k+1,4)]-P[std::max(k-1,0)]);
      int v0=nv; for(int k=0;k<4;k++){ float w=b.w*powf(1-BS[k],0.6f); V n=norm(cross(side,T[k])); V alb=evalMat(M_GRASS,b.rnd,BS[k],V(-1,-1,-1)).albedo;
        diode(vb,P[k]-side*w,GS,n,alb,b.sv[k],b.kv[k],BS[k],-1,b.phase); diode(vb,P[k]+side*w,GS,n,alb,b.sv[k],b.kv[k],BS[k],+1,b.phase); nv+=2; }
      { V n=norm(cross(side,T[4])); V alb=evalMat(M_GRASS,b.rnd,1.f,V(-1,-1,-1)).albedo; diode(vb,P[4],GS,n,alb,b.sv[4],b.kv[4],1.f,0,b.phase); nv++; }
      // 7 треугольников, тот же порядок обхода, что в pt.cpp (L,R,R',L')
      for(int k=0;k<3;k++){ int L=v0+k*2, R=L+1, L1=L+2, R1=L+3; ib.u16(L);ib.u16(R);ib.u16(R1); ib.u16(L);ib.u16(R1);ib.u16(L1); }
      { int L=v0+6, R=L+1, tip=v0+8; ib.u16(L);ib.u16(R);ib.u16(tip); } }
    int bladeIdx=(int)(ib.d.size()/2);
    // цветы: стебель + лепестки + серединка, отдельными треугольниками (нормаль вверх)
    for(const auto&f:p.flowers){ V base(f.x,0,f.z); V top=base+V(0,f.h,0); V sd(0.003f,0,0); V n=norm(cross(top-base,V(0,0,1))); V alb=evalMat(M_GRASS,0.3f,0.5f,V(-1,-1,-1)).albedo;
      auto tri=[&](V a,V b2,V c,V nn,V al,float sv,float kv){ diode(vb,a,GS,nn,al,sv,kv,0.5f,0,0); diode(vb,b2,GS,nn,al,sv,kv,0.5f,0,0); diode(vb,c,GS,nn,al,sv,kv,0.5f,0,0); ib.u16(nv);ib.u16(nv+1);ib.u16(nv+2); nv+=3; };
      tri(base-sd,base+sd,top+sd,n,alb,0.65f,0.65f); tri(base-sd,top+sd,top-sd,n,alb,0.65f,0.65f);
      V pm = f.kind==1?V(0.98f,0.75f,0.12f):V(0.95f,0.95f,0.92f); int np=f.kind==2?6:5; float pr=f.kind==2?0.025f:0.02f;
      for(int k=0;k<np;k++){ float a=f.yaw+k*2*PI/np; V d(cosf(a),0.25f,sinf(a)); V s2=norm(cross(d,V(0,1,0)))*pr*0.55f; V tip=top+norm(d)*pr*2.2f; V mid=top+norm(d)*pr*1.1f; tri(top,mid+s2,tip,V(0,1,0),pm,0.85f,0.7f); tri(top,tip,mid-s2,V(0,1,0),pm,0.85f,0.7f); }
      float cr=pr*0.7f; V cc=f.kind==1?V(0.12f,0.07f,0.035f):V(0.98f,0.75f,0.12f); for(int k=0;k<6;k++){ float a0=k*PI/3,a1=(k+1)*PI/3; tri(top+V(0,0.004f,0),top+V(cosf(a1)*cr,0.004f,sinf(a1)*cr),top+V(cosf(a0)*cr,0.004f,sinf(a0)*cr),V(0,1,0),cc,0.85f,0.7f); } }
    bin.align4(); size_t vo=bin.pos(); bin.d.insert(bin.d.end(),vb.d.begin(),vb.d.end()); bin.align4(); size_t io=bin.pos(); bin.d.insert(bin.d.end(),ib.d.begin(),ib.d.end());
    snprintf(tmp,512,"%s{\"vOff\":%zu,\"nv\":%d,\"iOff\":%zu,\"ni\":%zu,\"bladeIdx\":%d,\"blades\":%zu,\"wind\":%g,\"gsv\":%.3f,\"gkv\":%.3f}",i?",":"",vo,nv,io,ib.d.size()/2,bladeIdx,p.blades.size(),windAmp,gsv[i],gkv[i]); hdr+=tmp;
    fprintf(stderr,"patch %d: %zu blades, %d verts, %zu idx\n",i,p.blades.size(),nv,ib.d.size()/2); }
  hdr+="],";
  // --- ячейки ---
  { bin.align4(); size_t off=bin.pos(); for(const TileI&t:tiles){ bin.f32(t.x); bin.f32(hstat(t.x,t.z)); bin.f32(t.z); bin.u32((uint32_t)t.patch); }
    snprintf(tmp,512,"\"tiles\":{\"off\":%zu,\"n\":%zu},",off,tiles.size()); hdr+=tmp; }
  // --- земля: тот же heightfield, диоды с float-позицией; свет под травой — по ближайшей ячейке ---
  { const float X0=-45,X1=65,Z0=-80,Z1=30; const float st=1.0f; int nx=(int)((X1-X0)/st), nz=(int)((Z1-Z0)/st); Rng gr(5); Buf vb,ib;
    auto Pq=[&](int i,int j){ float x=X0+i*st, z=Z0+j*st; return V(x,hstat(x,z)-0.01f,z); }; auto N=[&](int i,int j){ V a=Pq(i+1,j)-Pq(i-1,j), b=Pq(i,j+1)-Pq(i,j-1); return norm(cross(b,a)); };
    auto tileAt=[&](float x,float z){ int best=0; float bd=1e30f; for(size_t k=0;k<tiles.size();k++){ float dx=tiles[k].x-x, dz=tiles[k].z-z; float d=dx*dx+dz*dz; if(d<bd){bd=d;best=(int)k;} } return tiles[best].patch; };
    for(int j=0;j<=nz;j++) for(int i=0;i<=nx;i++){ V p=Pq(i,j); float u=gr.f(); int pi=tileAt(p.x,p.z); V alb=V(0.085f,0.062f,0.038f)*(0.7f+0.6f*u); diodeF(vb,p,N(i,j),alb,gsv[pi],gkv[pi]); }
    for(int j=0;j<nz;j++) for(int i=0;i<nx;i++){ uint32_t a=j*(nx+1)+i, b=a+1, c=a+(nx+1), d=c+1; ib.u32(a);ib.u32(c);ib.u32(d); ib.u32(a);ib.u32(d);ib.u32(b); }
    bin.align4(); size_t vo=bin.pos(); bin.d.insert(bin.d.end(),vb.d.begin(),vb.d.end()); bin.align4(); size_t io=bin.pos(); bin.d.insert(bin.d.end(),ib.d.begin(),ib.d.end());
    snprintf(tmp,512,"\"ground\":{\"vOff\":%zu,\"nv\":%d,\"iOff\":%zu,\"ni\":%zu},",vo,(nx+1)*(nz+1),io,ib.d.size()/4); hdr+=tmp; }
  // --- деревья: ствол (свет — быстрая прошивка по своей кроне) и листва ---
  hdr+="\"trees\":[";
  for(int i=0;i<NT;i++){ TreeDef&T=trees[i]; Scene bs; bs.meshes.push_back(T.trunk); Mesh lm; buildTreeLeaves(lm,T,0,0); bs.meshes.push_back(lm);
    for(int k=0;k<2;k++){ Inst in; in.mesh=k; in.xf=xfMake(V(0,0,0),0,0,V(1,1,1)); in.inv=in.xf; in.matOverride=-1; in.tint=V(-1,-1,-1); bs.insts.push_back(in); } buildTLAS(bs);
    Buf tv,ti; int nv=0; Rng rng(777+i);
    for(const Tri&t:T.trunk.tris){ V P3[3]={t.p0,t.p0+t.e1,t.p0+t.e2}; V N3[3]={t.n0,t.n1,t.n2}; float vv[3]={t.v0,t.v1,t.v2};
      for(int k=0;k<3;k++){ int vs=0,vk=0; for(int q=0;q<6;q++){ V d=coneDir(SUN,SUN_COS,rng.f(),rng.f()); if(!sceneAny(bs,P3[k]+N3[k]*0.03f,d,1e30f)) vs++; V d2=cosHemi(N3[k],rng.f(),rng.f()); if(!sceneAny(bs,P3[k]+N3[k]*0.03f,d2,1e30f)) vk++; }
        V alb=V(0.16f,0.11f,0.07f)*1.0f; (void)vv; diode(tv,P3[k],TS,N3[k],alb,vs/6.f*0.35f,vk/6.f*0.7f,0,0,0); /* соседние деревья тоже затеняют ствол */ ti.u16(nv++); } }
    Buf lv,li; int lnv=0;
    for(const Leaf&L:T.leaves){ V n=L.n; V tt,bb; onb(n,tt,bb); V p=L.p; float a=L.rnd*6.28f; V e1=(tt*cosf(a)+bb*sinf(a))*L.s, e2=(bb*cosf(a)-tt*sinf(a))*L.s*0.6f;
      V c=lerp(V(0.06f,0.16f,0.03f),V(0.3f,0.42f,0.07f),L.rnd); if(L.rnd>0.9f) c=V(0.6f,0.35f,0.06f);
      V q[4]={p-e1,p+e2,p+e1,p-e2}; for(int k=0;k<4;k++) diode(lv,q[k],TS,n,c,L.sv,L.kv,0.5f,0,L.rnd*6.28f);
      li.u16(lnv);li.u16(lnv+1);li.u16(lnv+2); li.u16(lnv);li.u16(lnv+3);li.u16(lnv+1); lnv+=4; }
    bin.align4(); size_t tvo=bin.pos(); bin.d.insert(bin.d.end(),tv.d.begin(),tv.d.end()); bin.align4(); size_t tio=bin.pos(); bin.d.insert(bin.d.end(),ti.d.begin(),ti.d.end());
    bin.align4(); size_t lvo=bin.pos(); bin.d.insert(bin.d.end(),lv.d.begin(),lv.d.end()); bin.align4(); size_t lio=bin.pos(); bin.d.insert(bin.d.end(),li.d.begin(),li.d.end());
    snprintf(tmp,512,"%s{\"tvOff\":%zu,\"tnv\":%d,\"tiOff\":%zu,\"tni\":%zu,\"lvOff\":%zu,\"lnv\":%d,\"liOff\":%zu,\"lni\":%zu}",i?",":"",tvo,nv,tio,ti.d.size()/2,lvo,lnv,lio,li.d.size()/2); hdr+=tmp;
    fprintf(stderr,"tree %d: trunk %d verts, %d leaves\n",i,nv,lnv/4); }
  hdr+="],";
  { bin.align4(); size_t off=bin.pos(); for(const TreeI&t:treeI){ bin.f32(t.x); bin.f32(hstat(t.x,t.z)-0.1f); bin.f32(t.z); bin.f32(t.yaw); bin.f32(t.sc); bin.f32(t.ph); bin.u32((uint32_t)t.v); bin.u32(0); }
    snprintf(tmp,512,"\"treeInst\":{\"off\":%zu,\"n\":%zu},",off,treeI.size()); hdr+=tmp; }
  { bin.align4(); size_t off=bin.pos(); for(const Pol&p:pol){ bin.f32(p.x); bin.f32(p.y); bin.f32(p.z); bin.f32(p.ph); }
    snprintf(tmp,512,"\"pollen\":{\"off\":%zu,\"n\":%zu},",off,pol.size()); hdr+=tmp; }
  { bin.align4(); size_t off=bin.pos(); for(const Rip&rp:RIPS){ bin.f32(rp.x); bin.f32(rp.z); bin.f32(rp.t); bin.f32(rp.speed); bin.f32(rp.amp); bin.f32(rp.decay); bin.f32(rp.width); bin.f32(0); }
    snprintf(tmp,512,"\"rips\":{\"off\":%zu,\"n\":%zu},",off,RIPS.size()); hdr+=tmp; }
  // --- свет под кронами (карта по земле) и свет в воздухе (3D) — только деревья заслоняют ---
  if(catMode){
    Scene ts; for(int i=0;i<NT;i++){ ts.meshes.push_back(trees[i].trunk); Mesh lm; buildTreeLeaves(lm,trees[i],0,0); ts.meshes.push_back(lm); }
    for(const TreeI&t:treeI){ float y=hstat(t.x,t.z); Xf x=xfYaw(V(t.x,y-0.1f,t.z),t.yaw,V(t.sc,t.sc,t.sc)); for(int k=0;k<2;k++){ Inst in; in.mesh=t.v*2+k; in.xf=x; in.inv=xfInverse(x); in.matOverride=-1; in.tint=V(-1,-1,-1); ts.insts.push_back(in); } }
    buildTLAS(ts); double t0=omp_get_wtime();
    // карта: x -45..65, z -80..30, шаг 0.2 м; в точке на высоте травы: 8 лучей к солнцу (с диском), 8 к небу
    const float X0=-45,Z0=-80; const float st=0.2f; const int nx=550,nz=550; std::vector<uint8_t> cmap(nx*nz*2);
    #pragma omp parallel for schedule(dynamic,8)
    for(int j=0;j<nz;j++){ for(int i=0;i<nx;i++){ float x=X0+(i+0.5f)*st, z=Z0+(j+0.5f)*st; V P(x,hstat(x,z)+0.25f,z); Rng rng(j*7919+i*13+1); int vs=0,vk=0;
      for(int k=0;k<16;k++){ V d=coneDir(SUN,cosf(0.035f),rng.f(),rng.f()); if(!sceneAny(ts,P,d,1e30f)) vs++; if(k<8){ V d2=cosHemi(V(0,1,0),rng.f(),rng.f()); if(!sceneAny(ts,P,d2,1e30f)) vk++; } }
      cmap[(j*nx+i)*2]=(uint8_t)(vs*255/16); cmap[(j*nx+i)*2+1]=(uint8_t)(vk*255/8); } }
    bin.align4(); size_t coff=bin.pos(); bin.d.insert(bin.d.end(),cmap.begin(),cmap.end());
    snprintf(tmp,512,"\"canopy\":{\"off\":%zu,\"nx\":%d,\"nz\":%d,\"x0\":%g,\"z0\":%g,\"step\":%g},",coff,nx,nz,X0,Z0,st); hdr+=tmp;
    fprintf(stderr,"canopy map %dx%d %.1fs\n",nx,nz,omp_get_wtime()-t0); t0=omp_get_wtime();
    // объём: x -4..16, y 0..8 (над землёй у тропы), z -52..-22, шаг 0.25; видимость солнца из точки воздуха
    const float VX0=-4,VY0=0.0f,VZ0=-52; const float vst=0.25f; const int vx=80,vy=32,vz=120; std::vector<uint8_t> vol(vx*vy*vz);
    #pragma omp parallel for schedule(dynamic,2)
    for(int k=0;k<vz;k++){ for(int j=0;j<vy;j++) for(int i=0;i<vx;i++){ float x=VX0+(i+0.5f)*vst, z=VZ0+(k+0.5f)*vst; float gy=hstat(CX,z); float y=gy+VY0+(j+0.5f)*vst; V P(x,y,z); Rng rng(k*100003+j*1009+i*7+3); int vs=0;
        for(int q=0;q<6;q++){ V d=coneDir(SUN,cosf(0.025f),rng.f(),rng.f()); if(!sceneAny(ts,P,d,1e30f)) vs++; }
        vol[(k*vy+j)*vx+i]=(uint8_t)(vs*255/6); } }
    bin.align4(); size_t voff=bin.pos(); bin.d.insert(bin.d.end(),vol.begin(),vol.end());
    snprintf(tmp,512,"\"volume\":{\"off\":%zu,\"nx\":%d,\"ny\":%d,\"nz\":%d,\"x0\":%g,\"y0\":%g,\"z0\":%g,\"step\":%g,\"groundX\":%g},",voff,vx,vy,vz,VX0,VY0,VZ0,vst,CX); hdr+=tmp;
    fprintf(stderr,"light volume %dx%dx%d %.1fs\n",vx,vy,vz,omp_get_wtime()-t0);
    // камни во мху у тропы: сплюснутые сферы с шумом, диоды с float-позицией (как земля)
    hdr+="\"props\":[";
    float rocks[][6]={{8.3f,-33.5f,0.55f,0.32f,0.45f,0.9f},{3.9f,-37.8f,0.42f,0.26f,0.36f,2.1f},{8.9f,-40.2f,0.7f,0.38f,0.55f,0.4f},{3.4f,-42.6f,0.35f,0.22f,0.3f,1.3f},{9.2f,-45.8f,0.5f,0.3f,0.42f,2.8f},{3.1f,-31.0f,0.48f,0.3f,0.4f,0.2f},{8.6f,-29.0f,0.33f,0.2f,0.28f,1.7f}};
    float mounds[][6]={{2.4f,-35.5f,1.3f,0.55f,1.0f,0.6f},{10.2f,-38.0f,1.6f,0.6f,1.2f,1.9f},{1.8f,-41.5f,1.1f,0.45f,0.9f,2.4f},{10.6f,-33.0f,1.2f,0.5f,1.0f,0.3f},{3.0f,-47.5f,1.5f,0.6f,1.1f,1.1f},{9.8f,-44.6f,1.0f,0.42f,0.9f,2.9f}};
    int nr=sizeof(rocks)/sizeof(rocks[0]), nm=sizeof(mounds)/sizeof(mounds[0]); Rng rr(99);
    for(int r=0;r<nr+nm;r++){ bool isM=r>=nr; const float*R=isM?mounds[r-nr]:rocks[r]; float x=R[0], z=R[1], sx=R[2], sy=R[3], sz=R[4], yaw=R[5]; float gy=hstat(x,z); Buf vb,ib; int nv=0; const int NU=36,NV=20; float c=cosf(yaw),s=sinf(yaw);
      auto Pt=[&](int i,int j){ float th=PI*j/NV, ph=2*PI*i/NU; V d(sinf(th)*cosf(ph),cosf(th),sinf(th)*sinf(ph)); float nse=1+0.08f*sinf(5*ph+2*th+r)+0.05f*sinf(9*ph-3*th)+0.04f*sinf(3*th*th+7*ph); V p(d.x*sx*nse,d.y*sy*nse,d.z*sz*nse); return V(c*p.x+s*p.z, p.y, -s*p.x+c*p.z)+V(x,gy-sy*0.35f,z); };
      std::vector<V> P((NU+1)*(NV+1)); for(int j=0;j<=NV;j++) for(int i=0;i<=NU;i++) P[j*(NU+1)+i]=Pt(i,j);
      for(int j=0;j<=NV;j++) for(int i=0;i<=NU;i++){ V p=P[j*(NU+1)+i]; V du=P[j*(NU+1)+(i+1)%NU]-P[j*(NU+1)+(i+NU-1)%NU]; V dv=P[std::min(j+1,NV)*(NU+1)+i]-P[std::max(j-1,0)*(NU+1)+i]; V n=norm(cross(dv,du)); if(len(n)<0.5f) n=V(0,j==0?1:-1,0);
        float moss=isM?1.0f:clampf((n.y-0.25f)*1.6f,0,1)*(0.7f+0.3f*sinf(p.x*9+p.z*7)); V rock=V(0.30f,0.28f,0.25f)*(0.8f+0.4f*rr.f()); V mossC=(isM?V(0.2f,0.34f,0.08f):V(0.16f,0.3f,0.07f))*(0.85f+0.3f*rr.f()); V alb=lerp(rock,mossC,moss);
        diodeF(vb,p,n,alb,isM?0.9f:1.0f,0.75f); nv++; }
      for(int j=0;j<NV;j++) for(int i=0;i<NU;i++){ uint32_t a=j*(NU+1)+i, b=a+1, c2=a+(NU+1), d2=c2+1; ib.u32(a);ib.u32(c2);ib.u32(d2); ib.u32(a);ib.u32(d2);ib.u32(b); }
      bin.align4(); size_t vo=bin.pos(); bin.d.insert(bin.d.end(),vb.d.begin(),vb.d.end()); bin.align4(); size_t io=bin.pos(); bin.d.insert(bin.d.end(),ib.d.begin(),ib.d.end());
      snprintf(tmp,512,"%s{\"vOff\":%zu,\"nv\":%d,\"iOff\":%zu,\"ni\":%zu}",r?",":"",vo,nv,io,ib.d.size()/4); hdr+=tmp; }
    hdr+="],"; }
  // --- меши героя: pos f32x3, normal f32x3, uv f32x2; индексы u16 ---
  hdr+="\"heroMeshes\":[";
  for(int mi=0;mi<8;mi++){ const Mesh&m=SC.meshes[mi]; Buf vb,ib; int nv=0; for(const Tri&t:m.tris){ V P3[3]={t.p0,t.p0+t.e1,t.p0+t.e2}; V N3[3]={t.n0,t.n1,t.n2}; float uu[3]={t.u0,t.u1,t.u2}, vv[3]={t.v0,t.v1,t.v2};
      for(int k=0;k<3;k++){ vb.f32(P3[k].x);vb.f32(P3[k].y);vb.f32(P3[k].z); vb.f32(N3[k].x);vb.f32(N3[k].y);vb.f32(N3[k].z); vb.f32(uu[k]); vb.f32(vv[k]); ib.u16(nv++); } }
    bin.align4(); size_t vo=bin.pos(); bin.d.insert(bin.d.end(),vb.d.begin(),vb.d.end()); bin.align4(); size_t io=bin.pos(); bin.d.insert(bin.d.end(),ib.d.begin(),ib.d.end());
    int mat=m.tris.empty()?0:m.tris[0].mat; snprintf(tmp,512,"%s{\"vOff\":%zu,\"nv\":%d,\"iOff\":%zu,\"ni\":%zu,\"mat\":%d}",mi?",":"",vo,nv,io,ib.d.size()/2,mat); hdr+=tmp; }
  hdr+="],";
  snprintf(tmp,512,"\"hstat\":\"0.35*sin(0.07*x+0.3)*cos(0.055*z)+0.18*sin(0.13*x-0.09*z+1.0)+0.09*sin(0.25*x+0.19*z+2.0)+0.0016*max(0,-z-18)^2\",\"frames\":%d,\"fps\":%d,\"heroInst\":29}",NF,FPS); hdr+=tmp;
  { std::string fn=std::string(outdir)+"/scene.bin"; FILE*fp=fopen(fn.c_str(),"wb"); uint32_t hl=(uint32_t)hdr.size(); fwrite("NEON",1,4,fp); fwrite(&hl,4,1,fp); fwrite(hdr.data(),1,hdr.size(),fp); int pad=(4-(hdr.size()%4))%4; char z[4]={0,0,0,0}; fwrite(z,1,pad,fp);
    // смещения в заголовке считались от начала bin -> проектор прибавит base = 8+hl+pad
    fwrite(bin.d.data(),1,bin.d.size(),fp); fclose(fp); fprintf(stderr,"scene.bin: header %u + data %zu bytes\n",hl,bin.d.size()); }

  // ---------- frames.bin: камера + герой на каждый кадр ----------
  { std::string fn=std::string(outdir)+"/frames.bin"; FILE*fp=fopen(fn.c_str(),"wb"); Buf fb; int ninst=-1;
    for(int f=0;f<NF;f++){ float t=f/(float)FPS; Cam c=cameraFor(t); HeroState HS=heroState(t); std::vector<Inst> hi; buildHero(hi,t); if(ninst<0) ninst=(int)hi.size(); if((int)hi.size()!=ninst){ fprintf(stderr,"hero inst count changed!\n"); return 1; }
      fb.f32(c.eye.x);fb.f32(c.eye.y);fb.f32(c.eye.z); fb.f32(c.look.x);fb.f32(c.look.y);fb.f32(c.look.z); fb.f32(c.fov); fb.f32(c.focus); fb.f32(c.aperture);
      fb.f32(HS.x); fb.f32(HS.z); fb.f32(HS.inAir?0.f:1.f);
      // три сферы тени: брюшко, грудь, голова — из матриц инстансов (центр = сдвиг, радиус = средняя длина осей)
      for(int k=0;k<3;k++){ const Xf&x=hi[k].xf; V cc(x.m[3],x.m[7],x.m[11]); float rr=(len(V(x.m[0],x.m[4],x.m[8]))+len(V(x.m[1],x.m[5],x.m[9]))+len(V(x.m[2],x.m[6],x.m[10])))/3; fb.f32(cc.x);fb.f32(cc.y);fb.f32(cc.z);fb.f32(rr); }
      for(const Inst&in:hi){ fb.u32((uint32_t)in.mesh); fb.u32((uint32_t)(in.matOverride<0?255:in.matOverride)); for(int k=0;k<12;k++) fb.f32(in.xf.m[k]); } }
    fwrite(fb.d.data(),1,fb.d.size(),fp); fclose(fp); fprintf(stderr,"frames.bin: %d frames, %d hero insts, %zu bytes\n",NF,ninst,fb.d.size()); }
  return 0; }
