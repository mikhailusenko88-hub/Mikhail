const S = require('../g1-draw/sim.js');
function seeded(seed){let s=seed>>>0||1;return()=>{s^=s<<13;s>>>=0;s^=s>>17;s^=s<<5;s>>>=0;return s/4294967296;};}
for (let n=1;n<=8;n++){
  const res=[];
  for (let trial=0; trial<6; trial++){
    const w=S.makeLevel(n, seeded(100+trial*7+n));
    const lvlIdx=(n-1)%S.count;
    w.line=S.densify(w.hint);
    const inkUsed=S.lineLength(w.line);
    w.released=true;
    let t=0; let coins=0;
    while(t<14){ S.step(w,1/60); t+=1/60; for(const e of w.events){ if(e.e==='coin')coins++; } w.events.length=0;
      const p=w.balls[0]; if(p.done||p.dead||p.out) { if(w.balls.every(b=>b.done||b.dead||b.out||b.still>2)) break; } }
    const p=w.balls[0];
    res.push({trial, ink:Math.round(inkUsed)+'/'+w.ink, player: p.done?('#'+p.place+' '+p.finishT.toFixed(2)+'s'):(p.dead?'DEAD':p.out?'OUT':'STUCK@'+Math.round(p.x)+','+Math.round(p.y)), coins,
      rivals: w.balls.slice(1).map(b=>b.done?b.finishT.toFixed(2):(b.dead?'dead':b.out?'out':'stuck@'+Math.round(b.x)+','+Math.round(b.y))).join(' ')});
  }
  console.log('LEVEL',n); res.forEach(r=>console.log(' ',JSON.stringify(r)));
}
