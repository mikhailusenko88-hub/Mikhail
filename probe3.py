# Альбина → ONNX: части переписаны «обычным» PyTorch с весами из модели Silero, затем экспорт и сверка с оригиналом
import os, json, time, traceback, urllib.request, wave
import numpy as np, torch, torch.nn as nn, torch.nn.functional as F, onnxruntime as ort
torch.set_grad_enabled(False)
os.makedirs("out/onnx", exist_ok=True)
log = open("out/probe3.txt", "w")
def P(*a):
    print(*a); print(*a, file=log); log.flush()
f = "v5_cis_base.pt"
if not os.path.exists(f):
    urllib.request.urlretrieve("https://models.silero.ai/models/tts/ru/v5_cis_base.pt", f)
m = torch.package.PackageImporter(f).load_pickle("tts_models", "model")
pack = m.packages[0]; jm = pack.models[0]; tac, voc = jm.tacotron, jm.vocoder
spk_id = pack.speaker_to_ids[0]["ru_albina"]

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

class PE(nn.Module):
    def __init__(s, sm): super().__init__(); s.register_buffer("scale", sm.scale.detach().clone()); s.register_buffer("pe", sm.pe.detach().clone())
    def forward(s, x): return x + s.scale * s.pe[:x.size(0)]
class FFT(nn.Module):
    def __init__(s, sm):
        super().__init__(); s.attn = leaf(sm.self_attn); s.norm1 = leaf(sm.norm1); s.norm2 = leaf(sm.norm2); s.conv1 = leaf(sm.conv1); s.conv2 = leaf(sm.conv2)
        s.lin = bool(sm.use_linear); s.pp = bool(sm.pitch_pred)
    def forward(s, src):
        src = s.norm1(src + s.attn(src, src, src, need_weights=True)[0])
        s3 = src if s.lin else src.transpose(1, 2)
        y = s.conv2(F.relu(s.conv1(s3)))
        if s.pp:
            r = F.relu(y); s7 = s3 + r + r
        else:
            s7 = s3 + y
        s6 = s7 if s.lin else s7.transpose(1, 2)
        return s.norm2(s6)
class FT(nn.Module):
    def __init__(s, sm): super().__init__(); s.pe = PE(sm.pos_encoder); s.layers = nn.ModuleList([FFT(l) for l in sm.layers]); s.norm = leaf(sm.norm)
    def forward(s, x):
        x = s.pe(x.transpose(0, 1)).transpose(0, 1)
        for l in s.layers: x = l(x)
        return s.norm(x)
class HG(nn.Module):
    def __init__(s, sm):
        super().__init__(); s.pe = PE(sm.pos_encoder); s.pre = FFT(sm.pre_vanilla_layers[0]); s.sh1 = FFT(sm.shorten_layers[1]); s.post = FFT(sm.post_vanilla_layers[0]); s.norm = leaf(sm.norm)
        s.sf = int(sm.shorten_factor); s.pool = leaf(sm.downsample.avg_pool); s.proj = leaf(sm.upsample.proj); s.dim = int(sm.upsample.dim)
        P("HG shorten", s.sf, "pool", s.pool, "dim", s.dim, "n pre/short/post", len(sm.pre_vanilla_layers), len(sm.shorten_layers), len(sm.post_vanilla_layers))
    def forward(s, x):
        L = x.size(1)
        x = s.pe(x.transpose(0, 1)).transpose(0, 1)
        x = s.pre(x)
        x = F.pad(x, (0, 0, 0, s.sf - 1))  # то же, что дополнение до кратного: лишние нули не попадают в окна
        d = s.pool(x.transpose(1, 2)).transpose(1, 2)
        u = s.proj(s.sh1(d)); u = u.view(u.size(0), -1, s.dim)  # слой shorten[0] в оригинале считается, но не используется
        x = (u[:, :L] + x[:, :L])
        return s.norm(s.post(x))
class Pred(nn.Module):
    def __init__(s, sm): super().__init__(); s.emb = leaf(sm.embedding); s.spe = leaf(sm.speaker_embedding); s.tr = FT(sm.transformer); s.lin = leaf(sm.lin)
    def forward(s, x, spk): return s.lin(s.tr(s.emb(x) + s.spe(spk).unsqueeze(1)))
class Front(nn.Module):
    def __init__(s): super().__init__(); s.dp = Pred(jm.dur_predictor.dur_pred); s.pp = Pred(jm.pitch_predictor.pitch_pred)
    def forward(s, seq, spk): return s.dp(seq, spk).squeeze(-1), s.pp(seq, spk).transpose(1, 2)
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

def seq_for(text):
    sentences, clean, br, pr, pp, sp = pack.prepare_tts_model_input(text, ssml=False, speaker_ids=[spk_id], lang="ru")
    seq, sd, dr, pc = pack.merge_batch_model(sentences, br, pr, pp)
    return seq, sp
fr, en, de = Front().eval(), Enc().eval(), Dec().eval()
vo = torch.jit.script(VocT(voc).eval())
# 1) сверка «обычного» PyTorch с оригинальными частями
seq, sp = seq_for("Прив+ет! Ж+или-б+ыли кот и мыш+онок.")
mask = torch.eq(seq, 0)
ld0 = jm.dur_predictor(seq, sp, mask, 1.0, None); ph0 = jm.pitch_predictor(seq, sp, mask, 1.0)
ld1, ph1 = fr(seq, sp)
P("dur diff", float((ld0 - ld1).abs().max()), "pitch diff", float((ph0 - ph1).abs().max()))
d = torch.clamp(torch.exp(ld0) - 1, min=0).round()
for n_extra in (0, 1, 2, 3):
    dd = d.clone(); dd[0, 5] += n_extra
    mel0 = tac(seq, sp, mask, dd, ph0, None)
    e1 = en(seq, sp, ph0); ex = torch.repeat_interleave(e1[0], dd[0].long(), 0)[None]; mel1 = de(ex)
    P("frames", ex.shape[1], "mel diff", float((mel0 - mel1).abs().max()), "mel scale", float(mel0.abs().max()))

def exp(name, mod, args, ins, outs, dyn):
    path = f"out/onnx/{name}.onnx"
    try:
        t0 = time.time()
        torch.onnx.export(mod, args, path, input_names=ins, output_names=outs, dynamic_axes=dyn, opset_version=17, do_constant_folding=True)
        P("export", name, "ok", round(time.time() - t0, 1), "s", round(os.path.getsize(path) / 1e6, 1), "MB")
        return ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    except Exception:
        P("export", name, "FAIL", traceback.format_exc()[-2500:])
        return None
e1 = en(seq, sp, ph0); ex = torch.repeat_interleave(e1[0], d[0].long(), 0)[None]; mel = de(ex)
S = {"front": exp("front", fr, (seq, sp), ["seq", "spk"], ["logdur", "pitch"], {"seq": {1: "n"}, "logdur": {1: "n"}, "pitch": {2: "n"}}),
     "enc": exp("enc", en, (seq, sp, ph0), ["seq", "spk", "pitch"], ["enc"], {"seq": {1: "n"}, "pitch": {2: "n"}, "enc": {1: "n"}}),
     "dec": exp("dec", de, (ex,), ["x"], ["mel"], {"x": {1: "t"}, "mel": {2: "t"}}),
     "voc": exp("voc", vo, (mel,), ["mel"], ["mag", "phase"], {"mel": {2: "t"}, "mag": {2: "f"}, "phase": {2: "f"}})}
ist = voc.head.istft
I = {"padding": ist.padding, "n_fft": int(ist.n_fft), "hop": int(ist.hop_length), "win": int(ist.win_length)}
W = ist.window.numpy().astype(np.float32)
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
def pipeline(text):
    seq, sp = seq_for(text); a = seq.numpy(); s = sp.numpy(); T = {}
    t0 = time.time(); ld, ph = S["front"].run(None, {"seq": a, "spk": s}); T["front"] = time.time() - t0
    d = durs(ld)
    t0 = time.time(); e = S["enc"].run(None, {"seq": a, "spk": s, "pitch": ph})[0]; T["enc"] = time.time() - t0
    ex = np.repeat(e[0], d[0].astype(np.int64), axis=0)[None].astype(np.float32)
    t0 = time.time(); mel = S["dec"].run(None, {"x": ex})[0]; T["dec"] = time.time() - t0
    t0 = time.time(); mg, pz = S["voc"].run(None, {"mel": mel}); T["voc"] = time.time() - t0
    t0 = time.time(); y = istft_np(mg, pz); T["istft"] = time.time() - t0
    return y, T
if all(S.values()):
    json.dump({"istft": I, "window": W.tolist(), "symbol_to_id": pack.symbol_to_id, "sos": pack.sos_token, "eos": pack.eos_token, "symbols": pack.symbols,
               "speakers": pack.speaker_to_ids[0], "ext_alph": pack.ext_alph}, open("out/meta.json", "w"), ensure_ascii=False)
    for i, text in enumerate(["Прив+ет! Ж+или-б+ыли кот и мыш+онок.", "+Утром друзь+я отпр+авились в л+ес за гриб+ами.", "Вдр+уг из-за +ёлки посл+ышался стр+анный ш+орох, и вс+е з+амерли."]):
        ref = m.apply_tts(text=text, speaker="ru_albina", sample_rate=48000).numpy()
        y, T = pipeline(text)
        n = min(len(ref), len(y)); c = float(np.corrcoef(ref[:n], y[:n])[0, 1])
        P(f"[{i}] ref {len(ref)} onnx {len(y)} corr {c:.5f} maxdiff {float(np.max(np.abs(ref[:n] - y[:n]))):.5f} audio {len(y) / 48000:.2f}s times", {k: round(v, 3) for k, v in T.items()})
        for nm, x in (("ref", ref), ("onnx", y)):
            with wave.open(f"out/{nm}{i}.wav", "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
# Mon Nov  2 22:23:40 MSK 2026
