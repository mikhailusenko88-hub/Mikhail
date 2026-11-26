"""Чтение и запись файлов 3ds Max (.max) без 3ds Max — для моделей «Наш декор» на 3ddd.

Файл .max — составной документ Microsoft (CFB/OLE2) с потоками Scene, ClassDirectory3, DllDirectory, Config…
Поток Scene — дерево чанков: [тип u16][размер u32, старший бит = контейнер] (если размер 0 — дальше u64),
размер включает заголовок. Здесь: точный разбор и обратная сборка (без правок — байт в байт), правка листьев,
пересчёт размеров контейнеров, своя запись CFB (сектор 512, мини-поток для потоков < 4096 байт).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

MAGIC = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
FREESECT, ENDOFCHAIN, FATSECT, DIFSECT, NOSTREAM = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD, 0xFFFFFFFC, 0xFFFFFFFF


# ------------------------------------------------------------------ CFB: чтение
@dataclass
class Entry:
    name: str
    typ: int            # 1 storage, 2 stream, 5 root
    color: int
    left: int
    right: int
    child: int
    clsid: bytes
    state: int
    ctime: bytes
    mtime: bytes
    start: int
    size: int
    data: bytes = b""


def read_cfb(raw: bytes) -> list[Entry]:
    assert raw[:8] == MAGIC, "не составной документ"
    sshift, mshift = struct.unpack_from("<HH", raw, 30)
    ssz, msz = 1 << sshift, 1 << mshift
    nfat, first_dir, _, mini_cut, first_mfat, nmfat, first_difat, ndifat = struct.unpack_from("<IIIIIIII", raw, 44)
    difat = list(struct.unpack_from("<109I", raw, 76))
    sec = lambda i: raw[512 + i * ssz: 512 + (i + 1) * ssz] if ssz == 512 else raw[ssz + i * ssz: ssz + (i + 1) * ssz]  # noqa: E731
    d = first_difat
    for _ in range(ndifat):
        b = sec(d)
        vals = struct.unpack("<%dI" % (ssz // 4), b)
        difat += vals[:-1]
        d = vals[-1]
    fat = []
    for s in difat[:nfat]:
        fat += struct.unpack("<%dI" % (ssz // 4), sec(s))

    def chain(start):
        out, s, guard = [], start, 0
        while s not in (ENDOFCHAIN, FREESECT) and guard < len(fat) + 2:
            out.append(s)
            s = fat[s]
            guard += 1
        return out

    dirdata = b"".join(sec(s) for s in chain(first_dir))
    entries = []
    for i in range(len(dirdata) // 128):
        e = dirdata[i * 128:(i + 1) * 128]
        nlen = struct.unpack_from("<H", e, 64)[0]
        name = e[:max(0, nlen - 2)].decode("utf-16le")
        typ, color = e[66], e[67]
        left, right, child = struct.unpack_from("<III", e, 68)
        clsid = e[80:96]
        state = struct.unpack_from("<I", e, 96)[0]
        ctime, mtime = e[100:108], e[108:116]
        start, size = struct.unpack_from("<IQ", e, 116)
        if ssz == 512:
            size &= 0xFFFFFFFF
        entries.append(Entry(name, typ, color, left, right, child, clsid, state, ctime, mtime, start, size))
    root = entries[0]
    ministream = b"".join(sec(s) for s in chain(root.start))[:root.size]
    mfat = []
    for s in chain(first_mfat):
        mfat += struct.unpack("<%dI" % (ssz // 4), sec(s))
    for e in entries:
        if e.typ != 2:
            continue
        if e.size < mini_cut:
            out, s = [], e.start
            while s not in (ENDOFCHAIN, FREESECT) and len(out) * msz < e.size + msz:
                out.append(ministream[s * msz:(s + 1) * msz])
                s = mfat[s]
            e.data = b"".join(out)[:e.size]
        else:
            e.data = b"".join(sec(s) for s in chain(e.start))[:e.size]
    return entries


def streams(entries: list[Entry]) -> dict[str, bytes]:
    return {e.name: e.data for e in entries if e.typ == 2}


# ------------------------------------------------------------------ CFB: запись
def write_cfb(entries: list[Entry], new_data: dict[str, bytes]) -> bytes:
    """Собрать документ заново: дерево каталога (имена, цвета, связи, CLSID, время) — как было, данные — новые."""
    SSZ, MSZ, CUT = 512, 64, 4096
    ents = [Entry(**{k: getattr(e, k) for k in e.__dataclass_fields__}) for e in entries]
    for e in ents:
        if e.typ == 2:
            e.data = new_data.get(e.name, e.data)
            e.size = len(e.data)
    # мини-поток
    mini, mfat = bytearray(), []
    for e in ents:
        if e.typ == 2 and e.size < CUT:
            if e.size == 0:
                e.start = ENDOFCHAIN
                continue
            n = (e.size + MSZ - 1) // MSZ
            e.start = len(mfat)
            mfat += [len(mfat) + k + 1 for k in range(n - 1)] + [ENDOFCHAIN]
            mini += e.data + b"\0" * (n * MSZ - e.size)
    root = ents[0]
    root.size = len(mini)
    root.data = bytes(mini)
    # раскладка секторов: большие потоки, мини-поток, мини-FAT, каталог, FAT
    sectors: list[bytes] = []
    fat: list[int] = []

    def put(blob: bytes) -> int:
        if not blob:
            return ENDOFCHAIN
        n = (len(blob) + SSZ - 1) // SSZ
        start = len(sectors)
        for k in range(n):
            sectors.append(blob[k * SSZ:(k + 1) * SSZ].ljust(SSZ, b"\0"))
            fat.append(start + k + 1 if k < n - 1 else ENDOFCHAIN)
        return start

    for e in ents:
        if e.typ == 2 and e.size >= CUT:
            e.start = put(e.data)
    root.start = put(bytes(mini)) if mini else ENDOFCHAIN
    mfat_blob = b"".join(struct.pack("<I", x) for x in mfat)
    mfat_blob += b"\xff" * ((-len(mfat_blob)) % SSZ)
    first_mfat = put(mfat_blob) if mfat else ENDOFCHAIN
    nmfat = len(mfat_blob) // SSZ if mfat else 0
    d = bytearray()
    for e in ents:
        nm = (e.name + "\0").encode("utf-16le")
        rec = nm.ljust(64, b"\0") + struct.pack("<HBB", len(nm) if e.name or e.typ else 0, e.typ, e.color)
        rec += struct.pack("<III", e.left, e.right, e.child) + e.clsid + struct.pack("<I", e.state) + e.ctime + e.mtime
        size = e.size if e.typ != 1 else 0
        start = e.start if e.typ != 1 else 0
        rec += struct.pack("<IQ", start, size)
        d += rec
    while len(d) % SSZ:
        d += (b"\0" * 64 + struct.pack("<HBB", 0, 0, 0) + struct.pack("<III", NOSTREAM, NOSTREAM, NOSTREAM)
              + b"\0" * 16 + b"\0" * 4 + b"\0" * 16 + struct.pack("<IQ", 0, 0))
    first_dir = put(bytes(d))
    # FAT: сколько секторов нужно под сам FAT (каждый вмещает 128 записей)
    nfat = 1
    while (len(sectors) + nfat) > nfat * (SSZ // 4):
        nfat += 1
    assert nfat <= 109, "слишком большой файл для простого заголовка"
    fat_start = len(sectors)
    fat += [FATSECT] * nfat
    fat += [FREESECT] * (nfat * (SSZ // 4) - len(fat))
    for k in range(nfat):
        sectors.append(b"".join(struct.pack("<I", x) for x in fat[k * 128:(k + 1) * 128]))
    hdr = bytearray(512)
    hdr[0:8] = MAGIC
    struct.pack_into("<HHHHH", hdr, 24, 0x3E, 3, 0xFFFE, 9, 6)
    struct.pack_into("<IIIIIIII", hdr, 44, nfat, first_dir, 0, CUT, first_mfat, nmfat, ENDOFCHAIN, 0)
    difat = [fat_start + k for k in range(nfat)] + [FREESECT] * (109 - nfat)
    struct.pack_into("<109I", hdr, 76, *difat)
    return bytes(hdr) + b"".join(sectors)


# ------------------------------------------------------------------ чанки
@dataclass
class Chunk:
    typ: int
    container: bool
    data: bytes = b""                  # лист
    children: list = field(default_factory=list)
    long: bool = False                 # 64-битный размер в оригинале

    def find(self, typ):
        return next((c for c in self.children if c.typ == typ), None)


def parse(data: bytes, pos: int = 0, end: int | None = None) -> list[Chunk]:
    end = len(data) if end is None else end
    out = []
    while pos < end:
        typ, siz = struct.unpack_from("<HI", data, pos)
        head, long = 6, False
        if siz == 0:
            siz, = struct.unpack_from("<Q", data, pos + 6)
            head, long = 14, True
            cont = bool(siz & (1 << 63))
            size = siz & ~(1 << 63)
        else:
            cont = bool(siz & 0x80000000)
            size = siz & 0x7FFFFFFF
        body = (pos + head, pos + size)
        if cont:
            out.append(Chunk(typ, True, children=parse(data, *body), long=long))
        else:
            out.append(Chunk(typ, False, data=data[body[0]:body[1]], long=long))
        pos += size
    return out


def dump(chunks: list[Chunk]) -> bytes:
    out = bytearray()
    for c in chunks:
        body = dump(c.children) if c.container else c.data
        if c.long or len(body) + 6 > 0x7FFFFFFF:
            size = len(body) + 14
            out += struct.pack("<HIQ", c.typ, 0, size | ((1 << 63) if c.container else 0))
        else:
            size = len(body) + 6
            out += struct.pack("<HI", c.typ, size | (0x80000000 if c.container else 0))
        out += body
    return bytes(out)
