# На кого похож голос: отпечаток говорящего (ECAPA, speechbrain) каждой записи, сходство с исходными дикторами.
#   python spk_sim.py <папка с v/*.mp3> <out.json>
import sys, os, json, glob, subprocess, numpy as np, torch
from speechbrain.inference.speaker import EncoderClassifier
src, out = sys.argv[1], sys.argv[2]
m = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb", savedir="/tmp/ecapa", run_opts={"device": "cpu"})
E = {}
for p in sorted(glob.glob(f"{src}/v/*.mp3")):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
    x = torch.from_numpy(np.frombuffer(raw, np.float32).copy()).unsqueeze(0)
    with torch.no_grad(): e = m.encode_batch(x).squeeze().numpy()
    E[os.path.basename(p)[:-4]] = (e / np.linalg.norm(e)).tolist()
json.dump(E, open(out, "w"))
print(len(E), "отпечатков")
