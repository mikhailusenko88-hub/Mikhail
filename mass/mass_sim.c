/* mass_sim.c — физика «1000 шарик» для «Білесің бе?» (15.11.2026).
   Вход (stdin, текст): N R G HZ FPS T  / шары x y / штырьки: P, затем px py pr / отрезки: S, затем x1 y1 x2 y2
   / вертушки: K, затем cx cy len w ang0 / кубок: cx0 cx1 cy0 cy1 (прямоугольник «внутри»)
   Выход (stdout, бинарно): на каждый кадр N×2 float32 (x,y; ушедшие за экран = -1000) + uint16 ударов о штырьки. */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include <stdint.h>

typedef struct { float x1, y1, x2, y2; } Seg;
typedef struct { float cx, cy, len, w, a; } Spin;

static int N, P, S, K; static float R, G; static int HZ, FPS; static float T;
static float *x, *y, *vx, *vy; static unsigned char *alive;
static float *px, *py, *pr; static Seg *sg; static Spin *sp;
static float cup[4];

static void seg_collide(int i, float ax, float ay, float bx, float by, float svx, float svy, float e, float mu, int *hits) {
  float dx = bx - ax, dy = by - ay, L2 = dx * dx + dy * dy;
  float t = L2 > 0 ? ((x[i] - ax) * dx + (y[i] - ay) * dy) / L2 : 0; if (t < 0) t = 0; if (t > 1) t = 1;
  float qx = ax + t * dx, qy = ay + t * dy, ox = x[i] - qx, oy = y[i] - qy, d2 = ox * ox + oy * oy;
  if (d2 >= R * R) return;
  float d = sqrtf(d2); float nx, ny;
  if (d < 1e-4f) { nx = -dy; ny = dx; float l = sqrtf(nx * nx + ny * ny) + 1e-9f; nx /= l; ny /= l; d = 0; } else { nx = ox / d; ny = oy / d; }
  x[i] += nx * (R - d); y[i] += ny * (R - d);
  float rvx = vx[i] - svx, rvy = vy[i] - svy, vn = rvx * nx + rvy * ny;
  if (vn < 0) {
    float tx = -ny, ty = nx, vt = rvx * tx + rvy * ty;
    rvx -= (1 + e) * vn * nx; rvy -= (1 + e) * vn * ny;
    rvx -= mu * vt * tx; rvy -= mu * vt * ty;
    vx[i] = rvx + svx; vy[i] = rvy + svy;
    if (hits && vn < -120) (*hits)++;
  }
}

int main(void) {
  if (scanf("%d %f %f %d %d %f", &N, &R, &G, &HZ, &FPS, &T) != 6) return 1;
  x = malloc(N * 4); y = malloc(N * 4); vx = calloc(N, 4); vy = calloc(N, 4); alive = malloc(N);
  for (int i = 0; i < N; i++) { if (scanf("%f %f", &x[i], &y[i]) != 2) return 2; alive[i] = 1; }
  if (scanf("%d", &P) != 1) return 3; px = malloc(P * 4 + 4); py = malloc(P * 4 + 4); pr = malloc(P * 4 + 4);
  for (int i = 0; i < P; i++) if (scanf("%f %f %f", &px[i], &py[i], &pr[i]) != 3) return 4;
  if (scanf("%d", &S) != 1) return 5; sg = malloc(sizeof(Seg) * (S + 1));
  for (int i = 0; i < S; i++) if (scanf("%f %f %f %f", &sg[i].x1, &sg[i].y1, &sg[i].x2, &sg[i].y2) != 4) return 6;
  if (scanf("%d", &K) != 1) return 7; sp = malloc(sizeof(Spin) * (K + 1));
  for (int i = 0; i < K; i++) if (scanf("%f %f %f %f %f", &sp[i].cx, &sp[i].cy, &sp[i].len, &sp[i].w, &sp[i].a) != 5) return 8;
  if (scanf("%f %f %f %f", &cup[0], &cup[1], &cup[2], &cup[3]) != 4) return 9;

  const float W = 1080, H = 1920, cs = 2 * R; const int gw = (int)(W / cs) + 3, gh = (int)((H + 400) / cs) + 3;
  int *head = malloc(sizeof(int) * gw * gh), *next = malloc(sizeof(int) * N);
  float dt = 1.0f / HZ; int sub = HZ / FPS, frames = (int)(T * FPS);
  float *out = malloc(sizeof(float) * N * 2);
  for (int f = 0; f < frames; f++) {
    int hits = 0;
    for (int s = 0; s < sub; s++) {
      for (int k = 0; k < K; k++) sp[k].a += sp[k].w * dt;
      for (int i = 0; i < N; i++) if (alive[i]) {
        vy[i] += G * dt; vx[i] *= 0.9995f; vy[i] *= 0.9995f;
        float sp2 = vx[i] * vx[i] + vy[i] * vy[i]; if (sp2 > 2200 * 2200) { float k = 2200 / sqrtf(sp2); vx[i] *= k; vy[i] *= k; }
        x[i] += vx[i] * dt; y[i] += vy[i] * dt;
        if (y[i] > H + 60 || x[i] < -60 || x[i] > W + 60) { alive[i] = 0; x[i] = -1000; y[i] = -1000; }
      }
      for (int it = 0; it < 2; it++) {
        for (int c = 0; c < gw * gh; c++) head[c] = -1;
        for (int i = 0; i < N; i++) if (alive[i]) {
          int cx = (int)(x[i] / cs) + 1, cy = (int)((y[i] + 200) / cs) + 1;
          if (cx < 0) cx = 0; if (cx >= gw) cx = gw - 1; if (cy < 0) cy = 0; if (cy >= gh) cy = gh - 1;
          next[i] = head[cy * gw + cx]; head[cy * gw + cx] = i;
        }
        for (int i = 0; i < N; i++) if (alive[i]) {
          int cx = (int)(x[i] / cs) + 1, cy = (int)((y[i] + 200) / cs) + 1;
          for (int oy = -1; oy <= 1; oy++) for (int ox = -1; ox <= 1; ox++) {
            int nx_ = cx + ox, ny_ = cy + oy; if (nx_ < 0 || ny_ < 0 || nx_ >= gw || ny_ >= gh) continue;
            for (int j = head[ny_ * gw + nx_]; j >= 0; j = next[j]) {
              if (j <= i) continue;
              float dx = x[j] - x[i], dy = y[j] - y[i], d2 = dx * dx + dy * dy;
              if (d2 >= 4 * R * R || d2 < 1e-8f) continue;
              float d = sqrtf(d2), nx = dx / d, ny = dy / d, ov = (2 * R - d) * 0.5f;
              x[i] -= nx * ov; y[i] -= ny * ov; x[j] += nx * ov; y[j] += ny * ov;
              float vn = (vx[j] - vx[i]) * nx + (vy[j] - vy[i]) * ny;
              if (vn < 0) { float jn = -(1 + 0.25f) * vn * 0.5f; vx[i] -= jn * nx; vy[i] -= jn * ny; vx[j] += jn * nx; vy[j] += jn * ny; }
            }
          }
        }
        for (int i = 0; i < N; i++) if (alive[i]) {
          for (int p = 0; p < P; p++) {
            float dx = x[i] - px[p], dy = y[i] - py[p], rr = R + pr[p], d2 = dx * dx + dy * dy;
            if (d2 >= rr * rr || d2 < 1e-8f) continue;
            float d = sqrtf(d2), nx = dx / d, ny = dy / d; x[i] += nx * (rr - d); y[i] += ny * (rr - d);
            float vn = vx[i] * nx + vy[i] * ny;
            if (vn < 0) { vx[i] -= 1.45f * vn * nx; vy[i] -= 1.45f * vn * ny; if (vn < -150) hits++; }
          }
          for (int k = 0; k < S; k++) seg_collide(i, sg[k].x1, sg[k].y1, sg[k].x2, sg[k].y2, 0, 0, 0.3f, 0.02f, &hits);
          for (int k = 0; k < K; k++) {
            float c = cosf(sp[k].a), sn = sinf(sp[k].a), h = sp[k].len / 2;
            float ax = sp[k].cx - c * h, ay = sp[k].cy - sn * h, bx = sp[k].cx + c * h, by = sp[k].cy + sn * h;
            float qx = x[i] - sp[k].cx, qy = y[i] - sp[k].cy; /* скорость точки вертушки рядом с шаром */
            seg_collide(i, ax, ay, bx, by, -sp[k].w * qy, sp[k].w * qx, 0.4f, 0.05f, &hits);
          }
        }
      }
    }
    for (int i = 0; i < N; i++) { out[2 * i] = alive[i] ? x[i] : -1000; out[2 * i + 1] = alive[i] ? y[i] : -1000; }
    fwrite(out, sizeof(float), N * 2, stdout);
    uint16_t h16 = hits > 65535 ? 65535 : hits; fwrite(&h16, 2, 1, stdout);
  }
  return 0;
}
