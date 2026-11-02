# Разведка: что внутри Silero v5_cis_base и можно ли его перевести в ONNX для телефона
import os, sys, json, traceback, urllib.request, inspect, zipfile
import torch
os.makedirs("out/src", exist_ok=True)
f = "v5_cis_base.pt"
if not os.path.exists(f):
    urllib.request.urlretrieve("https://models.silero.ai/models/tts/ru/v5_cis_base.pt", f)
log = open("out/probe.txt", "w")
def P(*a):
    print(*a); print(*a, file=log); log.flush()
P("torch", torch.__version__, "size", os.path.getsize(f))
# исходники из пакета
z = zipfile.ZipFile(f)
for n in z.namelist():
    if n.endswith(".py") or n.endswith(".txt") or n.endswith(".json") or n.endswith(".yml"):
        d = os.path.join("out/src", n.replace("/", "__"))
        open(d, "wb").write(z.read(n))
P("files:", len(z.namelist()))
for n in z.namelist()[:400]:
    P("  ", n, z.getinfo(n).file_size)
imp = torch.package.PackageImporter(f)
m = imp.load_pickle("tts_models", "model")
P("type", type(m), type(m).__mro__)
for k, v in vars(m).items():
    s = repr(v)
    P("attr", k, type(v), s[:300].replace("\n", " "))
for k in dir(m):
    if not k.startswith("__"):
        P("dir", k)
try:
    P("speakers", getattr(m, "speakers", None))
except Exception as e:
    P("speakers err", e)
# скрипт-модули и их код
for k, v in vars(m).items():
    if isinstance(v, torch.jit.ScriptModule) or isinstance(v, torch.nn.Module):
        P("== module", k, type(v))
        try:
            open(f"out/code_{k}.txt", "w").write(v.code)
        except Exception as e:
            P("no code", e)
        try:
            for n2, sub in v.named_children():
                P("   child", n2, type(sub))
        except Exception as e:
            P("children err", e)
        try:
            P("   params", sum(p.numel() for p in v.parameters()))
        except Exception as e:
            P("params err", e)
        try:
            P("   methods", [x for x in dir(v) if not x.startswith("_")][:80])
        except Exception:
            pass
# пробный синтез с перехватом входов модели
calls = []
def wrap(mod, name):
    if not isinstance(mod, torch.jit.ScriptModule):
        return
    orig = mod.forward
for k, v in vars(m).items():
    if isinstance(v, torch.nn.Module):
        def hook(mod, args, kwargs=None, k=k):
            calls.append((k, [(type(a).__name__, tuple(a.shape) if hasattr(a, "shape") else repr(a)[:100], str(getattr(a, "dtype", ""))) for a in args]))
        try:
            v.register_forward_pre_hook(hook)
        except Exception as e:
            P("hook err", k, e)
try:
    a = m.apply_tts(text="Прив+ет, мир.", speaker="ru_albina", sample_rate=48000)
    P("audio", a.shape, a.dtype)
except Exception as e:
    P("apply err", traceback.format_exc())
P("calls", json.dumps(calls, ensure_ascii=False)[:3000])
try:
    src = inspect.getsource(type(m))
    open("out/model_class.py", "w").write(src)
except Exception as e:
    P("getsource err", e)
