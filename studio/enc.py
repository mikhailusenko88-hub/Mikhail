"""Двухпроходная нормализация громкости (linear, без сжатия динамики) и AAC 256k: python3 enc.py in.wav out.m4a [-14]"""
import json, subprocess, sys
src, dst = sys.argv[1], sys.argv[2]
I = sys.argv[3] if len(sys.argv) > 3 else "-14"
r = subprocess.run(["ffmpeg", "-hide_banner", "-i", src, "-af", f"loudnorm=I={I}:TP=-1.2:LRA=14:print_format=json", "-f", "null", "-"],
                   capture_output=True, text=True).stderr
j = json.loads(r[r.rindex("{"):r.rindex("}") + 1])
af = (f"loudnorm=I={I}:TP=-1.2:LRA=14:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
      f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af", af, "-ar", "44100", "-c:a", "aac", "-b:a", "256k", dst], check=True)
o = subprocess.run(["ffmpeg", "-hide_banner", "-i", dst, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
print(dst, [l.strip() for l in o.splitlines() if l.strip().startswith(("I:", "LRA:", "Peak:"))][-3:])
