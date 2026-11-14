const S = require('../g1-draw/sim.js');
const n=+process.argv[2]||4; const hint=process.argv[3]?JSON.parse(process.argv[3]):null;
const w=S.makeLevel(n,()=>0.5); if(hint) w.hint=hint; w.line=S.densify(w.hint); w.released=true;
let t=0; const p=w.balls[0];
while(t<5){ S.step(w,1/60); t+=1/60; for(const e of w.events){ if(e.b===p||e.e==='coin') console.log(t.toFixed(2),e.e, Math.round(p.x),Math.round(p.y)); } w.events.length=0;
 if(Math.round(t*60)%6===0) console.log(' t',t.toFixed(2),'p',Math.round(p.x),Math.round(p.y),'v',Math.round(p.vx),Math.round(p.vy), p.done?'DONE#'+p.place:'', p.dead?'DEAD':'');
 if(p.done||p.dead||p.out) break; }
