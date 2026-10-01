// Run: node audit_frontend_test.js (no browser or production connection).
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync(__dirname+'/static/supervision.js','utf8');
const fn=src.slice(src.indexOf('async function supLoad(){'),src.indexOf('function supNote('));
const elements=new Map(),requests=[];
const element=id=>{if(!elements.has(id))elements.set(id,{value:'',innerHTML:'',textContent:''});return elements.get(id);};
const c={supRequestSerial:0,supPending:false,supBusy:false,supTimer:null,supGeneration:1,supMode:'history',supPage:0,
 currentUser:{id:1},location:{hash:'#supervision'},URLSearchParams,setTimeout,clearTimeout,
 $:element,$$:()=>[],show:()=>{},supRenderCharts:()=>{},supSourceLabel:()=>'',supDuration:String,esc:String,
 flash:String,api:q=>new Promise(resolve=>requests.push({q,resolve}))};
vm.createContext(c);vm.runInContext(fn,c);
(async()=>{
 element('#sup-agent').value='1001';const first=c.supLoad();
 element('#sup-agent').value='1002';await c.supLoad();
 requests[0].resolve({});await first;
 await new Promise(r=>setTimeout(r,20));
 assert.equal(requests.length,2);assert(requests[1].q.includes('agent=1002'));
 requests[1].resolve({summary:{agents:0,anomalies:0,durations:{pause:0,offline:0}},clock:'',health:[],rows:[],imports:[],count:0,config:{work_start:'08:00',work_end:'19:00'}});
 await new Promise(r=>setTimeout(r,20));assert.equal(c.supBusy,false);
 console.log('PASS: changement de filtre pendant une requête, ancien résultat ignoré et dernier filtre relancé.');
})().catch(e=>{console.error(e);process.exitCode=1;});
