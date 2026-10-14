
<script>
// ===== Режим «Кромка»: цветная полоса на каждом закромлённом торце (из файла технолога) =====
(function(){
  const COLS=[0xff2d2d,0x0a84ff,0x2fbf4f,0xe0b000,0xa64ee0,0xff8a00];
  const kinds=Object.keys(D.edgeTot||{}); const colOf=k=>COLS[Math.max(0,kinds.indexOf(k))%COLS.length];
  const hexs=c=>'#'+c.toString(16).padStart(6,'0');
  const strips=[]; const emats={}; kinds.forEach(k=>emats[k]=new THREE.MeshBasicMaterial({color:colOf(k),side:THREE.DoubleSide}));
  pick.forEach(m=>{ const p=m.userData; if(!p||!p.ed||!p.ed.length) return;
    const all=p.pts; const cx=all.reduce((s,a)=>s+a[0],0)/all.length, cy=all.reduce((s,a)=>s+a[1],0)/all.length;
    const byK={};
    p.ed.forEach(([pts,k])=>{ const arr=byK[k]||(byK[k]=[]);
      for(let i=0;i<pts.length-1;i++){ const [x1,y1]=pts[i],[x2,y2]=pts[i+1]; let nx=y2-y1,ny=-(x2-x1); const l=Math.hypot(nx,ny); if(l<1e-6) continue; nx/=l; ny/=l;
        if(nx*((x1+x2)/2-cx)+ny*((y1+y2)/2-cy)<0){nx=-nx;ny=-ny;}
        const o=1.5, a=[x1+nx*o,y1+ny*o], c=[x2+nx*o,y2+ny*o], z0=-0.8, z1=p.th+0.8;
        arr.push(a[0],a[1],z0,c[0],c[1],z0,c[0],c[1],z1, a[0],a[1],z0,c[0],c[1],z1,a[0],a[1],z1); } });
    Object.entries(byK).forEach(([k,arr])=>{ const g=new THREE.BufferGeometry(); g.setAttribute('position',new THREE.Float32BufferAttribute(arr,3));
      const s=new THREE.Mesh(g,emats[k]); s.visible=false; s.renderOrder=3; m.add(s); strips.push(s); });
  });
  const grp=document.querySelector('header .grp:nth-of-type(2)')||document.querySelector('header');
  const btn=document.createElement('button'); btn.textContent='Кромка'; btn.setAttribute('aria-pressed','false'); grp.prepend(btn);
  const chip='display:flex;align-items:center;gap:6px;padding:5px 9px;font-size:12px;border-radius:6px;background:var(--panel);color:var(--ink);box-shadow:0 2px 8px rgba(0,0,0,.12)';
  const leg=document.createElement('div');
  leg.style.cssText='display:none;gap:6px;flex-wrap:wrap';
  leg.innerHTML=kinds.map(k=>`<span style="${chip}"><i style="width:16px;height:6px;border-radius:2px;background:${hexs(colOf(k))}"></i>${/кромка/i.test(k)?k:"Кромка "+k} · ${D.edgeTot[k][0]} торцов · ${(D.edgeTot[k][1]/1000).toFixed(1)} м</span>`).join('')
    +`<span style="${chip}"><i style="width:16px;height:6px;border-radius:2px;background:#cfc8bd"></i>без кромки</span>`;
  // одна панель внизу: сверху кромка, под ней крепёж (переносится в несколько строк)
  const box=document.createElement('div'); box.style.cssText='position:absolute;left:8px;right:8px;bottom:8px;display:flex;flex-direction:column;gap:6px;z-index:3;pointer-events:none';
  const fl=document.getElementById('legend'); box.appendChild(leg); if(fl){ fl.style.position='static'; fl.style.left=fl.style.right=fl.style.bottom=''; box.appendChild(fl); }
  [leg,fl].forEach(e=>e&&(e.style.pointerEvents='auto'));
  stage.appendChild(box);
  btn.onclick=()=>{ const on=btn.getAttribute('aria-pressed')!=='true'; btn.setAttribute('aria-pressed',String(on));
    strips.forEach(s=>s.visible=on); leg.style.display=on?'flex':'none'; const h=document.getElementById('hint'); if(h) h.style.display=on?'none':''; };
  // в карточке детали — какие торцы закромлены и позиция
  cv.addEventListener('pointerup',()=>{ setTimeout(()=>{ if(!selMesh||card.hidden) return; const p=selMesh.userData; if(!p||!p.ne) return;
    const by={}; (p.ed||[]).forEach(([,k])=>by[k]=(by[k]||0)+1); const n=(p.ed||[]).length;
    const txt=n? Object.entries(by).map(([k,c])=>`${k} ×${c}`).join(', ')+(n>=p.ne?' · по кругу':` из ${p.ne}`) : 'без кромки';
    const t=info.querySelector('table'); if(t) t.insertAdjacentHTML('beforeend',`<tr><td>Кромка</td><td class="v">${txt}</td></tr>`+(p.art?`<tr><td>Позиция</td><td class="v">${p.art}</td></tr>`:''));
  },0); });
  card.style.zIndex=5;
  // нажатие на крепёж / присадку — название и отверстие
  const WHAT={dowel:'Шкант',confirmat:'Конфирмат',cam:'Эксцентрик',screw:'Саморез / отверстие',leg:'Крепление ножки',mark:'Наколка (разметка)',slide:'Присадка под направляющую',shelf:'Присадка под полкодержатель',tie:'Стяжка'};
  const rc=new THREE.Raycaster(), mp2=new THREE.Vector2(); let d2=null;
  cv.addEventListener('pointerdown',e=>d2=[e.clientX,e.clientY]);
  cv.addEventListener('pointerup',e=>{ if(!d2||Math.hypot(e.clientX-d2[0],e.clientY-d2[1])>6) return;
    const r=cv.getBoundingClientRect(); mp2.set((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1); rc.setFromCamera(mp2,cam);
    const ims=[]; scene.traverse(o=>{ if(o.isInstancedMesh&&o.userData.list){ let v=o; while(v){ if(!v.visible) return; v=v.parent; } ims.push(o);} });
    const h=rc.intersectObjects(ims,false)[0]; if(!h) return;
    const f=h.object.userData.list[h.instanceId]; if(!f) return;
    setTimeout(()=>{ card.hidden=false; const nm=f[9]||WHAT[f[0]]||'';
      info.innerHTML=`<h2>${WHAT[f[0]]||'Отверстие'}</h2><table><tr><td>Фурнитура</td><td class="v" style="white-space:normal">${nm}</td></tr><tr><td>Отверстие</td><td class="v">Ø${(+f[7]*2).toFixed(1).replace('.0','')} × ${(+f[8]).toFixed(1).replace('.0','')} мм</td></tr></table>`; },10);
  });
  btn.click();
})();
</script>
