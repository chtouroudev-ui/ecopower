from pathlib import Path
from unittest.mock import patch
import json

ROOT=Path(__file__).resolve().parent


def _module():
    import importlib.util
    spec=importlib.util.spec_from_file_location('production_acceptance',ROOT/'tools'/'production_acceptance.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


def test_phase8_files_and_no_secret_in_report(tmp_path):
    p=_module();r=p.Report(version='X',internal_url='http://127.0.0.1:9051',public_url='https://localhost:9050')
    r.add('x','PASS','ok');data=r.finish()
    out=tmp_path/'r.md';p.write_markdown(data,out)
    text=out.read_text(encoding='utf-8')
    assert 'password' not in json.dumps(data).lower()
    assert 'mot de passe' not in text.lower()
    assert (ROOT/'RECETTE_PRODUCTION.bat').is_file()
    assert (ROOT/'RECETTE_PRODUCTION.ps1').is_file()


def test_phase8_missing_credentials_makes_recipe_incomplete():
    p=_module();r=p.Report(version='X',internal_url='x',public_url='y')
    opener,user=p.check_authenticated_runtime(r,'http://127.0.0.1:1','','',timeout=.1)
    assert opener is None and user is None
    data=r.finish()
    assert data['status']=='INCOMPLET'
    assert any(x['name']=='Connexion recette' and x['status']=='SKIP' for x in data['checks'])


def test_phase8_internal_health_rejects_wrong_build_and_non_postgres():
    p=_module();r=p.Report(version='60.5-ARCH-RC19',internal_url='x',public_url='y')
    fake={'ok':True,'status':200,'seconds':.01,'error':'','data':{'ok':True,'build':'OLD','database':'sqlite','architecture':'monolith','services_ok':False}}
    with patch.object(p,'json_request',return_value=fake):
        p.check_internal_health(r,'http://x','60.5-ARCH-RC19')
    row=r.data['checks'][-1]
    assert row['status']=='FAIL'
    assert 'build=' in row['detail'] and 'database=' in row['detail'] and 'services_ok' in row['detail']


def test_phase8_group_check_does_not_claim_success_without_assignment_source():
    p=_module();r=p.Report(version='X',internal_url='x',public_url='y')
    user={'username':'u','role':'admin','permissions':{}}
    responses={
      '/api/services/status':{'all_healthy':True,'required':['web','live','analytics'],'services':[]},
      '/api/groups/status':{'ok':True,'assignment_source_available':False,'group_summary':{'saved':2,'scoped_agents':0,'unclassified_agent_count':10}},
      '/api/live/supervision':{'health':{'fresh':True,'worker_healthy':True,'last_response_age':1}},
      '/api/live/campaigns':{'campaigns':[],'windows':{}},
      '/api/quality/pilotage':{'day':'2026-09-01','current':None,'reliability':{'status':'Données insuffisantes'}},
    }
    class Dummy: pass
    with patch.object(p,'login',return_value=(Dummy(),{'user':user})):
        def req(_op,url,**kwargs):
            path=url.split('9051',1)[-1].split('?',1)[0]
            return {'ok':True,'status':200,'seconds':.01,'error':'','data':responses[path]}
        with patch.object(p,'json_request',side_effect=req):
            p.check_authenticated_runtime(r,'http://127.0.0.1:9051','u','pw')
    assert any(x['name']=='Affectations groupes' and x['status']=='WARN' for x in r.data['checks'])


def test_phase8_benchmark_fails_on_http_errors():
    p=_module();r=p.Report(version='X',internal_url='x',public_url='y')
    class Dummy: pass
    with patch.object(p,'login',return_value=(Dummy(),{})):
        with patch.object(p,'json_request',return_value={'ok':False,'status':500,'seconds':.01,'error':'boom','data':{}}):
            p.benchmark(r,'http://x','u','p',users=5,rounds=1,timeout=1)
    assert r.data['checks'][-1]['status']=='FAIL'
    assert r.data['benchmark']['summary']['errors']==5
