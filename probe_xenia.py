# Разведка xenia (Silero v5_6_ru): исходники пакета и что именно apply_tts подаёт в модель (type_ids, focus, emphasis, symb_durs)
import os, json, zipfile, urllib.request, inspect, traceback
import torch, numpy as np
RD = "vb/refs/xenia"; os.makedirs(RD + "/src", exist_ok=True)
log = open(RD + "/probe.log", "w")
def P(*a):
    print(*a); print(*a, file=log); log.flush()
f = "v5_6_ru.pt"
if not os.path.exists(f): urllib.request.urlretrieve("https://models.silero.ai/models/tts/ru/v5_6_ru.pt", f)
z = zipfile.ZipFile(f)
for n in z.namelist():
    if n.endswith((".py", ".txt", ".json", ".yml", ".yaml")): open(os.path.join(RD, "src", n.replace("/", "__")), "wb").write(z.read(n))
m = torch.package.PackageImporter(f).load_pickle("tts_models", "model"); pack = m.packages[0]; jm = pack.models[0]
def walk(mod, pre, depth=0):
    for nm, ch in mod.named_children():
        on = getattr(ch, "original_name", type(ch).__name__); P("  " * depth + pre + nm, on)
        try: open(f"{RD}/src/code_{pre}{nm}.txt", "w").write(ch.code)
        except Exception: pass
        if depth < 4: walk(ch, pre + nm + ".", depth + 1)
walk(jm, "")
for k in ["cap_sos", "fx_durs", "process_pauses", "update_pitch_coef", "get_support_ids", "replace_comma"]:
    try: P("== jm." + k); P(getattr(jm, k).code)
    except Exception as e: P(k, e)
try: P("punkt_symbols", jm.punkt_symbols)
except Exception as e: P("punkt", e)
calls = []
class Rec(torch.nn.Module):
    def __init__(s, o): super().__init__(); s.o = o
    def forward(s, *a, **k):
        def cv(x):
            if isinstance(x, torch.Tensor): return {"shape": list(x.shape), "dtype": str(x.dtype), "v": x.detach().cpu().numpy().round(5).tolist() if x.numel() < 4000 else None}
            if isinstance(x, dict): return {str(kk): cv(vv) for kk, vv in x.items()}
            if isinstance(x, (list, tuple)): return [cv(v) for v in x]
            return x
        calls.append({"args": [cv(x) for x in a], "kwargs": {kk: cv(vv) for kk, vv in k.items()}})
        out = s.o(*a, **k); calls[-1]["durs"] = cv(out[1]); return out
try:
    pack.models[0] = Rec(jm)
except Exception as e: P("cannot wrap models[0]", e)
TX = ["Привет! Я Барсик!", "Ой... Кто это там шуршит в кустах?", "Пойдём посмотрим! Ура!", "Прив+ет! Ж+или-б+ыли кот и мыш+онок."]
for t in TX:
    for acc in (True, False):
        try:
            a = m.apply_tts(text=t, speaker="xenia", sample_rate=48000, put_accent=acc, put_yo=acc); P("ok", t, acc, len(a))
        except Exception as e: P("err", t, acc, repr(e)); traceback.print_exc(file=log)
json.dump(calls, open(RD + "/calls.json", "w"), ensure_ascii=False)
P("calls", len(calls))
try: P(inspect.getsource(type(pack).apply_tts))
except Exception as e: P("src", e)
P("OK")
