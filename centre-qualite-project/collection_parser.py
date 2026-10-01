"""Read the validated Hermes callbacks without evaluating any JavaScript.

Only the fields observed in the user's archived capture are accepted. Tokens,
headers, cookies, callback bodies and audio are not stored. Numeric counters
are retained by argument position, never assigned unverified business meanings.
A decoder is scoped to ONE connection: its first state is always partial.
"""
from __future__ import annotations

import ast
from collections import Counter
import hashlib
import json
import math
import re
from dataclasses import dataclass, field

from supervision_utils import kind

CALLBACKS = ('InitQueue', 'InitAgt', 'InitCamp', 'UpAgtTState',
             'UpAgtGState', 'UpAgtCtxQu', 'UpAgtH', 'UpAgtSH', 'UpAgtCtxH', 'UpQuH',
             'UpQuR', 'UpCaR', 'UpQuCB', 'UpQuMR', 'UpAgtMState')
CALL_RE = re.compile(r'\b(' + '|'.join(CALLBACKS) + r')\s*\(')
MAX_BODY_BYTES = 4 * 1024 * 1024
MAX_CALLBACKS = 10000
PARSER_VERSION = 'V56.5-live-2'
FUNCTION_RE = re.compile(r'[A-Za-z_$][A-Za-z0-9_$]*')
CLOSING = {'(': ')', '[': ']', '{': '}'}


def clean(value, limit=250):
    return re.sub(r'[\x00-\x1f|]+', ' ', str(value or '')).strip()[:limit]


def identifier(value):
    value = str(value).strip()
    if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,80}', value):
        raise ValueError('Identifiant de capture invalide.')
    return value


def queue_ids(value):
    if isinstance(value, str):
        value = value.split(',') if value.strip() else []
    if not isinstance(value, list) or len(value) > 3000:
        raise ValueError('Liste de files invalide.')
    result = []
    for item in value:
        s = str(item).strip()
        if not s.isdecimal():
            raise ValueError('Identifiant de file non numerique.')
        if s not in result:
            result.append(s)
    return result


def _literal(token):
    """JSON first; quoted JS strings are literal-only, never eval()."""
    token = token.strip()
    try:
        return json.loads(token)
    except (ValueError, TypeError):
        if len(token) >= 2 and token[0] in ('"', "'") and token[-1] == token[0]:
            value = ast.literal_eval(token)
            if isinstance(value, str):
                return value
    raise ValueError('Argument non litteral ou format inconnu.')


def split_arguments(text):
    items, start, depth, quote, escaped = [], 0, 0, None, False
    for i, ch in enumerate(text):
        if quote:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == quote:
                quote = None
        elif ch in ('"', "'"):
            quote = ch
        elif ch in '[{(':
            depth += 1
        elif ch in ']})':
            depth -= 1
            if depth < 0:
                raise ValueError('Argument desequilibre.')
        elif ch == ',' and depth == 0:
            items.append(_literal(text[start:i])); start = i + 1
    if quote or depth:
        raise ValueError('Argument tronque.')
    if text[start:].strip():
        items.append(_literal(text[start:]))
    return items


def _comment_end(body, position):
    """Saute uniquement les commentaires ; aucun contenu n'est journalise."""
    if body.startswith('//', position):
        end = body.find('\n', position + 2)
        return len(body) if end < 0 else end + 1
    if body.startswith('/*', position):
        end = body.find('*/', position + 2)
        if end < 0:
            raise ValueError('Commentaire live tronque.')
        return end + 2
    return None


def scan_callbacks(body):
    """Lit les invocations de premier niveau, y compris les noms inconnus.

    Les noms dans les chaines/commentaires/arguments ne sont pas des callbacks.
    Le protocole attendu est une suite d'appels litteraux, pas un programme JS.
    La liste blanche n'intervient qu'APRES ce balayage, pour la telemetrie.
    """
    if not isinstance(body, str):
        raise ValueError('Reponse live non textuelle.')
    if len(body.encode('utf-8')) > MAX_BODY_BYTES:
        raise ValueError('Reponse live trop volumineuse (limite 4 Mo).')
    if '<html' in body[:200].lower() or '<!doctype html' in body[:200].lower():
        return
    cursor = count = 0
    while cursor < len(body):
        if body[cursor].isspace() or body[cursor] in ';\ufeff':
            cursor += 1
            continue
        end = _comment_end(body, cursor)
        if end is not None:
            cursor = end
            continue
        match = FUNCTION_RE.match(body, cursor)
        if not match:
            raise ValueError('Syntaxe live de premier niveau non prise en charge.')
        name = match.group(0)
        cursor = match.end()
        while cursor < len(body) and body[cursor].isspace():
            cursor += 1
        if cursor >= len(body) or body[cursor] != '(':
            raise ValueError('Invocation live sans parenthese.')
        count += 1
        if count > MAX_CALLBACKS:
            raise ValueError('Trop de messages dans une reponse.')
        start = cursor + 1
        cursor += 1
        stack, quote, escaped = [')'], None, False
        while cursor < len(body) and stack:
            ch = body[cursor]
            if quote:
                if escaped:
                    escaped = False
                elif ch == '\\':
                    escaped = True
                elif ch == quote:
                    quote = None
            elif ch in ('"', "'"):
                quote = ch
            elif ch == '`':
                raise ValueError('Gabarit JavaScript live non pris en charge.')
            else:
                end = _comment_end(body, cursor)
                if end is not None:
                    cursor = end
                    continue
                if ch in CLOSING:
                    stack.append(CLOSING[ch])
                elif ch in ')]}':
                    if ch != stack[-1]:
                        raise ValueError('Delimiteurs live incoherents.')
                    stack.pop()
            cursor += 1
        if stack or quote:
            raise ValueError('Message live tronque.')
        yield name, body[start:cursor - 1]


def callbacks(body):
    """Point d'entree historique : ne retourne que la liste blanche."""
    for name, arguments in scan_callbacks(body):
        if name in CALLBACKS:
            yield name, arguments


def _telemetry_name(name):
    # Borner la taille des noms sans conserver un argument ou un corps source.
    return name if len(name) <= 120 else 'nom_long_sha256_' + hashlib.sha256(name.encode()).hexdigest()


def _strict_integers(parts, indexes):
    """Contrat observe : entiers JSON finis, sans bool/conversion permissive."""
    for index in indexes:
        if type(parts[index]) is not int or abs(parts[index]) > 10**15:
            raise ValueError('Argument numerique live hors contrat observe.')


def _strict_label(value, *, allow_empty=False):
    if not isinstance(value, str) or len(value) > 250:
        raise ValueError('Libelle live hors contrat observe.')
    label = clean(value)
    if not label and not allow_empty:
        raise ValueError('Libelle live vide.')
    return label


def _source_sample(name, parts):
    """Les cinq formes observees dans le HAR, sans equation metier nouvelle.

    arg_0 : identifiant de source/tenant observe, valide mais non publie.
    arg_1 : cle file/agent ou libelle de campagne ; pas un identifiant d'appel.
    Autres positions : valeurs source indexees, UNITE/SENS NON CONFIRMES.
    Toute nouvelle arite doit etre examinee, pas acceptee silencieusement.
    """
    sizes = {'UpQuR': 10, 'UpCaR': 9, 'UpQuCB': 3, 'UpQuMR': 22, 'UpAgtMState': 13}
    if len(parts) != sizes[name]:
        raise ValueError('Nombre d arguments live different du contrat observe.')
    if name == 'UpCaR':
        _strict_integers(parts, [0, *range(2, 9)])
        label = _strict_label(parts[1])
        # arg_1 ressemble au NOM de campagne, pas au campaign_id de InitCamp.
        # Cle locale explicitement namespacee : aucune jointure metier inferee.
        entity = 'source-label:' + hashlib.sha256((str(parts[0]) + '|' + parts[1]).encode()).hexdigest()
        typ = 'campaign_metrics'
        payload = dict(scope='campaign', source_label=label,
                       identity_basis='source_label_not_campaign_id',
                       source_counters=numeric_arguments(parts, range(2, 9)))
    elif name == 'UpAgtMState':
        _strict_integers(parts, [0, 1, 2, 3, *range(5, 11)])
        label = _strict_label(parts[4])
        # arg_11/12 : chaines non documentees. Ne pas supposer campagne/ANI.
        # Leur contenu peut etre sensible : valider la forme, ne pas le garder.
        if any(not isinstance(parts[i], str) or len(parts[i]) > 4096 for i in (11, 12)):
            raise ValueError('Chaine MState hors contrat observe.')
        if parts[1] < 0:
            raise ValueError('Identifiant agent live negatif.')
        entity = identifier(parts[1])
        typ = 'agent_state_sample'
        # arg_2/3 et 5..10 ne sont PAS traduits en contexte, duree ou LineId.
        # arg_4 est un libelle observe, sans transition technique deduite.
        payload = dict(scope='agent', agent=entity, state=label,
                       source_counters=numeric_arguments(parts, [2, 3, *range(5, 11)]),
                       state_semantics='source_state_label_unmapped',
                       redacted_string_positions=['arg_11', 'arg_12'])
    else:
        _strict_integers(parts, range(len(parts)))
        if parts[1] < 0:
            raise ValueError('Identifiant file live negatif.')
        entity = queue_ids([parts[1]])[0]
        typ = 'queue_metrics'
        # R: arg_2..9 ; CB: arg_2 ; MR: arg_2..21. Aucune unite inventee.
        payload = dict(scope='queue', line_id=entity,
                       source_counters=numeric_arguments(parts, range(2, len(parts))))
        if name == 'UpQuR':
            # Mapping verified against the legacy Hermes supervision HAR:
            # aggregate arg_2 == "Appels en cours", aggregate arg_3 ==
            # "Appels en attente", and arg_8 matches "Agents dispo" per queue.
            payload['mapped_metrics'] = {
                'calls_in_progress': parts[2],
                'calls_waiting': parts[3],
                'agents_available_on_queue': parts[8],
            }
            payload['semantics'] = 'hermes_legacy_supervision_verified'
    payload.update(source_function=name, semantics=payload.get('semantics','source_counters_unmapped'),
                   parser_version=PARSER_VERSION, timing_basis='receipt_observation')
    # Chaque nouvel echantillon reste une preuve horodatee, meme a valeur egale.
    # L'idempotence des reponses est assuree dans collection_store, pas par
    # l'effacement de compteurs egaux provenant de receptions distinctes.
    return dict(type=typ, entity=entity, payload=payload)


@dataclass
class Decoder:
    include_phone: bool = False
    states: dict = field(default_factory=dict)
    seen: dict = field(default_factory=dict)
    calls: dict = field(default_factory=dict)
    call_sequence: int = 0

    def _changed(self, key, value):
        if self.seen.get(key) == value:
            return False
        self.seen[key] = value
        return True

    def decode(self, body):
        events, recognized, rejected = [], 0, 0
        unknown_names, rejected_names = Counter(), Counter()
        # Valider la structure entiere avant de modifier les etats en memoire.
        invocations = list(scan_callbacks(body))
        for name, text in invocations:
            if name not in CALLBACKS:
                unknown_names[_telemetry_name(name)] += 1
                continue
            try:
                parts = split_arguments(text)
                current = self._decode(name, parts)
                recognized += 1
                events.extend(current)
            except (ValueError, TypeError, IndexError, SyntaxError, OverflowError):
                rejected += 1
                rejected_names[name] += 1
        unknown = sum(unknown_names.values())
        telemetry = None
        if unknown or rejected:
            # Compteur durable sans arguments. Meme une reponse inconnue seule
            # sera conservee par le store, sans heartbeat ni etat sain fictif.
            telemetry = dict(
                parser_version=PARSER_VERSION, semantics='protocol_telemetry',
                unknown_callbacks=dict(unknown_names), unknown_total=unknown,
                rejected_callbacks=dict(rejected_names), rejected_total=rejected,
                recognized_total=recognized)
        valid = recognized > 0 or not body.strip(' \t\r\n;')
        return dict(events=events, recognized=recognized, rejected=rejected,
                    telemetry=telemetry, unknown=unknown, unknown_callbacks=dict(unknown_names),
                    rejected_callbacks=dict(rejected_names), encountered=len(invocations),
                    valid=valid, groups_supported=False)

    def _decode(self, name, p):
        event = lambda typ, entity, payload: dict(type=typ, entity=str(entity), payload=payload)
        if name in ('UpQuR', 'UpCaR', 'UpQuCB', 'UpQuMR', 'UpAgtMState'):
            return [_source_sample(name, p)]
        if name == 'InitQueue':
            # Observed: tenant, token, token, LineId, description, ...
            if len(p) < 5: raise ValueError('InitQueue incomplet')
            q = queue_ids([p[3]])[0]; label = clean(p[4])
            if label and self._changed(('queue', q), label):
                return [event('queue', q, dict(line_id=q, name=label))]
        elif name == 'InitCamp':
            if len(p) < 6: raise ValueError('InitCamp incomplet')
            cid, label = str(p[4]).strip(), clean(p[5])
            if not re.fullmatch(r'[a-zA-Z0-9_. -]{1,120}', cid):
                raise ValueError('Identifiant de campagne invalide.')
            if label and self._changed(('campaign', cid), label):
                return [event('campaign', cid, dict(campaign_id=cid, name=label))]
        elif name == 'InitAgt':
            if len(p) < 10: raise ValueError('InitAgt incomplet')
            aid = identifier(p[3]); queues = queue_ids(p[8])
            value = dict(agent=aid, first_name=clean(p[4]), last_name=clean(p[5]),
                         queues=queues)
            # p[9] is a comma-separated label list. Do NOT zip it to IDs:
            # a label itself may contain a comma. InitQueue is the name source.
            if self._changed(('agent', aid), value):
                return [event('agent', aid, value)]
        elif name == 'UpAgtCtxQu':
            if len(p) < 4: raise ValueError('UpAgtCtxQu incomplet')
            aid, context = identifier(p[1]), int(p[2])
            queues = queue_ids(p[3]); value = dict(agent=aid, context=context, queues=queues)
            if self._changed(('context', aid, context), queues):
                return [event('context', aid, value)]
        elif name == 'UpAgtGState':
            if len(p) < 4: raise ValueError('UpAgtGState incomplet')
            aid, label = identifier(p[1]), clean(p[3])
            if self._changed(('global', aid), label):
                return [event('global_state', aid, dict(agent=aid, state=label))]
        elif name == 'UpAgtTState':
            if len(p) < 5: raise ValueError('UpAgtTState incomplet')
            aid, context, state = identifier(p[1]), int(p[2]), clean(p[4])
            if not state: raise ValueError('Etat vide')
            q = str(p[10]) if len(p) > 10 and str(p[10]).isdecimal() else ''
            campaign = clean(p[11]) if len(p) > 11 else ''
            candidate = str(p[12]).strip() if len(p) > 12 else ''
            phone_status = 'disabled'
            phone = ''
            if self.include_phone:
                if candidate.casefold() in ('anonymous', 'anonyme', 'private', 'restricted'):
                    phone_status = 'anonymous'
                elif re.fullmatch(r'[+0-9 ().-]{3,64}', candidate) and sum(ch.isdigit() for ch in candidate) >= 3:
                    phone, phone_status = candidate, 'available'
                else:
                    phone_status = 'not_provided'
            # A numeric allowlist: no unknown string arguments or raw body.
            counters = numeric_arguments(p, (3, 5, 6, 9, 14, 15, 16, 17))
            sample = dict(agent=aid, context=context, state=state, line_id=q,
                          campaign=campaign, phone=phone, phone_status=phone_status,
                          source_function=name, source_counters=counters,
                          timing_basis='receipt_observation', parser_version=PARSER_VERSION)
            if context != -1:
                return [event('context_state', aid, sample)] if self._changed(('ctxstate', aid, context), sample) else []
            old = self.states.get(aid)
            signature = (state, q, campaign)
            out = []
            if old is None or old != signature:
                out.append(event('state', aid, dict(agent=aid, state=state, old_state=old[0] if old else '',
                    initial=old is None, line_id=q, campaign=campaign, context=-1,
                    source_function=name, source_counters=counters)))
                self.states[aid] = signature
            call = self.calls.get(aid)
            is_call = kind(state) in ('call', 'hold')
            # A changed number/file is a new observation segment, not a claim
            # that a unique Hermes call has ended. Nothing crosses a reconnect.
            same = call and call['signature'] == (q, campaign, candidate)
            if call and (not is_call or not same):
                ending = dict(call['sample'], observation_ref=call['ref'],
                              phase='left_call' if not is_call else 'segment_changed',
                              next_state=state, end_counters=counters)
                out.append(event('call_update', aid, ending))
                self.calls.pop(aid, None)
                call = None
            if is_call:
                if call is None:
                    self.call_sequence += 1
                    ref = f'{aid}-{self.call_sequence}'
                    value = dict(sample, observation_ref=ref, phase='observing',
                                 line_name=self.seen.get(('queue', q), ''),
                                 partial_start=old is None)
                    self.calls[aid] = dict(ref=ref, signature=(q, campaign, candidate), sample=sample)
                    out.append(event('call_observation', aid, value))
                elif call['sample'] != sample:
                    out.append(event('call_update', aid, dict(sample, observation_ref=call['ref'], phase='observing')))
                    call['sample'] = sample
            elif old == signature and self.seen.get(('primary_sample', aid)) != sample:
                # Repeated post-work/ready counters are evidence only; never
                # turned into additional technical incidents or patient waits.
                out.append(event('state_counters', aid, sample))
            self.seen[('primary_sample', aid)] = sample
            return out
        elif name in ('UpAgtH', 'UpAgtSH', 'UpAgtCtxH', 'UpQuH'):
            if not 3 <= len(p) <= 64:
                raise ValueError('Compteurs live incomplets ou trop nombreux')
            entity = identifier(p[1])
            value = dict(source_function=name, source_counters=numeric_arguments(p, range(2, len(p))),
                         scope='queue' if name == 'UpQuH' else 'agent',
                         semantics='source_counters_unmapped')
            if name == 'UpAgtH' and len(p) >= 10:
                # Correlated with the legacy agent table: arg_6 follows the
                # "Réception" counter; the two final fields are pause count
                # and cumulative pause seconds (e.g. 1/732 == 00:12:12,
                # 3/2254 == 00:37:34 in the supplied HAR/screenshot).
                value['mapped_metrics'] = {
                    'reception_today': p[6],
                    'pause_count_today': p[8],
                    'pause_seconds_today': p[9],
                }
                value['semantics'] = 'hermes_legacy_supervision_verified'
            elif name == 'UpQuH' and len(p) >= 20:
                # Mapping verified by matching the legacy queue table and its
                # displayed QoS. The three exclusion counters are deliberately
                # kept generically named until their Hermes labels are proven.
                received, abandoned, handled = p[3], p[5], p[12]
                ex1, ex2, ex3 = p[6], p[10], p[11]
                denominator = received - ex1 - ex2 - ex3
                value['mapped_metrics'] = {
                    'received_today': received,
                    'abandoned_today': abandoned,
                    'handled_today': handled,
                    'qos_exclusion_1': ex1,
                    'qos_exclusion_2': ex2,
                    'qos_exclusion_3': ex3,
                    'qos_denominator': denominator,
                    'qos_today': (100.0 * handled / denominator) if denominator > 0 else None,
                }
                value['semantics'] = 'hermes_legacy_supervision_verified'
            if not value['source_counters']:
                raise ValueError('Aucun compteur numerique')
            value['line_id' if name == 'UpQuH' else 'agent'] = entity
            key = ('metrics', name, entity)
            if self._changed(key, value):
                return [event('queue_metrics' if name == 'UpQuH' else 'agent_metrics', entity, value)]
        return []


def numeric_arguments(parts, indexes):
    """Preserve finite numeric source values, keyed by zero-based argument index."""
    out = {}
    for index in indexes:
        if index >= len(parts):
            continue
        value = parts[index]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if math.isfinite(value) and abs(value) <= 10**15:
            out['arg_' + str(index)] = value
    return out
