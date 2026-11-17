// Шарики размножаются при отскоке от стенок силуэта кота.
// sim out.bin events.txt seed P VMIN KICK R
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>

#define MAXN 6000
#define W 1080
#define H 1920
static float X[MAXN], Y[MAXN], PX[MAXN], PY[MAXN];
static int N = 0;
static double R;

static const double CX = 540.0, CY = 1060.0;

static double sd_circle(double x, double y, double cx, double cy, double r) { return hypot(x - cx, y - cy) - r; }
static double clampd(double v, double a, double b) { return v < a ? a : (v > b ? b : v); }
static double sgn(double v) { return (v > 0) - (v < 0); }
static double sd_tri(double x, double y, double ax, double ay, double bx, double by, double cx, double cy) {
    double e0x = bx - ax, e0y = by - ay, e1x = cx - bx, e1y = cy - by, e2x = ax - cx, e2y = ay - cy;
    double v0x = x - ax, v0y = y - ay, v1x = x - bx, v1y = y - by, v2x = x - cx, v2y = y - cy;
    double t0 = clampd((v0x * e0x + v0y * e0y) / (e0x * e0x + e0y * e0y), 0, 1);
    double t1 = clampd((v1x * e1x + v1y * e1y) / (e1x * e1x + e1y * e1y), 0, 1);
    double t2 = clampd((v2x * e2x + v2y * e2y) / (e2x * e2x + e2y * e2y), 0, 1);
    double q0x = v0x - e0x * t0, q0y = v0y - e0y * t0, q1x = v1x - e1x * t1, q1y = v1y - e1y * t1, q2x = v2x - e2x * t2, q2y = v2y - e2y * t2;
    double s = sgn(e0x * e2y - e0y * e2x);
    double d0 = q0x * q0x + q0y * q0y, c0 = s * (v0x * e0y - v0y * e0x);
    double d1 = q1x * q1x + q1y * q1y, c1 = s * (v1x * e1y - v1y * e1x);
    double d2 = q2x * q2x + q2y * q2y, c2 = s * (v2x * e2y - v2y * e2x);
    double d = fmin(fmin(d0, d1), d2), c = fmin(fmin(c0, c1), c2);
    return -sqrt(d) * sgn(c);
}
static double smin(double a, double b, double k) { double h = fmax(k - fabs(a - b), 0) / k; return fmin(a, b) - h * h * k * 0.25; }
static double sdf(double x, double y) {  // медведь
    double d = smin(sd_circle(x, y, CX, CY, 380), sd_circle(x, y, CX, CY + 90, 340), 80);
    d = smin(d, sd_circle(x, y, CX - 285, CY - 290, 118), 60);
    d = smin(d, sd_circle(x, y, CX + 285, CY - 290, 118), 60);
    return d;
}
static double NOTES[512]; static int NN = 0;
static int near_note(double t) {  // шарики рождаются только сразу после ноты
    for (int i = 0; i < NN; i++) if (t >= NOTES[i] && t < NOTES[i] + 0.06) return 1;
    return 0;
}

// сетка
#define CS 20
#define GW (W / CS + 2)
#define GH (H / CS + 2)
static int head[GW * GH], nxt[MAXN];
static void build_grid(void) {
    for (int i = 0; i < GW * GH; i++) head[i] = -1;
    for (int i = 0; i < N; i++) {
        int gx = (int)(X[i] / CS) + 1, gy = (int)(Y[i] / CS) + 1;
        if (gx < 0) gx = 0; if (gx >= GW) gx = GW - 1; if (gy < 0) gy = 0; if (gy >= GH) gy = GH - 1;
        int c = gy * GW + gx; nxt[i] = head[c]; head[c] = i;
    }
}
static int is_free(double x, double y, double minD) {
    int gx = (int)(x / CS) + 1, gy = (int)(y / CS) + 1;
    for (int dy = -2; dy <= 2; dy++) for (int dx = -2; dx <= 2; dx++) {
        int cx = gx + dx, cy = gy + dy;
        if (cx < 0 || cy < 0 || cx >= GW || cy >= GH) continue;
        for (int j = head[cy * GW + cx]; j >= 0; j = nxt[j]) {
            double ddx = X[j] - x, ddy = Y[j] - y;
            if (ddx * ddx + ddy * ddy < minD * minD) return 0;
        }
    }
    return 1;
}
static double rnd(void) { return rand() / (RAND_MAX + 1.0); }


static float VX[MAXN], VY[MAXN];
int main(int argc, char **argv) {
    const char *out = argv[1], *evp = argv[2];
    int seed = atoi(argv[3]);
    double P = atof(argv[4]), SPEED = atof(argv[5]), G = atof(argv[6]);
    R = atof(argv[7]);
    double MAXT = argc > 8 ? atof(argv[8]) : 40;
    int NT = argc > 9 ? atoi(argv[9]) : MAXN;
    double T97 = argc > 10 ? atof(argv[10]) : 10.5, TL = argc > 11 ? atof(argv[11]) : 2.0, TS = argc > 12 ? atof(argv[12]) : 0.0;
    int N0 = argc > 13 ? atoi(argv[13]) : 1;
    if (argc > 14) { FILE *fn = fopen(argv[14], "r"); while (NN < 512 && fscanf(fn, "%lf", &NOTES[NN]) == 1) NN++; fclose(fn); }
    double KL = log((1.0 / 0.97 - 1.0) > 0 ? (NT - 1) / (1.0 / 0.97 - 1.0) : 1) / T97;
    srand(seed);
    const int FPS = 60, SUB = 10;
    const double dt = 1.0 / FPS / SUB;
    FILE *fo = fopen(out, "wb"), *fe = fopen(evp, "w");
    X[0] = CX - 40 + 80 * rnd(); Y[0] = CY - 120 + 60 * rnd(); N = 1;
    double a0 = (rnd() < 0.5 ? -1 : 1) * (0.6 + 0.5 * rnd()) - 1.5708;
    VX[0] = cos(a0) * SPEED; VY[0] = sin(a0) * SPEED;
    while (N < N0) {  // старт «уже в деле»: N0 шариков в случайных местах
        double x = 140 + 800 * rnd(), y = 640 + 860 * rnd();
        if (sdf(x, y) > -R * 1.2) continue;
        int ok = 1;
        for (int q = 0; q < N; q++) if (hypot(X[q] - x, Y[q] - y) < 2.2 * R) { ok = 0; break; }
        if (!ok) continue;
        double an = rnd() * 6.2832;
        X[N] = x; Y[N] = y; VX[N] = cos(an) * SPEED; VY[N] = sin(an) * SPEED; N++;
    }
    fprintf(fe, "I %d\n", N0);
    double t = 0, last_spawn = 0; int settle = 0, frame, hits = 0;
    for (frame = 0; frame < MAXT * FPS; frame++) {
        for (int s = 0; s < SUB; s++) {
            t += dt;
            for (int i = 0; i < N; i++) {
                if (settle) { VX[i] *= 0.985; VY[i] *= 0.985; }
                VY[i] += G * dt;
                X[i] += VX[i] * dt; Y[i] += VY[i] * dt;
            }
            for (int it = 0; it < 2; it++) {
                build_grid();
                for (int i = 0; i < N; i++) {
                    int gx = (int)(X[i] / CS) + 1, gy = (int)(Y[i] / CS) + 1;
                    for (int dy = -1; dy <= 1; dy++) for (int dx = -1; dx <= 1; dx++) {
                        int cx = gx + dx, cy = gy + dy;
                        if (cx < 0 || cy < 0 || cx >= GW || cy >= GH) continue;
                        for (int j = head[cy * GW + cx]; j >= 0; j = nxt[j]) {
                            if (j <= i) continue;
                            double ddx = X[j] - X[i], ddy = Y[j] - Y[i], d2 = ddx * ddx + ddy * ddy, m = 2 * R;
                            if (d2 < m * m && d2 > 1e-9) {
                                double d = sqrt(d2), nx = ddx / d, ny = ddy / d, k = (m - d) * 0.5;
                                X[i] -= nx * k; Y[i] -= ny * k; X[j] += nx * k; Y[j] += ny * k;
                                double vr = (VX[j] - VX[i]) * nx + (VY[j] - VY[i]) * ny;
                                if (vr < 0 && it == 0) {  // упругий удар равных масс
                                    VX[i] += vr * nx; VY[i] += vr * ny; VX[j] -= vr * nx; VY[j] -= vr * ny;
                                }
                            }
                        }
                    }
                }
            }
            build_grid();
            int n0 = N;
            for (int i = 0; i < n0; i++) {
                double d = sdf(X[i], Y[i]);
                if (d <= -R) continue;
                double gx = (sdf(X[i] + 0.5, Y[i]) - sdf(X[i] - 0.5, Y[i])), gy = (sdf(X[i], Y[i] + 0.5) - sdf(X[i], Y[i] - 0.5));
                double gl = hypot(gx, gy); if (gl < 1e-9) continue;
                double nx = gx / gl, ny = gy / gl, pen = d + R;
                X[i] -= nx * pen; Y[i] -= ny * pen;
                double vn = VX[i] * nx + VY[i] * ny;
                if (vn <= 0) continue;
                VX[i] -= 2 * vn * nx; VY[i] -= 2 * vn * ny;
                if (settle) { VX[i] *= 0.5; VY[i] *= 0.5; continue; }
                if (vn < 120) continue;
                hits++;
                fprintf(fe, "H %.4f %d %.1f %.1f %.0f\n", t, i, X[i], Y[i], vn);
                double tt = t + TS, L = NT / (1.0 + (NT - 1) * exp(-KL * tt)), budget;
                if (tt < T97) budget = L; else budget = 0.97 * NT + (tt - T97) / TL * 0.03 * NT;
                double pp = (N <= 4 && N0 <= 1) ? 1.0 : (N < budget ? P : 0.0);
                if (NN && !near_note(t)) pp = 0.0;
                if (N < NT && rnd() < pp) {
                    int placed = 0;
                    for (int tr = 0; tr < 10; tr++) {
                        double off = 2.05 * R + tr * 0.35 * R;
                        double lat = (rnd() - 0.5) * (1.0 + 0.3 * tr) * R;
                        double sx = X[i] - nx * off - ny * lat, sy = Y[i] - ny * off + nx * lat;
                        if (sdf(sx, sy) > -R * 1.02) continue;
                        if (!is_free(sx, sy, 2.0 * R)) continue;
                        int ok = 1;
                        for (int q = n0; q < N; q++) if (hypot(X[q] - sx, Y[q] - sy) < 2 * R) ok = 0;
                        if (!ok) continue;
                        double ang = (rnd() < 0.5 ? -1 : 1) * (0.3 + 0.7 * rnd());
                        double c = cos(ang), sn = sin(ang);
                        double sp = hypot(VX[i], VY[i]); if (sp < 1) sp = 1;
                        double k = SPEED / sp;
                        X[N] = sx; Y[N] = sy; VX[N] = (VX[i] * c - VY[i] * sn) * k; VY[N] = (VX[i] * sn + VY[i] * c) * k;
                        fprintf(fe, "S %.4f %d %d\n", t, N, i);
                        N++; last_spawn = t; placed = 1;
                        break;
                    }
                    if (!placed && N > 600) {  // места нет — рождается внахлёст и расталкивает соседей
                        double sx = X[i] - nx * 1.2 * R, sy = Y[i] - ny * 1.2 * R;
                        double ang = (rnd() < 0.5 ? -1 : 1) * (0.3 + 0.7 * rnd());
                        double c = cos(ang), sn = sin(ang);
                        double sp = hypot(VX[i], VY[i]); if (sp < 1) sp = 1;
                        double k = SPEED / sp;
                        X[N] = sx; Y[N] = sy; VX[N] = (VX[i] * c - VY[i] * sn) * k; VY[N] = (VX[i] * sn + VY[i] * c) * k;
                        fprintf(fe, "S %.4f %d %d\n", t, N, i);
                        N++; last_spawn = t;
                    }
                }
            }
        }
        if (!settle && N > 300 && (N >= NT || t - last_spawn > 1.0)) { settle = 1; fprintf(fe, "F %.4f %d\n", last_spawn, N); }
        if (frame % 2 == 0) {
            fwrite(&N, 4, 1, fo);
            for (int i = 0; i < N; i++) { float v[2] = {X[i], Y[i]}; fwrite(v, 4, 2, fo); }
        }
        if (settle && t - last_spawn > 3.0) break;
    }
    fprintf(fe, "E %.4f %d\n", t, N);
    fclose(fo); fclose(fe);
    fprintf(stderr, "N=%d full=%.2f end=%.2f hits=%d\n", N, last_spawn, t, hits);
    return 0;
}
