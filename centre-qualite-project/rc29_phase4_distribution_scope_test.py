from quality_workforce import expected_agents,bucket_status,new_interval_map,merge_intervals


def _scope():
    return {
        'agent_files':{'1001':[10],'1002':[10,20],'1003':[20]},
        'campaign_to_files':{'C1':[{'line_id':10}],'C2':[{'line_id':20}]},
    }


def test_group_population_active_only():
    g={'member_agent_ids':['1001','1002']}
    assert expected_agents(_scope(),[g])=={'1001','1002'}
    assert expected_agents(_scope(),[g],campaign='C2')=={'1002'}


def test_pause_distinct_same_bucket():
    work=new_interval_map();pause=new_interval_map()
    merge_intervals(pause,'1001',(10,20));merge_intervals(pause,'1001',(30,40))
    s=bucket_status({'1001'},work,pause,0,60)
    assert s['pause']=={'1001'}


def test_pause_crosses_two_buckets():
    work=new_interval_map();pause=new_interval_map()
    merge_intervals(pause,'1001',(55,70))
    assert '1001' in bucket_status({'1001'},work,pause,0,60)['pause']
    assert '1001' in bucket_status({'1001'},work,pause,60,120)['pause']


def test_worked_then_disconnected_stays_worked():
    work=new_interval_map();pause=new_interval_map()
    merge_intervals(work,'1001',(10,20))
    # There is deliberately no offline input to the worked proof.
    s=bucket_status({'1001'},work,pause,60,120)
    assert s['worked']=={'1001'}
    assert not s['not_worked']


def test_no_positive_evidence_is_not_worked_when_population_is_known():
    s=bucket_status({'1001','1002'},new_interval_map(),new_interval_map(),0,60)
    assert s['not_worked']=={'1001','1002'}


def test_med1_acceptance_30_active_27_worked_3_absent():
    pop={str(1000+i) for i in range(30)}
    work=new_interval_map();pause=new_interval_map()
    for aid in sorted(pop)[:27]:merge_intervals(work,aid,(10,20))
    s=bucket_status(pop,work,pause,0,60)
    assert len(s['active'])==30
    assert len(s['worked'])==27
    assert len(s['not_worked'])==3


def main():
    tests=[v for k,v in globals().items() if k.startswith('test_') and callable(v)]
    for fn in tests:fn();print('OK',fn.__name__)
    print(f'{len(tests)}/{len(tests)} tests OK')

if __name__=='__main__':main()
