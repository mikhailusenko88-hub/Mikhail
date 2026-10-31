// Проверка сценария: node tools/multik/check.js серия.json [ещё.json…] — коды персонажей, ошибки, оценка длительности
const fs = require('fs'), path = require('path');
require(path.join(__dirname, '../../Resources/Mebel/multik-engine.js'));
const MK = globalThis.MK, lib = { characters: {}, locations: {} };
for (const f of process.argv.slice(2)) {
  const ep = JSON.parse(fs.readFileSync(f, 'utf8')), v = MK.validate(ep, lib);
  for (const c of v.newChars) { lib.characters[c.id] = { spec: c, code: c._code }; }
  for (const l of v.newLocs) { lib.locations[l.id] = { spec: l, code: l._code }; }
  const tl = v.errors.length ? null : MK.compile(ep, lib, {});
  console.log(`${f}: ${ep.series} — серия ${ep.episode}. ${ep.title}`);
  console.log('  персонажи:', Object.values(lib.characters).map(c => c.code + ' ' + c.spec.name).join(', '));
  if (v.errors.length) console.log('  ОШИБКИ:\n   ' + v.errors.join('\n   '));
  if (v.warnings.length) console.log('  внимание: ' + v.warnings.join('; '));
  if (tl) console.log(`  длительность ≈ ${Math.floor(tl.dur / 60)}:${String(Math.round(tl.dur % 60)).padStart(2, '0')} (озвучка уточнит), реплик: ${tl.speech.length}, хэш: ${MK.hash32(MK.canon(ep))}`);
}
