// Замер Кисти 4 на Mac GitHub (видеокарта Metal, как у студии): время кадра 1920×1080 при 1/4/8/16 проходах и кадры на настоящей видеокарте
const { chromium } = require('playwright'); const fs = require('fs'); const OUT = process.argv[2] || 'bench/out'; fs.mkdirSync(OUT, { recursive: true });
const log = []; const L = s => { console.log(s); log.push(s); fs.writeFileSync(OUT + '/log.txt', log.join('\n') + '\n'); };
(async () => {
  const b = await chromium.launch({ headless: true, channel: 'chromium', timeout: 180000, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: 1000, height: 1300 } });
  p.on('pageerror', e => L('PAGEERR ' + e.message)); p.on('console', m => { const t = m.text(); if (/error|warn/i.test(t)) L('CONSOLE ' + t.slice(0, 300)); });
  const t0 = Date.now(); await p.goto('http://127.0.0.1:8772/local.html');
  await p.waitForFunction(() => !document.getElementById('go').disabled, null, { timeout: 300000 });
  L('Готово за ' + ((Date.now() - t0) / 1000).toFixed(1) + ' с\n' + await p.evaluate(() => document.getElementById('log').innerText));
  L('Видеокарта: ' + await p.evaluate(() => { const gl = document.createElement('canvas').getContext('webgl2'); const e = gl.getExtension('WEBGL_debug_renderer_info'); return e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : '?'; }));
  await p.evaluate(() => { KUI.pause(); KUI.hold(true); });
  const res = await p.evaluate(async () => {
    const KI = KIST2, THREE = KI.THREE, W = 1920, H = 1080; const tgt = new THREE.WebGLRenderTarget(W, H, { type: THREE.UnsignedByteType, depthBuffer: false }); const px = new Uint8Array(W * H * 4); const out = {};
    const run = (spp, N) => { KI.frame(W, H, 0, { target: tgt, spp }); KI.R.readRenderTargetPixels(tgt, 0, 0, W, H, px); const t0 = performance.now();
      for (let i = 0; i < N; i++) { KI.frame(W, H, i / 25, { target: tgt, spp }); KI.R.readRenderTargetPixels(tgt, 0, 0, W, H, px); } return Math.round((performance.now() - t0) / N); };
    KI.mode = 'strokes'; KI.lightPreset('blender'); KI.shadowOn = true;
    for (const shot of ['photo', 'close']) { KI.setShot(KI.SHOTS[shot]); for (const spp of [1, 4, 8, 16]) { out[shot + '_x' + spp] = run(spp, spp >= 8 ? 8 : 20); await new Promise(r => setTimeout(r, 0)); } }
    KI.lightPreset('app'); KI.shadowOn = false; KI.setShot(KI.SHOTS.photo); out.kist3_photo_x1 = run(1, 20);
    KI.mode = 'hair'; out.volosky_prilozhenie_x1 = run(1, 20); KI.mode = 'strokes';
    return out; });
  L('Мс на кадр 1920×1080 (рисование + выдача из видеокарты, без сжатия в JPEG): ' + JSON.stringify(res));
  const shots = [['photo_x16', 'photo', 16, 'blender', true, 'strokes'], ['close_x16', 'close', 16, 'blender', true, 'strokes'], ['macro_x16', 'macro', 16, 'blender', true, 'strokes'], ['photo_x1_kist3', 'photo', 1, 'app', false, 'strokes'], ['close_x1_kist3', 'close', 1, 'app', false, 'strokes']];
  for (const [name, shot, spp, preset, sh, mode] of shots) {
    const url = await p.evaluate(([shot, spp, preset, sh, mode]) => { const KI = KIST2, THREE = KI.THREE, W = 1920, H = 1080; KI.mode = mode; KI.lightPreset(preset); KI.shadowOn = sh; KI.setShot(KI.SHOTS[shot]);
      const tgt = new THREE.WebGLRenderTarget(W, H, { type: THREE.UnsignedByteType, depthBuffer: false }); KI.frame(W, H, 1.2, { target: tgt, spp }); const px = new Uint8Array(W * H * 4); KI.R.readRenderTargetPixels(tgt, 0, 0, W, H, px); tgt.dispose();
      const c = document.createElement('canvas'); c.width = W; c.height = H; const x = c.getContext('2d'); const im = x.createImageData(W, H);
      for (let y = 0; y < H; y++) im.data.set(px.subarray((H - 1 - y) * W * 4, (H - y) * W * 4), y * W * 4); x.putImageData(im, 0, 0); return c.toDataURL('image/jpeg', .92); }, [shot, spp, preset, sh, mode]);
    fs.writeFileSync(OUT + '/' + name + '.jpg', Buffer.from(url.split(',')[1], 'base64')); L('кадр ' + name + ' готов'); }
  await b.close(); L('конец');
})().catch(e => { L('СБОЙ ' + (e && e.stack || e)); process.exit(0); });
