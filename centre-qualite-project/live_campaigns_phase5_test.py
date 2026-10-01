import unittest
from unittest.mock import patch

import live_campaigns
from routes_collection import CollectionRoutesMixin

SCOPE={
    'campaigns': {'C1': {'campaign_id':'C1','campaign_name':'CABINET A'}},
    'queues': [
        {'line_id':571,'display_name':'File 571'},
        {'line_id':588,'display_name':'File 588'},
        {'line_id':505,'display_name':'File 505'},
    ],
    'campaign_to_files': {'C1':[{'line_id':571,'line_name':'File 571'},{'line_id':588,'line_name':'File 588'},{'line_id':505,'line_name':'File 505'}]},
    'agent_files': {'1001':[571,588,505],'1002':[571],'1003':[588]},
    'configured_agents_by_line': {'571':['1001','1002'],'588':['1001','1003'],'505':['1001']},
    'agents_by_line_state': {'active': {'571':['1001','1002'],'588':['1001','1003'],'505':['1001']}},
    'groups': [{'id':'G1','name':'MED02','service_name':'MEDICAL','line_ids':[571,588,505]}],
}

def metric(received=100):
    return {'campaign_id':'C1','campaign_label':'CABINET A','identity_quality':'configured_id','received':received,
            'handled':90,'treated_agent':90,'abandoned':8,'abandon_rate':8.0,'qos':92.0,
            'wait_average_seconds':45.0,'wait_median_seconds':30.0,'wait_p90_seconds':120.0,
            'wait_sample_size':80,'low_volume_flag':False,'agents_treating':3}

def payload():
    history={
        'day':'2026-09-25',
        'last_15m':{'source':'Stats.INBOUND importé','quality':'partial','reason':'current_day_import_is_not_live','campaigns':[metric(25)]},
        'today':{'source':'Stats.INBOUND importé','quality':'partial','reason':'current_day_import_is_not_live','campaigns':[metric(100)]},
        'reference':{'source':'Stats.INBOUND importé','quality':'reliable','reason':'','days':['2026-09-18','2026-09-11'],'label':'médiane même tranche','campaigns':[metric(80)]},
        'queue_distribution':{
            'source':'ODCalls.FirstQueue','quality':'partial',
            'last_15m':{'C1':{'total':25,'files':[
                {'file_id':'571','file_label':'File 571','received':18,'treated':16,'abandoned':1,'agents_treating':2,'share_percent':72.0},
                {'file_id':'588','file_label':'File 588','received':5,'treated':4,'abandoned':1,'agents_treating':1,'share_percent':20.0},
            ]}},'today':{}
        },
        'query_plan':{'bounded':True,'independent_of_campaign_count':True},
    }
    snapshot={
        'day':'2026-09-25','health':{'fresh':True},
        'agents':[
            {'agent':'1001','name':'Agent 1001','kind':'call','state':'Inbound call','line_id':'571','campaign':'CABINET A','state_age_seconds':60,'ticking':True,
             'groups':[{'id':'G1','name':'MED02','service_name':'MEDICAL'}],'service_names':['MEDICAL'],'current_call':{'reference':'1001-4','status':'observing','campaign':'CABINET A','line_id':'571'}},
            {'agent':'1002','name':'Agent 1002','kind':'ready','state':'Prêt','line_id':'571','campaign':'CABINET A','state_age_seconds':15,'ticking':True,'groups':[],'service_names':['MEDICAL'],'current_call':None},
        ],
        'quality':{'center':{'data_quality':{'quality':'reliable'},'scopes':[
            {'scope_type':'CAMPAIGN','scope_key':'CABINET A','scope_label':'CABINET A','incident_count':1,'status':{'level_key':'DEGRADE','label':'DÉGRADÉ','rank':300,'color':'#B54708'}},
            {'scope_type':'QUEUE','scope_key':'571','scope_label':'571','incident_count':1,'status':{'level_key':'DEGRADE','label':'DÉGRADÉ','rank':300,'color':'#B54708'}},
        ]}},
    }
    bundle={'history':history,'agent_metrics':{'source':'Stats.AGENT importé','quality':'partial','reason':'current_day_import_is_not_live','hold_quality':'reliable','agents':{
        '1001':{'agent':'1001','name':'Agent 1001','handled':8,'call_average_seconds':72.5,'call_sample_size':8,'hold_seconds':25.0,'hold_segments':2,'source':'Stats.AGENT importé','quality':'partial','hold_quality':'reliable'}
    }}}
    calls={'day':'2026-09-25','window':'30m','count':1,'rows':[{'reference':'1001-4','agent':'1001','name':'Agent 1001','line_id':'571','line_name':'File 571','campaign':'CABINET A','timeline':[{'stamp_text':'10:31:04','state':'Inbound call','phase':'call'}]}],'source':'Hermes Live','quality':'reliable','truncated':False}
    return snapshot,bundle,calls

class Phase5CampaignDrilldownTests(unittest.TestCase):
    @patch('live_campaigns.load_quality_file_scope',return_value=SCOPE)
    def test_drilldown_preserves_queue_agent_call_chain(self,_scope):
        snapshot,bundle,calls=payload()
        d=live_campaigns.drilldown(snapshot,bundle,'C1',calls_preview=calls,clock=1_800_000_000)
        self.assertEqual(d['campaign_id'],'C1')
        self.assertEqual({q['file_id'] for q in d['queues']},{'571','588','505'})
        self.assertEqual(next(q for q in d['queues'] if q['file_id']=='571')['share_percent'],72.0)
        a=next(x for x in d['agents'] if x['agent']=='1001')
        self.assertEqual(a['handled_today'],8)
        self.assertEqual(a['active_files'],['505','571','588'])
        self.assertEqual(d['calls']['rows'][0]['reference'],'1001-4')
        self.assertTrue(d['query_plan']['independent_of_agent_count'])

    @patch('live_campaigns.load_quality_file_scope',return_value=SCOPE)
    def test_missing_queue_history_is_not_invented_as_zero(self,_scope):
        snapshot,bundle,calls=payload()
        d=live_campaigns.drilldown(snapshot,bundle,'C1',calls_preview=calls,clock=1_800_000_000)
        q=next(x for x in d['queues'] if x['file_id']=='505')
        self.assertIsNone(q['received'])
        self.assertIsNone(q['share_percent'])

    @patch('live_campaigns.load_quality_file_scope',return_value=SCOPE)
    def test_agent_without_live_state_is_non_observed_not_disconnected(self,_scope):
        snapshot,bundle,calls=payload()
        d=live_campaigns.drilldown(snapshot,bundle,'C1',calls_preview=calls,clock=1_800_000_000)
        a=next(x for x in d['agents'] if x['agent']=='1003')
        self.assertEqual(a['kind'],'unobserved')
        self.assertTrue(a['active_on_campaign_queues'])

    @patch('routes_collection.store.live_campaign_call_preview')
    @patch('routes_collection.store.live_supervision_snapshot')
    @patch('routes_collection.live_campaigns.historical_drilldown_view' if False else 'live_campaigns.historical_drilldown_view')
    @patch('service_mode.external_services_enabled',return_value=False)
    @patch('live_campaigns.load_quality_file_scope',return_value=SCOPE)
    def test_api_detail_is_single_bounded_payload(self,_scope,_external,_hist,_snap,_calls):
        snapshot,bundle,calls=payload();_hist.return_value=bundle;_snap.return_value=snapshot;_calls.return_value=calls
        class Fake(CollectionRoutesMixin):
            def send_json(self,payload,status=200): return status,payload
        status,d=Fake().api_live_campaign_detail('C1',{},include_history=True,include_calls=True,show_phone=False)
        self.assertEqual(status,200)
        self.assertEqual(d['campaign_id'],'C1')
        self.assertTrue(d['query_plan']['bounded'])
        _calls.assert_called_once()

    @patch('routes_collection.store.live_supervision_snapshot')
    @patch('live_campaigns.load_quality_file_scope',return_value=SCOPE)
    def test_no_calls_permission_does_not_query_live_calls(self,_scope,_snap):
        snapshot,bundle,calls=payload();_snap.return_value=snapshot
        class Fake(CollectionRoutesMixin):
            def send_json(self,payload,status=200): return status,payload
        with patch('live_campaigns.historical_drilldown_view',return_value=bundle), patch('service_mode.external_services_enabled',return_value=False), patch('routes_collection.store.live_campaign_call_preview') as preview:
            status,d=Fake().api_live_campaign_detail('C1',{},include_history=True,include_calls=False,show_phone=False)
        self.assertEqual(status,200)
        self.assertEqual(d['calls']['quality'],'unavailable')
        preview.assert_not_called()

if __name__=='__main__': unittest.main()
