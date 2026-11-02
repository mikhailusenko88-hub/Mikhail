# Перевод Silero v5_cis_base (ru_albina) в ONNX: 4 части + сверка с оригиналом
import os, json, time, traceback, urllib.request
import numpy as np, torch, onnxruntime as ort
os.makedirs("out/onnx", exist_ok=True)
log = open("out/probe2.txt", "w")
def P(*a):
    print(*a); print(*a, file=log); log.flush()
f = "v5_cis_base.pt"
if not os.path.exists(f):
    urllib.request.urlretrieve("https://models.silero.ai/models/tts/ru/v5_cis_base.pt", f)
P("torch", torch.__version__, "ort", ort.__version__)
m = torch.package.PackageImporter(f).load_pickle("tts_models", "model")
pack = m.packages[0]; jm = pack.models[0]
P("accentor", type(pack.accentor), "phons", pack.phons, "models", len(pack.models))
spk_id = pack.speaker_to_ids[0]["ru_albina"]
P("albina id", spk_id, "n speakers", len(pack.speaker_to_ids[0]))
tac, voc = jm.tacotron, jm.vocoder
ist = voc.head.istft
meta = {"symbol_to_id": pack.symbol_to_id, "symbols": pack.symbols, "alphabet": "".join(pack.alphabet), "sos": pack.sos_token, "eos": pack.eos_token,
        "speakers": pack.speaker_to_ids[0], "ext_alph_ru": (pack.ext_alph or {}).get("ru"),
        "pitch_emb_type": tac.pitch_emb_type, "pitch_strength": tac.pitch_strength, "log_dur": tac.log_dur,
        "istft": {"padding": ist.padding, "n_fft": ist.n_fft, "hop": ist.hop_length, "win": ist.win_length, "window": ist.window.tolist()},
        "punkt_symbols": list(jm.punkt_symbols), "sil_value": jm.sil_value, "mean_std_coef_albina": jm.mean_std_coef[spk_id] if spk_id < len(jm.mean_std_coef) else None}
json.dump(meta, open("out/meta.json", "w"), ensure_ascii=False)
P("pitch_emb_type", tac.pitch_emb_type, "istft", ist.padding, ist.n_fft, ist.hop_length, ist.win_length)

from typing import Tuple
class Front(torch.nn.Module):
    def __init__(s, dp, pp): super().__init__(); s.dp = dp; s.pp = pp
    def forward(s, seq: torch.Tensor, spk: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        mask = torch.eq(seq, 0)
        return s.dp(seq, spk, mask, 1.0, None), s.pp(seq, spk, mask, 1.0)
class Enc(torch.nn.Module):
    def __init__(s, t):
        super().__init__(); s.emb = t.embedding; s.spe = t.speaker_embedding; s.enc = t.encoder; s.pproj = t.pitch_proj; s.ps = float(t.pitch_strength)
    def forward(s, seq: torch.Tensor, spk: torch.Tensor, pitch: torch.Tensor) -> torch.Tensor:
        mask = torch.eq(seq, 0)
        x = s.emb(seq)
        se = s.spe(spk).unsqueeze(1).expand(-1, x.size(1), -1)
        enc = s.enc(x, mask, None) + se
        return enc + s.pproj(pitch).transpose(1, 2) * s.ps
class Dec(torch.nn.Module):
    def __init__(s, t): super().__init__(); s.dec = t.decoder; s.lin = t.lin
    def forward(s, x: torch.Tensor) -> torch.Tensor:
        return s.lin(s.dec(x, None, None)).transpose(1, 2)
class Voc(torch.nn.Module):
    def __init__(s, v): super().__init__(); s.bb = v.backbone; s.out = v.head.out
    def forward(s, mel: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        x = s.out(s.bb(mel)).transpose(1, 2)
        mag, p = torch.chunk(x, 2, 1)
        return torch.clamp(torch.exp(mag), max=100.), p

def seq_for(text):
    sentences, clean, br, pr, pp, sp = pack.prepare_tts_model_input(text, ssml=False, speaker_ids=[spk_id], lang="ru")
    seq, sd, dr, pc = pack.merge_batch_model(sentences, br, pr, pp)
    return seq, sp
seq, sp = seq_for("Прив+ет! Ж+или-б+ыли кот и мыш+онок.")
P("seq", seq.shape, seq.tolist())
fr, en, de, vo = [torch.jit.script(x.eval()) for x in (Front(jm.dur_predictor, jm.pitch_predictor), Enc(tac), Dec(tac), Voc(voc))]
with torch.no_grad():
    ld, ph = fr(seq, sp); P("logdur", ld.shape, "pitch", ph.shape)
    d = torch.clamp(torch.exp(ld) - 1, min=0).round()
    e = en(seq, sp, ph); P("enc", e.shape)
    ex = torch.repeat_interleave(e[0], d[0].long(), 0)[None]
    mel = de(ex); P("mel", mel.shape)
    mg, pz = vo(mel); P("mag", mg.shape)
def exp(name, mod, args, ins, outs, dyn):
    path = f"out/onnx/{name}.onnx"
    try:
        t0 = time.time()
        torch.onnx.export(mod, args, path, input_names=ins, output_names=outs, dynamic_axes=dyn, opset_version=17, do_constant_folding=True)
        P("export", name, "ok", round(time.time() - t0, 1), "s", round(os.path.getsize(path) / 1e6, 1), "MB")
        return ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    except Exception:
        P("export", name, "FAIL", traceback.format_exc()[-3000:])
        return None
S = {}
with torch.no_grad():
    S["front"] = exp("front", fr, (seq, sp), ["seq", "spk"], ["logdur", "pitch"], {"seq": {1: "n"}, "logdur": {1: "n"}, "pitch": {2: "n"}})
    S["enc"] = exp("enc", en, (seq, sp, ph), ["seq", "spk", "pitch"], ["enc"], {"seq": {1: "n"}, "pitch": {2: "n"}, "enc": {1: "n"}})
    S["dec"] = exp("dec", de, (ex,), ["x"], ["mel"], {"x": {1: "t"}, "mel": {2: "t"}})
    S["voc"] = exp("voc", vo, (mel,), ["mel"], ["mag", "phase"], {"mel": {2: "t"}, "mag": {2: "f"}, "phase": {2: "f"}})

def istft_np(mag, ph):  # то же, что будет на телефоне
    I = meta["istft"]; n_fft, hop, win = I["n_fft"], I["hop"], I["win"]; w = np.array(I["window"], dtype=np.float32)
    S_ = mag[0] * np.exp(1j * ph[0])  # [F, T]
    T = S_.shape[1]
    fr_ = np.fft.irfft(S_, n=n_fft, axis=0).astype(np.float32) * w[:, None]
    if I["padding"] == "same":
        pad = (win - hop) // 2
        out = np.zeros((T - 1) * hop + win, np.float32); env = np.zeros_like(out)
        for t in range(T):
            out[t * hop:t * hop + win] += fr_[:win, t]; env[t * hop:t * hop + win] += w ** 2
        y = out[pad:-pad] / np.maximum(env[pad:-pad], 1e-11)
        return y
    return None

def pipeline(text):
    seq, sp = seq_for(text)
    a = seq.numpy(); s = sp.numpy()
    t0 = time.time()
    ld, ph = S["front"].run(None, {"seq": a, "spk": s})
    d = np.round(np.maximum(np.exp(ld) - 1, 0))
    if d[0, 0] > 5: d[0, 0] = 5
    if d[0, -1] > 7: d[0, -1] = 7
    d[0, -2] = 13
    if d[0, -3] > 13: d[0, -3] = 13
    e = S["enc"].run(None, {"seq": a, "spk": s, "pitch": ph})[0]
    ex = np.repeat(e[0], d[0].astype(np.int64), axis=0)[None].astype(np.float32)
    mel = S["dec"].run(None, {"x": ex})[0]
    mg, pz = S["voc"].run(None, {"mel": mel})
    y = istft_np(mg, pz)
    return y, time.time() - t0, d
if all(S.values()):
    for i, text in enumerate(["Прив+ет! Ж+или-б+ыли кот и мыш+онок.", "+Утром друзь+я отпр+авились в л+ес за гриб+ами.", "Вдр+уг из-за +ёлки послышался стр+анный ш+орох, и все з+амерли."]):
        ref = m.apply_tts(text=text, speaker="ru_albina", sample_rate=48000).numpy()
        y, dt, d = pipeline(text)
        n = min(len(ref), len(y))
        c = float(np.corrcoef(ref[:n], y[:n])[0, 1]) if n > 100 else 0
        P(f"[{i}] ref {len(ref)} onnx {len(y)} corr {c:.4f} maxdiff {float(np.max(np.abs(ref[:n]-y[:n]))):.4f} time {dt:.2f}s audio {len(y)/48000:.2f}s")
        import wave
        for nm, x in (("ref", ref), ("onnx", y)):
            with wave.open(f"out/{nm}{i}.wav", "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
