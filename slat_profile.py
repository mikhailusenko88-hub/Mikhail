# Сечение реечной панели «под дерево» серии 3 (120×12 мм). Снято с живого образца — фото Михаила 12.11.2026:
# профиль «змейкой» постоянной толщины ~6 мм. Рейки 29,5 мм (верх на 12 мм), между ними пазы 10,5 мм (дно на 6 мм),
# под рейками пустоты, в пазах панель опирается на стену; под левым краем первой рейки узкая ножка, справа полка 10,5 мм.
# Срез — вспененный пористый, тыльная сторона — глянцевая чёрная. Раньше (по каталогу) было 24,8 / 15,2 и сплошная основа — неверно.
import math

STEP, LAM, T, TH, WEB, FLANGE, FL_TOP = 40.0, 29.5, 12.0, 6.0, 3.0, 10.5, 5.0
LFOOT = (2.0, 6.0)


def outline(n=3):
    """[(x, z, tag)] по часовой стрелке (x вправо, z вверх), мм. tag — поверхность ребра ОТ этой точки к следующей:
    w — плёнка «под дерево», s — чёрная лицевая (бока реек, пазы, полка), b — тыльная сторона."""
    P = [(0.0, T - TH, 's')]
    for i in range(n):
        xs, xe = i * STEP, i * STEP + LAM
        if i > 0:
            P.append((xs, T - TH, 's'))
        P.append((xs, T, 'w'))
        P.append((xe, T, 's'))
        if i < n - 1:
            P.append((xe, T - TH, 's'))
        else:
            P.append((xe, FL_TOP, 's'))
            P.append((n * STEP, FL_TOP, 's'))
    P.append((n * STEP, 0.0, 'b'))
    x = (n - 1) * STEP + LAM - WEB
    P += [(x, 0.0, 'b'), (x, T - TH, 'b')]
    for i in range(n - 2, -1, -1):
        right, left = (i + 1) * STEP + WEB, i * STEP + LAM - WEB
        P += [(right, T - TH, 'b'), (right, 0.0, 'b'), (left, 0.0, 'b'), (left, T - TH, 'b')]
    P += [(LFOOT[1], T - TH, 'b'), (LFOOT[1], 0.0, 'b'), (LFOOT[0], 0.0, 'b'), (LFOOT[0], T - TH, 'b')]
    return P


def rounded(P, r_top=0.8, r=0.5, seg=3):
    """Скругляет все углы контура (углы у верха реек — r_top: плёнка заходит на кромку)."""
    out, n = [], len(P)
    for k in range(n):
        px, pz, tp = P[k - 1]
        cx, cz, tc = P[k]
        qx, qz, _ = P[(k + 1) % n]
        l1, l2 = math.hypot(px - cx, pz - cz), math.hypot(qx - cx, qz - cz)
        d = min(r_top if abs(cz - T) < 1e-6 else r, 0.45 * l1, 0.45 * l2)
        ax, az = cx + (px - cx) / l1 * d, cz + (pz - cz) / l1 * d
        bx, bz = cx + (qx - cx) / l2 * d, cz + (qz - cz) / l2 * d
        ta = 'w' if 'w' in (tp, tc) else tc
        for j in range(seg):
            t = j / seg
            out.append(((1 - t) ** 2 * ax + 2 * t * (1 - t) * cx + t * t * bx, (1 - t) ** 2 * az + 2 * t * (1 - t) * cz + t * t * bz, ta))
        out.append((bx, bz, tc))
    return out


if __name__ == '__main__':
    o = outline()
    print(len(o), 'точек; ширина', max(p[0] for p in o), 'высота', max(p[1] for p in o))
    a = sum(o[k][0] * o[(k + 1) % len(o)][1] - o[(k + 1) % len(o)][0] * o[k][1] for k in range(len(o))) / 2
    print('площадь сечения, мм²:', round(abs(a), 1), '(сплошная была бы', 120 * 12, ')')
