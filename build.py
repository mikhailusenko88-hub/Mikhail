import json, subprocess, sys
sys.path.insert(0, '/root/clips-bot')
import make_video as mv
cfg = json.load(open('/root/clips-bot/config.json', encoding='utf-8'))
cfg['use_stock_video'] = False
s = json.load(open('script.json', encoding='utf-8'))
def tts(text, voice, rate, path):
    i = s['lines'].index(text)
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', f'l{i:02d}.wav', '-c:a', 'libmp3lame', '-b:a', '128k', str(path)], check=True)
mv.build(s, cfg, '/root/silero-test/out.mp4', '/root/silero-test/work', tts=tts)
