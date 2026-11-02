# Разведка silero-stress: из чего состоит, сколько весит, как хранит словарь
import os, sys, json, time, traceback, pickle
import torch
log = open("out/probe4.txt", "w")
def P(*a):
    print(*a); print(*a, file=log); log.flush()
t0 = time.time()
acc = torch.hub.load(repo_or_dir="snakers4/silero-stress", model="silero_stress", trust_repo=True)
P("load", round(time.time() - t0, 1), "s", type(acc))
hub = torch.hub.get_dir(); 
for root, ds, fs in os.walk(hub):
    for f in fs:
        p = os.path.join(root, f); P("file", p.replace(hub, "HUB"), os.path.getsize(p))
def show(o, name, depth=0):
    if depth > 3: return
    for k, v in (vars(o).items() if hasattr(o, "__dict__") else []):
        s = type(v).__name__
        extra = ""
        if isinstance(v, (dict, list, set, tuple)): extra = f" len={len(v)}"
        if isinstance(v, torch.Tensor): extra = f" shape={tuple(v.shape)} {v.dtype}"
        if isinstance(v, torch.nn.Module): extra = f" params={sum(p.numel() for p in v.parameters())}"
        P("  " * depth + f"{name}.{k}: {s}{extra}")
        if isinstance(v, dict) and len(v) > 0:
            it = list(v.items())[:5]; P("  " * depth + "   sample", repr(it)[:400])
        if hasattr(v, "__dict__") and not isinstance(v, (torch.Tensor,)) and type(v).__module__ not in ("builtins",):
            show(v, f"{name}.{k}", depth + 1)
show(acc, "acc")
for s in ["Меня зовут Лёва Королёв. Я из готов. И я уже готов открыть все ваши замки любой сложности!",
          "Утром друзья отправились в лес за грибами. Вдруг из-за ёлки послышался странный шорох.",
          "На холме стоял старый замок. Барсик, Пик и Рон пошли к замку."]:
    t0 = time.time(); r = acc(s); P("acc", round(time.time() - t0, 3), r)
try:
    import inspect
    open("out/stress_src.py", "w").write(inspect.getsource(type(acc)))
except Exception as e:
    P("src err", e)
