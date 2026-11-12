# Сечение панели A910 «волна» под покраску (180×12 мм, 9 валиков по 20 мм). Сверено с живым образцом — фото Михаила 12.11.2026:
# валик — почти полукруглая дуга высотой ~5,5 мм (толщина 6,5…12 мм; раньше по каталогу было 8,2…12 — неверно), между валиками узкая ровная полоска ~1,5 мм (на лице — двойная линия);
# тыльная сторона ровная, под серединой каждого валика продольная канавка ~6×3 мм; срез — белый мелкозернистый (плотная пена).
import math

PITCH, N, T_MIN, T_MAX, FL = 20.0, 9, 6.5, 12.0, 1.5
NOTCH_W, NOTCH_H = 6.0, 3.0


def t_at(u, pitch=PITCH, t_min=T_MIN, t_max=T_MAX, fl=FL):
    """Толщина на расстоянии u от начала валика (0…pitch), в тех же единицах, что и аргументы."""
    c, h = pitch - fl, t_max - t_min
    rr = ((c / 2) ** 2 + h * h) / (2 * h)
    d = abs(u - pitch / 2)
    if d >= c / 2:
        return t_min
    return t_min + math.sqrt(rr * rr - d * d) - (rr - h)


def rib_samples(seg=14, pitch=PITCH, fl=FL):
    """Точки вдоль одного валика: края полосок и дуга."""
    c = pitch - fl
    return [0.0, fl / 2] + [fl / 2 + c * j / seg for j in range(1, seg)] + [pitch - fl / 2, pitch]


def outline(n=N, seg=14, nseg=8):
    """[(x, z, tag)] по часовой стрелке (x вправо, z вверх), мм. tag ребра ОТ точки: f — лицо, b — тыл."""
    P = [(0.0, 0.0, 'f')]
    us = rib_samples(seg)
    for i in range(n):
        for k, u in enumerate(us):
            if i > 0 and k == 0:
                continue
            P.append((i * PITCH + u, t_at(u), 'f'))
    P.append((n * PITCH, 0.0, 'b'))
    for i in range(n - 1, -1, -1):
        cx = i * PITCH + PITCH / 2
        for j in range(nseg + 1):
            a = math.pi * j / nseg
            P.append((cx + NOTCH_W / 2 * math.cos(a), NOTCH_H * math.sin(a), 'b'))
    return P


if __name__ == '__main__':
    o = outline()
    print(len(o), 'точек; ширина', max(p[0] for p in o), 'высота', round(max(p[1] for p in o), 2))
