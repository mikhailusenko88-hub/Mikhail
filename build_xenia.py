# Сборка голоса Барсика «xenia» (Silero v5_6_ru) для телефона: те же 4 части ONNX, что у «Альбины», в voice/xenia/
import os, json, time, gzip, random, re, urllib.request, wave, struct
import numpy as np, torch, torch.nn as nn, torch.nn.functional as F, onnxruntime as ort
torch.set_grad_enabled(False)
import inspect, traceback, hashlib
SPK = "xenia"; OUT = "vb"; VD = f"{OUT}/voice/xenia"; RD = f"{OUT}/refs/xenia"; os.makedirs(VD, exist_ok=True); os.makedirs(RD, exist_ok=True)
log = open(f"{RD}/build_xenia.log", "w")
def P(*a):
    print(*a); print(*a, file=log); log.flush()
f = "v5_6_ru.pt"
if not os.path.exists(f):
    urllib.request.urlretrieve("https://models.silero.ai/models/tts/ru/v5_6_ru.pt", f)
P("size", os.path.getsize(f))
m = torch.package.PackageImporter(f).load_pickle("tts_models", "model")
P("type", type(m), [k for k in dir(m) if not k.startswith("__")])
P("speakers", getattr(m, "speakers", None))
pack = m.packages[0] if hasattr(m, "packages") else m
P("pack", type(pack), [k for k in dir(pack) if not k.startswith("__")])
jm = pack.models[0]; P("jm", type(jm), [k for k, _ in jm.named_children()])
for nm, mod in [("jm", jm)] + list(jm.named_children()):
    try: open(f"{RD}/code_{nm}.txt", "w").write(mod.code)
    except Exception as e: P("code", nm, e)
try: P("prepare sig", inspect.signature(pack.prepare_tts_model_input))
except Exception as e: P("sig err", e)
P("speaker_to_ids", pack.speaker_to_ids)
tac, voc = jm.tacotron, jm.vocoder
spk_id = pack.speaker_to_ids[0][SPK]
def leaf(sm):
    n = sm.original_name
    if n == "Dropout": return nn.Identity()
    if n == "ReLU": return nn.ReLU()
    if n == "Conv1d":
        w = sm.weight; pad = sm.padding if isinstance(sm.padding, str) else sm.padding[0]
        c = nn.Conv1d(w.shape[1] * sm.groups, w.shape[0], w.shape[2], stride=sm.stride[0], padding=pad, dilation=sm.dilation[0], groups=sm.groups, bias=sm.bias is not None, padding_mode=sm.padding_mode)
    elif n == "Linear": c = nn.Linear(sm.weight.shape[1], sm.weight.shape[0], bias=sm.bias is not None)
    elif n == "LayerNorm": c = nn.LayerNorm(tuple(sm.normalized_shape), eps=sm.eps)
    elif n == "Embedding": c = nn.Embedding(sm.weight.shape[0], sm.weight.shape[1])
    elif n == "MultiheadAttention": c = nn.MultiheadAttention(sm.embed_dim, sm.num_heads, bias=sm.in_proj_bias is not None, batch_first=sm.batch_first)
    elif n == "AvgPool1d":
        ks = sm.kernel_size; st = sm.stride; pd = sm.padding
        c = nn.AvgPool1d(ks[0] if isinstance(ks, (list, tuple)) else ks, st[0] if isinstance(st, (list, tuple)) else st, pd[0] if isinstance(pd, (list, tuple)) else pd, sm.ceil_mode, sm.count_include_pad)
        return c
    else: raise ValueError("leaf " + n)
    c.load_state_dict({k: v for k, v in sm.state_dict().items()}); return c.eval()

class MHA(nn.Module):  # внимание «вручную» (то же, что nn.MultiheadAttention), чтобы переводилось в ONNX
    def __init__(s, sm):
        super().__init__(); s.h = int(sm.num_heads); s.d = int(sm.embed_dim)
        s.register_buffer("w", sm.in_proj_weight.detach().clone()); s.register_buffer("b", sm.in_proj_bias.detach().clone())
        s.out = nn.Linear(s.d, s.d); s.out.load_state_dict({"weight": sm.out_proj.weight.detach().clone(), "bias": sm.out_proj.bias.detach().clone()})
    def forward(s, x):
        B, T = x.size(0), x.size(1); hd = s.d // s.h
        q, k, v = F.linear(x, s.w, s.b).chunk(3, dim=-1)
        q = q.reshape(B, T, s.h, hd).transpose(1, 2); k = k.reshape(B, T, s.h, hd).transpose(1, 2); v = v.reshape(B, T, s.h, hd).transpose(1, 2)
        a = torch.softmax(torch.matmul(q, k.transpose(-1, -2)) / (hd ** 0.5), dim=-1)
        return s.out(torch.matmul(a, v).transpose(1, 2).reshape(B, T, s.d))
class PE(nn.Module):
    def __init__(s, sm): super().__init__(); s.register_buffer("scale", sm.scale.detach().clone()); s.register_buffer("pe", sm.pe.detach().clone())
    def forward(s, x): return x + s.scale * s.pe[:x.size(0)]
class FFT(nn.Module):
    def __init__(s, sm):
        super().__init__(); s.attn = MHA(sm.self_attn); P('mha batch_first', bool(sm.self_attn.batch_first)) if not hasattr(FFT, '_p') else None; FFT._p = 1; s.norm1 = leaf(sm.norm1); s.norm2 = leaf(sm.norm2); s.conv1 = leaf(sm.conv1); s.conv2 = leaf(sm.conv2)
        s.lin = bool(sm.use_linear); s.pp = bool(sm.pitch_pred)
    def forward(s, src):
        src = s.norm1(src + s.attn(src))
        s3 = src if s.lin else src.transpose(1, 2)
        y = s.conv2(F.relu(s.conv1(s3)))
        if s.pp:
            r = F.relu(y); s7 = s3 + r + r
        else:
            s7 = s3 + y
        s6 = s7 if s.lin else s7.transpose(1, 2)
        return s.norm2(s6)
class FT(nn.Module):
    def __init__(s, sm): super().__init__(); s.pe = PE(sm.pos_encoder); s.layers = nn.ModuleList([FFT(l) for _, l in sm.layers.named_children()]); s.norm = leaf(sm.norm)
    def forward(s, x):
        x = s.pe(x.transpose(0, 1)).transpose(0, 1)
        for l in s.layers: x = l(x)
        return s.norm(x)
class HG(nn.Module):
    def __init__(s, sm):
        super().__init__(); s.pe = PE(sm.pos_encoder); s.pre = FFT(getattr(sm.pre_vanilla_layers, '0')); s.sh1 = FFT(getattr(sm.shorten_layers, '1')); s.post = FFT(getattr(sm.post_vanilla_layers, '0')); s.norm = leaf(sm.norm)
        s.sf = int(sm.shorten_factor); s.pool = leaf(sm.downsample.avg_pool); s.proj = leaf(sm.upsample.proj); s.dim = int(sm.upsample.dim)
        P("HG shorten", s.sf, "pool", s.pool, "dim", s.dim, "n pre/short/post", [len(list(x.named_children())) for x in (sm.pre_vanilla_layers, sm.shorten_layers, sm.post_vanilla_layers)])
    def forward(s, x):
        L = x.size(1)
        x = s.pe(x.transpose(0, 1)).transpose(0, 1)
        x = s.pre(x)
        x = F.pad(x, (0, 0, 0, s.sf - 1))  # то же, что дополнение до кратного: лишние нули не попадают в окна
        d = s.pool(x.transpose(1, 2)).transpose(1, 2)
        u = s.proj(s.sh1(d)); u = u.view(u.size(0), -1, s.dim)  # слой shorten[0] в оригинале считается, но не используется
        x = (u[:, :L] + x[:, :L])
        return s.norm(s.post(x))
class Pred(nn.Module):   # у xenia к символам добавляются ещё тип предложения (вопрос/восклицание…) и «фокус» (0 — без выделения)
    def __init__(s, sm):
        super().__init__(); s.emb = leaf(sm.embedding); s.spe = leaf(sm.speaker_embedding); s.tr = FT(sm.transformer); s.lin = leaf(sm.lin)
        s.te = leaf(sm.type_embedding) if bool(sm.utt_type_emb) else None; s.fe = leaf(sm.focus_embedding) if bool(sm.focus_emb) else None
        P("pred: type", s.te is not None, sm.type_embedding.weight.shape if s.te is not None else None, "focus", s.fe is not None, "emph", bool(sm.emphasis_emb))
    def forward(s, x, spk, typ, foc):
        h = s.emb(x) + s.spe(spk).unsqueeze(1)
        if s.te is not None: h = h + s.te(typ)
        if s.fe is not None: h = h + s.fe(foc)
        return s.lin(s.tr(h))
class Front(nn.Module):
    def __init__(s): super().__init__(); s.dp = Pred(jm.dur_predictor.dur_pred); s.pp = Pred(jm.pitch_predictor.pitch_pred)
    def forward(s, seq, spk, typ, foc): return s.dp(seq, spk, typ, foc).squeeze(-1), s.pp(seq, spk, typ, foc).transpose(1, 2)
class Enc(nn.Module):
    def __init__(s):
        super().__init__(); s.emb = leaf(tac.embedding); s.spe = leaf(tac.speaker_embedding); s.enc = FT(tac.encoder); s.pproj = leaf(tac.pitch_proj); s.ps = float(tac.pitch_strength)
    def forward(s, seq, spk, pitch): return s.enc(s.emb(seq)) + s.spe(spk).unsqueeze(1) + s.pproj(pitch).transpose(1, 2) * s.ps
class Dec(nn.Module):
    def __init__(s): super().__init__(); s.dec = HG(tac.decoder); s.lin = leaf(tac.lin)
    def forward(s, x): return s.lin(s.dec(x)).transpose(1, 2)
class VocT(torch.nn.Module):
    def __init__(s, v): super().__init__(); s.bb = v.backbone; s.out = v.head.out
    def forward(s, mel: torch.Tensor):
        x = s.out(s.bb(mel)).transpose(1, 2)
        mag, p = torch.chunk(x, 2, 1)
        return torch.clamp(torch.exp(mag), max=100.), p

def seq_for(text, spk=SPK):
    sid = pack.speaker_to_ids[0][spk]
    import sys as _s
    sentences, clean, br, pr, pp, sp = pack.prepare_tts_model_input(text, ssml=False, speaker_ids=[sid], lang=None)
    seq, sd, dr, pc = pack.merge_batch_model(sentences, br, pr, pp, put_accent=False, put_stress_homo=False, put_yo=False, put_yo_homo=False)
    pkg = _s.modules[type(pack).__module__]; spans, stx = pack.token_sent_spans(seq[0])
    types = [pkg.classify_sentence(t.replace("+", "")) for t in stx]
    typ = pack.build_type_ids_tokens(seq[0], types, set()); foc = torch.zeros_like(seq)
    return seq, sp, typ, foc, types
fr, en, de = Front().eval(), Enc().eval(), Dec().eval()
vo = torch.jit.script(VocT(voc).eval())
seq, sp, typ, foc, _ = seq_for("Прив+ет! Ж+или-б+ыли кот и мыш+онок.")
ld, ph = fr(seq, sp, typ, foc); d = torch.clamp(torch.exp(ld) - 1, min=0).round()
e1 = en(seq, sp, ph); ex = torch.repeat_interleave(e1[0], d[0].long(), 0)[None]; mel = de(ex)
def exp(name, mod, args, ins, outs, dyn):
    path = f"{VD}/{name}.onnx"
    torch.onnx.export(mod, args, path, input_names=ins, output_names=outs, dynamic_axes=dyn, opset_version=17, do_constant_folding=True)
    P("export", name, round(os.path.getsize(path) / 1e6, 1), "MB")
    return ort.InferenceSession(path, providers=["CPUExecutionProvider"])
S = {"front": exp("front", fr, (seq, sp, typ, foc), ["seq", "spk", "typ", "foc"], ["logdur", "pitch"], {"seq": {1: "n"}, "typ": {1: "n"}, "foc": {1: "n"}, "logdur": {1: "n"}, "pitch": {2: "n"}}),
     "enc": exp("enc", en, (seq, sp, ph), ["seq", "spk", "pitch"], ["enc"], {"seq": {1: "n"}, "pitch": {2: "n"}, "enc": {1: "n"}}),
     "dec": exp("dec", de, (ex,), ["x"], ["mel"], {"x": {1: "t"}, "mel": {2: "t"}}),
     "voc": exp("voc", vo, (mel,), ["mel"], ["mag", "phase"], {"mel": {2: "t"}, "mag": {2: "f"}, "phase": {2: "f"}})}
ist = voc.head.istft
I = {"padding": ist.padding, "n_fft": int(ist.n_fft), "hop": int(ist.hop_length), "win": int(ist.win_length)}
W = ist.window.numpy().astype(np.float32)
tts_meta = {"symbols": pack.symbols, "symbol_to_id": pack.symbol_to_id, "sos": pack.sos_token, "eos": pack.eos_token, "alphabet": "".join(pack.alphabet),
            "speakers": pack.speaker_to_ids[0], "mean_std_coef": [float(x) for x in jm.mean_std_coef], "istft": I, "window": [float(x) for x in W], "sr": 48000,
            "rate2value": getattr(pack, "rate2value", None), "pitch2value": getattr(pack, "pitch2value", None), "model": "v5_6_ru", "speaker": SPK}
json.dump(tts_meta, open(f"{VD}/tts.json", "w"), ensure_ascii=False)
def istft_np(mag, ph):
    n_fft, hop, win = I["n_fft"], I["hop"], I["win"]
    S_ = mag[0] * np.exp(1j * ph[0]); T = S_.shape[1]
    fr_ = np.fft.irfft(S_, n=n_fft, axis=0).astype(np.float32) * W[:, None]
    pad = (win - hop) // 2
    out = np.zeros((T - 1) * hop + win, np.float32); env = np.zeros_like(out)
    for t in range(T):
        out[t * hop:t * hop + win] += fr_[:win, t]; env[t * hop:t * hop + win] += W ** 2
    return out[pad:-pad] / np.maximum(env[pad:-pad], 1e-11)
def durs(ld):
    d = np.round(np.maximum(np.exp(ld) - 1, 0))
    if d[0, 0] > 5: d[0, 0] = 5
    if d[0, -1] > 7: d[0, -1] = 7
    d[0, -2] = 13
    if d[0, -3] > 13: d[0, -3] = 13
    return d
tts_refs = []
for i, text in enumerate(["Прив+ет! +Я Б+арсик!", "+Ой... Кт+о +это т+ам шурш+ит в куст+ах?", "Пойд+ём посм+отрим! Ур+а!", "Прив+ет! Ж+или-б+ыли кот и мыш+онок.", "Т+ы пойдёшь с н+ами в л+ес?"]):
    seq, sp, typ, foc, types = seq_for(text); a = seq.numpy(); s = sp.numpy()
    ld, ph = S["front"].run(None, {"seq": a, "spk": s, "typ": typ.numpy(), "foc": foc.numpy()}); d = durs(ld)
    e = S["enc"].run(None, {"seq": a, "spk": s, "pitch": ph})[0]
    ex = np.repeat(e[0], d[0].astype(np.int64), axis=0)[None].astype(np.float32)
    mel = S["dec"].run(None, {"x": ex})[0]; mg, pz = S["voc"].run(None, {"mel": mel}); y = istft_np(mg, pz)
    try: ref = m.apply_tts(text=text, speaker=SPK, sample_rate=48000, put_accent=False, put_yo=False, put_stress_homo=False, put_yo_homo=False).numpy()
    except TypeError: ref = m.apply_tts(text=text, speaker=SPK, sample_rate=48000).numpy()
    n = min(len(ref), len(y)); c = float(np.corrcoef(ref[:n], y[:n])[0, 1])
    P(f"tts[{i}] corr {c:.5f} len {len(y)} ref {len(ref)}")
    with wave.open(f"{RD}/ref{i}.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes((np.clip(ref, -1, 1) * 32767).astype(np.int16).tobytes())
    tts_refs.append({"text": text, "ids": a[0].tolist(), "typ": typ[0].tolist(), "types": types, "durs": d[0].tolist(), "n": int(len(y)), "rms": float(np.sqrt(np.mean(y ** 2))), "head": [float(x) for x in y[2000:2064]]})
    with wave.open(f"{RD}/tts{i}.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())
json.dump(tts_refs, open(f"{RD}/tts.json", "w"), ensure_ascii=False)


# тот же ли вокодер, что у «Альбины» (тогда в приложение его второй раз не класть)
try:
    g = "v5_cis_base.pt"; urllib.request.urlretrieve("https://models.silero.ai/models/tts/ru/v5_cis_base.pt", g)
    m2 = torch.package.PackageImporter(g).load_pickle("tts_models", "model"); v2 = m2.packages[0].models[0].vocoder
    a, b = voc.state_dict(), v2.state_dict(); same = a.keys() == b.keys() and all(torch.equal(a[k], b[k]) for k in a)
    P("vocoder same as albina:", same)
    t2 = m2.packages[0].models[0].tacotron; a, b = tac.state_dict(), t2.state_dict(); P("tacotron same keys:", a.keys() == b.keys(), "shapes same:", all(a[k].shape == b[k].shape for k in a if k in b))
except Exception as e: P("compare err", e)
for k in sorted(os.listdir(VD)): P(k, os.path.getsize(f"{VD}/{k}"), hashlib.md5(open(f"{VD}/{k}", "rb").read()).hexdigest())
P("OK")
