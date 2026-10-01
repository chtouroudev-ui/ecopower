"""Canonical business rules for Stats.INBOUND quality metrics.

This module contains SQL fragments shared by the Quality service, agent summary,
and hourly distributions. It deliberately keeps source flags (answered/lost/etc.)
separate from the business KPI "treated by an agent".
"""

CANONICAL_FIELDS = (
    'received', 'treated_agent', 'answered', 'completed', 'transferred',
    'rerouted_agent', 'rerouted_no_agent', 'abandoned', 'closed', 'overflow',
    'hangup_before_queue', 'ignored', 'lost_with_agent', 'qos_numerator',
    'qos_denominator', 'qos_percent', 'asa_seconds',
    'treated_under_60_count', 'treated_under_60_percent', 'outbound_count',
    'coherence_delta', 'coherence_ok', 'treated_subcategory_delta',
    'treated_subcategory_ok',
)


def agent_assigned_sql(alias='f'):
    """AgentId > 0 semantics, tolerant of legacy S-prefixed identifiers."""
    col=f"TRIM(COALESCE({alias}.agent,''))"
    return f"({col} NOT IN ('','0','S0'))"


def agent_unassigned_sql(alias='f'):
    return f"NOT {agent_assigned_sql(alias)}"


def principal_hits_sql(alias='f'):
    """Number of explicit main classes matched by a row (ignored excluded)."""
    assigned=agent_assigned_sql(alias)
    unassigned=agent_unassigned_sql(alias)
    return (
        f"(CASE WHEN {alias}.closed=1 THEN 1 ELSE 0 END + "
        f"CASE WHEN {alias}.overflow=1 THEN 1 ELSE 0 END + "
        f"CASE WHEN {unassigned} AND {alias}.rerouted=1 THEN 1 ELSE 0 END + "
        f"CASE WHEN {alias}.before_queue=1 THEN 1 ELSE 0 END + "
        f"CASE WHEN {alias}.abandoned=1 THEN 1 ELSE 0 END + "
        f"CASE WHEN {assigned} THEN 1 ELSE 0 END)"
    )


def aggregate_sql(alias='f', threshold_placeholder='?'):
    """One canonical aggregate projection for the Quality screens/API."""
    a=alias
    assigned=agent_assigned_sql(a)
    unassigned=agent_unassigned_sql(a)
    hits=principal_hits_sql(a)
    # lost is nullable for legacy facts created before RC2H. New imports always
    # populate it from IsCallLost. Keeping NULL makes missing source fidelity
    # explicit instead of inventing a flag during migration.
    return f'''COUNT(*) AS received,
      COALESCE(SUM({a}.received),0) AS is_call_count,
      COALESCE(SUM(CASE WHEN {assigned} THEN 1 ELSE 0 END),0) AS treated_agent,
      COALESCE(SUM(CASE WHEN {a}.answered=1 THEN 1 ELSE 0 END),0) AS answered,
      COALESCE(SUM(CASE WHEN {assigned} AND {a}.transferred=0 AND {a}.rerouted=0 THEN 1 ELSE 0 END),0) AS completed,
      COALESCE(SUM(CASE WHEN {assigned} AND {a}.transferred=1 THEN 1 ELSE 0 END),0) AS transferred,
      COALESCE(SUM(CASE WHEN {assigned} AND {a}.rerouted=1 THEN 1 ELSE 0 END),0) AS rerouted_agent,
      COALESCE(SUM(CASE WHEN {unassigned} AND {a}.rerouted=1 THEN 1 ELSE 0 END),0) AS rerouted_no_agent,
      COALESCE(SUM(CASE WHEN {a}.abandoned=1 THEN 1 ELSE 0 END),0) AS abandoned,
      COALESCE(SUM(CASE WHEN {a}.closed=1 THEN 1 ELSE 0 END),0) AS closed,
      COALESCE(SUM(CASE WHEN {a}.overflow=1 THEN 1 ELSE 0 END),0) AS overflow,
      COALESCE(SUM(CASE WHEN {a}.before_queue=1 THEN 1 ELSE 0 END),0) AS hangup_before_queue,
      COALESCE(SUM(CASE WHEN {hits}=0 THEN 1 ELSE 0 END),0) AS ignored,
      COALESCE(SUM(CASE WHEN {hits}>1 THEN 1 ELSE 0 END),0) AS double_classified,
      COALESCE(SUM(CASE WHEN {assigned} AND {a}.lost=1 THEN 1 ELSE 0 END),0) AS lost_with_agent_known,
      COALESCE(SUM(CASE WHEN {assigned} AND {a}.lost IS NULL THEN 1 ELSE 0 END),0) AS lost_source_missing,
      COALESCE(SUM({a}.invalid_duration),0) AS invalid_durations,
      COALESCE(SUM(CASE WHEN {assigned} AND {a}.wait>=0 THEN {a}.wait ELSE 0 END),0) AS wait_sum,
      COALESCE(SUM(CASE WHEN {assigned} AND {a}.wait>=0 THEN 1 ELSE 0 END),0) AS wait_count,
      COALESCE(SUM(CASE WHEN {assigned} AND {a}.wait>=0 AND {a}.wait<={threshold_placeholder} THEN 1 ELSE 0 END),0) AS within_threshold'''


def decorate(row, threshold=60, outbound_count=None):
    """Add formula-derived KPI fields to one aggregate row."""
    r=dict(row)
    treated=int(r.get('treated_agent') or 0)
    received=int(r.get('received') or 0)
    closed=int(r.get('closed') or 0)
    before=int(r.get('hangup_before_queue') or 0)
    abandoned=int(r.get('abandoned') or 0)
    rerouted_no_agent=int(r.get('rerouted_no_agent') or 0)
    # Canonical Nelyio QoS confirmed by the operator:
    # treated / (received - closed - hangup before queue).
    # A non-positive denominator is non-calculable and must never become zero.
    qos_numerator=treated
    qos_denominator=received-closed-before
    r['qos_numerator']=qos_numerator
    r['qos_denominator']=qos_denominator
    r['qos_percent']=100*qos_numerator/qos_denominator if qos_denominator>0 else None
    # Backward-compatible reference aliases now mirror the canonical QoS.
    # There must be only one QoS formula throughout the application.
    reference_qos_numerator=qos_numerator
    reference_qos_denominator=qos_denominator
    r['reference_qos_numerator']=reference_qos_numerator
    r['reference_qos_denominator']=reference_qos_denominator
    r['reference_qos_percent']=100*reference_qos_numerator/reference_qos_denominator if reference_qos_denominator>0 else None
    # Backward-compatible aliases consumed by older front-end code/plugins.
    r['qos_rate']=r['qos_percent']
    r['response_rate']=r['qos_percent']
    r['asa_seconds']=r['wait_sum']/r['wait_count'] if r.get('wait_count') else None
    r['answered_wait_average']=r['asa_seconds']
    r['treated_under_60_count']=int(r.get('within_threshold') or 0) if int(threshold)==60 else None
    r['treated_within_threshold_count']=int(r.get('within_threshold') or 0)
    r['treated_within_threshold_percent']=100*int(r.get('within_threshold') or 0)/r['wait_count'] if r.get('wait_count') else None
    r['treated_under_60_percent']=r['treated_within_threshold_percent'] if int(threshold)==60 else None
    r['answered_within_threshold_rate']=r['treated_within_threshold_percent']
    r['lost_with_agent_source_complete']=int(r.get('lost_source_missing') or 0)==0
    r['lost_with_agent']=int(r.get('lost_with_agent_known') or 0) if r['lost_with_agent_source_complete'] else None
    treated_subtotal=(int(r.get('completed') or 0)+int(r.get('transferred') or 0)+
                      int(r.get('rerouted_agent') or 0))
    r['treated_subtotal']=treated_subtotal
    r['treated_subcategory_delta']=treated-treated_subtotal
    r['treated_subcategory_ok']=r['treated_subcategory_delta']==0
    partition=(int(r.get('closed') or 0)+int(r.get('overflow') or 0)+rerouted_no_agent+
               int(r.get('ignored') or 0)+int(r.get('hangup_before_queue') or 0)+
               int(r.get('abandoned') or 0)+treated)
    r['classified_total']=partition
    r['coherence_delta']=received-partition
    r['coherence_ok']=(r['coherence_delta']==0 and int(r.get('double_classified') or 0)==0
                       and r['treated_subcategory_ok'])
    r['outbound_count']=outbound_count
    # Compatibility: historically "answered" was displayed as "treated".
    # Do not overwrite it; clients can distinguish answered from treated_agent.
    return r


def public_metric_aliases(row):
    """Return stable aliases for old clients while making new semantics explicit."""
    r=dict(row)
    r['treated']=r.get('treated_agent')
    r['asa']=r.get('asa_seconds')
    return r
