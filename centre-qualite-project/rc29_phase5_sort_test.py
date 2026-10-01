from __future__ import annotations
import os, subprocess, textwrap
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def test_backend_whitelists():
    os.environ.setdefault('NELYIO_FORCE_SQLITE','1')
    from calls import _call_sort
    from suspicious_calls import _sort_spec
    assert _call_sort({}) == ('','default')
    assert _call_sort({'sort':['duration'],'sort_dir':['asc']}) == ('duration','asc')
    assert _sort_spec({'sort':['hold'],'sort_dir':['desc']}) == ('hold','desc')
    for fn in (_call_sort,_sort_spec):
        for bad in [
            {'sort':['start DESC; DROP TABLE phone_calls;--'],'sort_dir':['asc']},
            {'sort':['duration'],'sort_dir':['sideways']},
        ]:
            try: fn(bad)
            except ValueError: pass
            else: raise AssertionError(f'{fn.__name__} accepted {bad!r}')

def test_server_sort_before_pagination_contract():
    calls=(ROOT/'calls.py').read_text(encoding='utf-8')
    suspects=(ROOT/'suspicious_calls.py').read_text(encoding='utf-8')
    assert "SELECT * FROM ('+page_scope+') q ORDER BY" in calls
    assert "LIMIT ? OFFSET ?" in calls
    assert calls.index("SELECT * FROM ('+page_scope+') q ORDER BY") < calls.index("LIMIT ? OFFSET ?", calls.index("SELECT * FROM ('+page_scope+') q ORDER BY"))
    assert "SELECT * FROM ('+source+') q ORDER BY '+null_last" in suspects
    assert "LIMIT ? OFFSET ?" in suspects

def test_frontend_three_state_and_types():
    app=(ROOT/'static'/'app.js').read_text(encoding='utf-8')
    assert "ASC -> DESC -> default" in app
    assert "type==='duration'" in app and 'qualityParseDuration' in app
    assert 'qualityParseDate' in app and "type==='percentage'" in app
    assert 'qualityStateRank' in app
    assert "return am?1:-1" in app  # missing always last, independent of direction
    assert "sessionStorage.setItem('nelyio.rc29.sort.'+key" in app
    q=(ROOT/'static'/'quality.js').read_text(encoding='utf-8')
    assert "s.sort='';s.direction='default'" in q
    support=(ROOT/'static'/'support.js').read_text(encoding='utf-8')
    assert "callsSortState={key:'',direction:'default'}" in support
    assert "q.set('sort',callsSortState.key)" in support
    suspect=(ROOT/'static'/'suspicious-calls.js').read_text(encoding='utf-8')
    assert "query.set('sort',s.sort)" in suspect

def test_duration_parser_runtime():
    src=(ROOT/'static'/'app.js').read_text(encoding='utf-8')
    a=src.index('// RC29 Phase 5 - shared sortable-table contract outside the Live Center.')
    b=src.index('// End RC29 Phase 5 sortable-table contract.')
    block=src[a:b]
    js="""
    global.sessionStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
    %s
    const vals=[['59 s',59],['2m 00s',120],['1h 01m',3660],['01:30',90]];
    for(const [v,e] of vals){const got=qualityParseDuration(v);if(got!==e)throw new Error(v+' => '+got+' expected '+e);}
    if(!(qualitySortCompare('59 s','2m 00s','asc','duration')<0))throw new Error('duration ASC broken');
    if(!(qualitySortCompare('—','2m 00s','desc','duration')>0))throw new Error('missing not last in DESC');
    if(!(qualitySortCompare('10 %%','2 %%','asc','percentage')>0))throw new Error('percentage broken');
    console.log('JS_SORT_RUNTIME_OK');
    """%block
    out=subprocess.check_output(['node','-e',js],cwd=ROOT,text=True)
    assert 'JS_SORT_RUNTIME_OK' in out

def main():
    tests=[v for k,v in globals().items() if k.startswith('test_') and callable(v)]
    for fn in tests:
        fn();print('OK',fn.__name__)
    print(f'{len(tests)}/{len(tests)} tests Phase 5 réussis')

if __name__=='__main__':main()
