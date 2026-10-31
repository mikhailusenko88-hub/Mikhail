// Все предметы на одном листе: node sheet.js [hq] [ball,apple,...] [колонок=8] [файл.png]
const {chromium}=require('playwright');const path=require('path');
const ALL=['ball','apple','fish','box','gift','flower','book','star','cake','bone','carrot','cheese','balloon','key','cup','pumpkin','jack','mushroom','umbrella','candy','icecream','lollipop','banana','pear','watermelon','honey','bucket','shovel','car','teddy','drum','guitar','wand','lantern','map','letter','basket','chest','coin','egg','pie','cookie','milk','clock','candle','leaf','rock','stick','phone','kite','bag','door','moon','ghost','bat','garland','tree','snowman','fire','tent','castle','rainbow'];
(async()=>{const b=await chromium.launch({timeout:180000,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--allow-file-access-from-files']});
const hq=process.argv[2]==='hq';const p=await b.newPage({viewport:{width:1600,height:1400}});p.on('pageerror',e=>console.log('ERR',e.message));
await p.goto('file://'+path.join(__dirname,'frame.html')+(hq?'#hq':''));await p.waitForFunction(()=>window.ready);
await p.evaluate(()=>{const c=document.getElementById('c');c.width=1600;c.height=1400;c.style.width='1600px';c.style.height='1400px';});
const types=(process.argv[3]||'').split(',').filter(Boolean);const list=types.length?types:ALL;const cols=+(process.argv[4]||8);
await p.evaluate(([l,cols])=>MK3D.propSheet(document.getElementById('c'),l,cols),[list,cols]);
await p.locator('#c').screenshot({path:process.argv[5]||(hq?'sheet_hq.png':'sheet.png'),timeout:300000});await b.close();})();
