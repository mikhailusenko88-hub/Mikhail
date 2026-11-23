# Свой голос, круг 2 — итог

Основа — №3 из первой пробы (ритм Марата, мелодия nash3, тембр nash2). Каждая часть — смесь многих дикторов с долями;
доли подбирались по естественности (UTMOS) и разборчивости (распознаватель), круг 1 — 48 смесей, круг 2 — 20 вокруг лучших.
Отдельно — модель Барсика (v5_ru, лицензия CC BY-NC): манера xenia с мужским тембром.

## Финалисты (полная проверка, 12 фраз)

| | голос | состав | слова | UTMOS | ошибки удар. | интонация | диапазон | Гц | темп | оценка |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Как №3 в прошлой пробе (c00) | dp: marat 1.00; pp: nash3 1.00; spe: nash2 1.00 | 0.940 | 3.61 | 0.29 | 0.92 | 10.9 | 112 | 5.6 | 8.141 |
| 2 | Новый 1 (r32) | dp: marat 0.57 + nash2 0.43; pp: nash3 0.71 + bogdan 0.22 + nash2 0.06 + aigul 0.01; spe: nash2 0.81 + miyau 0.19 | 0.931 | 3.69 | 0.25 | 0.92 | 10.9 | 109 | 5.6 | 8.19 |
| 3 | Новый 2 (r13) | dp: marat 0.64 + kejilgan 0.21 + nash1 0.15; pp: nash3 0.44 + nurgul 0.29 + zara 0.27; spe: nash2 0.78 + kejilgan 0.22 | 0.931 | 3.70 | 0.17 | 0.92 | 11.5 | 113 | 5.6 | 8.237 |
| 4 | Манера Барсика, мужской голос (q00) | dp: xenia 1.00; pp: xenia 0.70 + eugene 0.30; spe: eugene 1.00 | 0.938 | 3.59 | 0.50 | 0.75 | 10.9 | 85 | 6.6 | 7.781 |
| 5 | Барсик для сравнения (его голос без подъёма) (b_xenia) | dp: xenia 1.00; pp: xenia 1.00; spe: xenia 1.00 | 0.945 | 3.37 | 0.38 | 0.92 | 7.0 | 196 | 6.6 | 7.717 |
| 6 | Сейчас в «Почему так?» (nash3) (c01) | dp: nash3 1.00; pp: nash3 1.00; spe: nash3 1.00 | 0.932 | 3.20 | 0.12 | 0.92 | 12.5 | 124 | 5.9 | 7.86 |

## Быстрая оценка всех смесей (J = 4·слова + UTMOS + 0,3·худший UTMOS + живость − темп)

| смесь | дорожка | J | UTMOS | худший | слова | Гц | состав |
|---|---|---|---|---|---|---|---|
| r32 | cis | 9.154 | 3.691 | 3.397 | 0.931 | 109 | dp: marat 0.57 + nash2 0.43; pp: nash3 0.71 + bogdan 0.22 + nash2 0.06 + aigul 0.01; spe: nash2 0.81 + miyau 0.19 |
| r13 | cis | 9.147 | 3.699 | 3.348 | 0.931 | 113 | dp: marat 0.64 + kejilgan 0.21 + nash1 0.15; pp: nash3 0.44 + nurgul 0.29 + zara 0.27; spe: nash2 0.78 + kejilgan 0.22 |
| r31 | cis | 9.142 | 3.683 | 3.382 | 0.931 | 114 | dp: marat 0.57 + nash2 0.43; pp: nash3 0.54 + marat 0.24 + bogdan 0.17 + nash2 0.04; spe: nash2 1.00 |
| c31 | cis | 9.126 | 3.663 | 3.397 | 0.931 | 116 | dp: marat 0.59 + eduard 0.41; pp: nash3 0.45 + nurgul 0.35 + zhadyra 0.17 + marat 0.03; spe: nash2 1.00 |
| r22 | cis | 9.11 | 3.664 | 3.341 | 0.931 | 115 | dp: aigul 0.50 + marat 0.50; pp: nash3 0.60 + alfia 0.21 + bogdan 0.12 + marat 0.07; spe: nash2 0.73 + marat 0.27 |
| r11 | cis | 9.108 | 3.673 | 3.302 | 0.931 | 111 | dp: marat 0.64 + kejilgan 0.21 + nash1 0.15; pp: nash3 0.50 + nurgul 0.33 + nash1 0.17; spe: nash2 0.78 + kejilgan 0.22 |
| c40 | cis | 9.105 | 3.697 | 3.372 | 0.919 | 112 | dp: marat 0.64 + kejilgan 0.21 + nash1 0.15; pp: nash3 0.60 + nurgul 0.40; spe: nash2 0.78 + kejilgan 0.22 |
| r10 | cis | 9.104 | 3.711 | 3.322 | 0.919 | 112 | dp: marat 0.54 + kejilgan 0.18 + alfia 0.15 + nash1 0.12; pp: nash3 0.60 + nurgul 0.40; spe: nash2 0.78 + kejilgan 0.22 |
| r23 | cis | 9.102 | 3.656 | 3.341 | 0.931 | 113 | dp: aigul 0.50 + marat 0.50; pp: nash3 0.48 + nash2 0.20 + alfia 0.17 + bogdan 0.10 + marat 0.05; spe: nash2 1.00 |
| c06 | cis | 9.1 | 3.668 | 3.292 | 0.931 | 113 | dp: aigul 0.50 + marat 0.50; pp: nash3 0.60 + alfia 0.21 + bogdan 0.12 + marat 0.07; spe: nash2 1.00 |
| r01 | cis | 9.097 | 3.713 | 3.293 | 0.919 | 116 | dp: marat 0.59 + eduard 0.41; pp: nash3 0.35 + nurgul 0.27 + aigul 0.22 + zhadyra 0.13 + marat 0.03; spe: nash2 1.00 |
| c23 | cis | 9.092 | 3.707 | 3.404 | 0.911 | 113 | dp: marat 0.57 + nash2 0.43; pp: nash3 0.71 + bogdan 0.22 + nash2 0.06 + aigul 0.01; spe: nash2 1.00 |
| r34 | cis | 9.088 | 3.652 | 3.186 | 0.94 | 107 | dp: marat 0.57 + nash2 0.43; pp: nash3 0.71 + bogdan 0.22 + nash2 0.06 + aigul 0.01; spe: nash2 0.72 + kejilgan 0.28 |
| r20 | cis | 9.078 | 3.674 | 3.199 | 0.931 | 113 | dp: aigul 0.43 + marat 0.43 + zhadyra 0.14; pp: nash3 0.60 + alfia 0.21 + bogdan 0.12 + marat 0.07; spe: nash2 1.00 |
| q00 | bars | 9.071 | 3.595 | 3.345 | 0.938 | 91 | dp: xenia 1.00; pp: xenia 0.70 + eugene 0.30; spe: eugene 1.00 |
| c27 | cis | 9.063 | 3.624 | 3.196 | 0.94 | 107 | dp: marat 0.79 + kermen 0.21; pp: nash3 0.76 + aigul 0.24; spe: nash2 0.65 + kejilgan 0.35 |
| c25 | cis | 9.063 | 3.628 | 3.302 | 0.931 | 111 | dp: marat 0.71 + zara 0.28; pp: nash3 0.64 + zinaida 0.19 + marat 0.17; spe: nash2 0.81 + nash1 0.11 + miyau 0.09 |
| c13 | cis | 9.059 | 3.639 | 3.255 | 0.931 | 112 | dp: marat 0.61 + aigul 0.39; pp: nash3 1.00; spe: nash2 1.00 |
| c12 | cis | 9.047 | 3.651 | 3.333 | 0.919 | 108 | dp: marat 0.81 + nash3 0.19; pp: nash3 0.73 + nash1 0.15 + alfia 0.10; spe: nash2 0.74 + safarhuja 0.23 + marat 0.03 |
| r03 | cis | 9.043 | 3.657 | 3.139 | 0.931 | 114 | dp: marat 0.59 + eduard 0.41; pp: nash3 0.37 + nurgul 0.29 + miyau 0.17 + zhadyra 0.14 + marat 0.03; spe: nash2 1.00 |
| b07 | bars | 9.039 | 3.589 | 3.26 | 0.938 | 92 | dp: xenia 1.00; pp: xenia 1.00; spe: eugene 1.00 |
| c36 | cis | 9.039 | 3.617 | 3.299 | 0.928 | 112 | dp: marat 0.81 + zara 0.19; pp: nash3 1.00; spe: nash2 0.68 + dmitriy 0.23 + kejilgan 0.09 |
| b09 | bars | 9.036 | 3.578 | 3.206 | 0.944 | 93 | dp: kseniya 1.00; pp: xenia 1.00; spe: eugene 1.00 |
| c11 | cis | 9.034 | 3.599 | 3.304 | 0.931 | 111 | dp: marat 1.00; pp: nash3 0.58 + zhadyra 0.21 + zinaida 0.20; spe: nash2 0.73 + eduard 0.27 |
| c08 | cis | 9.022 | 3.648 | 3.099 | 0.931 | 112 | dp: marat 0.59 + nash2 0.24 + zara 0.14 + vika 0.02; pp: nash3 0.83 + nash1 0.15 + zhadyra 0.02; spe: nash2 1.00 |
| c00 | cis | 9.02 | 3.613 | 3.09 | 0.94 | 112 | dp: marat 1.00; pp: nash3 1.00; spe: nash2 1.00 |
| c21 | cis | 9.018 | 3.641 | 3.109 | 0.931 | 112 | dp: marat 0.55 + zara 0.33 + kejilgan 0.12; pp: nash3 1.00; spe: nash2 1.00 |
| r14 | cis | 9.015 | 3.635 | 3.28 | 0.919 | 113 | dp: marat 0.64 + kejilgan 0.21 + nash1 0.15; pp: nash3 0.60 + nurgul 0.40; spe: nash2 0.55 + nash1 0.30 + kejilgan 0.16 |
| c24 | cis | 9.011 | 3.634 | 3.27 | 0.919 | 112 | dp: marat 0.80 + miyau 0.13 + nash2 0.07; pp: nash3 1.00; spe: nash2 1.00 |
| r21 | cis | 9.005 | 3.623 | 3.126 | 0.931 | 112 | dp: aigul 0.50 + marat 0.50; pp: nash3 0.50 + alfia 0.17 + miyau 0.17 + bogdan 0.10 + marat 0.06; spe: nash2 1.00 |
| r12 | cis | 8.999 | 3.605 | 3.326 | 0.919 | 109 | dp: marat 0.64 + kejilgan 0.21 + nash1 0.15; pp: nash3 0.60 + nurgul 0.40; spe: nash2 0.69 + kejilgan 0.20 + safarhuja 0.11 |
| c35 | cis | 8.999 | 3.601 | 3.18 | 0.931 | 107 | dp: marat 0.79 + kejilgan 0.15 + zinaida 0.06; pp: nash3 0.60 + zara 0.40; spe: nash2 0.54 + miyau 0.41 + safarhuja 0.05 |
| c30 | cis | 8.99 | 3.648 | 3.179 | 0.917 | 114 | dp: marat 1.00; pp: nash3 0.54 + aigul 0.26 + marat 0.20; spe: nash2 1.00 |
| c32 | cis | 8.983 | 3.563 | 3.252 | 0.931 | 112 | dp: marat 0.53 + miyau 0.39 + kermen 0.08; pp: nash3 0.54 + zinaida 0.35 + marat 0.11; spe: nash2 0.75 + eduard 0.24 + bogdan 0.01 |
| b08 | bars | 8.976 | 3.541 | 3.25 | 0.935 | 90 | dp: xenia 1.00; pp: xenia 0.50 + eugene 0.50; spe: eugene 1.00 |
| c18 | cis | 8.975 | 3.624 | 3.183 | 0.919 | 113 | dp: marat 0.58 + zhadyra 0.30 + nash3 0.12; pp: nash3 0.70 + zara 0.23 + zhadyra 0.07; spe: nash2 1.00 |
| c43 | cis | 8.975 | 3.591 | 3.014 | 0.94 | 111 | dp: marat 0.68 + vika 0.14 + zhadyra 0.13 + eduard 0.04; pp: nash3 0.85 + aigul 0.08 + zinaida 0.06 + bogdan 0.02; spe: nash2 0.83 + miyau 0.13 + marat 0.03 |
| c02 | cis | 8.969 | 3.593 | 3.108 | 0.931 | 120 | dp: marat 0.58 + bogdan 0.38 + kermen 0.04; pp: nash3 1.00; spe: nash2 0.55 + marat 0.45 |
| c37 | cis | 8.961 | 3.506 | 3.251 | 0.94 | 110 | dp: marat 1.00; pp: nash3 1.00; spe: nash2 0.51 + alexandr 0.49 |
| c22 | cis | 8.959 | 3.58 | 3.116 | 0.931 | 110 | dp: marat 0.77 + nash2 0.23; pp: nash3 1.00; spe: nash2 0.75 + roman 0.23 + dmitriy 0.02 |
| r30 | cis | 8.95 | 3.634 | 3.173 | 0.911 | 112 | dp: marat 0.49 + nash2 0.37 + aigul 0.14; pp: nash3 0.71 + bogdan 0.22 + nash2 0.06 + aigul 0.01; spe: nash2 1.00 |
| c28 | cis | 8.937 | 3.574 | 3.064 | 0.931 | 108 | dp: marat 0.60 + nash2 0.33 + alfia 0.07; pp: nash3 0.68 + kejilgan 0.20 + eduard 0.12; spe: nash2 0.71 + safarhuja 0.20 + marat 0.09 |
| r00 | cis | 8.936 | 3.653 | 2.798 | 0.931 | 116 | dp: marat 0.48 + eduard 0.33 + zinaida 0.19; pp: nash3 0.45 + nurgul 0.35 + zhadyra 0.17 + marat 0.03; spe: nash2 1.00 |
| c34 | cis | 8.932 | 3.617 | 3.17 | 0.911 | 109 | dp: marat 1.00; pp: nash3 0.59 + bogdan 0.41; spe: nash2 0.60 + roman 0.40 |
| c14 | cis | 8.932 | 3.61 | 3.113 | 0.917 | 108 | dp: marat 0.84 + zara 0.10 + bogdan 0.04 + nash3 0.02; pp: zhadyra 0.51 + nash3 0.49; spe: nash2 0.62 + alexandr 0.31 + nash1 0.07 |
| r02 | cis | 8.926 | 3.642 | 2.906 | 0.923 | 114 | dp: marat 0.59 + eduard 0.41; pp: nash3 0.45 + nurgul 0.35 + zhadyra 0.17 + marat 0.03; spe: nash2 0.83 + alexandr 0.17 |
| r04 | cis | 8.925 | 3.597 | 3.054 | 0.923 | 114 | dp: marat 0.59 + eduard 0.41; pp: nash3 0.45 + nurgul 0.35 + zhadyra 0.17 + marat 0.03; spe: nash2 0.83 + alexandr 0.17 |
| r33 | cis | 8.925 | 3.556 | 3.084 | 0.931 | 112 | dp: marat 0.57 + nash2 0.43; pp: nash3 0.62 + bogdan 0.19 + zhadyra 0.12 + nash2 0.05; spe: nash2 1.00 |
| c07 | cis | 8.923 | 3.573 | 3.206 | 0.917 | 116 | dp: marat 0.53 + kermen 0.47; pp: nash3 0.56 + aigul 0.22 + bogdan 0.14 + marat 0.07; spe: nash2 0.63 + marat 0.30 + miyau 0.06 |
| q10 | bars | 8.923 | 3.539 | 3.067 | 0.936 | 91 | dp: kseniya 1.00; pp: xenia 0.70 + eugene 0.30; spe: eugene 1.00 |
| c47 | cis | 8.92 | 3.509 | 3.104 | 0.94 | 114 | dp: marat 0.69 + miyau 0.27 + eduard 0.04; pp: nash3 0.75 + zinaida 0.18 + aigul 0.07; spe: nash2 0.65 + nash3 0.35 |
| c38 | cis | 8.92 | 3.594 | 3.101 | 0.919 | 115 | dp: marat 0.56 + zinaida 0.34 + kermen 0.07 + zhadyra 0.03; pp: nash3 0.71 + bogdan 0.17 + eduard 0.11; spe: nash2 0.64 + dmitriy 0.30 + nash3 0.06 |
| c16 | cis | 8.899 | 3.518 | 3.124 | 0.931 | 111 | dp: marat 0.77 + aigul 0.23; pp: nash3 0.57 + eduard 0.36 + miyau 0.07; spe: nash2 0.63 + eduard 0.22 + bogdan 0.15 |
| c44 | cis | 8.891 | 3.56 | 3.118 | 0.919 | 112 | dp: marat 0.81 + zhadyra 0.19; pp: nash3 0.79 + kermen 0.17 + eduard 0.04; spe: nash2 1.00 |
| c42 | cis | 8.888 | 3.565 | 3.09 | 0.919 | 115 | dp: marat 0.70 + kejilgan 0.30; pp: nash3 0.70 + vika 0.30; spe: nash2 0.81 + eduard 0.19 |
| c29 | cis | 8.881 | 3.633 | 3.026 | 0.905 | 105 | dp: marat 1.00; pp: aigul 0.50 + nash3 0.50; spe: nash2 0.63 + safarhuja 0.29 + miyau 0.08 |
| q12 | bars | 8.879 | 3.547 | 3.316 | 0.944 | 92 | dp: xenia 0.50 + eugene 0.50; pp: xenia 1.00; spe: eugene 1.00 |
| q02 | bars | 8.879 | 3.547 | 3.316 | 0.944 | 92 | dp: xenia 0.50 + eugene 0.50; pp: xenia 1.00; spe: eugene 1.00 |
| c17 | cis | 8.867 | 3.546 | 2.922 | 0.931 | 110 | dp: marat 0.46 + alfia 0.28 + aigul 0.26; pp: nash3 0.82 + kejilgan 0.18; spe: nash2 0.64 + alexandr 0.27 + miyau 0.10 |
| c05 | cis | 8.856 | 3.576 | 2.787 | 0.931 | 107 | dp: marat 1.00; pp: nash3 1.00; spe: nash2 0.54 + miyau 0.42 + nash3 0.04 |
| c20 | cis | 8.855 | 3.474 | 3.124 | 0.931 | 112 | dp: marat 1.00; pp: nash3 0.53 + nash1 0.47; spe: nash2 1.00 |
| c10 | cis | 8.847 | 3.541 | 3.033 | 0.919 | 113 | dp: nash3 0.54 + marat 0.46; pp: nash3 1.00; spe: nash2 0.76 + eduard 0.24 |
| c03 | cis | 8.843 | 3.516 | 2.942 | 0.931 | 120 | dp: marat 0.84 + nash1 0.16; pp: nash3 1.00; spe: nash2 0.51 + marat 0.49 |
| q01 | bars | 8.839 | 3.5 | 3.072 | 0.941 | 90 | dp: xenia 1.00; pp: eugene 0.70 + xenia 0.30; spe: eugene 1.00 |
| c26 | cis | 8.834 | 3.575 | 2.877 | 0.919 | 113 | dp: marat 0.47 + nash1 0.46 + nash2 0.05 + aigul 0.01; pp: nash3 0.53 + nash1 0.24 + kejilgan 0.23; spe: nash2 0.56 + nash1 0.43 |
| b10 | bars | 8.834 | 3.515 | 2.89 | 0.933 | 90 | dp: kseniya 1.00; pp: xenia 0.50 + eugene 0.50; spe: eugene 1.00 |
| c33 | cis | 8.82 | 3.47 | 3.02 | 0.931 | 116 | dp: marat 0.63 + kejilgan 0.17 + miyau 0.15 + nash3 0.05; pp: nash3 0.77 + zinaida 0.21 + nash2 0.01 + zhadyra 0.01; spe: nash3 0.53 + nash2 0.47 |
| c04 | cis | 8.818 | 3.553 | 2.92 | 0.919 | 113 | dp: marat 1.00; pp: nash3 0.65 + miyau 0.32 + nash1 0.04; spe: nash2 0.74 + dmitriy 0.26 |
| c39 | cis | 8.783 | 3.446 | 3.135 | 0.919 | 110 | dp: marat 0.79 + alfia 0.21; pp: nash3 0.52 + marat 0.46; spe: nash2 0.46 + nash1 0.29 + safarhuja 0.25 |
| c19 | cis | 8.771 | 3.432 | 2.983 | 0.931 | 115 | dp: marat 0.66 + nash3 0.28 + kermen 0.05 + aigul 0.02; pp: nash3 0.76 + miyau 0.24; spe: nash2 0.53 + nash3 0.47 |
| r24 | cis | 8.765 | 3.427 | 2.98 | 0.931 | 113 | dp: aigul 0.50 + marat 0.50; pp: nash3 0.60 + alfia 0.21 + bogdan 0.12 + marat 0.07; spe: nash2 0.75 + bogdan 0.25 |
| c15 | cis | 8.725 | 3.522 | 2.69 | 0.919 | 112 | dp: zhadyra 0.52 + marat 0.48; pp: nash3 0.57 + eduard 0.24 + zinaida 0.11 + zhadyra 0.08; spe: nash1 0.51 + nash2 0.49 |
| c45 | cis | 8.717 | 3.461 | 2.895 | 0.917 | 113 | dp: marat 0.81 + kermen 0.15 + eduard 0.03; pp: nash3 0.72 + nash2 0.28; spe: nash2 0.58 + bogdan 0.30 + nash1 0.12 |
| b11 | bars | 8.69 | 3.521 | 3.176 | 0.935 | 92 | dp: eugene 1.00; pp: xenia 1.00; spe: eugene 1.00 |
| c41 | cis | 8.676 | 3.437 | 2.81 | 0.919 | 108 | dp: marat 0.68 + kejilgan 0.28 + miyau 0.04; pp: nash3 0.81 + bogdan 0.16 + nurgul 0.03; spe: roman 0.55 + nash2 0.45 |
| c46 | cis | 8.67 | 3.41 | 2.72 | 0.931 | 115 | dp: marat 0.56 + eduard 0.25 + alfia 0.17 + aigul 0.01; pp: nash3 0.83 + zara 0.17; spe: nash2 0.56 + eduard 0.44 |
| q11 | bars | 8.666 | 3.443 | 2.924 | 0.925 | 90 | dp: kseniya 1.00; pp: eugene 0.70 + xenia 0.30; spe: eugene 1.00 |
| b12 | bars | 8.641 | 3.461 | 3.228 | 0.935 | 90 | dp: eugene 1.00; pp: xenia 0.50 + eugene 0.50; spe: eugene 1.00 |
| b_xenia | bars | 8.609 | 3.373 | 2.981 | 0.945 | 200 | dp: xenia 1.00; pp: xenia 1.00; spe: xenia 1.00 |
| c09 | cis | 8.589 | 3.363 | 2.872 | 0.911 | 113 | dp: marat 1.00; pp: nash3 0.77 + miyau 0.23; spe: nash2 0.60 + eduard 0.40 |
| b04 | bars | 8.5 | 3.129 | 2.798 | 0.953 | 118 | dp: kseniya 1.00; pp: xenia 0.50 + aidar 0.50; spe: aidar 1.00 |
| b02 | bars | 8.455 | 3.073 | 2.914 | 0.947 | 118 | dp: xenia 1.00; pp: xenia 0.50 + aidar 0.50; spe: aidar 1.00 |
| c01 | cis | 8.424 | 3.2 | 2.588 | 0.932 | 125 | dp: nash3 1.00; pp: nash3 1.00; spe: nash3 1.00 |
| b_eugene | bars | 8.409 | 3.441 | 3.002 | 0.935 | 89 | dp: eugene 1.00; pp: eugene 1.00; spe: eugene 1.00 |
| b_aidar | bars | 8.403 | 3.077 | 2.447 | 0.968 | 124 | dp: aidar 1.00; pp: aidar 1.00; spe: aidar 1.00 |
| b05 | bars | 8.393 | 3.067 | 2.646 | 0.953 | 113 | dp: aidar 1.00; pp: xenia 1.00; spe: aidar 1.00 |
| b06 | bars | 8.378 | 3.018 | 2.56 | 0.968 | 119 | dp: aidar 1.00; pp: xenia 0.50 + aidar 0.50; spe: aidar 1.00 |
| b03 | bars | 8.377 | 3.086 | 2.689 | 0.941 | 112 | dp: kseniya 1.00; pp: xenia 1.00; spe: aidar 1.00 |
| b01 | bars | 8.298 | 3.082 | 2.519 | 0.935 | 111 | dp: xenia 1.00; pp: xenia 1.00; spe: aidar 1.00 |
