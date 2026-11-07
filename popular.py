"""Страны, за которые болеет больше всего зрителей YouTube (порядок — примерная величина аудитории).
Из них выбираем «лица» заезда для обложки и названия: зритель кликает на свой флаг."""
RANK = ("us in br id mx jp ru gb de tr ph vn fr th eg kr pk it es ar co sa ca pl bd ng ir my ua au za pe iq ma dz "
        "nl cl kz uz ro ve ec gt ae sy ye np lk kh mm tn jo az ge am by il pt se no fi dk cz hu gr rs hr bg sk "
        "at ch be ie nz sg hk tw cn kw qa om lb ly sd et ke gh tz ug cm ci sn ml bo py uy cu do hn sv ni cr pa "
        "jm tt ht af mn kg tj tm md lt lv ee ba mk al me si cy mt lu is").split()
POS = {c: i for i, c in enumerate(RANK)}


def featured(codes, k=3):
    """k самых «кликабельных» стран заезда (по порядку RANK; неизвестные — в конец)."""
    return sorted(codes, key=lambda c: POS.get(c, 999))[:k]
