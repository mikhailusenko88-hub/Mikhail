// fur.cpp — Барсик в туманном лесу. Свой рендерер по «неоновой основе»:
// свет живёт в сотах-ячейках вокруг героя и запекается один раз; каждый волосок и травинка
// получают свой готовый свет и сами «светятся» им. В кадре считается только то, что зависит
// от камеры: какой волосок виден (первичный луч), блик, туман и боке. Вторичных лучей нет.
// g++ -O3 -march=native -ffast-math -fopenmp -o fur fur.cpp
// ./fur shot=close spp=16 w=1280 h=720 out=out/close.ppm [geo=out/geo_base]
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <cstdint>
#include <vector>
#include <array>
#include <string>
#include <map>
#include <algorithm>
#include <chrono>
#include <omp.h>

static double T0;
static double now() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
#define LOG(...) do { fprintf(stderr, "[%6.1fs] ", now() - T0); fprintf(stderr, __VA_ARGS__); fprintf(stderr, "\n"); } while (0)

// ---------------- вектор ----------------
struct V3 { float x, y, z; V3() : x(0), y(0), z(0) {} V3(float a, float b, float c) : x(a), y(b), z(c) {} };
static inline V3 operator+(V3 a, V3 b) { return V3(a.x + b.x, a.y + b.y, a.z + b.z); }
static inline V3 operator-(V3 a, V3 b) { return V3(a.x - b.x, a.y - b.y, a.z - b.z); }
static inline V3 operator*(V3 a, float s) { return V3(a.x * s, a.y * s, a.z * s); }
static inline V3 operator*(float s, V3 a) { return V3(a.x * s, a.y * s, a.z * s); }
static inline V3 operator*(V3 a, V3 b) { return V3(a.x * b.x, a.y * b.y, a.z * b.z); }
static inline V3 operator/(V3 a, float s) { return a * (1.f / s); }
static inline V3& operator+=(V3& a, V3 b) { a.x += b.x; a.y += b.y; a.z += b.z; return a; }
static inline V3& operator*=(V3& a, float s) { a.x *= s; a.y *= s; a.z *= s; return a; }
static inline float dot(V3 a, V3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
static inline V3 cross(V3 a, V3 b) { return V3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x); }
static inline float len(V3 a) { return sqrtf(dot(a, a)); }
static inline V3 nrm(V3 a) { float l = len(a); return l > 1e-20f ? a / l : V3(0, 0, 1); }
static inline V3 vmin(V3 a, V3 b) { return V3(fminf(a.x, b.x), fminf(a.y, b.y), fminf(a.z, b.z)); }
static inline V3 vmax(V3 a, V3 b) { return V3(fmaxf(a.x, b.x), fmaxf(a.y, b.y), fmaxf(a.z, b.z)); }
static inline V3 vpow(V3 a, float p) { return V3(powf(fmaxf(a.x, 0), p), powf(fmaxf(a.y, 0), p), powf(fmaxf(a.z, 0), p)); }
static inline V3 lerp(V3 a, V3 b, float t) { return a + (b - a) * t; }
static inline float clampf(float x, float a, float b) { return x < a ? a : x > b ? b : x; }
static inline float sstep(float a, float b, float x) { float t = clampf((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); }
static inline float comp(V3 a, int i) { return i == 0 ? a.x : i == 1 ? a.y : a.z; }

// ---------------- случайные числа ----------------
struct Rng { uint64_t s; Rng(uint64_t x) : s(x * 0x9E3779B97F4A7C15ull + 1) {} inline uint32_t u() { s ^= s << 13; s ^= s >> 7; s ^= s << 17; return (uint32_t)(s >> 11); } inline float f() { return (u() & 0xFFFFFF) / 16777216.f; } };
static inline float hash3(int x, int y, int z) { uint32_t h = x * 374761393u + y * 668265263u + z * 2147483647u; h = (h ^ (h >> 13)) * 1274126177u; return ((h ^ (h >> 16)) & 0xFFFFFF) / 16777216.f; }
static float vnoise(V3 p) {  // плавный шум значений
    int xi = (int)floorf(p.x), yi = (int)floorf(p.y), zi = (int)floorf(p.z); float fx = p.x - xi, fy = p.y - yi, fz = p.z - zi;
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy); fz = fz * fz * (3 - 2 * fz);
    float a = 0;
    for (int k = 0; k < 8; k++) { int dx = k & 1, dy = (k >> 1) & 1, dz = k >> 2; a += hash3(xi + dx, yi + dy, zi + dz) * (dx ? fx : 1 - fx) * (dy ? fy : 1 - fy) * (dz ? fz : 1 - fz); }
    return a;
}
static float fbm(V3 p, int oct) { float a = 0, w = 0.5f, s = 0; for (int i = 0; i < oct; i++) { a += w * vnoise(p); s += w; p = p * 2.03f + V3(1.7f, 9.2f, 3.1f); w *= 0.5f; } return a / s; }

// ---------------- загрузка массивов ----------------
struct Arr { char code; std::vector<int> shape; std::vector<float> f; std::vector<int> i; std::vector<signed char> b; size_t n() const { size_t s = 1; for (int x : shape) s *= x; return s; } };
static std::map<std::string, Arr> G;
static void loadGeo(const std::string& dir) {
    FILE* m = fopen((dir + "/manifest.txt").c_str(), "r"); if (!m) { fprintf(stderr, "нет %s\n", dir.c_str()); exit(1); }
    char name[128], code; int nd;
    while (fscanf(m, "%127s %c %d", name, &code, &nd) == 3) {
        Arr a; a.code = code; for (int k = 0; k < nd; k++) { int s; if (fscanf(m, "%d", &s) != 1) exit(2); a.shape.push_back(s); }
        FILE* f = fopen((dir + "/" + name + ".bin").c_str(), "rb"); size_t n = a.n();
        if (code == 'f') { a.f.resize(n); if (n && fread(a.f.data(), 4, n, f) != n) exit(3); }
        else if (code == 'i') { a.i.resize(n); if (n && fread(a.i.data(), 4, n, f) != n) exit(3); }
        else { a.b.resize(n); if (n && fread(a.b.data(), 1, n, f) != n) exit(3); }
        fclose(f); G[name] = std::move(a);
    }
    fclose(m);
}
static V3 gv(const char* k, size_t i) { const auto& a = G[k].f; return V3(a[i * 3], a[i * 3 + 1], a[i * 3 + 2]); }

// ---------------- сцена ----------------
enum { M_SKIN = 0, M_NOSE, M_SCARF };
enum { S_FUR = 0, S_GRASS, S_WHISK, S_MOUTH };
struct Tri { int a, b, c, mat; };
struct Seg { int v; float r0, r1; uint8_t type; };
// вершины треугольников
static std::vector<V3> TV, TN, TA; static std::vector<uint8_t> TR;   // позиция, нормаль, альбедо, область
static std::vector<std::array<float, 6>> TB;                          // запечённый свет вершины
// вершины прядей (шерсть, трава, усы, рот)
static std::vector<V3> SV, SA, SNV; static std::vector<float> ST;          // позиция, альбедо, доля длины 0..1
static std::vector<std::array<float, 6>> SB;
static std::vector<Tri> tris; static std::vector<Seg> segs;
static int nTri = 0;

// ---------------- BVH ----------------
struct AABB { V3 mn, mx; AABB() : mn(1e30f, 1e30f, 1e30f), mx(-1e30f, -1e30f, -1e30f) {} void grow(V3 p) { mn = vmin(mn, p); mx = vmax(mx, p); } void grow(const AABB& b) { mn = vmin(mn, b.mn); mx = vmax(mx, b.mx); } float area() const { V3 d = mx - mn; if (d.x < 0) return 0; return 2 * (d.x * d.y + d.y * d.z + d.z * d.x); } };
struct Node { float mn[3], mx[3]; int first, cnt; };
static std::vector<Node> nodes; static std::vector<int> pidx; static std::vector<AABB> pbox; static std::vector<V3> pcen;
static AABB primBox(int p) {
    AABB b;
    if (p < nTri) { const Tri& t = tris[p]; b.grow(TV[t.a]); b.grow(TV[t.b]); b.grow(TV[t.c]); }
    else { const Seg& s = segs[p - nTri]; float r = fmaxf(s.r0, s.r1); V3 a = SV[s.v], c = SV[s.v + 1]; b.grow(a - V3(r, r, r)); b.grow(a + V3(r, r, r)); b.grow(c - V3(r, r, r)); b.grow(c + V3(r, r, r)); }
    return b;
}
static void buildBVH() {
    int N = nTri + (int)segs.size(); pidx.resize(N); pbox.resize(N); pcen.resize(N);
    #pragma omp parallel for schedule(static)
    for (int i = 0; i < N; i++) { pidx[i] = i; pbox[i] = primBox(i); pcen[i] = (pbox[i].mn + pbox[i].mx) * 0.5f; }
    nodes.reserve(N / 2 + 16); nodes.push_back(Node());
    struct Job { int node, s, e; }; std::vector<Job> st; st.push_back({0, 0, N});
    const int NB = 16;
    while (!st.empty()) {
        Job j = st.back(); st.pop_back();
        AABB bb, cb; for (int i = j.s; i < j.e; i++) { bb.grow(pbox[pidx[i]]); cb.grow(pcen[pidx[i]]); }
        Node& nd = nodes[j.node]; for (int k = 0; k < 3; k++) { nd.mn[k] = comp(bb.mn, k); nd.mx[k] = comp(bb.mx, k); }
        int cnt = j.e - j.s;
        auto leaf = [&]() { nodes[j.node].first = j.s; nodes[j.node].cnt = cnt; };
        if (cnt <= 4) { leaf(); continue; }
        int bestAx = -1, bestB = 0; float bestC = 1e30f;
        for (int ax = 0; ax < 3; ax++) {
            float lo = comp(cb.mn, ax), hi = comp(cb.mx, ax); if (hi - lo < 1e-9f) continue;
            AABB bx[NB]; int bc[NB] = {0}; float sc = NB / (hi - lo);
            for (int i = j.s; i < j.e; i++) { int p = pidx[i]; int b = std::min(NB - 1, (int)((comp(pcen[p], ax) - lo) * sc)); bc[b]++; bx[b].grow(pbox[p]); }
            float la[NB]; int lc[NB]; AABB acc; int ac = 0;
            for (int b = 0; b < NB - 1; b++) { acc.grow(bx[b]); ac += bc[b]; la[b] = acc.area(); lc[b] = ac; }
            AABB acc2; int ac2 = 0;
            for (int b = NB - 1; b > 0; b--) { acc2.grow(bx[b]); ac2 += bc[b]; float c = la[b - 1] * lc[b - 1] + acc2.area() * ac2; if (lc[b - 1] && ac2 && c < bestC) { bestC = c; bestAx = ax; bestB = b; } }
        }
        float leafC = bb.area() * cnt;
        if (bestAx < 0 || (bestC >= leafC && cnt <= 12)) {
            if (bestAx < 0 && cnt > 12) {  // все центры совпали — делим пополам
                int m = (j.s + j.e) / 2; int l = (int)nodes.size(); nodes[j.node].first = l; nodes[j.node].cnt = 0; nodes.push_back(Node()); nodes.push_back(Node());
                st.push_back({l, j.s, m}); st.push_back({l + 1, m, j.e}); continue;
            }
            leaf(); continue;
        }
        float lo = comp(cb.mn, bestAx), hi = comp(cb.mx, bestAx), sc = NB / (hi - lo);
        int* mid = std::partition(pidx.data() + j.s, pidx.data() + j.e, [&](int p) { return std::min(NB - 1, (int)((comp(pcen[p], bestAx) - lo) * sc)) < bestB; });
        int m = (int)(mid - pidx.data()); if (m == j.s || m == j.e) m = (j.s + j.e) / 2;
        int l = (int)nodes.size(); nodes[j.node].first = l; nodes[j.node].cnt = 0; nodes.push_back(Node()); nodes.push_back(Node());
        st.push_back({l, j.s, m}); st.push_back({l + 1, m, j.e});
    }
    std::vector<AABB>().swap(pbox); std::vector<V3>().swap(pcen);
}
struct Hit { float t; int prim; float u, v; };   // tri: барицентрики; прядь: u = доля по отрезку, v = смещение поперёк (-1..1)
static inline bool hitTri(const Tri& tr, V3 o, V3 d, float tmax, Hit& h) {
    V3 a = TV[tr.a], e1 = TV[tr.b] - a, e2 = TV[tr.c] - a; V3 p = cross(d, e2); float det = dot(e1, p);
    if (fabsf(det) < 1e-14f) return false; float inv = 1.f / det; V3 s = o - a; float u = dot(s, p) * inv; if (u < 0 || u > 1) return false;
    V3 q = cross(s, e1); float v = dot(d, q) * inv; if (v < 0 || u + v > 1) return false; float t = dot(e2, q) * inv;
    if (t <= 1e-5f || t >= tmax) return false; h.t = t; h.u = u; h.v = v; return true;
}
static inline bool hitSeg(const Seg& sg, V3 o, V3 d, float tmax, Hit& h) {
    V3 p0 = SV[sg.v], u = SV[sg.v + 1] - p0, w = o - p0;
    float b = dot(d, u), c = dot(u, u), dd = dot(d, w), e = dot(u, w), den = c - b * b;
    float v = den > 1e-14f ? (e - b * dd) / den : 0.f; v = clampf(v, 0, 1);
    V3 q = p0 + u * v; float s = dot(q - o, d); V3 off = o + d * s - q; float d2 = dot(off, off); float r = sg.r0 + (sg.r1 - sg.r0) * v;
    if (d2 >= r * r) return false; float th = s - sqrtf(r * r - d2);
    if (th <= 1e-4f || th >= tmax) return false;
    h.t = th; h.u = v; float sgn = dot(cross(u, d), off) > 0 ? 1.f : -1.f; h.v = sgn * sqrtf(d2) / r; return true;
}
static bool traceBVH(V3 o, V3 d, float tmax, Hit& best) {
    V3 id(1.f / d.x, 1.f / d.y, 1.f / d.z); int stack[96]; int sp = 0; int ni = 0; bool any = false; best.t = tmax;
    while (true) {
        const Node& n = nodes[ni];
        if (n.cnt) {
            for (int i = n.first; i < n.first + n.cnt; i++) { int p = pidx[i]; Hit h; if (p < nTri ? hitTri(tris[p], o, d, best.t, h) : hitSeg(segs[p - nTri], o, d, best.t, h)) { best = h; best.prim = p; any = true; } }
            if (!sp) break; ni = stack[--sp]; continue;
        }
        int l = n.first, r = l + 1; float tl0, tr0;
        auto box = [&](const Node& c, float& tn) { float t1 = (c.mn[0] - o.x) * id.x, t2 = (c.mx[0] - o.x) * id.x; float a = fminf(t1, t2), b = fmaxf(t1, t2);
            t1 = (c.mn[1] - o.y) * id.y; t2 = (c.mx[1] - o.y) * id.y; a = fmaxf(a, fminf(t1, t2)); b = fminf(b, fmaxf(t1, t2));
            t1 = (c.mn[2] - o.z) * id.z; t2 = (c.mx[2] - o.z) * id.z; a = fmaxf(a, fminf(t1, t2)); b = fminf(b, fmaxf(t1, t2)); tn = a; return b >= fmaxf(a, 0.f) && a < best.t; };
        bool hl = box(nodes[l], tl0), hr = box(nodes[r], tr0);
        if (hl && hr) { if (tl0 > tr0) { std::swap(l, r); } stack[sp++] = r; ni = l; }
        else if (hl) ni = l; else if (hr) ni = r; else { if (!sp) break; ni = stack[--sp]; }
    }
    return any;
}

// ---------------- свет ----------------
static V3 LSUN = nrm(V3(-0.55f, -0.5f, 0.67f));
static V3 CSUN = V3(1.0f, 0.85f, 0.66f) * 3.3f;
struct Lamp { V3 pos, col; float P; V3 aim; };
static Lamp LAMP[4];   // 0 — солнце (только цвет), 1 — контровой, 2 — ключевой, 3 — заполняющий
static V3 SKY = V3(0.42f, 0.62f, 0.6f) * 0.9f;   // равномерное небо-дымка
static V3 FOGC = V3(0.56f, 0.74f, 0.7f);
static float KAREA = 0.08f;
static bool hasEyeL = false; static Lamp EYEL;
static inline void lightAt(int i, V3 p, V3& L, V3& E) {
    if (i == 0) { L = LSUN; E = CSUN; return; }
    const Lamp& l = LAMP[i]; V3 d = l.pos - p; float r2 = dot(d, d); L = d / sqrtf(r2);
    float c = fmaxf(0.f, -dot(L, l.aim)); E = l.col * (l.P * KAREA / r2 * (0.35f + 0.65f * c));
}

static V3 EYE[2]; static float RE; static V3 EYEF[2]; static int FACEONLY = 0, OLDBAKE = 0; static size_t FURN = 0; static float FARSIG = 0.06f; static int SIGBLUR = 1, BKMODE = 0;
// ---------------- соты света вокруг героя ----------------
// сетка 4 мм: плотность шерсти (сколько волосков закрывают свет) + поле кожи; для каждой нужной ячейки
// один раз запекается: сколько дойдёт солнца, контрового, ключевого, заполняющего, видно ли небо и землю
static V3 gLo, gHi; static int GX, GY, GZ; static float GH = 0.004f; static std::vector<float> SIG; static std::vector<std::array<float, 6>> LV; static std::vector<uint8_t> LVok;
static int VX, VY, VZ; static V3 vLo; static float vH; static const float* VOLp;
static inline float sdf(V3 p) {
    float fx = (p.x - vLo.x) / vH, fy = (p.y - vLo.y) / vH, fz = (p.z - vLo.z) / vH;
    if (fx < 0 || fy < 0 || fz < 0 || fx >= VX - 1 || fy >= VY - 1 || fz >= VZ - 1) return 0.05f;
    int x = (int)fx, y = (int)fy, z = (int)fz; float ax = fx - x, ay = fy - y, az = fz - z;
    auto at = [&](int i, int j, int k) { return VOLp[((size_t)i * VY + j) * VZ + k]; };
    float c00 = at(x, y, z) * (1 - ax) + at(x + 1, y, z) * ax, c10 = at(x, y + 1, z) * (1 - ax) + at(x + 1, y + 1, z) * ax;
    float c01 = at(x, y, z + 1) * (1 - ax) + at(x + 1, y, z + 1) * ax, c11 = at(x, y + 1, z + 1) * (1 - ax) + at(x + 1, y + 1, z + 1) * ax;
    return (c00 * (1 - ay) + c10 * ay) * (1 - az) + (c01 * (1 - ay) + c11 * ay) * az;
}
static inline V3 sdfGrad(V3 p) { float e = 0.002f; return nrm(V3(sdf(p + V3(e, 0, 0)) - sdf(p - V3(e, 0, 0)), sdf(p + V3(0, e, 0)) - sdf(p - V3(0, e, 0)), sdf(p + V3(0, 0, e)) - sdf(p - V3(0, 0, e)))); }
static inline size_t gidx(int x, int y, int z) { return ((size_t)z * GY + y) * GX + x; }
static inline float sig(V3 p) {   // плотность шерсти — плавно (трилинейно), иначе сетка рисует «кольца» на круглой голове
    float fx = (p.x - gLo.x) / GH - 0.5f, fy = (p.y - gLo.y) / GH - 0.5f, fz = (p.z - gLo.z) / GH - 0.5f;
    int x = (int)floorf(fx), y = (int)floorf(fy), z = (int)floorf(fz); if (x < 0 || y < 0 || z < 0 || x >= GX - 1 || y >= GY - 1 || z >= GZ - 1) return 0;
    float ax = fx - x, ay = fy - y, az = fz - z; const float* a = &SIG[gidx(x, y, z)]; size_t sy = GX, sz = (size_t)GX * GY;
    float c00 = a[0] * (1 - ax) + a[1] * ax, c10 = a[sy] * (1 - ax) + a[sy + 1] * ax, c01 = a[sz] * (1 - ax) + a[sz + 1] * ax, c11 = a[sz + sy] * (1 - ax) + a[sz + sy + 1] * ax;
    return (c00 * (1 - ay) + c10 * ay) * (1 - az) + (c01 * (1 - ay) + c11 * ay) * az;
}
static float FURK = 0.32f; static float FURPOW = 0.6f, FURMUL = 0.85f, RIMP = 140.f, BLOOM = 0.35f, BTH = 1.1f, GRASSK = 1.f;   // доля света, которую волосок «гасит» (остальное он пропускает вперёд)
static float march(V3 p, V3 d, float maxd, float jit = 0.5f) {
    float tau = 0; const float st = 0.0030f;
    if (d.z < -1e-4f) maxd = fminf(maxd, -p.z / d.z);   // земля
    // отрезать по коробке сот
    float t0 = 0, t1 = maxd;
    for (int k = 0; k < 3; k++) { float o = comp(p, k), dk = comp(d, k), lo = comp(gLo, k), hi = comp(gHi, k);
        if (fabsf(dk) < 1e-9f) { if (o < lo || o > hi) return 1.f; continue; }
        float a = (lo - o) / dk, b = (hi - o) / dk; if (a > b) std::swap(a, b); t0 = fmaxf(t0, a); t1 = fminf(t1, b); }
    for (float t = t0 + st * jit; t < t1; t += st) {
        V3 q = p + d * t; float s = sdf(q);
        tau += sstep(0.0005f, -0.0035f, s) * 3.2f;   // внутри тела свет гаснет плавно, без ступенек
        tau += sig(q) * FURK * st; if (tau > 9.f) return 0.f;
    }
    return expf(-tau);
}
static V3 SKYD[16], GNDD[8];
static float marchFar(V3 p, V3 d, float maxd, float jit) {   // дальние тени: голова на грудь, ухо на голову; своя кожа и свой мех сюда не входят
    float tau = 0; const float st = 0.0030f;
    if (d.z < -1e-4f) maxd = fminf(maxd, -p.z / d.z);
    float t0 = 0, t1 = maxd;
    for (int k = 0; k < 3; k++) { float o = comp(p, k), dk = comp(d, k), lo = comp(gLo, k), hi = comp(gHi, k);
        if (fabsf(dk) < 1e-9f) { if (o < lo || o > hi) return 1.f; continue; }
        float a = (lo - o) / dk, b = (hi - o) / dk; if (a > b) std::swap(a, b); t0 = fmaxf(t0, a); t1 = fminf(t1, b); }
    for (float t = fmaxf(t0, 0.012f) + st * jit; t < t1; t += st) {
        V3 q = p + d * t; float s = sdf(q);
        tau += sstep(-0.002f, -0.006f, s) * 3.2f;   // только если луч ушёл глубоко внутрь другой части тела
        if (t > FARSIG) tau += sig(q) * FURK * st; if (tau > 9.f) return 0.f;
    }
    return expf(-tau);
}
static float TAUK = 1.f;
static void bakeHair(V3 p, V3 N, std::array<float, 6>& o, uint32_t seed, int nsky, float trans = 0.f, float tauSelf = -1.f) {
    Rng r(seed); float tauN = 0;
    if (tauSelf >= 0) tauN = tauSelf * TAUK;   // свой слой меха — по соседним волоскам, без сетки
    else for (float t = 0.00075f; t < 0.03f; t += 0.0015f) tauN += sig(p + N * t) * 0.0015f;
    auto Td = [&](V3 L, float md) { float c = dot(N, L); float ts = fmaxf(sstep(-0.3f, 0.15f, c), trans); if (ts <= 0.f) return 0.f;
        float jj = r.f(); return ts * (BKMODE == 2 ? 1.f : expf(-FURK * tauN * (1 - 0.6f * trans) / fmaxf(c + 0.15f, 0.22f + trans))) * (BKMODE == 1 ? 1.f : marchFar(p, L, md, jj)); };
    for (int i = 0; i < 4; i++) { V3 L, E; lightAt(i, p, L, E); o[i] = Td(L, i ? len(LAMP[i].pos - p) : 9.f); }
    float a = 0, w = 0; int off = r.u() % 16, stp = 16 / nsky; for (int k = 0; k < nsky; k++) { int i = (off + k * stp) % 16; float ww = 0.3f + SKYD[i].z; a += Td(SKYD[i], 2.f) * ww; w += ww; } o[4] = a / w;
    float g = 0; int ng = nsky >= 16 ? 8 : 4; for (int k = 0; k < ng; k++) g += Td(GNDD[(off + k * (8 / ng)) % 8], 2.f); o[5] = g / ng;
    float gr = 0.35f + 0.65f * sstep(0.0f, 0.12f, p.z); o[4] *= gr; o[5] *= 0.4f + 0.6f * sstep(0, 0.1f, p.z); o[0] *= 0.25f + 0.75f * sstep(0.0f, 0.1f, p.z);
}
static void bakeCell(V3 p, std::array<float, 6>& o, uint32_t seed, int nl = 3, int nsky = 16) {
    float s = sdf(p); if (s < 0.0012f) p = p + sdfGrad(p) * (0.0012f - s);
    Rng r(seed); auto J = [&]() { return r.f(); };
    for (int i = 0; i < 4; i++) { V3 L, E; lightAt(i, p, L, E); float md = i ? len(LAMP[i].pos - p) : 9.f; float a = 0; for (int k = 0; k < nl; k++) a += march(p, L, md, (k + J()) / nl); o[i] = a / nl; }
    float a = 0, w = 0; int off = r.u() % 16, stp = 16 / nsky; for (int k = 0; k < nsky; k++) { int i = (off + k * stp) % 16; float ww = 0.3f + SKYD[i].z; a += march(p, SKYD[i], 2.f, J()) * ww; w += ww; } o[4] = a / w;
    float g = 0; int ng = nsky >= 16 ? 8 : 4; for (int k = 0; k < ng; k++) g += march(p, GNDD[(off + k * (8 / ng)) % 8], 2.f, J()); o[5] = g / ng;
    // трава у лап закрывает небо и солнце
    float gr = 0.35f + 0.65f * sstep(0.0f, 0.12f, p.z); o[4] *= gr; o[5] *= 0.4f + 0.6f * sstep(0, 0.1f, p.z); o[0] *= 0.25f + 0.75f * sstep(0.0f, 0.1f, p.z);
}
static void buildLightCells() {
    // коробка — по шерсти и коже
    gLo = V3(1e9, 1e9, 1e9); gHi = V3(-1e9, -1e9, -1e9);
    for (auto& p : TV) { gLo = vmin(gLo, p); gHi = vmax(gHi, p); }
    const auto& fp = G["fur_pts"].f; size_t nf = fp.size() / 3;
    for (size_t i = 0; i < nf; i++) { V3 p(fp[i * 3], fp[i * 3 + 1], fp[i * 3 + 2]); gLo = vmin(gLo, p); gHi = vmax(gHi, p); }
    gLo = gLo - V3(0.03f, 0.03f, 0.03f); gHi = gHi + V3(0.03f, 0.03f, 0.03f); gLo.z = fmaxf(gLo.z, -0.01f);
    GX = (int)ceilf((gHi.x - gLo.x) / GH); GY = (int)ceilf((gHi.y - gLo.y) / GH); GZ = (int)ceilf((gHi.z - gLo.z) / GH);
    SIG.assign((size_t)GX * GY * GZ, 0.f);
    // плотность: каждый отрезок волоска кладёт свою «тень» (2r·длина) в ячейки, по которым проходит
    float iv = 1.f / (GH * GH * GH);
    for (const Seg& s : segs) {
        if (s.type == S_GRASS) continue;
        V3 a = SV[s.v], b = SV[s.v + 1]; float L = len(b - a); int n = std::max(1, (int)(L / 0.001f));
        for (int k = 0; k < n; k++) { float t = (k + 0.5f) / n; V3 q = lerp(a, b, t); float r = s.r0 + (s.r1 - s.r0) * t;
            float fx = (q.x - gLo.x) / GH - 0.5f, fy = (q.y - gLo.y) / GH - 0.5f, fz = (q.z - gLo.z) / GH - 0.5f; int x = (int)floorf(fx), y = (int)floorf(fy), z = (int)floorf(fz);
            float ax = fx - x, ay = fy - y, az = fz - z, m = 2 * r * (L / n) * iv;
            for (int k = 0; k < 8; k++) { int xx = x + (k & 1), yy = y + ((k >> 1) & 1), zz = z + (k >> 2); if (xx < 0 || yy < 0 || zz < 0 || xx >= GX || yy >= GY || zz >= GZ) continue;
                SIG[gidx(xx, yy, zz)] += m * ((k & 1) ? ax : 1 - ax) * (((k >> 1) & 1) ? ay : 1 - ay) * ((k >> 2) ? az : 1 - az); } }
    }
    for (int pass = 0; pass < 3 * SIGBLUR; pass++) {   // размытие [1 2 1] по x, y, z
        int ax = pass % 3; std::vector<float> tmpS(SIG.size()); size_t st = ax == 0 ? 1 : ax == 1 ? (size_t)GX : (size_t)GX * GY; int n = ax == 0 ? GX : ax == 1 ? GY : GZ;
        #pragma omp parallel for
        for (long i = 0; i < (long)SIG.size(); i++) { int c = ax == 0 ? i % GX : ax == 1 ? (i / GX) % GY : i / ((size_t)GX * GY);
            float a = SIG[i] * 2; a += c > 0 ? SIG[i - st] : SIG[i]; a += c < n - 1 ? SIG[i + st] : SIG[i]; tmpS[i] = a * 0.25f; }
        SIG.swap(tmpS);
    }
    // направления неба и земли
    for (int i = 0; i < 16; i++) { float z = 0.06f + 0.94f * (i + 0.5f) / 16, r = sqrtf(1 - z * z), a = i * 2.39996f; SKYD[i] = V3(r * cosf(a), r * sinf(a), z); }
    for (int i = 0; i < 8; i++) { float z = -(0.15f + 0.8f * (i + 0.5f) / 8), r = sqrtf(1 - z * z), a = i * 2.39996f + 0.5f; GNDD[i] = V3(r * cosf(a), r * sinf(a), z); }
    LV.assign((size_t)GX * GY * GZ, std::array<float, 6>{1, 1, 1, 1, 1, 1}); LVok.assign(LV.size(), 0);
    auto mark = [&](V3 p) { float fx = (p.x - gLo.x) / GH - 0.5f, fy = (p.y - gLo.y) / GH - 0.5f, fz = (p.z - gLo.z) / GH - 0.5f; int x = (int)floorf(fx), y = (int)floorf(fy), z = (int)floorf(fz);
        for (int k = 0; k < 8; k++) { int xx = x + (k & 1), yy = y + ((k >> 1) & 1), zz = z + (k >> 2); if (xx >= 0 && yy >= 0 && zz >= 0 && xx < GX && yy < GY && zz < GZ) LVok[gidx(xx, yy, zz)] = 1; } };
    for (int e = 0; e < 2; e++) for (int k = 0; k < 4000; k++) { float z = 1 - 2 * (k + 0.5f) / 4000, rr = sqrtf(1 - z * z), a = k * 2.39996f; for (float sh : {0.002f, 0.004f, 0.007f}) mark(EYE[e] + V3(rr * cosf(a), rr * sinf(a), z) * (RE + sh)); }
    std::vector<size_t> todo; for (size_t i = 0; i < LVok.size(); i++) if (LVok[i]) todo.push_back(i);
    LOG("соты света: %dx%dx%d, запекаю %zu ячеек", GX, GY, GZ, todo.size());
    #pragma omp parallel for schedule(dynamic, 256)
    for (size_t k = 0; k < todo.size(); k++) { size_t i = todo[k]; int x = i % GX, y = (i / GX) % GY, z = i / ((size_t)GX * GY); bakeCell(gLo + V3((x + 0.5f) * GH, (y + 0.5f) * GH, (z + 0.5f) * GH), LV[i], (uint32_t)i * 2654435761u + 7); }
}
static std::array<float, 6> cellLight(V3 p) {
    float fx = (p.x - gLo.x) / GH - 0.5f, fy = (p.y - gLo.y) / GH - 0.5f, fz = (p.z - gLo.z) / GH - 0.5f; int x = (int)floorf(fx), y = (int)floorf(fy), z = (int)floorf(fz);
    float ax = fx - x, ay = fy - y, az = fz - z; std::array<float, 6> o{0, 0, 0, 0, 0, 0}; float W = 0;
    for (int k = 0; k < 8; k++) { int xx = x + (k & 1), yy = y + ((k >> 1) & 1), zz = z + (k >> 2); if (xx < 0 || yy < 0 || zz < 0 || xx >= GX || yy >= GY || zz >= GZ) continue; size_t i = gidx(xx, yy, zz); if (!LVok[i]) continue;
        float w = ((k & 1) ? ax : 1 - ax) * (((k >> 1) & 1) ? ay : 1 - ay) * ((k >> 2) ? az : 1 - az); for (int c = 0; c < 6; c++) o[c] += LV[i][c] * w; W += w; }
    if (W < 1e-6f) return {1, 1, 1, 1, 1, 1}; for (int c = 0; c < 6; c++) o[c] /= W; return o;
}

// ---------------- мир: лес в тумане ----------------
struct Cyl { float x, y, r; }; static std::vector<Cyl> trunks;
struct Ell { V3 c, r; }; static std::vector<Ell> stones;
static inline bool hitCyl(const Cyl& c, V3 o, V3 d, float tmax, float& t) {
    float ox = o.x - c.x, oy = o.y - c.y; float a = d.x * d.x + d.y * d.y; if (a < 1e-12f) return false; float b = ox * d.x + oy * d.y, cc = ox * ox + oy * oy - c.r * c.r;
    float D = b * b - a * cc; if (D < 0) return false; t = (-b - sqrtf(D)) / a; if (t < 1e-4f || t >= tmax) return false; float z = o.z + d.z * t; return z > -0.1f && z < 14.f;
}
static inline bool hitEll(const Ell& e, V3 o, V3 d, float tmax, float& t) {
    V3 oo = (o - e.c) * V3(1 / e.r.x, 1 / e.r.y, 1 / e.r.z), dd = d * V3(1 / e.r.x, 1 / e.r.y, 1 / e.r.z);
    float a = dot(dd, dd), b = dot(oo, dd), c = dot(oo, oo) - 1, D = b * b - a * c; if (D < 0) return false; t = (-b - sqrtf(D)) / a; return t > 1e-4f && t < tmax;
}
static inline bool hitSph(V3 c, float r, V3 o, V3 d, float tmax, float& t) {
    V3 oc = o - c; float b = dot(oc, d), cc = dot(oc, oc) - r * r, D = b * b - cc; if (D < 0) return false; t = -b - sqrtf(D); return t > 1e-4f && t < tmax;
}

// ---------------- материалы ----------------
static inline float gauss(float x, float b) { return expf(-x * x / (2 * b * b)) / (2.5066f * b); }
static V3 hairSpec(V3 T, V3 L, V3 V, V3 alb, float specK) {   // блик волоска: отражение (белое), сквозь (цветное), внутреннее (цветное)
    float si = clampf(dot(T, L), -1, 1), so = clampf(dot(T, V), -1, 1);
    float ti = asinf(si), to = asinf(so), th = 0.5f * (ti + to), td = 0.5f * (to - ti); float ci = sqrtf(fmaxf(0, 1 - si * si));
    V3 lp = L - T * si, vp = V - T * so; float ll = len(lp) * len(vp); float cphi = ll > 1e-8f ? clampf(dot(lp, vp) / ll, -1, 1) : 1.f;
    float phi = acosf(cphi); float ch = cosf(0.5f * phi); float cd2 = fmaxf(0.2f, cosf(td) * cosf(td));
    float R = gauss(th + 0.06f, 0.16f) * 0.25f * ch * 0.09f;
    float tt = gauss(th - 0.03f, 0.09f) * expf(-(3.14159f - phi) * (3.14159f - phi) / (2 * 0.32f * 0.32f)) * 0.55f;
    float trt = gauss(th - 0.12f, 0.3f) * 0.25f * ch * 0.35f;
    V3 cTT = vpow(alb, 0.6f), cTRT = vpow(alb, 1.3f);
    return (V3(R, R, R) + cTT * tt + cTRT * trt) * (ci / cd2 * specK);
}
static V3 GNDL;   // свет, отражённый землёй (снизу)
static inline float fract_(float x) { return x - floorf(x); }

// ---------------- солнце за деревьями: кроны с просветами, лучи в тумане, пятна на траве ----------------
static V3 LBACK = nrm(V3(-0.49f, 0.77f, 0.44f)); static V3 CBACK = V3(1.0f, 0.84f, 0.6f) * 2.2f; static float KSHAFT = 1.f, KDAPPLE = 1.f;
static std::vector<float> CAN; static float CANF = 0.55f, CANT = 0.6f; static const int CN = 1024; static const float CX0 = -30.f, CY0 = -25.f, CSZ = 60.f, CANZ = 8.5f;
static void buildCanopy() {
    CAN.resize(CN * CN); V3 cat = V3(0, 0, 0.7f) + LBACK * ((CANZ - 0.7f) / LBACK.z);
    #pragma omp parallel for
    for (int j = 0; j < CN; j++) for (int i = 0; i < CN; i++) { float x = CX0 + (i + 0.5f) / CN * CSZ, y = CY0 + (j + 0.5f) / CN * CSZ;
        float n = fbm(V3(x * CANF, y * CANF, 0.5f), 4) * 0.8f + fbm(V3(x * CANF * 3.3f, y * CANF * 3.3f, 2.3f), 3) * 0.2f;
        float hole = sstep(0.9f, 0.45f, sqrtf((x - cat.x) * (x - cat.x) + (y - cat.y) * (y - cat.y)));   // герой стоит в луче
        CAN[j * CN + i] = fmaxf(sstep(CANT, CANT + 0.06f, n), hole); }
}
static inline float canopy(V3 p) {
    float s = (CANZ - p.z) / LBACK.z; if (s < 0) return 1.f; float x = p.x + LBACK.x * s, y = p.y + LBACK.y * s;
    float fx = (x - CX0) / CSZ * CN - 0.5f, fy = (y - CY0) / CSZ * CN - 0.5f; if (fx < 0 || fy < 0 || fx >= CN - 1 || fy >= CN - 1) return 0.f;
    int ix = (int)fx, iy = (int)fy; float ax = fx - ix, ay = fy - iy; const float* c = &CAN[iy * CN + ix];
    return (c[0] * (1 - ax) + c[1] * ax) * (1 - ay) + (c[CN] * (1 - ax) + c[CN + 1] * ax) * ay;
}
static Ell CATSH[2];   // тень героя в луче: голова и тело
static inline float backVis(V3 p, bool cat) {
    float v = canopy(p); if (v < 0.002f) return 0.f; float t;
    for (const Cyl& c : trunks) if (hitCyl(c, p, LBACK, 1e9f, t)) return 0.f;
    if (cat) for (int k = 0; k < 2; k++) if (hitEll(CATSH[k], p, LBACK, 1e9f, t)) return 0.f;
    return v;
}
// ---------------- бабочка ----------------
struct Fly { V3 pos, f, u, r; float flap; bool on; }; static Fly FLY;
static float FLYS = 1.55f;
static inline float wingE(float x, float y, int part) { x /= FLYS; y /= FLYS; return part == 0 ? ((x - 0.012f) / 0.027f) * ((x - 0.012f) / 0.027f) + ((y - 0.031f) / 0.034f) * ((y - 0.031f) / 0.034f)
                                                                         : ((x + 0.016f) / 0.021f) * ((x + 0.016f) / 0.021f) + ((y - 0.021f) / 0.023f) * ((y - 0.021f) / 0.023f); }
static bool hitFly(V3 o, V3 d, float tmax, float& tb, V3& nW, float& wx, float& wy, int& what) {
    if (!FLY.on) return false; bool any = false;
    { V3 oc = o - FLY.pos; float b = dot(oc, d), c = dot(oc, oc) - 0.0064f; if (b * b - c < 0) return false; }   // далеко — пропуск
    for (int w = 0; w < 2; w++) { V3 wr = (w ? FLY.r : FLY.r * -1.f) * cosf(FLY.flap) + FLY.u * sinf(FLY.flap); V3 n = nrm(cross(FLY.f, wr)); float den = dot(d, n); if (fabsf(den) < 1e-6f) continue;
        float t = dot(FLY.pos - o, n) / den; if (t <= 1e-3f || t >= tmax) continue; V3 P = o + d * t - FLY.pos; float x = dot(P, FLY.f), y = dot(P, wr); if (y < 0.0015f) continue;
        if (wingE(x, y, 0) < 1 || wingE(x, y, 1) < 1) { tmax = t; tb = t; nW = n; wx = x; wy = y; what = w; any = true; } }
    for (int k = 0; k < 4; k++) { float x = (-0.014f + k * 0.0095f) * FLYS; float r = (k == 3 ? 0.0042f : 0.0046f - 0.0006f * (k == 0)) * FLYS; float t; if (hitSph(FLY.pos + FLY.f * x, r, o, d, tmax, t)) { tmax = t; tb = t; nW = nrm(o + d * t - (FLY.pos + FLY.f * x)); what = 2; any = true; } }
    return any;
}
static V3 flyShade(V3 p, V3 d, V3 n, float x, float y, int what) {
    V3 V = d * -1.f; if (dot(n, V) < 0) n = n * -1.f;
    if (what == 2) { V3 alb(0.05f, 0.035f, 0.025f); return alb * (CSUN * fmaxf(0.f, dot(n, LSUN)) + SKY * 3.14159f * 0.7f) / 3.14159f + SKY * (powf(1 - fabsf(dot(n, V)), 2.f) * 0.15f); }
    float e0 = wingE(x, y, 0), e1 = wingE(x, y, 1);  float e = fminf(e0, e1);   // ближе к 1 — край крыла
    x /= FLYS; y /= FLYS; float ang = atan2f(y, x + 0.004f); float vein = sstep(0.16f, 0.07f, fabsf(sinf(ang * 4.5f + 0.4f)) * (0.35f + 0.65f * sqrtf(fmaxf(0.f, 1 - e)))) * sstep(0.05f, 0.25f, e); vein = fmaxf(vein, sstep(0.06f, 0.0f, fabsf(e0 - e1)) * sstep(0.2f, 0.4f, e));
    V3 alb = lerp(V3(0.92f, 0.3f, 0.015f), V3(0.98f, 0.5f, 0.05f), sstep(0.9f, 0.2f, e));
    float border = sstep(0.66f, 0.72f, e); alb = lerp(alb, V3(0.025f, 0.02f, 0.02f), fmaxf(border, vein * 0.85f));
    if (border > 0.5f) { float sx = floorf(ang * 14.f), dots = hash3((int)sx, what, e0 < e1 ? 1 : 2); float c = fabsf(fract_(ang * 14.f) - 0.5f); if (dots > 0.35f && c < 0.22f && e > 0.75f && e < 0.92f) alb = V3(0.9f, 0.88f, 0.84f); }
    V3 col = alb * (CSUN * fabsf(dot(n, LSUN)) * 0.9f + SKY * (3.14159f * 0.75f)) / 3.14159f;
    float cb = canopy(p); bool behind = dot(n, LBACK) * dot(n, V) < 0;
    col += (behind ? vpow(alb, 0.8f) * 0.55f : alb * fabsf(dot(n, LBACK))) * CBACK * (cb / 3.14159f);
    return col;
}


// ---------------- камера ----------------
struct Cam { V3 pos, fw, rt, up; float tanh, lensR, focus; };
static Cam cam; static int W = 1280, H = 720;
static void lookAt(V3 pos, V3 tgt, float lensMM, float fstop, float focusD) {
    cam.pos = pos; cam.fw = nrm(tgt - pos); cam.rt = nrm(cross(cam.fw, V3(0, 0, 1))); cam.up = cross(cam.rt, cam.fw);
    cam.tanh = 18.f / lensMM; cam.lensR = fstop > 0 ? lensMM * 0.001f / fstop * 0.5f : 0; cam.focus = focusD;
}


// ---------------- движение: кости-повороты, свет волоска едет вместе с ним ----------------
struct M3 { V3 r0, r1, r2; };
static inline V3 mul(const M3& m, V3 v) { return V3(dot(m.r0, v), dot(m.r1, v), dot(m.r2, v)); }
static inline M3 mtr(const M3& m) { return {V3(m.r0.x, m.r1.x, m.r2.x), V3(m.r0.y, m.r1.y, m.r2.y), V3(m.r0.z, m.r1.z, m.r2.z)}; }
static inline M3 mmul(const M3& a, const M3& b) { M3 bt = mtr(b); return {V3(dot(a.r0, bt.r0), dot(a.r0, bt.r1), dot(a.r0, bt.r2)), V3(dot(a.r1, bt.r0), dot(a.r1, bt.r1), dot(a.r1, bt.r2)), V3(dot(a.r2, bt.r0), dot(a.r2, bt.r1), dot(a.r2, bt.r2))}; }
static M3 rotAxis(V3 a, float g) { a = nrm(a); float c = cosf(g), s = sinf(g), t = 1 - c;
    return {V3(t * a.x * a.x + c, t * a.x * a.y - s * a.z, t * a.x * a.z + s * a.y), V3(t * a.x * a.y + s * a.z, t * a.y * a.y + c, t * a.y * a.z - s * a.x), V3(t * a.x * a.z - s * a.y, t * a.y * a.z + s * a.x, t * a.z * a.z + c)}; }
static const M3 I3 = {V3(1, 0, 0), V3(0, 1, 0), V3(0, 0, 1)};
struct Pose { M3 head = I3, sway = I3, ear[2] = {I3, I3}; float tailA = 0, tailPh = 0, breath = 0; float lid[2] = {1, 1}; V3 gaze; };
static Pose POSE; static bool ANIM = false;
struct LidStr { int e, base; float lam, u, L, lift; }; static std::vector<LidStr> LIDS; static V3 LB1[2], LB2[2]; static float LID_TH0 = 0.7f, LID_R = 0.065f;
static const float LID_CLOSED = -0.72f;   // докуда опускается веко (доля радиуса глаза)
static V3 PH(0.f, -0.01f, 0.6f); static V3 EARB[2] = {V3(-0.122f, 0.012f, 0.893f), V3(0.122f, 0.012f, 0.893f)};
static V3 TAILP[6] = {V3(0, 0.13f, 0.19f), V3(0.05f, 0.25f, 0.2f), V3(0.13f, 0.31f, 0.3f), V3(0.17f, 0.31f, 0.45f), V3(0.15f, 0.27f, 0.58f), V3(0.1f, 0.25f, 0.64f)};
static std::vector<V3> SV0, TV0, TN0; static std::vector<float> WH, WT, WE, WB; static size_t HERO_END = 0;
static V3 EYE0[2], LIDN0[2], LIDN[2], HEADF; static float LIDOFF = 0.05f; static V3 LIDCOL(0.7f, 0.4f, 0.15f);
static inline V3 poseP(V3 p, float wh, float ts, float we, float wb) {
    V3 q = p;
    if (wb > 0.01f) { float b = POSE.breath * wb; q.x *= 1 + b; q.y = (q.y + 0.02f) * (1 + b * 0.9f) - 0.02f; }
    if (ts >= 0) { float a = POSE.tailA * sinf(POSE.tailPh - 2.4f * ts) * powf(ts, 1.2f); M3 R = rotAxis(V3(0.15f, 0, 1), a); q = mul(R, q - TAILP[0]) + TAILP[0]; }
    if (we != 0) { int e = we > 0 ? 1 : 0; float w = fabsf(we); q = lerp(q, mul(POSE.ear[e], q - EARB[e]) + EARB[e], w); }
    if (wh > 0) q = lerp(q, mul(POSE.head, q - PH) + PH, wh);
    return mul(POSE.sway, q);
}
static inline V3 poseN(V3 n, float wh) { return nrm(mul(POSE.sway, lerp(n, mul(POSE.head, n), wh))); }
static inline V3 toRest(V3 p) { V3 q = mul(mtr(POSE.sway), p); return mul(mtr(POSE.head), q - PH) + PH; }   // для головы (вес 1)
static float tailS(V3 p) {   // доля длины хвоста у ближайшей точки цепочки
    float best = 1e9f, s = 0, acc = 0, tot = 0; for (int i = 0; i < 5; i++) tot += len(TAILP[i + 1] - TAILP[i]);
    for (int i = 0; i < 5; i++) { V3 a = TAILP[i], b = TAILP[i + 1]; V3 ab = b - a; float L = len(ab); float t = clampf(dot(p - a, ab) / (L * L), 0, 1); float d = len(p - (a + ab * t)); if (d < best) { best = d; s = (acc + t * L) / tot; } acc += L; }
    return s;
}
static void weightsOf(V3 p, int reg, float& wh, float& ts, float& we, float& wb) {
    wh = reg == 7 ? 0.f : sstep(0.5f, 0.62f, p.z); ts = reg == 7 ? tailS(p) : -1.f;
    { int e = p.x > 0 ? 1 : 0; V3 B = EARB[e], T = V3(e ? 0.19f : -0.19f, 0.035f, 1.058f), a = T - B; float s = dot(p - B, a) / dot(a, a); float r = len(p - (B + a * s));
      we = sstep(-0.05f, 0.3f, s) * sstep(0.12f, 0.075f, r) * (e ? 1.f : -1.f); }
    wb = expf(-(p.z - 0.37f) * (p.z - 0.37f) / (0.13f * 0.13f)) * (reg == 7 ? 0.f : 1.f);
}

// ---------------- оттенение одного луча ----------------
static float GTIME = 0; static int DBG = 0; static thread_local int LASTK = -9, LASTA = -1;
static V3 envRefl(V3 d) {   // что отражается в глазу: небо-дымка, тёмные стволы у горизонта, трава снизу
    V3 sky = lerp(FOGC * 0.95f, V3(0.8f, 0.9f, 0.9f), sstep(0.1f, 0.7f, d.z));
    float trees = sstep(0.35f, -0.05f, d.z) * (0.5f + 0.5f * sstep(0.2f, 0.8f, fbm(V3(atan2f(d.y, d.x) * 9.f, 0, 0), 2)));
    sky = lerp(sky, V3(0.16f, 0.24f, 0.2f), trees * 0.7f);
    if (d.z < -0.02f) sky = lerp(V3(0.1f, 0.2f, 0.05f), V3(0.05f, 0.1f, 0.03f), sstep(-0.02f, -0.5f, d.z));
    return sky;
}
static V3 shade(V3 o, V3 d, float& dist) {
    Hit h; bool hb = traceBVH(o, d, 60.f, h); float tbest = hb ? h.t : 60.f; int kind = hb ? 0 : -1; int aid = -1; float ta;
    for (int i = 0; i < (int)trunks.size(); i++) if (hitCyl(trunks[i], o, d, tbest, ta)) { tbest = ta; kind = 1; aid = i; }
    for (int i = 0; i < (int)stones.size(); i++) if (hitEll(stones[i], o, d, tbest, ta)) { tbest = ta; kind = 2; aid = i; }
    for (int i = 0; i < 2; i++) if (hitSph(EYE[i], RE, o, d, tbest, ta)) { tbest = ta; kind = 3; aid = i; }
    for (int i = 0; i < 2; i++) if (POSE.lid[i] < 0.999f && hitSph(EYE[i], RE + 0.0045f, o, d, tbest, ta)) { V3 q = o + d * ta - EYE[i];
        float off = LID_CLOSED * RE + (LIDOFF - LID_CLOSED * RE) * POSE.lid[i]; if (dot(q, HEADF) > -0.35f * RE && dot(q, LIDN[i]) > off) { tbest = ta; kind = 5; aid = i; } }
    if (d.z < 0) { ta = -o.z / d.z; if (ta < tbest) { tbest = ta; kind = 4; } }
    V3 fn; float fx, fy; int fw; if (hitFly(o, d, tbest, ta, fn, fx, fy, fw)) { tbest = ta; dist = ta; return flyShade(o + d * ta, d, fn, fx, fy, fw); }
    dist = tbest; V3 V = d * -1.f; LASTK = kind; LASTA = aid;
    if (kind < 0) return SKY;
    V3 p = o + d * tbest;
    if (kind == 1) {   // ствол: кора с мхом
        const Cyl& c = trunks[aid]; V3 n = nrm(V3(p.x - c.x, p.y - c.y, 0)); float ang = atan2f(n.y, n.x);
        float nz = fbm(V3(ang * c.r * 6.f, p.z * 0.6f, aid * 3.1f), 5); V3 bark = lerp(V3(0.05f, 0.035f, 0.025f), V3(0.22f, 0.17f, 0.11f), sstep(0.25f, 0.75f, nz));
        float moss = sstep(0.9f, 0.3f, (p.z - 7.f) / 14.f * 2.f + 0.5f + (fbm(V3(ang * 2.f, p.z * 0.8f, aid), 3) - 0.5f) * 0.6f);
        V3 alb = lerp(bark, V3(0.09f, 0.17f, 0.06f), moss * 0.75f);
        float dif = fmaxf(0.f, dot(n, LSUN)) * 0.35f; float sk = 0.32f - 0.1f * sstep(1.5f, 0.f, p.z);
        return alb * (CSUN * dif + SKY * (3.14159f * sk) + CBACK * (canopy(p) * fmaxf(0.f, dot(n, LBACK)) * 0.8f * KDAPPLE)) / 3.14159f;
    }
    if (kind == 2) {   // мшистый камень
        const Ell& e = stones[aid]; V3 n = nrm((p - e.c) * V3(1 / (e.r.x * e.r.x), 1 / (e.r.y * e.r.y), 1 / (e.r.z * e.r.z)));
        float nz = fbm(p * 14.f, 4); V3 alb = lerp(V3(0.12f, 0.24f, 0.06f), V3(0.2f, 0.36f, 0.09f), nz);
        float ao = 0.45f + 0.55f * sstep(0.0f, 0.12f, p.z); float dif = fmaxf(0.f, dot(n, LSUN));
        float sheen = powf(1 - fabsf(dot(n, V)), 2.f) * 0.6f;
        return alb * (CSUN * dif + SKY * (3.14159f * (0.6f + 0.4f * n.z)) + CBACK * (backVis(p, true) * fmaxf(0.f, dot(n, LBACK)) * KDAPPLE)) * (ao / 3.14159f) + SKY * sheen * ao * 0.3f;
    }
    if (kind == 4) {   // земля под травой
        float nz = fbm(V3(p.x, p.y, 0) * 1.5f, 4); V3 alb = lerp(V3(0.04f, 0.09f, 0.02f), V3(0.16f, 0.26f, 0.05f), nz);
        float sh = 0.3f; // под травой темно
        return alb * (CSUN * sh * LSUN.z + SKY * (3.14159f * 0.35f) + CBACK * (backVis(p, true) * LBACK.z * 0.25f * KDAPPLE)) / 3.14159f;
    }
    if (kind == 5) {   // веко опускается — моргание: пушистое, с тёмной линией смыкания
        V3 q = p - EYE[aid]; V3 n = nrm(q); float off = LID_CLOSED * RE + (LIDOFF - LID_CLOSED * RE) * POSE.lid[aid]; float edge = dot(q, LIDN[aid]) - off;
        V3 rq = toRest(p) - EYE0[aid]; V3 rn = nrm(rq);
        // ворс века: тонкие штрихи сверху вниз (по долготе), слегка вьются
        float lon = atan2f(rn.x, -rn.y) * 60.f + fbm(rq * 300.f, 2) * 4.f; float streak = 0.5f + 0.5f * sinf(lon * 3.1f) * sinf(lon * 1.7f + 1.3f);
        float fz = fbm(V3(lon * 0.6f, rq.z * 900.f, aid * 5.f), 3);
        V3 alb = LIDCOL * (0.5f + 0.2f * streak + 0.15f * (fz - 0.5f));
        float lin = sstep(0.0042f, 0.0012f, edge + (fz - 0.5f) * 0.0012f);   // ресничная кромка, мягкая
        alb = lerp(alb, V3(0.07f, 0.035f, 0.02f), lin);
        float top = sstep(-0.2f, 0.75f, dot(rn, gv("lid_ns", aid)));   // под бровью — тень
        auto cl = cellLight(toRest(p + n * 0.003f));
        V3 col(0, 0, 0); for (int i = 0; i < 4; i++) { V3 L, E; lightAt(i, p, L, E); col += E * (cl[i] * fmaxf(0.f, (dot(n, L) + 0.5f) / 1.5f)); }
        col += SKY * (3.14159f * cl[4] * 0.85f) + GNDL * (3.14159f * cl[5] * 0.5f);
        col = col * (0.62f + 0.38f * (1 - top * 0.6f));
        float sh = powf(1 - fabsf(dot(n, V)), 2.f) * 0.4f; return alb * col / 3.14159f + alb * SKY * (sh * cl[4] * (1 - lin));
    }
    if (kind == 3) {   // глаз
        V3 n = nrm(p - EYE[aid]); V3 f = EYEF[aid]; float c = dot(n, f);
        V3 ax1 = nrm(cross(f, V3(0, 0, 1))), ax2 = cross(ax1, f); float ang = atan2f(dot(n, ax2), dot(n, ax1));
        float rr = acosf(clampf(c, -1, 1));
        float iris = sstep(0.70f, 0.715f, c), pup = sstep(0.915f, 0.922f, c), ring = sstep(0.70f, 0.79f, c);
        float nzz = fbm(V3(cosf(ang) * 4.f, sinf(ang) * 4.f, rr * 6.f + aid * 7.f), 5);
        float fib = 0.5f + 0.5f * sinf(ang * 37.f + nzz * 9.f);
        float k = clampf(nzz * 1.1f + fib * 0.25f - 0.15f, 0, 1);
        V3 ic = k < 0.55f ? lerp(V3(0.06f, 0.2f, 0.05f), V3(0.16f, 0.42f, 0.08f), sstep(0.3f, 0.55f, k)) : lerp(V3(0.16f, 0.42f, 0.08f), V3(0.35f, 0.62f, 0.12f), sstep(0.55f, 0.75f, k));
        ic = lerp(ic * V3(0.2f, 0.25f, 0.16f), ic, ring);
        ic = ic * (0.85f + 0.5f * sstep(0.75f, 0.95f, c) * (0.6f + 0.4f * sstep(0.2f, -0.6f, dot(n, V3(0, 0, 1)) - 0.3f)));   // снизу радужка светлее — свет сквозь роговицу
        V3 alb = lerp(lerp(V3(0.9f, 0.88f, 0.86f), ic, iris), V3(0.004f, 0.003f, 0.003f), pup);
        auto cl = cellLight(toRest(p + n * 0.004f)); V3 col(0, 0, 0);
        for (int i = 0; i < 4; i++) { V3 L, E; lightAt(i, p, L, E); col += E * (cl[i] * fmaxf(0.f, dot(n, L) * 0.8f + 0.2f)); }
        col += SKY * (3.14159f * cl[4] * 0.8f) + GNDL * (3.14159f * cl[5] * 0.5f);
        V3 out = alb * col / 3.14159f;
        // роговица: выпуклая линза над радужкой
        V3 cc = EYE[aid] + f * (-0.208f * -RE) ; float tc; V3 cn = n;
        if (hitSph(EYE[aid] + f * (0.208f * RE), 0.872f * RE, o, d, 1e9f, tc)) cn = nrm(o + d * tc - (EYE[aid] + f * (0.208f * RE)));
        (void)cc;
        float cv = fmaxf(0.f, dot(cn, V)); float F = 0.04f + 0.96f * powf(1 - cv, 5.f); V3 R = d - cn * (2 * dot(d, cn));
        float occl = cl[4] * 0.85f + 0.15f;
        V3 refl = envRefl(R) * (F * occl * 0.9f);
        for (int i = 1; i < 3; i++) { V3 L, E; lightAt(i, p, L, E); float a = dot(R, L); float sz = i == 2 ? 0.93f : 0.97f; refl += E * (sstep(sz, sz + 0.02f, a) * 0.6f * cl[i]); }
        if (hasEyeL) { V3 L = nrm(EYEL.pos - p); float a = dot(R, L); refl += EYEL.col * (sstep(0.988f, 0.993f, a) * 3.5f); }
        { float a = dot(R, LSUN); refl += CSUN * (sstep(0.9985f, 0.9995f, a) * 1.5f * cl[0]); }
        return out + refl;
    }
    // ---- BVH: кожа/нос/шарф или пряди ----
    if (h.prim < nTri) {
        const Tri& tr = tris[h.prim]; float w0 = 1 - h.u - h.v;
        V3 n = nrm(TN[tr.a] * w0 + TN[tr.b] * h.u + TN[tr.c] * h.v); if (dot(n, V) < 0 && tr.mat != M_SKIN) n = n * -1.f;
        V3 alb = TA[tr.a] * w0 + TA[tr.b] * h.u + TA[tr.c] * h.v;
        std::array<float, 6> bk; for (int c = 0; c < 6; c++) bk[c] = TB[tr.a][c] * w0 + TB[tr.b][c] * h.u + TB[tr.c][c] * h.v;
        float wrap = tr.mat == M_SKIN ? 0.35f : tr.mat == M_SCARF ? 0.2f : 0.25f;
        if (tr.mat == M_SCARF) {   // вязаный рубчик
            float ph = p.z * 140.f * 6.2832f; float bump = cosf(ph) * 0.35f; n = nrm(n + V3(0, 0, 1) * bump - n * (n.z * bump));
        }
        V3 dif(0, 0, 0), spec(0, 0, 0);
        for (int i = 0; i < 4; i++) { V3 L, E; lightAt(i, p, L, E); float nl = (dot(n, L) + wrap) / (1 + wrap); if (nl <= 0) continue; dif += E * (nl * bk[i]);
            V3 Hh = nrm(L + V); float nh = fmaxf(0.f, dot(n, Hh)); float ex = tr.mat == M_NOSE ? 60.f : tr.mat == M_SCARF ? 6.f : 14.f; float ks = tr.mat == M_NOSE ? 0.35f : tr.mat == M_SCARF ? 0.02f : 0.05f;
            spec += E * (powf(nh, ex) * ks * (ex + 2) / 25.f * bk[i] * nl); }
        dif += SKY * (3.14159f * bk[4] * (0.6f + 0.4f * n.z)) + GNDL * (3.14159f * bk[5] * (0.5f - 0.4f * n.z));
        V3 col = alb * dif / 3.14159f + spec;
        float sheenK = tr.mat == M_SCARF ? 0.7f : (TR[tr.a] == 2 ? 0.5f : 0.15f);
        float sh = powf(1 - fabsf(dot(n, V)), 3.f) * sheenK; col += (tr.mat == M_SCARF ? alb * 1.5f + V3(0.03f, 0.05f, 0.1f) : alb) * (sh * (bk[4] * 0.6f + bk[2] * 0.25f));
        if (TR[tr.a] == 8) col += V3(0.9f, 0.25f, 0.2f) * (0.06f * bk[1] + 0.03f);   // ухо просвечивает
        return col;
    }
    const Seg& sg = segs[h.prim - nTri]; int i0 = sg.v, i1 = sg.v + 1; float u = h.u;
    V3 T = nrm(SV[i1] - SV[i0]); V3 alb = lerp(SA[i0], SA[i1], u); std::array<float, 6> bk; for (int c = 0; c < 6; c++) bk[c] = SB[i0][c] + (SB[i1][c] - SB[i0][c]) * u;
    if (sg.type == S_GRASS) {
        float tip = ST[i0] + (ST[i1] - ST[i0]) * u; (void)tip;
        float sl = sqrtf(fmaxf(0.f, 1 - dot(T, LSUN) * dot(T, LSUN)));
        V3 col = alb * (CSUN * (bk[0] * sl * 0.7f) + SKY * (3.14159f * bk[4])) / 3.14159f;
        float back = fmaxf(0.f, dot(d, LSUN)); col += vpow(alb, 0.8f) * CSUN * (bk[0] * 0.3f * (0.25f + back * back * 1.5f) / 3.14159f);
        col += hairSpec(T, LSUN, V, alb, 0.25f) * CSUN * bk[0] * 0.5f;
        float vb = backVis(p, true) * KDAPPLE * (0.25f + 0.75f * bk[4]);   // солнечные пятна сквозь кроны, трава светится на просвет
        if (vb > 0.001f) { float slb = sqrtf(fmaxf(0.f, 1 - dot(T, LBACK) * dot(T, LBACK))); float bb = fmaxf(0.f, dot(d, LBACK));
            col += (alb * (slb * 0.55f) + vpow(alb, 0.75f) * (0.5f * (0.2f + 1.3f * bb * bb))) * CBACK * (vb / 3.14159f) + hairSpec(T, LBACK, V, alb, 0.3f) * CBACK * vb * 0.5f; }
        return col;
    }
    if (DBG == 4) { float tt = ST[i0] + (ST[i1] - ST[i0]) * u; return V3(tt, tt, tt); }
    if (DBG == 1) return alb; if (DBG == 2) return V3(bk[2], bk[0], bk[4]); if (DBG == 3) return T * 0.5f + V3(0.5f, 0.5f, 0.5f);
    float ms = 0.f;
    V3 col(0, 0, 0), msc(0, 0, 0);
    for (int i = 0; i < 4; i++) { V3 L, E; lightAt(i, p, L, E); float sl = sqrtf(fmaxf(0.f, 1 - dot(T, L) * dot(T, L)));
        col += E * (bk[i] * (0.35f + 0.65f * sl)); msc += E * powf(fmaxf(bk[i], 0.f), 0.33f);
    }
    V3 c2 = alb * (col + SKY * (3.14159f * bk[4] * 0.85f) + GNDL * (3.14159f * bk[5] * 0.6f)) / 3.14159f;
    c2 += alb * alb * msc * (0.32f / 3.14159f) * (sg.type == S_FUR ? 1.f : 0.f); (void)ms;
    for (int i = 0; i < 4; i++) { V3 L, E; lightAt(i, p, L, E); c2 += hairSpec(T, L, V, alb, sg.type == S_WHISK ? 1.6f : 1.f) * E * bk[i]; }
    c2 += hairSpec(T, nrm(V3(0, 0, 1) + V * 0.3f), V, alb, 0.5f) * SKY * (bk[4] * 1.2f);   // небо даёт мягкий общий блеск
    return c2;
}

// ---------------- пост ----------------
static inline V3 agx(V3 c) {
    V3 v(0.842479062253094f * c.x + 0.0784335999999992f * c.y + 0.0792237451477643f * c.z,
         0.0423282422610123f * c.x + 0.878468636469772f * c.y + 0.0791661274605434f * c.z,
         0.0423756549057051f * c.x + 0.0784336f * c.y + 0.879142973793104f * c.z);
    const float mn = -12.47393f, mx = 4.026069f;
    auto f = [&](float x) { x = clampf(log2f(fmaxf(x, 1e-10f)), mn, mx); x = (x - mn) / (mx - mn); float x2 = x * x, x4 = x2 * x2;
        return 15.5f * x4 * x2 - 40.14f * x4 * x + 31.96f * x4 - 6.868f * x2 * x + 0.4298f * x2 + 0.1191f * x - 0.00232f; };
    v = V3(f(v.x), f(v.y), f(v.z));
    // взгляд «Punchy»
    v = vpow(v, 1.35f); float l = 0.2126f * v.x + 0.7152f * v.y + 0.0722f * v.z; v = V3(l, l, l) + (v - V3(l, l, l)) * 1.4f;
    V3 o(1.19687900512017f * v.x - 0.0980208811401368f * v.y - 0.0990297440797205f * v.z,
         -0.0528968517574562f * v.x + 1.15190312990417f * v.y - 0.0989611768448433f * v.z,
         -0.0529716355144438f * v.x - 0.0980434501171241f * v.y + 1.15107367264116f * v.z);
    return vpow(o, 2.2f);
}
static inline float srgb(float x) { x = clampf(x, 0, 1); return x <= 0.0031308f ? 12.92f * x : 1.055f * powf(x, 1 / 2.4f) - 0.055f; }

// ---------------- сборка сцены ----------------
static std::string SHOT = "close";
static void buildScene() {
    // кожа
    auto& sv = G["skin_v"]; auto& sf = G["skin_f"].i; auto& sn = G["skin_n"].f; auto& sr = G["skin_reg"].b; auto& sc = G["skin_col"].f;
    size_t nv = sv.shape[0]; RE = G["re"].f[0]; EYE[0] = gv("eyes", 0); EYE[1] = gv("eyes", 1);
    for (size_t i = 0; i < nv; i++) {
        V3 p = gv("skin_v", i); TV.push_back(p); TN.push_back(V3(sn[i * 3], sn[i * 3 + 1], sn[i * 3 + 2])); int r = sr[i]; TR.push_back((uint8_t)r);
        V3 a = V3(sc[i * 3], sc[i * 3 + 1], sc[i * 3 + 2]) * 0.9f;
        if (r == 2) a = V3(0.9f, 0.76f, 0.6f); if (r == 8) a = p.z < 0.42f ? V3(0.8f, 0.42f, 0.47f) : V3(0.62f, 0.3f, 0.32f);   /* подушечки лап (образец 6.2) — розовые */
        bool liner = false; for (int e = 0; e < 2; e++) { V3 q = p - EYE[e]; if (len(q) < RE + 0.011f && q.y < 0.01f) liner = true; }
        if (liner) a = V3(0.09f, 0.04f, 0.02f); TA.push_back(a);
    }
    for (size_t f = 0; f < sf.size() / 3; f++) tris.push_back({sf[f * 3], sf[f * 3 + 1], sf[f * 3 + 2], M_SKIN});
    auto addMesh = [&](const char* vk, const char* fk, int mat, V3 alb) {
        size_t base = TV.size(); auto& v = G[vk]; auto& f = G[fk].i; size_t n = v.shape[0]; std::vector<V3> nn(n);
        for (size_t i = 0; i < n; i++) { TV.push_back(gv(vk, i)); TA.push_back(alb); TR.push_back(20 + mat); }
        for (size_t k = 0; k < f.size() / 3; k++) { int a = f[k * 3], b = f[k * 3 + 1], c = f[k * 3 + 2]; V3 fn = cross(TV[base + b] - TV[base + a], TV[base + c] - TV[base + a]); nn[a] += fn; nn[b] += fn; nn[c] += fn; tris.push_back({(int)base + a, (int)base + b, (int)base + c, mat}); }
        V3 cen(0, 0, 0); for (size_t i = 0; i < n; i++) cen += TV[base + i]; cen = cen / (float)n; float sgn = 0;
        for (size_t i = 0; i < n; i++) sgn += dot(nn[i], TV[base + i] - cen);
        for (size_t i = 0; i < n; i++) TN.push_back(nrm(nn[i]) * (sgn < 0 ? -1.f : 1.f));   // нормали — наружу
    };
    addMesh("nose_v", "nose_f", M_NOSE, V3(0.78f, 0.36f, 0.42f));
    addMesh("scarf_v", "scarf_f", M_SCARF, V3(0.038f, 0.225f, 0.61f));   // вязаный, как в «Мультиках»
    // проверка направления нормалей носа/шарфа: должны смотреть наружу от центра
    nTri = (int)tris.size();
    // шерсть
    auto& fp = G["fur_pts"]; auto& fr = G["fur_rad"].f; auto& fc = G["fur_col"].f; size_t ns = fp.shape[0]; int P = fp.shape[1]; bool hasN = G.count("fur_nrm") > 0;
    for (size_t s = 0; s < ns; s++) {
        int base = (int)SV.size(); V3 c(fc[s * 3], fc[s * 3 + 1], fc[s * 3 + 2]);
        { V3 nn = hasN ? gv("fur_nrm", s) : nrm(gv("fur_pts", s * P + P - 1) - gv("fur_pts", s * P)); for (int k = 0; k < P; k++) SNV.push_back(nn); }
        for (int k = 0; k < P; k++) { float t = k / (float)(P - 1); SV.push_back(gv("fur_pts", s * P + k)); float dk = (1 - t) * (1 - t); SA.push_back(vpow(c, FURPOW) * FURMUL * lerp(V3(1, 1, 1), G["fur_reg"].b[s] == 12 ? V3(0.8f, 0.8f, 0.8f) : V3(0.62f, 0.55f, 0.5f), dk)); ST.push_back(t); }
        for (int k = 0; k < P - 1; k++) { float t0 = k / (float)(P - 1), t1 = (k + 1) / (float)(P - 1); segs.push_back({base + k, fr[s] * (1 - 0.85f * powf(t0, 1.3f)), fr[s] * (1 - 0.85f * powf(t1, 1.3f)), S_FUR}); }
    }
    // усы и рот
    auto addLine = [&](const char* k, int idx, int n, float r0, float r1, V3 alb, int type) {
        int base = (int)SV.size(); for (int j = 0; j < n; j++) { SV.push_back(gv(k, idx * n + j)); SA.push_back(alb); ST.push_back(j / (float)(n - 1)); SNV.push_back(nrm(V3(0, -0.9f, 0.4f))); }
        for (int j = 0; j < n - 1; j++) segs.push_back({base + j, r0 + (r1 - r0) * j / (n - 1), r0 + (r1 - r0) * (j + 1) / (n - 1), (uint8_t)type});
    };
    for (int i = 0; i < G["whisk"].shape[0]; i++) addLine("whisk", i, 8, 0.0011f, 0.00025f, V3(0.92f, 0.9f, 0.86f), S_WHISK);
    for (int i = 0; i < G["mouth"].shape[0]; i++) addLine("mouth", i, 12, 0.0017f, 0.0015f, V3(0.12f, 0.04f, 0.03f), S_MOUTH);
    // мех на веках: полоса на сфере над глазом, сползает вниз вместе с краем века при моргании
    { RE = G["re"].f[0]; float R = RE + 0.0045f; LID_R = R; float off0 = G["lid_off"].f[0]; float th0 = acosf(off0 / R), th1 = acosf(LID_CLOSED * RE / R); LID_TH0 = th0;
      VX = G["vol"].shape[0]; VY = G["vol"].shape[1]; VZ = G["vol"].shape[2]; VOLp = G["vol"].f.data(); vLo = gv("vol_lo", 0); vH = G["vol_h"].f[0];
      for (int e = 0; e < 2; e++) { V3 a = gv("lid_ns", e), E = gv("eyes", e); LB1[e] = nrm(cross(a, V3(1, 0, 0))); LB2[e] = cross(a, LB1[e]); Rng r(77 + e); int kept = 0;
        for (int k = 0; k < 26000; k++) { float lam = r.f() * 6.2832f, u = (th1 - th0) * r.f(); float th = th1 - u; float ct = cosf(th), st = sinf(th);
            V3 dir = a * ct + (LB1[e] * cosf(lam) + LB2[e] * sinf(lam)) * st; if (dir.y > 0.2f) continue; V3 pp = E + dir * R; if (sdf(pp) < -0.003f) continue;
            LidStr ls; ls.e = e; ls.base = (int)SV.size(); ls.lam = lam; ls.u = u; ls.L = (0.0055f + 0.003f * r.f()) * (u < 0.09f ? 1.35f : 1.f); ls.lift = 0.12f + 0.15f * r.f(); LIDS.push_back(ls); kept++;
            for (int j = 0; j < 5; j++) { SV.push_back(E); SA.push_back(V3(0.6f, 0.35f, 0.12f)); ST.push_back(j / 4.f); SNV.push_back(dir); }
            for (int j = 0; j < 4; j++) segs.push_back({ls.base + j, 0.0006f * (1 - 0.85f * powf(j / 4.f, 1.3f)), 0.0006f * (1 - 0.85f * powf((j + 1) / 4.f, 1.3f)), S_FUR}); }
        LOG("веко %d: %d волосков", e, kept); } }
    FURN = ns * P; size_t heroVerts = SV.size();
    // трава
    Rng rg(11); int NG = 140000; int ng = 0;
    for (int i = 0; i < NG; i++) {
        float R = sqrtf(rg.f()) * 3.4f, A = rg.f() * 6.2832f; V3 root(cosf(A) * R, sinf(A) * R * 1.7f + 0.6f, 0);
        if (fabsf(root.x) < 0.12f && fabsf(root.y + 0.03f) < 0.1f) continue;
        bool skip = false; for (int f = 0; f < 2; f++) { float dx = root.x - (f ? 0.092f : -0.092f), dy = root.y + 0.08f; if (dx * dx / 0.0049f + dy * dy / 0.016f < 1) skip = true; } if (skip) continue;
        float hg = 0.04f + 0.07f * rg.f(); float lx = (rg.f() + rg.f() + rg.f() - 1.5f) * 0.55f, ly = (rg.f() + rg.f() + rg.f() - 1.5f) * 0.55f;
        int base = (int)SV.size(); float shade = 0.8f + 0.4f * rg.f();
        for (int k = 0; k < 4; k++) { float t = k / 3.f; SV.push_back(root + V3(lx * t * t * hg, ly * t * t * hg, hg * t)); V3 a = lerp(V3(0.03f, 0.07f, 0.012f), V3(0.3f, 0.5f, 0.07f), t) * (shade * GRASSK); SA.push_back(a); ST.push_back(-10 - t); }
        const float rr[4] = {0.0028f, 0.0022f, 0.0014f, 0.0002f};
        for (int k = 0; k < 3; k++) segs.push_back({base + k, rr[k], rr[k + 1], S_GRASS});
        ng++;
    }
    SB.assign(SV.size(), std::array<float, 6>{1, 1, 1, 1, 1, 1}); TB.assign(TV.size(), std::array<float, 6>{1, 1, 1, 1, 1, 1});
    LOG("кожа %zu тр., шерсть %zu прядей, трава %d, отрезков %zu, вершин прядей %zu (герой %zu)", tris.size(), ns, ng, segs.size(), SV.size(), heroVerts);
    // стволы и камни
    Rng rt(11);
    for (int i = 0; i < 16; i++) { float x = -5.5f + 11 * rt.f(), y = 1.6f + 8.4f * rt.f(), r = 0.16f + 0.26f * rt.f(); if (fabsf(x) < 0.9f && y < 3) x += 1.6f * (x >= 0 ? 1 : -1); trunks.push_back({x, y, r}); }
    for (int i = 0; i < 5; i++) { float x = -2.5f + 5 * rt.f(), y = 1.2f + 3.3f * rt.f(), r = 0.2f + 0.25f * rt.f(); stones.push_back({V3(x, y, 0.05f), V3(1.3f * r, r, 0.6f * r)}); }
    // объём поля кожи
    VX = G["vol"].shape[0]; VY = G["vol"].shape[1]; VZ = G["vol"].shape[2]; VOLp = G["vol"].f.data(); vLo = gv("vol_lo", 0); vH = G["vol_h"].f[0];
}

static void bakeAll() {
    buildLightCells();
    size_t heroEnd = 0; for (size_t i = 0; i < SV.size(); i++) if (ST[i] > -5) heroEnd = i + 1;
    if (DBG == 7) { double so[5] = {0}, sn[5] = {0}; int cn[5] = {0}; for (size_t i = 0; i < FURN; i += 97) { int k = (int)roundf(ST[i] * 4); float t = 0; for (float u = 0.00075f; u < 0.03f; u += 0.0015f) t += sig(SV[i] + SNV[i] * u) * 0.0015f;
            so[k] += t; sn[k] += G["fur_tau"].f[i / 5] * powf(1 - ST[i], 1.5f); cn[k]++; } for (int k = 0; k < 5; k++) LOG("t=%.2f по сетке %.2f по соседям %.2f", k / 4.f, so[k] / cn[k], sn[k] / cn[k]); exit(0); }
    // каждый волосок сам запоминает свой свет — в каждой своей точке (неоновая основа)
    #pragma omp parallel for schedule(dynamic, 2048)
    for (size_t i = 0; i < heroEnd; i++) { if (FACEONLY && !(SV[i].y < -0.05f && SV[i].z > 0.6f && SV[i].z < 0.95f)) continue; if (OLDBAKE) bakeCell(SV[i], SB[i], (uint32_t)i * 2246822519u + 3, 1, 8); else { float tr = 0; if (i < FURN) { int rg = G["fur_reg"].b[i / 5]; if (rg == 4 || rg == 8) tr = 0.5f; else if (rg == 12) tr = 0.35f; } float ts_ = -1; if (i < FURN && G.count("fur_tau")) { float tt = ST[i]; ts_ = G["fur_tau"].f[i / 5] * (0.094f + 0.345f * powf(1 - tt, 1.47f)); } else if (i >= FURN) ts_ = 0;
            bakeHair(SV[i], SNV[i], SB[i], (uint32_t)i * 2246822519u + 3, 8, tr, ts_); } }
    LOG("волоски: %zu точек запомнили свой свет", heroEnd);
    #pragma omp parallel for schedule(dynamic, 1024)
    for (size_t i = 0; i < TV.size(); i++) { if (OLDBAKE) bakeCell(TV[i] + TN[i] * 0.002f, TB[i], (uint32_t)i * 3266489917u + 5, 2, 16); else bakeHair(TV[i] + TN[i] * 0.002f, TN[i], TB[i], (uint32_t)i * 3266489917u + 5, 16, 0.f, (i < G["skin_v"].shape[0] && G.count("skin_tau")) ? G["skin_tau"].f[i] * 0.44f : -1.f); }
    // трава: насколько глубоко в травяном ковре (снизу темно), тень героя, стволов и камней
    #pragma omp parallel for schedule(dynamic, 1024)
    for (size_t i = heroEnd; i < SV.size(); i++) {
        V3 p = SV[i]; float depth = fmaxf(0.f, 0.085f - p.z);
        float ts = expf(-depth * 13.f / fmaxf(LSUN.z, 0.2f)); float sk = 0.25f + 0.75f * expf(-depth * 11.f);
        // тень героя
        float tc = march(p, LSUN, 3.f); ts *= tc;
        // небо над героем
        V3 dc = V3(0, -0.02f, 0.5f) - p; float dh = sqrtf(dc.x * dc.x + dc.y * dc.y); if (dh < 0.7f) { float a = 0; for (int k = 0; k < 6; k++) a += march(p, SKYD[k * 2 + 1], 2.f); sk *= 0.3f + 0.7f * a / 6; }
        for (auto& c : trunks) { float t; if (hitCyl(c, p, LSUN, 1e9f, t)) { ts *= 0.f; break; } }
        for (auto& e : stones) { float t; if (hitEll(e, p, LSUN, 1e9f, t)) { ts *= 0.f; break; } }
        SB[i] = {ts, 1, 1, 1, sk, 1};
    }
}

// ---------------- кадр ----------------
struct Mote { V3 p, v; float ph, br; }; static std::vector<Mote> motes;
static void renderFrame(int SPP, const std::string& OUT, float expo, float tsec) {
    std::vector<V3> img((size_t)W * H); std::vector<float> dep((size_t)W * H);
    float aspect = (float)W / H; int S = std::max(1, (int)roundf(sqrtf((float)SPP)));
    #pragma omp parallel for schedule(dynamic, 1)
    for (int y = 0; y < H; y++) {
        Rng r(y * 7919 + 13 + (uint64_t)(tsec * 1000) * 100003);
        for (int x = 0; x < W; x++) {
            V3 acc(0, 0, 0); float dmin = 1e9f;
            for (int s = 0; s < S * S; s++) {
                float jx = ((s % S) + r.f()) / S, jy = ((s / S) + r.f()) / S;
                float px = ((x + jx) / W * 2 - 1) * cam.tanh, py = (1 - (y + jy) / H * 2) * cam.tanh / aspect;
                V3 d = nrm(cam.fw + cam.rt * px + cam.up * py); V3 o = cam.pos;
                if (cam.lensR > 0) { float a = r.f() * 6.2832f, rr = sqrtf(r.f()) * cam.lensR; V3 off = cam.rt * (cosf(a) * rr) + cam.up * (sinf(a) * rr);
                    V3 fp = cam.pos + d * (cam.focus / dot(d, cam.fw)); o = cam.pos + off; d = nrm(fp - o); }
                float dist; V3 c = shade(o, d, dist);
                float m = clampf((dist - 3.f) / 10.f, 0, 1); m = m * m * 0.72f; c = c * (1 - m) + FOGC * m;
                acc += c; dmin = fminf(dmin, dist);
            }
            img[(size_t)y * W + x] = acc / (float)(S * S); dep[(size_t)y * W + x] = dmin;
        }
    }
    // пылинки в солнце: мягкие кружки боке (сзади героя — прячутся по глубине)
    for (const Mote& m : motes) { if (DBG == 8) break;
        V3 q = m.p - cam.pos; float z = dot(q, cam.fw); if (z < 0.2f) continue;
        float sx = dot(q, cam.rt) / z / cam.tanh, sy = dot(q, cam.up) / z / (cam.tanh / aspect);
        float cx = (sx + 1) * 0.5f * W, cy = (1 - sy) * 0.5f * H;
        float fl = 0.018f / cam.tanh; float coc = 2 * cam.lensR * fabsf(z - cam.focus) / z * fl / fmaxf(cam.focus - fl, 0.05f) / 0.036f * W;
        float rad = fmaxf(1.3f, coc * 0.5f); if (cx < -rad || cy < -rad || cx > W + rad || cy > H + rad) continue;
        float tw = 0.55f + 0.45f * sinf(tsec * 2.1f + m.ph); V3 col = V3(1.0f, 0.88f, 0.66f) * (m.br * tw * 0.9f / fmaxf(1.f, rad * rad * 0.35f));
        int x0 = (int)(cx - rad - 1), x1 = (int)(cx + rad + 1), y0 = (int)(cy - rad - 1), y1 = (int)(cy + rad + 1);
        for (int y = std::max(0, y0); y <= std::min(H - 1, y1); y++) for (int x = std::max(0, x0); x <= std::min(W - 1, x1); x++) {
            float dd = sqrtf((x + 0.5f - cx) * (x + 0.5f - cx) + (y + 0.5f - cy) * (y + 0.5f - cy)); float a = clampf(rad + 0.5f - dd, 0, 1); if (a <= 0) continue;
            if (dep[(size_t)y * W + x] < z * 0.98f) continue; float rim = rad > 3 ? 0.8f + 0.4f * sstep(rad - 2.5f, rad, dd) : 1.f;
            float fogk = 1 - clampf((z - 3.f) / 10.f, 0, 1) * 0.6f; img[(size_t)y * W + x] += col * (a * rim * fogk); }
    }
    if (KSHAFT > 0) {   // лучи солнца в тумане
        int LW = W / 4, LH = H / 4; std::vector<V3> lo((size_t)LW * LH), lt(lo.size()); std::vector<float> ld(lo.size());
        float g = 0.55f;
        #pragma omp parallel for schedule(dynamic, 1)
        for (int ly = 0; ly < LH; ly++) { Rng r(ly * 31 + 7 + (uint64_t)(tsec * 997)); for (int lx = 0; lx < LW; lx++) {
            int cx = lx * 4 + 2, cy = ly * 4 + 2; float dpt = dep[(size_t)cy * W + cx]; ld[(size_t)ly * LW + lx] = dpt;
            float px = ((cx + 0.5f) / W * 2 - 1) * cam.tanh, py = (1 - (cy + 0.5f) / H * 2) * cam.tanh / aspect; V3 d = nrm(cam.fw + cam.rt * px + cam.up * py);
            float tmax = fminf(dpt, 32.f); const int NS = 44; float ds = tmax / NS, tt = ds * r.f(), T = 1, acc = 0;
            for (int k = 0; k < NS; k++, tt += ds) { V3 q = cam.pos + d * tt; float rho = (0.5f + 0.9f * expf(-q.z / 1.8f)) * (0.75f + 0.5f * vnoise(q * 0.6f + V3(tsec * 0.12f, 0, tsec * 0.03f)));
                rho *= sstep(1.2f, 3.5f, tt) * sstep(-1.6f, 0.6f, q.y);   // у самой камеры лучей не рисуем — иначе широкая полоса
                float v = backVis(q, false); acc += v * rho * T * ds; T *= expf(-0.02f * rho * ds); }
            float c = dot(d, LBACK); float ph = (1 - g * g) / (12.566f * powf(1 + g * g - 2 * g * c, 1.5f));
            lo[(size_t)ly * LW + lx] = CBACK * (acc * ph * KSHAFT * 0.3f); } }
        for (int pass = 0; pass < 2; pass++) {   // мягко размыть (лучи — крупные)
            #pragma omp parallel for
            for (int y = 0; y < LH; y++) for (int x = 0; x < LW; x++) { V3 a(0, 0, 0); float w = 0; float d0 = ld[(size_t)y * LW + x];
                for (int k = -2; k <= 2; k++) { int xx = pass ? x : std::min(LW - 1, std::max(0, x + k)), yy = pass ? std::min(LH - 1, std::max(0, y + k)) : y; float dk = ld[(size_t)yy * LW + xx];
                    float ww = 1.f / (0.05f + fabsf(logf(dk / d0))); a += lo[(size_t)yy * LW + xx] * ww; w += ww; } lt[(size_t)y * LW + x] = a / w; }
            std::swap(lo, lt);
        }
        #pragma omp parallel for
        for (int y = 0; y < H; y++) for (int x = 0; x < W; x++) { float fx = (x + 0.5f) / 4 - 0.5f, fy = (y + 0.5f) / 4 - 0.5f; int x0 = std::max(0, std::min(LW - 2, (int)floorf(fx))), y0 = std::max(0, std::min(LH - 2, (int)floorf(fy)));
            float ax = clampf(fx - x0, 0, 1), ay = clampf(fy - y0, 0, 1); float d0 = dep[(size_t)y * W + x]; V3 a(0, 0, 0); float w = 0;
            for (int k = 0; k < 4; k++) { int xx = x0 + (k & 1), yy = y0 + (k >> 1); float bw = ((k & 1) ? ax : 1 - ax) * ((k >> 1) ? ay : 1 - ay); float dk = ld[(size_t)yy * LW + xx];
                float ww = bw / (0.03f + fabsf(logf(dk / d0))); a += lo[(size_t)yy * LW + xx] * ww; w += ww; }
            img[(size_t)y * W + x] += a / fmaxf(w, 1e-6f); }
    }
    std::vector<V3> br(img.size()), tmp(img.size());
    for (size_t i = 0; i < img.size(); i++) { V3 c = img[i]; float l = fmaxf(c.x, fmaxf(c.y, c.z)); br[i] = l > BTH ? c * ((l - BTH) / l) : V3(0, 0, 0); }
    int R = W / 40; std::vector<float> ker(2 * R + 1); float ks = 0; for (int k = -R; k <= R; k++) { ker[k + R] = expf(-k * k / (2.f * (R / 2.5f) * (R / 2.5f))); ks += ker[k + R]; } for (auto& k : ker) k /= ks;
    for (int pass = 0; pass < 2; pass++) {
        #pragma omp parallel for
        for (int y = 0; y < H; y++) for (int x = 0; x < W; x++) { V3 a(0, 0, 0); for (int k = -R; k <= R; k++) { int xx = pass ? x : std::min(W - 1, std::max(0, x + k)), yy = pass ? std::min(H - 1, std::max(0, y + k)) : y; a += br[(size_t)yy * W + xx] * ker[k + R]; } tmp[(size_t)y * W + x] = a; }
        std::swap(br, tmp);
    }
    float ex = powf(2.f, expo);
    std::vector<uint8_t> out((size_t)W * H * 3); Rng gr(99 + (uint64_t)(tsec * 1000));
    for (int y = 0; y < H; y++) for (int x = 0; x < W; x++) {
        size_t i = (size_t)y * W + x; V3 c = (img[i] + br[i] * BLOOM) * ex;
        V3 t = agx(c); float vx = (x - W * 0.5f) / W, vy = (y - H * 0.5f) / H; float vig = 1 - 0.18f * (vx * vx + vy * vy) * 2.2f; t = t * vig;
        float g = (gr.f() - 0.5f) * 0.012f;
        out[i * 3] = (uint8_t)(srgb(t.x + g) * 255 + 0.5f); out[i * 3 + 1] = (uint8_t)(srgb(t.y + g) * 255 + 0.5f); out[i * 3 + 2] = (uint8_t)(srgb(t.z + g) * 255 + 0.5f);
    }
    std::string tmpf = OUT + ".tmp"; FILE* f = fopen(tmpf.c_str(), "wb"); fprintf(f, "P6\n%d %d\n255\n", W, H); fwrite(out.data(), 1, out.size(), f); fclose(f); rename(tmpf.c_str(), OUT.c_str());
}
static void refitBVH() {
    #pragma omp parallel for schedule(dynamic, 4096)
    for (long i = 0; i < (long)nodes.size(); i++) { Node& n = nodes[i]; if (!n.cnt) continue; AABB b; for (int k = n.first; k < n.first + n.cnt; k++) b.grow(primBox(pidx[k]));
        for (int a = 0; a < 3; a++) { n.mn[a] = comp(b.mn, a); n.mx[a] = comp(b.mx, a); } }
    for (long i = (long)nodes.size() - 1; i >= 0; i--) { Node& n = nodes[i]; if (n.cnt) continue; const Node& a = nodes[n.first]; const Node& b = nodes[n.first + 1];
        for (int k = 0; k < 3; k++) { n.mn[k] = fminf(a.mn[k], b.mn[k]); n.mx[k] = fmaxf(a.mx[k], b.mx[k]); } }
}
// ---------------- сценарий ролика (10 с) ----------------
static float bump(float t, float a, float b) { return sstep(a, a + (b - a) * 0.35f, t) * sstep(b, a + (b - a) * 0.6f, t); }
static float blinkAt(float t) {   // 1 — открыт, 0 — закрыт
    float c = 0; auto bl = [&](float t0, float dur) { float u = (t - t0) / dur; if (u > 0 && u < 1) c = fmaxf(c, u < 0.4f ? sstep(0, 0.4f, u) : sstep(1, 0.55f, u)); };
    bl(2.35f, 0.26f); bl(5.0f, 0.24f); bl(5.36f, 0.24f);
    { float u = (t - 8.15f); if (u > 0 && u < 1.25f) c = fmaxf(c, u < 0.4f ? sstep(0, 0.4f, u) : u < 0.8f ? 1.f : sstep(1.25f, 0.8f, u)); }   // медленное «кошачье» моргание
    return 1 - c;
}
static V3 FLYK[] = {V3(-1.4f, -1.1f, 1.1f), V3(-0.8f, -0.9f, 0.92f), V3(-0.42f, -0.68f, 0.82f), V3(-0.26f, -0.6f, 0.76f), V3(-0.14f, -0.62f, 0.84f), V3(0.02f, -0.5f, 1.02f), V3(0.34f, -0.2f, 1.25f), V3(0.9f, 0.45f, 1.6f), V3(1.65f, 1.3f, 2.1f), V3(2.4f, 2.1f, 2.6f)};
static float FLYT[] = {0.f, 0.8f, 1.4f, 1.9f, 2.4f, 2.9f, 3.4f, 4.2f, 5.2f, 6.2f};
static V3 flyPath(float t) {
    int n = 10; if (t <= FLYT[0]) return FLYK[0]; if (t >= FLYT[n - 1]) return FLYK[n - 1];
    int i = 0; while (i < n - 2 && t > FLYT[i + 1]) i++; float u = (t - FLYT[i]) / (FLYT[i + 1] - FLYT[i]);
    V3 p0 = FLYK[std::max(0, i - 1)], p1 = FLYK[i], p2 = FLYK[i + 1], p3 = FLYK[std::min(n - 1, i + 2)];
    float u2 = u * u, u3 = u2 * u;
    V3 p = (p1 * 2.f + (p2 - p0) * u + (p0 * 2.f - p1 * 5.f + p2 * 4.f - p3) * u2 + (p1 * 3.f - p0 - p2 * 3.f + p3) * u3) * 0.5f;
    return p + V3(0.022f * sinf(t * 9.f), 0.016f * sinf(t * 7.f + 1.f), 0.026f * sinf(t * 11.f + 2.f) + 0.012f * sinf(t * 53.4f));   // порхает
}
static void scriptPose(float t) {
    Pose P;
    P.breath = 0.011f * sinf(6.2832f * t / 3.1f);
    P.tailA = 0.26f + 0.06f * sinf(t * 0.7f); P.tailPh = 6.2832f * t / 2.7f;
    // голова следит за бабочкой (с запозданием), потом поворачивается к камере
    V3 bd = flyPath(t - 0.22f) - V3(0, -0.01f, 0.76f); float yawB = atan2f(bd.x, -bd.y), pitchB = atan2f(-bd.z, sqrtf(bd.x * bd.x + bd.y * bd.y));
    float wF = (1 - sstep(3.0f, 4.0f, t)) * (0.55f + 0.45f * sstep(0.0f, 0.8f, t));
    float yaw = wF * clampf(0.6f * yawB, -0.5f, 0.5f) + (1 - wF) * (-0.04f * sstep(7.0f, 9.0f, t));
    float roll = 0.16f * sstep(4.3f, 5.3f, t) * (1 - 0.75f * sstep(7.2f, 8.6f, t));
    float pitch = wF * clampf(0.5f * pitchB, -0.3f, 0.2f) + (1 - wF) * (0.05f * bump(t, 6.3f, 7.4f) - 0.03f * sstep(8.0f, 9.0f, t)) + 0.015f * sinf(t * 1.3f);
    M3 Ry = rotAxis(V3(0, 0, 1), yaw), Rr = rotAxis(V3(0, -1, 0.15f), roll), Rp = rotAxis(V3(1, 0, 0), pitch);
    P.head = mmul(Ry, mmul(Rp, Rr));
    P.sway = mmul(rotAxis(V3(0, 1, 0), 0.012f * sinf(6.2832f * t / 5.3f)), rotAxis(V3(1, 0, 0), 0.006f * sinf(6.2832f * t / 4.1f + 1)));
    float tw1 = bump(t, 1.25f, 1.6f) + 0.6f * bump(t, 1.65f, 1.9f), tw0 = bump(t, 6.0f, 6.35f);
    P.ear[1] = mmul(rotAxis(V3(0, 1, 0), 0.42f * tw1), rotAxis(V3(1, 0, 0), -0.25f * tw1));
    P.ear[0] = mmul(rotAxis(V3(0, 1, 0), -0.38f * tw0), rotAxis(V3(1, 0, 0), -0.2f * tw0));
    float b = blinkAt(t); P.lid[0] = P.lid[1] = b;
    POSE = P;
}
struct CamKey { V3 pos, tgt; float lens, f; };
static void scriptCam(float t, V3& pos, V3& tgt, float& lens, float& fst) {
    float u = sstep(0.f, 10.f, t); u = u * u * (3 - 2 * u) * 0.5f + u * 0.5f;
    pos = lerp(V3(1.0f, -3.05f, 0.76f), V3(0.6f, -1.92f, 0.9f), u) + V3(0.03f * sinf(t * 0.6f), 0, 0.01f * sinf(t * 0.9f));
    tgt = lerp(V3(0.f, 0.f, 0.52f), V3(0.f, -0.04f, 0.745f), u); lens = 50 + 5 * u; fst = 3.2f - 1.0f * u;
}
static void placeLidFur(std::vector<V3>& DST) {
    for (const LidStr& ls : LIDS) {
        int e = ls.e; V3 a = LIDN0[e], E = EYE0[e]; float off = LID_CLOSED * RE + (LIDOFF - LID_CLOSED * RE) * POSE.lid[e];
        float thm = acosf(clampf(off / LID_R, -1, 1)), th = thm - ls.u; V3 rad = LB1[e] * cosf(ls.lam) + LB2[e] * sinf(ls.lam);
        if (th < LID_TH0 - 0.01f) { V3 hid = E + (a * cosf(LID_TH0 - 0.12f) + rad * sinf(LID_TH0 - 0.12f)) * (RE + 0.003f); for (int j = 0; j < 5; j++) DST[ls.base + j] = hid; continue; }
        V3 dir = a * cosf(th) + rad * sinf(th), m = a * -sinf(th) + rad * cosf(th); V3 root = E + dir * (LID_R - 0.0004f);
        for (int j = 0; j < 5; j++) { float tt = j / 4.f; V3 dj = nrm(m * cosf(ls.lift * (1 - tt)) + dir * sinf(ls.lift * (1 - tt))); DST[ls.base + j] = root + dj * (ls.L * tt) - dir * (0.0009f * tt * tt); }
        for (int j = 0; j < 5; j++) SB[ls.base + j] = cellLight(DST[ls.base + j] + dir * 0.002f);
    }
}
static void applyPose(float t) {
    scriptPose(t); placeLidFur(SV0);
    #pragma omp parallel for schedule(static)
    for (long i = 0; i < (long)HERO_END; i++) SV[i] = poseP(SV0[i], WH[i], WT[i], WE[i], WB[i]);
    #pragma omp parallel for schedule(static)
    for (long i = 0; i < (long)TV.size(); i++) { TV[i] = poseP(TV0[i], WH[i + HERO_END], WT[i + HERO_END], WE[i + HERO_END], WB[i + HERO_END]); TN[i] = poseN(TN0[i], WH[i + HERO_END]); }
    // трава на ветру
    #pragma omp parallel for schedule(static)
    for (long i = (long)HERO_END; i < (long)SV.size(); i++) { float tt = -ST[i] - 10.f; if (tt <= 0) { SV[i] = SV0[i]; continue; } V3 r = SV0[i - (int)roundf(tt * 3)];
        float w = 0.011f * (sinf(0.9f * r.x + 0.6f * r.y - 1.7f * t) + 0.5f * sinf(2.3f * r.x - 1.1f * r.y - 2.9f * t + 1.f)) + 0.006f * sinf(5.f * r.x + 3.f * r.y - 4.f * t);
        float gust = 0.6f + 0.4f * sinf(0.35f * r.x - 0.8f * t); SV[i] = SV0[i] + V3(0.8f, 0.6f, 0) * (w * gust * tt * tt) - V3(0, 0, 1) * (fabsf(w * gust) * tt * tt * 0.25f); }
    for (int e = 0; e < 2; e++) { EYE[e] = mul(POSE.sway, mul(POSE.head, EYE0[e] - PH) + PH); LIDN[e] = nrm(mul(POSE.sway, mul(POSE.head, LIDN0[e]))); }
    HEADF = nrm(mul(POSE.sway, mul(POSE.head, V3(0, -1, 0))));
    CATSH[0] = {mul(POSE.sway, mul(POSE.head, V3(0, -0.01f, 0.76f) - PH) + PH), V3(0.2f, 0.18f, 0.18f)}; CATSH[1] = {mul(POSE.sway, V3(0, 0, 0.36f)), V3(0.16f, 0.15f, 0.3f)};
    for (auto& m : motes) { m.p = m.p; }
    refitBVH();
}

int main(int argc, char** argv) {
    T0 = now(); std::map<std::string, std::string> A; for (int i = 1; i < argc; i++) { std::string s = argv[i]; auto e = s.find('='); if (e != std::string::npos) A[s.substr(0, e)] = s.substr(e + 1); }
    auto ga = [&](const char* k, const char* d) { return A.count(k) ? A[k] : std::string(d); };
    SHOT = ga("shot", "close"); int SPP = atoi(ga("spp", "16").c_str()); W = atoi(ga("w", "1280").c_str()); H = atoi(ga("h", "720").c_str());
    std::string OUT = ga("out", "out/frame.ppm"); KAREA = atof(ga("karea", "0.08").c_str()); FURK = atof(ga("furk", "0.32").c_str());
    float expo = atof(ga("expo", "0").c_str()); FURPOW = atof(ga("furpow", "0.55").c_str()); FURMUL = atof(ga("furmul", "0.95").c_str()); RIMP = atof(ga("rim", "140").c_str()); BLOOM = atof(ga("bloom", "0.35").c_str()); BTH = atof(ga("bth", "1.1").c_str()); GRASSK = atof(ga("grass", "1").c_str()); DBG = atoi(ga("dbg", "0").c_str()); FACEONLY = atoi(ga("faceonly", "0").c_str()); OLDBAKE = atoi(ga("oldbake", "0").c_str()); FARSIG = atof(ga("farsig", "0.06").c_str()); SIGBLUR = atoi(ga("sigblur", "1").c_str()); BKMODE = atoi(ga("bkmode", "0").c_str()); TAUK = atof(ga("tauk", "1").c_str()); KSHAFT = atof(ga("shaft", "2.5").c_str()); CANF = atof(ga("canf", "0.55").c_str()); CANT = atof(ga("cant", "0.6").c_str()); KDAPPLE = atof(ga("dapple", "1").c_str());
    ANIM = A.count("anim") > 0; int F0 = atoi(ga("from", "0").c_str()), F1 = atoi(ga("to", "240").c_str()), FPS = atoi(ga("fps", "24").c_str()); std::string DIR = ga("dir", "out/anim");
    loadGeo(ga("geo", "out/geo_base")); LOG("геометрия загружена");
    LAMP[1] = {V3(-0.7f, 1.1f, 1.35f), V3(1.0f, 0.9f, 0.75f), RIMP, V3(0, 0, 0)};
    LAMP[2] = {V3(-1.3f, -1.5f, 1.55f), V3(1.0f, 0.95f, 0.88f), 70.f, V3(0, 0, 0)};
    LAMP[3] = {V3(1.6f, -1.0f, 0.6f), V3(0.75f, 0.9f, 1.0f), 45.f, V3(0, 0, 0)};
    LAMP[1].aim = nrm(V3(0, 0, 0.72f) - LAMP[1].pos); LAMP[2].aim = nrm(V3(0, -0.05f, 0.7f) - LAMP[2].pos); LAMP[3].aim = nrm(V3(0, 0, 0.6f) - LAMP[3].pos);
    GNDL = V3(0.1f, 0.2f, 0.04f) * (CSUN.y * LSUN.z * 0.5f + 0.9f) / 3.14159f;
    buildScene(); buildCanopy(); CATSH[0] = {V3(0, -0.01f, 0.76f), V3(0.2f, 0.18f, 0.18f)}; CATSH[1] = {V3(0, 0, 0.36f), V3(0.16f, 0.15f, 0.3f)}; FLY.on = false; LOG("сцена собрана");
    for (int e = 0; e < 2; e++) { EYE0[e] = EYE[e]; LIDN0[e] = gv("lid_ns", e); LIDN[e] = LIDN0[e]; } LIDOFF = G["lid_off"].f[0]; HEADF = V3(0, -1, 0);
    POSE.lid[0] = POSE.lid[1] = ANIM ? 0.f : 1.f; placeLidFur(SV); POSE.lid[0] = POSE.lid[1] = 1.f;   // дерево строим, когда волоски век разложены по месту
    buildBVH(); LOG("BVH: %zu узлов", nodes.size());
    // запечённый свет: один раз, потом берётся из файла
    std::string bf = ga("bake", "out/bake_base.bin"); bool loaded = false;
    { FILE* f = fopen(bf.c_str(), "rb"); if (f) { size_t a, b; if (fread(&a, 8, 1, f) == 1 && fread(&b, 8, 1, f) == 1 && a == SV.size() && b == TV.size()) {
        buildLightCells(); size_t ok = fread(SB.data(), sizeof(SB[0]), a, f) + fread(TB.data(), sizeof(TB[0]), b, f); loaded = ok == a + b; } fclose(f); } }
    if (!loaded) { bakeAll(); FILE* f = fopen(bf.c_str(), "wb"); size_t a = SV.size(), b = TV.size(); fwrite(&a, 8, 1, f); fwrite(&b, 8, 1, f); fwrite(SB.data(), sizeof(SB[0]), a, f); fwrite(TB.data(), sizeof(TB[0]), b, f); fclose(f); }
    LOG("свет %s", loaded ? "взят из файла" : "запечён в каждый волосок и сохранён");
    if (A.count("nobake")) { for (size_t i = 0; i < SV.size(); i++) if (ST[i] > -5) SB[i] = {0.8f, 0.8f, 0.8f, 0.8f, 0.8f, 0.8f}; for (auto& b : TB) b = {0.8f, 0.8f, 0.8f, 0.8f, 0.8f, 0.8f}; }
    // цвет закрытого века — как шерсть над глазом
    { V3 acc(0, 0, 0); int n = 0; for (size_t i = 0; i < SV.size(); i++) if (ST[i] > 0.7f && ST[i] <= 1.f) { for (int e = 0; e < 2; e++) { V3 q = SV[i] - EYE[e]; if (len(q) < RE + 0.02f && q.z > 0.02f && q.y < 0) { acc += SA[i]; n++; } } } if (n) LIDCOL = acc / (float)n; LIDCOL = vpow(LIDCOL, 1.15f) * 0.92f; LOG("веко: %d волосков, цвет %.2f %.2f %.2f", n, LIDCOL.x, LIDCOL.y, LIDCOL.z);
      Rng lr(9); for (const LidStr& ls : LIDS) { float v = 0.85f + 0.3f * lr.f(); V3 c = ls.u < 0.07f ? lerp(V3(0.08f, 0.04f, 0.02f), LIDCOL * v, sstep(0.03f, 0.07f, ls.u)) : LIDCOL * v;
          for (int j = 0; j < 5; j++) { float tt = j / 4.f; SA[ls.base + j] = c * lerp(V3(1, 1, 1), V3(0.62f, 0.55f, 0.5f), (1 - tt) * (1 - tt)); } } }

    if (A.count("export")) {   // выгрузка для страницы на телефоне: волоски с готовым светом, кожа, веса костей
        FILE* f = fopen(A["export"].c_str(), "wb"); const auto& frg = G["fur_reg"].b; size_t ns = G["fur_pts"].shape[0]; int P = G["fur_pts"].shape[1];
        auto W4 = [&](V3 p, int reg, float* o) { float wh, ts, we, wb; weightsOf(p, reg, wh, ts, we, wb); o[0] = wh; o[1] = ts; o[2] = we; o[3] = wb; };
        std::vector<int> keep; Rng kr(4242); for (size_t s2 = 0; s2 < ns; s2++) { int rg = frg[s2]; float fr = rg == 12 ? 1.f : (rg == 1 || rg == 3 || rg == 4 || rg == 8) ? 0.55f : 0.30f; if (kr.f() < fr) keep.push_back((int)s2); }
        uint32_t n = keep.size(); fwrite(&n, 4, 1, f);
        for (int s2 : keep) { float buf[5 * 3 + 5 * 6 + 3 + 1 + 4 + 1]; int k = 0; size_t b = (size_t)s2 * P;
            for (int j = 0; j < 5; j++) { buf[k++] = SV[b + j].x; buf[k++] = SV[b + j].y; buf[k++] = SV[b + j].z; }
            for (int j = 0; j < 5; j++) for (int c = 0; c < 6; c++) buf[k++] = SB[b + j][c];
            V3 al = SA[b + 4]; buf[k++] = al.x; buf[k++] = al.y; buf[k++] = al.z; buf[k++] = G["fur_rad"].f[s2];
            W4(SV[b], frg[s2], buf + k); k += 4; buf[k++] = frg[s2]; fwrite(buf, 4, k, f); }
        // усы и рот
        uint32_t nl = 0; std::vector<float> L; for (int which = 0; which < 2; which++) { const char* key = which ? "mouth" : "whisk"; int cnt = G[key].shape[0], np = G[key].shape[1];
            for (int i = 0; i < cnt; i++) { nl++; L.push_back(np); L.push_back(which); for (int j = 0; j < np; j++) { V3 p = gv(key, i * np + j); L.push_back(p.x); L.push_back(p.y); L.push_back(p.z); float w[4]; W4(p, 1, w); L.push_back(w[0]); } } }
        fwrite(&nl, 4, 1, f); uint32_t ln = L.size(); fwrite(&ln, 4, 1, f); fwrite(L.data(), 4, ln, f);
        // кожа, нос, шарф
        uint32_t nv = TV.size(), nt = tris.size(); fwrite(&nv, 4, 1, f); fwrite(&nt, 4, 1, f);
        for (uint32_t i = 0; i < nv; i++) { float buf[3 + 3 + 3 + 6 + 4 + 1]; int k = 0; buf[k++] = TV[i].x; buf[k++] = TV[i].y; buf[k++] = TV[i].z; buf[k++] = TN[i].x; buf[k++] = TN[i].y; buf[k++] = TN[i].z;
            buf[k++] = TA[i].x; buf[k++] = TA[i].y; buf[k++] = TA[i].z; for (int c = 0; c < 6; c++) buf[k++] = TB[i][c];
            int reg = TR[i] >= 20 ? (TR[i] == 20 + M_NOSE ? 2 : 0) : TR[i]; W4(TV[i], reg, buf + k); k += 4; buf[k++] = TR[i]; fwrite(buf, 4, k, f); }
        for (uint32_t i = 0; i < nt; i++) { int32_t b4[4] = {tris[i].a, tris[i].b, tris[i].c, tris[i].mat}; fwrite(b4, 4, 4, f); }
        float e[16] = {EYE0[0].x, EYE0[0].y, EYE0[0].z, EYE0[1].x, EYE0[1].y, EYE0[1].z, LIDN0[0].x, LIDN0[0].y, LIDN0[0].z, LIDN0[1].x, LIDN0[1].y, LIDN0[1].z, LIDOFF, RE, LIDCOL.x, LIDCOL.y}; fwrite(e, 4, 16, f); fwrite(&LIDCOL.z, 4, 1, f);
        fclose(f); LOG("выгружено: %u волосков, %u линий, кожа %u вершин", n, nl, nv); return 0;
    }
    if (!ANIM) {
        V3 tgtEye;
        if (SHOT == "close") { lookAt(V3(0.62f, -1.95f, 0.9f), V3(0.f, -0.04f, 0.74f), 55, 2.2f, len(V3(0.62f, -1.95f, 0.9f) - EYE[1])); tgtEye = V3(0.36f, -1.6f, 0.84f); hasEyeL = true; EYEL = {V3(0.2f, -1.4f, 1.05f), V3(1, 0.97f, 0.93f), 6.f, V3()}; }
        else if (SHOT == "medium") { lookAt(V3(0.62f, -2.4f, 0.82f), V3(0.f, -0.03f, 0.6f), 55, 3.2f, len(V3(0.62f, -2.4f, 0.82f) - V3(0, -0.1f, 0.6f))); tgtEye = V3(0.45f, -2.3f, 0.8f); hasEyeL = true; EYEL = {V3(0.25f, -2.0f, 1.05f), V3(1, 0.97f, 0.93f), 8.f, V3()}; }
        else { lookAt(V3(0.9f, -2.9f, 0.75f), V3(0.f, 0.f, 0.5f), 50, 3.2f, len(V3(0.9f, -2.9f, 0.75f) - V3(0, -0.1f, 0.6f))); tgtEye = V3(0.5f, -2.8f, 0.75f); }
        for (int i = 0; i < 2; i++) EYEF[i] = nrm(tgtEye - EYE[i]);
        if (hasEyeL) { EYEL.col = EYEL.col * (EYEL.P * KAREA / fmaxf(0.1f, dot(EYEL.pos - EYE[1], EYEL.pos - EYE[1]))); }
        renderFrame(SPP, OUT, expo, 0); LOG("готово: %s", OUT.c_str()); return 0;
    }
    // ---- ролик ----
    SV0 = SV; TV0 = TV; TN0 = TN; HERO_END = 0; for (size_t i = 0; i < SV.size(); i++) if (ST[i] > -5) HERO_END = i + 1;
    WH.assign(HERO_END + TV.size(), 0); WT.assign(WH.size(), -1); WE.assign(WH.size(), 0); WB.assign(WH.size(), 0);
    { const auto& frg = G["fur_reg"].b; size_t ns = G["fur_pts"].shape[0]; int P = G["fur_pts"].shape[1];
      for (size_t s = 0; s < ns; s++) { float wh, ts, we, wb; weightsOf(SV0[s * P], frg[s], wh, ts, we, wb); for (int k = 0; k < P; k++) { size_t i = s * P + k; WH[i] = wh; WT[i] = ts; WE[i] = we; WB[i] = wb; } }
      for (size_t i = ns * P; i < HERO_END; i++) { float wh, ts, we, wb; weightsOf(SV0[i], 1, wh, ts, we, wb); WH[i] = wh; WT[i] = -1; WE[i] = 0; WB[i] = 0; }   // усы и рот — с головой
      for (size_t i = 0; i < TV.size(); i++) { int reg = TR[i] >= 20 ? (TR[i] == 20 + M_NOSE ? 2 : 0) : TR[i]; float wh, ts, we, wb; weightsOf(TV0[i], reg, wh, ts, we, wb); WH[HERO_END + i] = wh; WT[HERO_END + i] = ts; WE[HERO_END + i] = we; WB[HERO_END + i] = wb; } }
    Rng mr(5); for (int i = 0; i < 150; i++) { Mote m; m.p = V3(-1.6f + 3.2f * mr.f(), -1.4f + 4.f * mr.f(), 0.15f + 1.5f * mr.f()); m.v = V3(mr.f() - 0.5f, mr.f() - 0.5f, mr.f() - 0.4f) * 0.03f; m.ph = mr.f() * 6.28f; m.br = 0.25f + 0.75f * mr.f() * mr.f(); motes.push_back(m); }
    std::vector<Mote> m0 = motes;
    for (int fr = F0; fr < F1; fr++) {
        char nm[256]; snprintf(nm, sizeof nm, "%s/f_%04d.ppm", DIR.c_str(), fr); FILE* ex = fopen(nm, "rb"); if (ex) { fclose(ex); continue; }
        float t = fr / (float)FPS; double tf = now();
        for (size_t i = 0; i < motes.size(); i++) { const Mote& a = m0[i]; motes[i].p = a.p + a.v * t + V3(0.04f * sinf(t * 0.7f + a.ph), 0.03f * sinf(t * 0.5f + a.ph * 2), 0.05f * sinf(t * 0.6f + a.ph * 3)); }
        applyPose(t);
        V3 cp, ct; float ln, fs; scriptCam(t, cp, ct, ln, fs);
        { FLY.on = t < 5.8f; FLY.pos = flyPath(t); V3 v = flyPath(t + 0.04f) - flyPath(t - 0.04f); v.z *= 0.3f; FLY.f = nrm(len(v) > 1e-4f ? v : V3(1, 0, 0));
          V3 tc = nrm(cp - FLY.pos); V3 u0 = nrm(V3(0, 0, 1) * 0.55f + tc * 0.85f); FLY.u = nrm(u0 - FLY.f * dot(u0, FLY.f)); FLY.r = cross(FLY.f, FLY.u); FLY.flap = 0.15f + 1.05f * (0.5f + 0.5f * sinf(6.2832f * 8.5f * t)); }
        V3 gz = lerp(FLY.pos, cp, sstep(3.0f, 3.7f, t)) + V3(0.02f * sinf(t * 3.1f), 0, 0.015f * sinf(t * 2.3f)) * sstep(3.7f, 4.2f, t);
        for (int i = 0; i < 2; i++) EYEF[i] = nrm(gz - EYE[i]);
        lookAt(cp, ct, ln, fs, len(cp - EYE[1]) * 0.995f);
        hasEyeL = true; EYEL = {cp + cam.up * 0.35f - cam.rt * 0.25f + cam.fw * 0.4f, V3(1, 0.97f, 0.93f), 6.f, V3()}; EYEL.col = EYEL.col * (EYEL.P * KAREA / fmaxf(0.1f, dot(EYEL.pos - EYE[1], EYEL.pos - EYE[1])) * sstep(1.f, 6.f, t));
        if (DBG == 9) { for (int px : {5, 20, 40, 60, 80}) { float sx = ((px + 0.5f) / W * 2 - 1) * cam.tanh, sy = (1 - (180 + 0.5f) / H * 2) * cam.tanh / ((float)W / H); V3 d = nrm(cam.fw + cam.rt * sx + cam.up * sy); float dist; V3 c = shade(cam.pos, d, dist);
            fprintf(stderr, "px %d: вид %d (%d) расст %.2f цвет %.2f %.2f %.2f\n", px, LASTK, LASTA, dist, c.x, c.y, c.z); } continue; }
        renderFrame(SPP, nm, expo, t);
        LOG("кадр %d/%d за %.1f с", fr + 1, F1, now() - tf);
    }
    LOG("ролик готов");
}
