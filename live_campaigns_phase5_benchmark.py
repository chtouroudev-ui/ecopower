"""Synthetic Phase 5 benchmark. Never reads production databases."""
import statistics,time
from unittest.mock import patch
import live_campaigns

N_AGENTS=114
N_QUEUES=20
N_CALLS=100
scope={
    'campaigns':{'C1':{'campaign_id':'C1','campaign_name':'CABINET A'}},
    'queues':[{'line_id':500+i,'display_name':f'File {500+i}'} for i in range(N_QUEUES)],
    'campaign_to_files':{'C1':[{'line_id':500+i,'line_name':f'File {500+i}'} for i in range(N_QUEUES)]},
    'agent_files':{str(1000+i):[500+(i%N_QUEUES)] for i in range(N_AGENTS)},
    'configured_agents_by_line':{str(500+i):[str(1000+a) for a in range(N_AGENTS) if a%N_QUEUES==i] for i in range(N_QUEUES)},
    'agents_by_line_state':{'active':{str(500+i):[str(1000+a) for a in range(N_AGENTS) if a%N_QUEUES==i] for i in range(N_QUEUES)}},
    'groups':[{'id':'G1','name':'MED02','service_name':'MEDICAL','line_ids':[500+i for i in range(N_QUEUES)]}],
}
metric={'campaign_id':'C1','campaign_label':'CABINET A','identity_quality':'configured_id','received':1200,'handled':1100,'treated_agent':1100,'abandoned':80,'abandon_rate':6.67,'qos':94.0,'wait_average_seconds':42,'wait_median_seconds':25,'wait_p90_seconds':115,'wait_sample_size':1100,'low_volume_flag':False,'agents_treating':100}
files=[{'file_id':str(500+i),'file_label':f'File {500+i}','received':60,'treated':55,'abandoned':4,'agents_treating':6,'share_percent':5.0} for i in range(N_QUEUES)]
history={'day':'2026-09-25','last_15m':{'source':'Stats.INBOUND importé','quality':'partial','reason':'current_day_import_is_not_live','campaigns':[metric]},'today':{'source':'Stats.INBOUND importé','quality':'partial','reason':'current_day_import_is_not_live','campaigns':[metric]},'reference':{'source':'Stats.INBOUND importé','quality':'reliable','reason':'','days':['2026-09-18','2026-09-11'],'label':'référence','campaigns':[metric]},'queue_distribution':{'source':'ODCalls.FirstQueue','quality':'partial','last_15m':{'C1':{'total':1200,'files':files}},'today':{}},'query_plan':{'bounded':True}}
agents=[]
for i in range(N_AGENTS):
    kind=('call','ready','wrap','pause')[i%4]
    agents.append({'agent':str(1000+i),'name':f'Agent {i}','kind':kind,'state':kind,'line_id':str(500+(i%N_QUEUES)),'campaign':'CABINET A','state_age_seconds':i*3,'ticking':True,'groups':[],'service_names':['MEDICAL'],'current_call':({'reference':f'R{i}','status':'observing','campaign':'CABINET A','line_id':str(500+(i%N_QUEUES))} if kind=='call' else None)})
snapshot={'day':'2026-09-25','health':{'fresh':True},'agents':agents,'quality':{'center':{'data_quality':{'quality':'reliable'},'scopes':[]}}}
agent_metrics={'source':'Stats.AGENT importé','quality':'partial','hold_quality':'reliable','agents':{str(1000+i):{'handled':10+i%5,'call_average_seconds':70+i%10,'hold_seconds':i%20,'hold_segments':i%3,'quality':'partial','hold_quality':'reliable'} for i in range(N_AGENTS)}}
calls={'day':'2026-09-25','window':'30m','count':N_CALLS,'rows':[{'reference':f'R{i}','agent':str(1000+(i%N_AGENTS)),'name':'Agent','line_id':str(500+(i%N_QUEUES)),'campaign':'CABINET A','timeline':[]} for i in range(N_CALLS)],'source':'Hermes Live','quality':'reliable','truncated':False}
bundle={'history':history,'agent_metrics':agent_metrics}
with patch('live_campaigns.load_quality_file_scope',return_value=scope):
    times=[]
    for _ in range(250):
        t=time.perf_counter();out=live_campaigns.drilldown(snapshot,bundle,'C1',calls_preview=calls,clock=1800000000);times.append((time.perf_counter()-t)*1000)
print(f'agents={len(out["agents"])} queues={len(out["queues"])} calls={len(out["calls"]["rows"])}')
print(f'median_ms={statistics.median(times):.3f}')
print(f'p95_ms={sorted(times)[int(len(times)*0.95)-1]:.3f}')
