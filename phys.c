// phys.c — 2D физика гонки шариков: шарики + капсулы-отрезки на телах (статика, вращение, качание, сдвиг).
// Сборка: gcc -O2 -o phys phys.c -lm      Запуск: ./phys input.txt
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAXB 64
#define MAXBODY 512
#define MAXSEG 20000
#define CELL 80.0

typedef struct { double x, y, vx, vy, rot, best_y, t_best; int state, kicks; double fin_t; } Ball;
typedef struct {
    double px, py, a0, w, amp, k, P, ph, bias, ox, oy, k2, P2, ph2, ton, toff;
    int hp, dynamic, alive; double brad, break_t;
} Body;
typedef struct { int body; double ax, ay, bx, by, rad, e, mu; int kind; } Seg;

static Ball B[MAXB]; static int NB; static double R;
static Body BD[MAXBODY]; static int NBD;
static Seg S[MAXSEG]; static int NS;
static double G = 1200, FIN_Y, TMAX, AFTER; static int QUAL;
static FILE *EV;
static double LASTHIT[MAXB][MAXBODY];
static double gx0, gy0; static int gw, gh; static int *gcnt, **glist;
static unsigned long long rng = 88172645463325252ULL;
static double frand(void) { rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17; return (rng >> 11) * (1.0 / 9007199254740992.0); }

static double sq(double k, double s) { if (k <= 0) return s; s *= k; return s > 1 ? 1 : (s < -1 ? -1 : s); }
static void xform(Body *b, double t, double *c, double *s, double *ox, double *oy) {
    double th = b->a0 + b->w * t;
    if (b->P > 0) th += b->amp * sq(b->k, sin(2 * M_PI * t / b->P + b->ph) - b->bias);
    double o = (b->P2 > 0) ? sq(b->k2, sin(2 * M_PI * t / b->P2 + b->ph2)) : 0;
    *c = cos(th); *s = sin(th); *ox = b->px + b->ox * o; *oy = b->py + b->oy * o;
}
static void segw(Seg *g, double c, double s, double ox, double oy, double *ax, double *ay, double *bx, double *by) {
    *ax = ox + c * g->ax - s * g->ay; *ay = oy + s * g->ax + c * g->ay;
    *bx = ox + c * g->bx - s * g->by; *by = oy + s * g->bx + c * g->by;
}

static void collide_seg(Ball *p, int bi, Seg *g, double t, double dt, double c, double s, double ox, double oy,
                        double c0, double s0, double ox0, double oy0) {
    double ax, ay, bx, by; segw(g, c, s, ox, oy, &ax, &ay, &bx, &by);
    double ex = bx - ax, ey = by - ay, L2 = ex * ex + ey * ey;
    double u = L2 > 0 ? ((p->x - ax) * ex + (p->y - ay) * ey) / L2 : 0; if (u < 0) u = 0; if (u > 1) u = 1;
    double qx = ax + u * ex, qy = ay + u * ey, dx = p->x - qx, dy = p->y - qy, d2 = dx * dx + dy * dy, RR = R + g->rad;
    if (d2 >= RR * RR) return;
    double d = sqrt(d2), nx, ny;
    if (d < 1e-6) { nx = 0; ny = -1; d = 0; } else { nx = dx / d; ny = dy / d; }
    p->x += nx * (RR - d); p->y += ny * (RR - d);
    double vsx = 0, vsy = 0;
    if (BD[g->body].dynamic) {
        double a0x, a0y, b0x, b0y; segw(g, c0, s0, ox0, oy0, &a0x, &a0y, &b0x, &b0y);
        double q0x = a0x + u * (b0x - a0x), q0y = a0y + u * (b0y - a0y);
        vsx = (qx - q0x) / dt; vsy = (qy - q0y) / dt;
    }
    double rx = p->vx - vsx, ry = p->vy - vsy, vn = rx * nx + ry * ny;
    if (vn >= 0) return;
    double e = (-vn < 40) ? 0 : g->e;
    double tx = rx - vn * nx, ty = ry - vn * ny, tl = sqrt(tx * tx + ty * ty);
    double jn = -(1 + e) * vn;
    rx += jn * nx; ry += jn * ny;
    if (tl > 1e-9) { double dv = g->mu * jn; if (dv > tl) dv = tl; rx -= tx / tl * dv; ry -= ty / tl * dv; }
    p->vx = rx + vsx; p->vy = ry + vsy;
    Body *b = &BD[g->body];
    if (-vn > 150) fprintf(EV, "H %.4f %d %.0f %.1f %.1f %d\n", t, g->kind, -vn, p->x, p->y, g->body);
    if (b->hp > 0 && -vn > 160 && t - LASTHIT[bi][g->body] > 0.3) {
        LASTHIT[bi][g->body] = t;
        fprintf(EV, "D %.4f %d\n", t, g->body);
        b->hp--;
        if (b->hp == 0) { b->alive = 0; b->break_t = t; fprintf(EV, "B %.4f %d\n", t, g->body); }
    }
}

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: phys input\n"); return 1; }
    FILE *f = fopen(argv[1], "r"); if (!f) return 1;
    for (int i = 0; i < MAXB; i++) for (int j = 0; j < MAXBODY; j++) LASTHIT[i][j] = -9;
    char tag[32], fpath[512], epath[512]; unsigned long long seed;
    fscanf(f, "%s %lf", tag, &G);
    fscanf(f, "%s %llu", tag, &seed); rng ^= seed * 2654435761ULL + 1;
    fscanf(f, "%s %d %lf", tag, &NB, &R);
    for (int i = 0; i < NB; i++) {
        fscanf(f, "%lf %lf %lf %lf", &B[i].x, &B[i].y, &B[i].vx, &B[i].vy);
        B[i].state = 0; B[i].rot = 0; B[i].best_y = B[i].y; B[i].t_best = 0; B[i].kicks = 0; B[i].fin_t = -1;
    }
    fscanf(f, "%s %d", tag, &NBD);
    for (int i = 0; i < NBD; i++) {
        Body *b = &BD[i];
        fscanf(f, "%lf %lf %lf %lf %lf %lf %lf %lf %lf %lf %lf %lf %lf %lf %lf %lf %d", &b->px, &b->py, &b->a0, &b->w,
               &b->amp, &b->k, &b->P, &b->ph, &b->bias, &b->ox, &b->oy, &b->k2, &b->P2, &b->ph2, &b->ton, &b->toff, &b->hp);
        b->dynamic = (b->w != 0 || b->P > 0 || b->P2 > 0); b->alive = 1; b->brad = 0; b->break_t = -1;
    }
    fscanf(f, "%s %d", tag, &NS);
    for (int i = 0; i < NS; i++) {
        Seg *g = &S[i];
        fscanf(f, "%d %lf %lf %lf %lf %lf %lf %lf %d", &g->body, &g->ax, &g->ay, &g->bx, &g->by, &g->rad, &g->e, &g->mu, &g->kind);
        double r1 = hypot(g->ax, g->ay) + g->rad, r2 = hypot(g->bx, g->by) + g->rad;
        Body *b = &BD[g->body];
        if (r1 > b->brad) b->brad = r1; if (r2 > b->brad) b->brad = r2;
    }
    fscanf(f, "%s %lf %d %lf %lf", tag, &FIN_Y, &QUAL, &TMAX, &AFTER);
    fscanf(f, "%s %s %s", tag, fpath, epath);
    fclose(f);

    // сетка статических отрезков
    double minx = 1e9, miny = 1e9, maxx = -1e9, maxy = -1e9;
    for (int i = 0; i < NS; i++) {
        Body *b = &BD[S[i].body]; if (b->dynamic) continue;
        double c, s, ox, oy, ax, ay, bx, by; xform(b, 0, &c, &s, &ox, &oy); segw(&S[i], c, s, ox, oy, &ax, &ay, &bx, &by);
        minx = fmin(minx, fmin(ax, bx)); maxx = fmax(maxx, fmax(ax, bx)); miny = fmin(miny, fmin(ay, by)); maxy = fmax(maxy, fmax(ay, by));
    }
    gx0 = minx - 200; gy0 = miny - 400; gw = (int)((maxx - minx + 400) / CELL) + 1; gh = (int)((maxy - miny + 1200) / CELL) + 1;
    gcnt = calloc(gw * gh, sizeof(int)); glist = calloc(gw * gh, sizeof(int *));
    for (int pass = 0; pass < 2; pass++) {
        if (pass == 1) { for (int i = 0; i < gw * gh; i++) { glist[i] = malloc(sizeof(int) * (gcnt[i] + 1)); gcnt[i] = 0; } }
        for (int i = 0; i < NS; i++) {
            Body *b = &BD[S[i].body]; if (b->dynamic) continue;
            double c, s, ox, oy, ax, ay, bx, by; xform(b, 0, &c, &s, &ox, &oy); segw(&S[i], c, s, ox, oy, &ax, &ay, &bx, &by);
            double pad = S[i].rad + 30;
            int x0 = (int)((fmin(ax, bx) - pad - gx0) / CELL), x1 = (int)((fmax(ax, bx) + pad - gx0) / CELL);
            int y0 = (int)((fmin(ay, by) - pad - gy0) / CELL), y1 = (int)((fmax(ay, by) + pad - gy0) / CELL);
            for (int yy = y0; yy <= y1; yy++) for (int xx = x0; xx <= x1; xx++) {
                if (xx < 0 || yy < 0 || xx >= gw || yy >= gh) continue;
                int id = yy * gw + xx; if (pass == 1) glist[id][gcnt[id]] = i; gcnt[id]++;
            }
        }
    }
    // отрезки динамических тел — по телам
    int *dstart = calloc(NBD + 1, sizeof(int)), *dseg = malloc(sizeof(int) * (NS + 1)), nd = 0;
    for (int b = 0; b < NBD; b++) { dstart[b] = nd; if (BD[b].dynamic) for (int i = 0; i < NS; i++) if (S[i].body == b) dseg[nd++] = i; }
    dstart[NBD] = nd;

    FILE *FR = fopen(fpath, "wb"); EV = fopen(epath, "w");
    const int SUB = 8; const double dt = 1.0 / 30 / SUB;
    double t = 0, t_stop = 1e9; int nfin = 0, frame = 0;
    double *cc = malloc(sizeof(double) * NBD * 8);
    int *mark = calloc(NS, sizeof(int)); int stamp = 0;
    while (1) {
        // кадр
        float buf[MAXB * 4];
        for (int i = 0; i < NB; i++) { buf[i * 4] = B[i].x; buf[i * 4 + 1] = B[i].y; buf[i * 4 + 2] = B[i].rot; buf[i * 4 + 3] = B[i].state; }
        fwrite(buf, sizeof(float), NB * 4, FR); frame++;
        if (t >= t_stop || t >= TMAX) break;
        for (int sub = 0; sub < SUB; sub++) {
            double t1 = t + dt;
            for (int b = 0; b < NBD; b++) {
                Body *bd = &BD[b];
                xform(bd, t1, &cc[b * 8], &cc[b * 8 + 1], &cc[b * 8 + 2], &cc[b * 8 + 3]);
                xform(bd, t, &cc[b * 8 + 4], &cc[b * 8 + 5], &cc[b * 8 + 6], &cc[b * 8 + 7]);
                if (bd->hp != 0 && bd->break_t < 0) bd->alive = (t1 >= bd->ton && t1 < bd->toff);
            }
            for (int i = 0; i < NB; i++) {
                Ball *p = &B[i]; if (p->state >= 2) continue;
                p->vy += G * dt;
                double sp = hypot(p->vx, p->vy); if (sp > 1500) { p->vx *= 1500 / sp; p->vy *= 1500 / sp; }
                p->x += p->vx * dt; p->y += p->vy * dt; p->rot += p->vx * dt / R;
            }
            for (int it = 0; it < 2; it++) {
                // шарик-шарик
                for (int i = 0; i < NB; i++) {
                    if (B[i].state >= 2) continue;
                    for (int j = i + 1; j < NB; j++) {
                        if (B[j].state >= 2) continue;
                        double dx = B[j].x - B[i].x, dy = B[j].y - B[i].y, d2 = dx * dx + dy * dy;
                        if (d2 >= 4 * R * R || d2 < 1e-9) continue;
                        double d = sqrt(d2), nx = dx / d, ny = dy / d, pen = 2 * R - d;
                        B[i].x -= nx * pen / 2; B[i].y -= ny * pen / 2; B[j].x += nx * pen / 2; B[j].y += ny * pen / 2;
                        double vn = (B[j].vx - B[i].vx) * nx + (B[j].vy - B[i].vy) * ny;
                        if (vn < 0) {
                            double e = (-vn < 40) ? 0.1 : 0.55, jj = -(1 + e) * vn / 2;
                            B[i].vx -= jj * nx; B[i].vy -= jj * ny; B[j].vx += jj * nx; B[j].vy += jj * ny;
                            if (-vn > 220 && it == 0) fprintf(EV, "H %.4f 9 %.0f %.1f %.1f -1\n", t1, -vn, B[i].x, B[i].y);
                        }
                    }
                }
                // шарик-трасса
                for (int i = 0; i < NB; i++) {
                    Ball *p = &B[i]; if (p->state >= 2) continue;
                    stamp++;
                    int x0 = (int)((p->x - R - gx0) / CELL), x1 = (int)((p->x + R - gx0) / CELL);
                    int y0 = (int)((p->y - R - gy0) / CELL), y1 = (int)((p->y + R - gy0) / CELL);
                    for (int yy = y0; yy <= y1; yy++) for (int xx = x0; xx <= x1; xx++) {
                        if (xx < 0 || yy < 0 || xx >= gw || yy >= gh) continue;
                        int id = yy * gw + xx;
                        for (int q = 0; q < gcnt[id]; q++) {
                            int si = glist[id][q]; if (mark[si] == stamp) continue; mark[si] = stamp;
                            int b = S[si].body; if (!BD[b].alive) continue;
                            collide_seg(p, i, &S[si], t1, dt, cc[b * 8], cc[b * 8 + 1], cc[b * 8 + 2], cc[b * 8 + 3], 0, 0, 0, 0);
                        }
                    }
                    for (int b = 0; b < NBD; b++) {
                        if (!BD[b].dynamic || !BD[b].alive) continue;
                        double dx = p->x - cc[b * 8 + 2], dy = p->y - cc[b * 8 + 3], lim = BD[b].brad + R + 2;
                        if (dx * dx + dy * dy > lim * lim) continue;
                        for (int q = dstart[b]; q < dstart[b + 1]; q++)
                            collide_seg(p, i, &S[dseg[q]], t1, dt, cc[b * 8], cc[b * 8 + 1], cc[b * 8 + 2], cc[b * 8 + 3],
                                        cc[b * 8 + 4], cc[b * 8 + 5], cc[b * 8 + 6], cc[b * 8 + 7]);
                    }
                }
            }
            t = t1;
            for (int i = 0; i < NB; i++) {
                Ball *p = &B[i];
                if (p->state == 0) {
                    if (p->x < -60 || p->x > 1060) { fprintf(EV, "O %.4f %d\n", t, i); p->x = p->x < 500 ? 40 : 960; p->vx = 0; }
                    if (p->y > p->best_y + 25) { p->best_y = p->y; p->t_best = t; }
                    else if (t - p->t_best > 9.0) {
                        p->vx += (frand() * 2 - 1) * 260; p->vy = -380; p->t_best = t; p->kicks++;
                        fprintf(EV, "K %.4f %d\n", t, i);
                    }
                    if (p->y > FIN_Y) {
                        p->state = 1; p->fin_t = t; nfin++;
                        fprintf(EV, "F %.4f %d\n", t, i);
                        if (nfin == QUAL) t_stop = t + AFTER;
                    }
                } else if (p->state == 1 && p->y > FIN_Y + 700) p->state = 2;
            }
        }
    }
    fprintf(EV, "END %.4f %d %d\n", t, nfin, frame);
    fclose(FR); fclose(EV);
    return 0;
}
