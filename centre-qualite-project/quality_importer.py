"""Read real SIMPLIFY2 configuration, not statistical activity as membership.

Agents.csv: Queues is JSON (LineId, Level, Delay, StartAllContexts,
StartContexts). Level is an AGENT priority. ODCalls.InitPriority is retained
as an OBSERVATION and is never copied into a configured base priority.
All parsers are pure; persistence/chronology lives in quality_service.py.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import re
import zipfile
import import_bundle
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
import unicodedata

MAX_BYTES = 100 * 1024 * 1024
MAX_EXPANDED = 200 * 1024 * 1024


def text(v):
    return '' if v is None else str(v).strip()


def key(v):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', text(v)).encode('ascii', 'ignore').decode().lower())


def agent_key(v):
    v = text(v).upper().rsplit('\\', 1)[-1].rsplit('/', 1)[-1].split('@')[0]
    return v[1:] if v.startswith('S') and v[1:].isdigit() else v


def integer(v, label, maximum=None, optional=True):
    if v is None or text(v) == '':
        if optional: return None
        raise ValueError(label + ' manquant')
    try:
        d = Decimal(text(v).replace(',', '.'))
    except InvalidOperation:
        raise ValueError(label + ' : entier attendu') from None
    if not d.is_finite() or d != d.to_integral_value() or d < 0 or (maximum is not None and d > maximum):
        raise ValueError(label + (' : entier de 0 a ' + str(maximum) if maximum is not None else ' : entier positif attendu'))
    return int(d)


def optional_bool(v):
    if v is None or text(v) == '': return None
    if isinstance(v, bool): return v
    k = key(v)
    if k in ('1', 'true', 'yes', 'oui', 'on', 'active', 'actif', 'enabled'): return True
    if k in ('0', 'false', 'no', 'non', 'off', 'inactive', 'inactif', 'notactive', 'disabled'): return False
    raise ValueError('Etat actif/inactif non reconnu')


def get(row, *names):
    lookup = {key(k): v for k, v in row.items() if k is not None}
    for n in names:
        if key(n) in lookup: return lookup[key(n)]
    return None


def present(row, *names):
    return any(key(n) in {key(k) for k in row if k is not None} for n in names)


def json_list(value, field):
    if value is None or text(value) == '': return []
    if isinstance(value, list): return value
    try: result = json.loads(value)
    except (ValueError, TypeError): raise ValueError(field + ' : liste JSON invalide') from None
    if not isinstance(result, list): raise ValueError(field + ' : liste JSON attendue')
    return result


def activation(row):
    explicit = get(row, 'is_active', 'Active', 'IsActive', 'Enabled', 'Actif')
    all_contexts = optional_bool(get(row, 'StartAllContexts', 'AllContexts', 'TousContextes'))
    raw_contexts = get(row, 'StartContexts', 'Contexts')
    contexts = json_list(raw_contexts, 'StartContexts')
    if explicit is not None and text(explicit) != '':
        active = optional_bool(explicit)
        return dict(is_active=active, activation_state='active' if active else 'inactive',
                    activation_source='explicit', start_all_contexts=all_contexts, start_contexts=contexts)
    if all_contexts is True: state = 'active'
    elif contexts: state = 'partial'
    elif all_contexts is False: state = 'inactive'
    else: state = 'unknown'
    return dict(is_active=None if state == 'unknown' else state != 'inactive', activation_state=state,
                activation_source='startup', start_all_contexts=all_contexts, start_contexts=contexts)


def parse_queue(row):
    lid = integer(get(row, 'line_id', 'LineId', 'QueueId', 'BaseId', 'SkillId'), 'LineId', optional=False)
    if lid == 0: raise ValueError('LineId nul : aucune file identifiable')
    ap = integer(get(row, 'agent_priority_level', 'AgentPriority', 'AgentPriorityLevel', 'Level',
                     'PriorityLevel', 'Priority', 'UserPriority', 'PrioriteAgent'), 'Priorite agent', 99)
    bp = integer(get(row, 'base_priority_level', 'BasePriority', 'LinePriority', 'QueuePriority',
                     'DefaultPriority', 'PrioriteBase'), 'Priorite base')
    return dict(line_id=lid, line_name=text(get(row, 'LineName', 'QueueName', 'BaseName', 'line_name')),
                agent_priority_level=ap, priority_level=ap, base_priority_level=bp,
                delay_seconds=integer(get(row, 'Delay', 'DelaySeconds', 'RingDelay'), 'Delai') or 0,
                **activation(row))


def parse_campaign(row):
    if isinstance(row, (str, int)):
        return dict(campaign_id=text(row), campaign_name='', agent_priority_level=None,
                    base_priority_level=None, assignment_source='configuration', **activation({}))
    return dict(campaign_id=text(get(row, 'campaign_id', 'CampaignId', 'Id')),
                campaign_name=text(get(row, 'campaign_name', 'CampaignName', 'Name', 'Campagne')),
                agent_priority_level=integer(get(row, 'agent_priority_level', 'AgentPriority', 'Level', 'priority_level', 'Priority'), 'Priorite agent', 99),
                base_priority_level=integer(get(row, 'base_priority_level', 'BasePriority', 'CampaignPriority'), 'Priorite campagne'),
                assignment_source='configuration', **activation(row))


def csv_table(raw):
    encodings = ('utf-16',) if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else ('utf-8-sig', 'cp1252')
    for enc in encodings:
        try: txt = raw.decode(enc); break
        except UnicodeError: continue
    else: raise ValueError('Encodage CSV non reconnu')
    lines = txt.splitlines()
    if lines and lines[0].lower().startswith('sep='): txt = '\n'.join(lines[1:]); lines = lines[1:]
    first = lines[0] if lines else ''
    sep = max((';', ',', '\t'), key=first.count)
    reader = csv.DictReader(io.StringIO(txt), delimiter=sep)
    fields = reader.fieldnames or []
    if len({key(h) for h in fields}) != len(fields): raise ValueError('Colonnes CSV dupliquees')
    rows = []
    for n, row in enumerate(reader, 2):
        if None in row or any(v is None for v in row.values()): raise ValueError('CSV ligne %d : nombre de colonnes incorrect' % n)
        if any(text(v) for v in row.values()): rows.append({text(k): v for k, v in row.items()})
    return [text(h) for h in fields], rows


def iter_tables(raw, filename):
    if len(raw) > MAX_BYTES: raise ValueError('Fichier superieur a 100 Mo')
    if filename.lower().endswith('.zip'):
        bundle=import_bundle.current(raw,filename)
        if bundle is not None:
            infos=bundle.infos()
            if len(infos)>2000: raise ValueError('Archive contenant trop de fichiers')
            expanded=0
            for info in infos:
                name=info.filename.lower()
                if not name.endswith('.csv') or '.crm_' in name or '/crm_' in name: continue
                if not any(t in name for t in ('agents.', 'agentlines.', 'agentqueues.', 'agentcampaigns.', 'lines.', 'queues.', 'campaigns.', 'priorit', '.stats.', 'odcalls.')): continue
                expanded += info.file_size
                if info.file_size > 80 * 1024 * 1024 or expanded > MAX_EXPANDED: raise ValueError('CSV de configuration trop volumineux')
                fields, rows = bundle.memo(('csv_table',info.filename), lambda info=info: csv_table(bundle.read(info)))
                yield info.filename, fields, rows
        else:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                if len(z.infolist()) > 2000: raise ValueError('Archive contenant trop de fichiers')
                expanded = 0
                for info in z.infolist():
                    name = info.filename.lower()
                    # No CRM/contact/address/phone data is read by this module.
                    if not name.endswith('.csv') or '.crm_' in name or '/crm_' in name: continue
                    if not any(t in name for t in ('agents.', 'agentlines.', 'agentqueues.', 'agentcampaigns.', 'lines.', 'queues.', 'campaigns.', 'priorit', '.stats.', 'odcalls.')): continue
                    expanded += info.file_size
                    if info.file_size > 80 * 1024 * 1024 or expanded > MAX_EXPANDED: raise ValueError('CSV de configuration trop volumineux')
                    fields, rows = csv_table(z.read(info))
                    yield info.filename, fields, rows
    elif filename.lower().endswith('.csv'):
        fields, rows = csv_table(raw)
        yield filename, fields, rows
    else: raise ValueError('Importer un export ZIP SIMPLIFY2 ou un CSV de configuration')


def source_day(filename):
    m = re.search(r'(20\d\d)[-_](\d\d)[-_](\d\d)', filename)
    if not m: return ''
    try: return datetime(*map(int, m.groups())).date().isoformat()
    except ValueError: return ''


def extract_snapshot(raw, filename):
    agents, queues, campaigns, observations = {}, {}, {}, {}
    scopes, matched, warnings = set(), [], []
    # Tables are small configuration rows, except for the selected statistical
    # tables used ONLY for exact CampaignID -> CampaignName correspondence.
    tables = list(iter_tables(raw, filename))

    def campaign(cid='', name='', **extra):
        cid, name = text(cid), text(name)
        if not cid and not name: return None
        k = cid or 'name:' + name.casefold()
        c = campaigns.setdefault(k, dict(campaign_id=cid, campaign_name=name, base_priority_level=None))
        if name: c['campaign_name'] = name
        for f, v in extra.items():
            if v is not None: c[f] = v
        return c

    def queue(lid, name='', **extra):
        q = queues.setdefault(lid, dict(line_id=lid, line_name=text(name), base_priority_level=None, campaign_ids=[]))
        if name: q['line_name'] = text(name)
        for f, v in extra.items():
            if v is not None: q[f] = v
        return q

    def agent(aid, row):
        aid = agent_key(aid)
        if not aid: raise ValueError('AgentId manquant')
        a = agents.setdefault(aid, dict(agent_id=aid, agent_last_name='', agent_first_name='', login='', queues=[], campaign_assignments=[]))
        for f, aliases in [('agent_last_name', ('AgentLastName', 'LastName', 'Nom')), ('agent_first_name', ('AgentFirstName', 'FirstName', 'Prenom')), ('login', ('LoginName', 'Login', 'AgentLogin'))]:
            v = get(row, *aliases)
            if v is not None: a[f] = text(v)
        if not a['login']: a['login'] = 'S' + aid if aid.isdigit() else aid
        return a

    # Resolve names first. Never treat activity rows as configured membership.
    for name, fields, rows in tables:
        if '.stats.' not in name.lower(): continue
        for row in rows:
            cid, cname = get(row, 'CampaignID'), get(row, 'CampaignName')
            if text(cid) and text(cname): campaign(cid, cname)

    for name, fields, rows in tables:
        low = name.lower()
        hs = {key(x) for x in fields}
        if '.stats.' in low: continue
        if low.endswith('.odcalls.csv') or Path(low).name == 'odcalls.csv':
            # Group -> File -> Campaign mapping only needs FirstQueue + FirstCampaign.
            # Older code also required InitPriority, which made campaigns disappear
            # from Groups when an ODCalls variant omitted that optional column.
            if not {'firstqueue', 'firstcampaign'}.issubset(hs): continue
            has_init_priority = 'initpriority' in hs
            for row in rows:
                lid_s, cid = get(row, 'FirstQueue'), text(get(row, 'FirstCampaign'))
                if not text(lid_s).isdigit() or int(lid_s) <= 0 or not cid: continue
                lid = int(lid_s)
                queue(lid); campaign(cid)
                if cid not in queues[lid]['campaign_ids']: queues[lid]['campaign_ids'].append(cid)
                # Priority remains an optional observation; it is NOT required
                # to retain the queue/campaign relationship used by Groups.
                if not has_init_priority:
                    continue
                raw_priority = get(row, 'InitPriority')
                try: value = integer(raw_priority, 'InitPriority')
                except ValueError:
                    warnings.append('InitPriority invalide ignore dans ODCalls'); continue
                if value is None: continue
                o = observations.setdefault((lid, cid), dict(line_id=lid, campaign_id=cid, values=Counter()))
                o['values'][value] += 1
            if rows: scopes.add('observations'); matched.append(name)
            continue
        if 'queues' in hs and ('agentid' in hs or 'agentlogin' in hs):
            # The real SIMPLIFY2 Agents.csv format.
            seen = set()
            for n, row in enumerate(rows, 2):
                aid = agent_key(get(row, 'AgentID', 'AgentLogin'))
                if aid in seen: raise ValueError('%s ligne %d : AgentID duplique' % (Path(name).name, n))
                seen.add(aid)
                try:
                    a = agent(aid, row)
                    a['queues'] = [parse_queue(q) for q in json_list(get(row, 'Queues'), 'Queues')]
                    lids = [q['line_id'] for q in a['queues']]
                    if len(lids) != len(set(lids)): raise ValueError('LineId duplique pour un agent')
                    for q in a['queues']: queue(q['line_id'], q['line_name'], base_priority_level=q['base_priority_level'])
                    if 'outcampaigns' in hs:
                        a['campaign_assignments'] = [parse_campaign(c) for c in json_list(get(row, 'OutCampaigns'), 'OutCampaigns')]
                        for c in a['campaign_assignments']: campaign(c['campaign_id'], c['campaign_name'])
                    a['default_campaign_id'] = text(get(row, 'DefaultOutCampaign', 'DefaultCampaign'))
                except (ValueError, TypeError) as exc: raise ValueError('%s ligne %d : %s' % (Path(name).name, n, exc)) from exc
            if rows:
                scopes.add('agent_queues')
                if 'outcampaigns' in hs: scopes.add('agent_campaigns')
                matched.append(name)
            continue
        # Flat configuration CSVs remain supported. Generic Priority belongs to
        # an agent only on rows with AgentId, never to both notions at once.
        if not hs.intersection({'priority', 'prioritylevel', 'agentpriority', 'agentprioritylevel', 'basepriority', 'baseprioritylevel', 'linepriority', 'queuepriority', 'campaignpriority', 'priorite', 'level', 'prioriteagent', 'prioritebase'}): continue
        has_agent_col = bool(hs.intersection({'agentid', 'agent', 'agentlogin', 'userid', 'login'}))
        has_queue_col = bool(hs.intersection({'lineid', 'queueid', 'baseid', 'skillid'}))
        has_campaign_col = bool(hs.intersection({'campaignid', 'campaignname', 'campagne', 'campaign'}))
        if not has_queue_col and not has_campaign_col: continue
        scope = ('agent_queues' if has_queue_col else 'agent_campaigns') if has_agent_col else ('queue_catalog' if has_queue_col else 'campaign_catalog')
        if rows: scopes.add(scope); matched.append(name)
        for n, row in enumerate(rows, 2):
            try:
                aid = get(row, 'AgentId', 'Agent', 'AgentLogin', 'UserId', 'Login')
                # normalize aliases once, preserving explicit zero values
                generic = get(row, 'Priority', 'PriorityLevel', 'Priorite', 'Level')
                ap = get(row, 'AgentPriority', 'AgentPriorityLevel', 'PrioriteAgent', 'agent_priority_level')
                bp = get(row, 'BasePriority', 'BasePriorityLevel', 'LinePriority', 'QueuePriority', 'CampaignPriority', 'PrioriteBase', 'base_priority_level')
                if has_agent_col and ap is None: ap = generic
                if not has_agent_col and bp is None: bp = generic
                if has_queue_col:
                    lid = integer(get(row, 'LineId', 'QueueId', 'BaseId', 'SkillId'), 'LineId', optional=False)
                    q = queue(lid, text(get(row, 'LineName', 'QueueName', 'BaseName')), base_priority_level=integer(bp, 'Priorite base'))
                    cid = text(get(row, 'CampaignId')); cname = text(get(row, 'CampaignName', 'Campaign', 'Campagne'))
                    if cid or cname:
                        c = campaign(cid, cname)
                        ident = c['campaign_id'] or 'name:' + c['campaign_name'].casefold()
                        if ident not in q['campaign_ids']: q['campaign_ids'].append(ident)
                        if ident not in q.setdefault('configured_campaign_ids', []): q['configured_campaign_ids'].append(ident)
                    if has_agent_col:
                        r = dict(row, line_id=lid, agent_priority_level=ap, base_priority_level=bp)
                        a = agent(aid, row); parsed = parse_queue(r)
                        a['queues'] = [v for v in a['queues'] if v['line_id'] != lid] + [parsed]
                else:
                    cid, cname = get(row, 'CampaignId'), get(row, 'CampaignName', 'Campaign', 'Campagne')
                    c = campaign(cid, cname, base_priority_level=integer(bp, 'Priorite campagne'))
                    if c is None: raise ValueError('Campagne manquante')
                    if has_agent_col:
                        a = agent(aid, row)
                        a['campaign_assignments'].append(parse_campaign(dict(row, campaign_id=c['campaign_id'], campaign_name=c['campaign_name'], agent_priority_level=ap, base_priority_level=bp)))
            except (ValueError, TypeError) as exc: raise ValueError('%s ligne %d : %s' % (Path(name).name, n, exc)) from exc

    if not scopes: return None
    for a in agents.values():
        for q in a['queues']:
            catalog = queues.get(q['line_id'], {})
            if not q['line_name']: q['line_name'] = catalog.get('line_name', '')
            if q['base_priority_level'] is None: q['base_priority_level'] = catalog.get('base_priority_level')
        for c in a['campaign_assignments']:
            cat = campaigns.get(c['campaign_id']) or campaigns.get('name:' + c['campaign_name'].casefold(), {})
            if not c['campaign_name']: c['campaign_name'] = cat.get('campaign_name', '')
            if c['base_priority_level'] is None: c['base_priority_level'] = cat.get('base_priority_level')
    return dict(version=3, source_type='import', source_label='Configuration SIMPLIFY2',
                source_file=Path(filename).name, source_day=source_day(filename),
                updated_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                digest=hashlib.sha256(raw).hexdigest(), scopes=sorted(scopes), matched_files=sorted(set(matched)),
                agents=list(agents.values()), queues=list(queues.values()), campaigns=list(campaigns.values()),
                observations=[dict(line_id=o['line_id'], campaign_id=o['campaign_id'],
                                   raw_priorities=[dict(value=v, count=n) for v, n in sorted(o['values'].items())]) for o in observations.values()],
                warnings=sorted(set(warnings)), observation_divisor=100,
                observation_scale_note='InitPriority / 100 : echelle proposee a partir des exemples utilisateur, a confirmer. Valeur brute conservee.')
