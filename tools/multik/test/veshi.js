// Вещи из разговора: что появляется в кадре от реплики героя. node tools/multik/test/veshi.js [veshi.txt]
// Строка файла: «+|реплика» — вещь должна появиться (вот / смотри / это …), «-|реплика» — только говорят о ней (похоже на, даже камень, на дне, утонул, из камня…).
const fs=require('fs'),vm=require('vm'),path=require('path');
const ctx={console,Math,Date,JSON,Object,Array,Set,Map,Float32Array,Int16Array,Uint8Array,Uint32Array,Int32Array,Float64Array,String,Number,RegExp,Error,isNaN,parseInt,parseFloat,Promise,setTimeout};ctx.window=ctx;ctx.self=ctx;ctx.globalThis=ctx;vm.createContext(ctx);
for(const f of ['multik-engine.js','multik-audio.js','multik-maker.js','multik-script.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../../../Resources/Mebel',f),'utf8'),ctx,{filename:f});
const H='СЕРИАЛ: Т\nСЕРИЯ: 1. Т\nПЕРСОНАЖ: Барсик — рыжий полосатый котёнок с синим шарфом, голос мальчика\nПЕРСОНАЖ: Пик — маленький серый мышонок с красным бантиком, голос девочки\nСЦЕНА: поляна, день\nБарсик стоит.\nПик стоит.\nБарсик: Привет!\n';
const want=process.argv[2]==='--show';
for(const l of fs.readFileSync(process.argv[want?3:2]||path.join(__dirname,'veshi.txt'),'utf8').split('\n').filter(Boolean)){const [exp,txt]=l.split('|');const r=ctx.MKScript.parse(H+'Пик: '+txt.trim()+'\n',{characters:{},locations:{}});const sc=r.episodes[0].scenes[0];
 const props=(sc.props||[]).map(p=>p.type+(p.holder?'(в лапах)':'')).join(',')||'—';const got=props!=='—'?'+':'-';console.log((got===exp.trim()?'  ok ':'  !! ')+exp.trim()+' '+props.padEnd(16)+' '+txt.trim());}
