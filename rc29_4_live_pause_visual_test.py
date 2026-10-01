from pathlib import Path
import subprocess, json

ROOT=Path(__file__).resolve().parent
JS=ROOT/'static'/'live-views.js'
CSS=ROOT/'static'/'collection.css'

def test_pause_taxonomy_is_visual_only_and_explicit():
    js=JS.read_text(encoding='utf-8')
    assert "label:'Coaching',classes:'pause pause-coaching'" in js
    assert "label:'Pause déjeuner',classes:'pause pause-lunch'" in js
    assert "label:'General Break',classes:'pause pause-general'" in js
    assert "label:'Pause',classes:'pause pause-normal'" in js
    assert "label:'Post-appel',classes:'wrap live-postwork'" in js
    assert 'r.state,r.line_id' in js


def test_postwork_threshold_contract():
    js=JS.read_text(encoding='utf-8')
    assert "if(n>25)return 'critical'" in js
    assert "if(n>=15)return 'alert'" in js
    assert "if(n>=10)return 'warning'" in js
    assert "Surveillance · 10–15 s" in js
    assert "Alerte · 15–25 s" in js
    assert "Critique · > 25 s" in js


def test_css_distinguishes_pause_types_and_red_critical_row():
    css=CSS.read_text(encoding='utf-8')
    for cls in ('pause-normal','pause-lunch','pause-coaching','pause-general','live-postwork'):
        assert cls in css
    assert 'tr.live-postwork-critical>td' in css
    assert 'box-shadow:inset 5px 0 0 #dc2626' in css


def test_js_pure_classification_and_thresholds_execute_in_node():
    source=JS.read_text(encoding='utf-8')
    probe=r'''
;globalThis.__pauseTest={
 coaching:liveAgentStatePresentation({state:'Coaching',kind:'other'}),
 lunch:liveAgentStatePresentation({state:'Pause déjeuner',kind:'pause'}),
 general:liveAgentStatePresentation({state:'General Break',kind:'other'}),
 normal:liveAgentStatePresentation({state:'Pause',kind:'pause'}),
 post:liveAgentStatePresentation({state:'Post-travail',kind:'wrap'}),
 levels:[livePostWorkSeverity(9),livePostWorkSeverity(10),livePostWorkSeverity(14.9),livePostWorkSeverity(15),livePostWorkSeverity(25),livePostWorkSeverity(26)]
};
'''
    node=r'''
const fs=require('fs'),vm=require('vm');
const src=fs.readFileSync(process.argv[1],'utf8')+fs.readFileSync(process.argv[2],'utf8');
const noop=()=>{};
const store={getItem(){return null},setItem(){},removeItem(){}};
const classList={add(){},remove(){}};
const document={addEventListener(){},fullscreenElement:null,body:{classList},styleSheets:[],querySelectorAll(){return[]}};
const window={addEventListener(){}};const location={hash:''};
const ctx={document,window,location,localStorage:store,sessionStorage:store,setTimeout(){return 1},clearTimeout:noop,setInterval(){return 1},clearInterval:noop,URLSearchParams,encodeURIComponent,decodeURIComponent,console};
vm.createContext(ctx);vm.runInContext(src,ctx);process.stdout.write(JSON.stringify(ctx.__pauseTest));
'''
    probe_path=ROOT/'_pause_probe_tmp.js'
    probe_path.write_text(probe,encoding='utf-8')
    try:
        result=subprocess.run(['node','-e',node,str(JS),str(probe_path)],capture_output=True,text=True,check=True)
    finally:
        probe_path.unlink(missing_ok=True)
    data=json.loads(result.stdout)
    assert data['coaching']['pauseType']=='coaching'
    assert data['lunch']['pauseType']=='lunch'
    assert data['general']['pauseType']=='general'
    assert data['normal']['pauseType']=='normal'
    assert data['post']['postWork'] is True
    assert data['levels']==['normal','warning','warning','alert','alert','critical']
