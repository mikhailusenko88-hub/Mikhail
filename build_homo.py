# Омографы для телефона: BERT из silero-stress (MIT) → ONNX (без таблицы слов — она отдельно, int8) + фразы + словарь токенов
import os, json, re, numpy as np, torch, onnxruntime as ort
torch.set_grad_enabled(False)
OUT = "vb"; os.makedirs(f"{OUT}/voice", exist_ok=True); os.makedirs(f"{OUT}/refs", exist_ok=True)
log = open(f"{OUT}/build_homo.log", "w")
def P(*a):
    print(*a); print(*a, file=log); log.flush()
acc = torch.hub.load(repo_or_dir="snakers4/silero-stress", model="silero_stress", trust_repo=True)
hs = acc.homosolver; jb = hs.model.bert; head = hs.model.homo_clf; tok = hs.tokenizer
sd = {k: v.detach().clone() for k, v in jb.state_dict().items()}
for k, v in list(sd.items())[:12]: P("sd", k, tuple(v.shape), v.dtype)
P("n keys", len(sd), "scale", jb.scale, "zp", jb.zero_point)
V, H = sd["embeddings.word_embeddings.weight"].shape
L = len({k.split(".")[2] for k in sd if k.startswith("encoder.layer.")})
I = sd["encoder.layer.0.intermediate.dense.weight"].shape[0]
heads = int(getattr(jb.encoder.layer, "0").attention.self.num_attention_heads)
eps = float(jb.embeddings.LayerNorm.eps)
P("config V H L I heads eps", V, H, L, I, heads, eps, "pos", sd["embeddings.position_embeddings.weight"].shape, "tt", sd["embeddings.token_type_embeddings.weight"].shape)
from transformers import BertConfig, BertModel
cfg = BertConfig(vocab_size=V, hidden_size=H, num_hidden_layers=L, num_attention_heads=heads, intermediate_size=I,
                 max_position_embeddings=sd["embeddings.position_embeddings.weight"].shape[0], type_vocab_size=sd["embeddings.token_type_embeddings.weight"].shape[0],
                 layer_norm_eps=eps, hidden_act="gelu")
cfg._attn_implementation = "eager"
bm = BertModel(cfg, add_pooling_layer=any(k.startswith("pooler") for k in sd)).eval()
r = bm.load_state_dict({k: v for k, v in sd.items() if k not in ("scale", "zero_point")}, strict=False); P("load", r)
raw = "Вдали на холме стоял [HOMO] замок [/HOMO] старого короля."
ids_call = tok(raw); ids_enc = tok.encode(raw); P("tok call", type(ids_call).__name__, ids_call[:20] if isinstance(ids_call, list) else ids_call, "encode", ids_enc[:20], "same", ids_call == ids_enc)
ids = torch.tensor([ids_enc])
h1 = jb(ids)[0]; h2 = bm(input_ids=ids).last_hidden_state; P("hidden diff jit vs hf", float((h1 - h2).abs().max()))
W = sd["embeddings.word_embeddings.weight"].float()
h3 = bm(inputs_embeds=W[ids]).last_hidden_state; P("hidden diff inputs_embeds", float((h1 - h3).abs().max()))
class Wrap(torch.nn.Module):
    def __init__(s, m): super().__init__(); s.m = m
    def forward(s, emb): return s.m(inputs_embeds=emb).last_hidden_state
path = f"{OUT}/voice/homo.onnx"
torch.onnx.export(Wrap(bm).eval(), (W[ids],), path, input_names=["emb"], output_names=["hidden"], dynamic_axes={"emb": {1: "l"}, "hidden": {1: "l"}}, opset_version=17, do_constant_folding=True)
P("homo.onnx", round(os.path.getsize(path) / 1e6, 1), "MB")
so = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
h4 = so.run(None, {"emb": W[ids].numpy()})[0]; P("onnx diff", float(np.abs(h4 - h1.numpy()).max()))
# таблица слов int8 (как хранит silero: scale*(q - zp))
sc = float(jb.scale); zp = float(jb.zero_point)
q = np.round(W.numpy() / sc + zp); P("q range", q.min(), q.max())
dt = np.uint8 if q.min() >= 0 else np.int8
q.astype(dt).tofile(f"{OUT}/voice/homo_emb.q8"); back = (q - zp) * sc; P("emb dequant err", float(np.abs(back - W.numpy()).max()), "dtype", dt.__name__, "MB", round(os.path.getsize(f"{OUT}/voice/homo_emb.q8") / 1e6, 1))
def mlp(seqm):
    out = []
    for n, mod in seqm.named_children():
        on = mod.original_name
        if on == "Linear": out.append({"t": "lin", "w": mod.weight.detach().numpy().tolist(), "b": mod.bias.detach().numpy().tolist()})
        else: out.append({"t": on})
    return out
H_ = mlp(head); P("head", [(l["t"], (len(l["w"]), len(l["w"][0])) if l["t"] == "lin" else "") for l in H_])
vocab = [None] * len(tok.ids_to_tokens)
for i, t in tok.ids_to_tokens.items(): vocab[i] = t
meta = {"vocab": "\n".join(vocab), "never_split": sorted(tok.never_split), "ids": {"cls": tok.cls_token_id, "sep": tok.sep_token_id, "unk": tok.unk_token_id, "pad": tok.pad_token_id, "hs": tok.homo_start_id, "he": tok.homo_end_id},
        "scale": sc, "zp": zp, "dtype": dt.__name__, "H": int(H), "V": int(V), "head": H_, "window": hs.window_size,
        "phrases": {w: p.pattern for w, p in hs.compiled_phrases.items()}, "homodict": hs.homodict}
json.dump(meta, open(f"{OUT}/voice/homo.json", "w"), ensure_ascii=False)
P("homo.json MB", round(os.path.getsize(f"{OUT}/voice/homo.json") / 1e6, 2))
sents = ["Вдали на холме стоял старый замок короля.", "Барсик повесил на дверь большой замок и закрыл его ключом.", "Солнышко село за горизонт.", "Мы приехали в большое село у реки.",
         "Ужин готов, садитесь за стол!", "Пик был готов ко всему.", "Мука для пирога лежала на столе.", "Это была настоящая мука — ждать так долго.",
         "Все пошли гулять, а всё остальное подождёт.", "Рон стоял у дороги и ждал друзей.", "Друзья вышли на берег и увидели белый парус.", "В лесу пахнет грибами и хвоей.",
         "Кот Барсик плачет: где наш торт?", "Пик открыл дверцу и выглянул наружу.", "Над озером кружили белые птицы."]
refs = []
for s in sents:
    tagged = hs._find_and_tag_homos(s)
    marks = [t[4] for t in tagged if t[4] is not None]
    refs.append({"text": s, "homo": hs(s), "full": acc(s), "marks": marks, "ids": [tok(mk) for mk in marks]})
json.dump(refs, open(f"{OUT}/refs/homo.json", "w"), ensure_ascii=False)
for r_ in refs: P(r_["full"])
P("done")
