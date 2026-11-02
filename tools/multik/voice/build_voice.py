# Сборка «Альбины» для телефона: TTS в ONNX (4 части) + данные ударений silero-stress + эталоны для проверки JS
import os, json, time, gzip, random, re, urllib.request, wave, struct
import numpy as np, torch, torch.nn as nn, torch.nn.functional as F, onnxruntime as ort
torch.set_grad_enabled(False)
OUT = "vb"; os.makedirs(f"{OUT}/voice", exist_ok=True); os.makedirs(f"{OUT}/refs", exist_ok=True)
log = open(f"{OUT}/build.log", "w")
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

def seq_for(text, spk="ru_albina"):
    sid = pack.speaker_to_ids[0][spk]
    sentences, clean, br, pr, pp, sp = pack.prepare_tts_model_input(text, ssml=False, speaker_ids=[sid], lang="ru")
    seq, sd, dr, pc = pack.merge_batch_model(sentences, br, pr, pp)
    return seq, sp
fr, en, de = Front().eval(), Enc().eval(), Dec().eval()
vo = torch.jit.script(VocT(voc).eval())
seq, sp = seq_for("Прив+ет! Ж+или-б+ыли кот и мыш+онок.")
ld, ph = fr(seq, sp); d = torch.clamp(torch.exp(ld) - 1, min=0).round()
e1 = en(seq, sp, ph); ex = torch.repeat_interleave(e1[0], d[0].long(), 0)[None]; mel = de(ex)
def exp(name, mod, args, ins, outs, dyn):
    path = f"{OUT}/voice/{name}.onnx"
    torch.onnx.export(mod, args, path, input_names=ins, output_names=outs, dynamic_axes=dyn, opset_version=17, do_constant_folding=True)
    P("export", name, round(os.path.getsize(path) / 1e6, 1), "MB")
    return ort.InferenceSession(path, providers=["CPUExecutionProvider"])
S = {"front": exp("front", fr, (seq, sp), ["seq", "spk"], ["logdur", "pitch"], {"seq": {1: "n"}, "logdur": {1: "n"}, "pitch": {2: "n"}}),
     "enc": exp("enc", en, (seq, sp, ph), ["seq", "spk", "pitch"], ["enc"], {"seq": {1: "n"}, "pitch": {2: "n"}, "enc": {1: "n"}}),
     "dec": exp("dec", de, (ex,), ["x"], ["mel"], {"x": {1: "t"}, "mel": {2: "t"}}),
     "voc": exp("voc", vo, (mel,), ["mel"], ["mag", "phase"], {"mel": {2: "t"}, "mag": {2: "f"}, "phase": {2: "f"}})}
ist = voc.head.istft
I = {"padding": ist.padding, "n_fft": int(ist.n_fft), "hop": int(ist.hop_length), "win": int(ist.win_length)}
W = ist.window.numpy().astype(np.float32)
tts_meta = {"symbols": pack.symbols, "symbol_to_id": pack.symbol_to_id, "sos": pack.sos_token, "eos": pack.eos_token, "alphabet": "".join(pack.alphabet),
            "speakers": pack.speaker_to_ids[0], "mean_std_coef": [float(x) for x in jm.mean_std_coef], "istft": I, "window": [float(x) for x in W], "sr": 48000,
            "rate2value": pack.rate2value, "pitch2value": pack.pitch2value}
json.dump(tts_meta, open(f"{OUT}/voice/tts.json", "w"), ensure_ascii=False)
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
for i, text in enumerate(["Прив+ет! Ж+или-б+ыли кот и мыш+онок.", "+Утром друзь+я отпр+авились в л+ес з+а гриб+ами.", "Вдр+уг +из-з+а +ёлки посл+ышался стр+анный ш+орох, +и вс+е з+амерли."]):
    seq, sp = seq_for(text); a = seq.numpy(); s = sp.numpy()
    ld, ph = S["front"].run(None, {"seq": a, "spk": s}); d = durs(ld)
    e = S["enc"].run(None, {"seq": a, "spk": s, "pitch": ph})[0]
    ex = np.repeat(e[0], d[0].astype(np.int64), axis=0)[None].astype(np.float32)
    mel = S["dec"].run(None, {"x": ex})[0]; mg, pz = S["voc"].run(None, {"mel": mel}); y = istft_np(mg, pz)
    ref = m.apply_tts(text=text, speaker="ru_albina", sample_rate=48000).numpy()
    n = min(len(ref), len(y)); c = float(np.corrcoef(ref[:n], y[:n])[0, 1])
    P(f"tts[{i}] corr {c:.5f} len {len(y)} ref {len(ref)}")
    tts_refs.append({"text": text, "ids": a[0].tolist(), "durs": d[0].tolist(), "n": int(len(y)), "rms": float(np.sqrt(np.mean(y ** 2))), "head": [float(x) for x in y[2000:2064]]})
    with wave.open(f"{OUT}/refs/tts{i}.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())
json.dump(tts_refs, open(f"{OUT}/refs/tts.json", "w"), ensure_ascii=False)

# ---------- ударения: silero-stress (MIT) ----------
acc = torch.hub.load(repo_or_dir="snakers4/silero-stress", model="silero_stress", trust_repo=True)
A = acc.accentor; mdl = A.model
emb = mdl.embedding.weight.detach().float().numpy()
P("emb", emb.shape, float(np.abs(emb).max()))
ng = sorted(mdl.embedding.ngram_dict.items(), key=lambda kv: kv[1])
assert [i for _, i in ng] == list(range(len(ng))), "ngram ids not dense"
def mlp(seqm):
    L = []
    for _, mod in seqm.named_children():
        if mod.original_name == "Linear": L.append({"w": mod.weight.detach().numpy().tolist(), "b": mod.bias.detach().numpy().tolist()})
    return L
stress_data = {"ngrams": "\n".join(g for g, _ in ng), "emb_dim": int(emb.shape[1]), "n_emb": int(emb.shape[0]),
               "stress": mlp(mdl.stress_clf), "yo": mlp(mdl.yo_clf), "exceptions": {k: list(v) for k, v in A.exceptions.items()},
               "homodict": acc.homosolver.homodict, "yohomodict": acc.homosolver.yohomodict, "vowels": A.vowels}
json.dump(stress_data, open(f"{OUT}/voice/stress.json", "w"), ensure_ascii=False)
emb.astype(np.float16).tofile(f"{OUT}/voice/stress_emb.f16")
P("stress.json", round(os.path.getsize(f"{OUT}/voice/stress.json") / 1e6, 2), "MB; emb", round(os.path.getsize(f"{OUT}/voice/stress_emb.f16") / 1e6, 2), "MB")
# numpy-копия модели ударений (то же будет в JS) и сверка
E16 = emb.astype(np.float16).astype(np.float32); G = {g: i for g, i in ng}
def ngrams(w):
    t = "<" + w + ">"; out = []
    for n in range(1, len(w) + 4):
        for i in range(len(t) - n + 1): out.append(t[i:i + n])
    if len(w) < 1: out.append(w)
    return out
def run_mlp(L, x):
    for k, l in enumerate(L):
        x = np.array(l["w"], np.float32) @ x + np.array(l["b"], np.float32)
        if k < len(L) - 1: x = np.maximum(x, 0)
    return x
def predict(w):
    ids = [G[g] for g in ngrams(w) if g in G] or [G["UNK"]]
    v = E16[ids].mean(0)
    return int(np.argmax(run_mlp(stress_data["stress"], v))), int(np.argmax(run_mlp(stress_data["yo"], v)))
words = [w for w in acc.homosolver.tokenizer.vocab.keys() if re.fullmatch(r"[а-яё]{2,}", w)]
random.seed(1); words = random.sample(words, min(3000, len(words)))
st, yo = mdl(words); st = st.argmax(1).tolist(); yo = yo.argmax(1).tolist()
bad = sum(1 for w, a, b in zip(words, st, yo) if predict(w) != (a, b))
P("stress numpy vs torch: mismatches", bad, "of", len(words))
sents = ["Меня зовут Лёва Королёв. Я из готов. И я уже готов открыть все ваши замки любой сложности!",
         "Утром друзья отправились в лес за грибами. Вдруг из-за ёлки послышался странный шорох.",
         "На холме стоял старый замок. Барсик, Пик и Рон пошли к замку.", "Жили-были в маленьком домике кот Барсик, мышонок Пик и пёс Рон.",
         "Кто-то постучал в дверь. Что-нибудь случилось? Нет, всё хорошо!", "Солнышко село за горизонт, и звёзды зажглись на небе.",
         "Барсик достал из рюкзака карту и бинокль.", "Друзья шли по тропинке, а ветер шумел в листве деревьев."]
json.dump([{"text": s, "ngram": A(s), "full": acc(s)} for s in sents], open(f"{OUT}/refs/stress.json", "w"), ensure_ascii=False)
json.dump([{"w": w, "s": a, "y": b} for w, a, b in zip(words[:500], st[:500], yo[:500])], open(f"{OUT}/refs/stress_words.json", "w"), ensure_ascii=False)
P("done")
