"""Merge generic Policies then punctual Declarations into one technical decision."""
from policy_engine import apply_event_policy, load_policies
from declaration_engine import apply_event_declarations, load_declarations
from governance_intervals import summarize_actions, attach_decision, ACTION_KEYS


def apply_event_governance(event, module='support', policies=None, declarations=None):
    policy_rows = policies if policies is not None else load_policies()
    declaration_rows = declarations if declarations is not None else load_declarations()
    # Common case: no configured rules. Avoid three separate interval passes.
    if not policy_rows and not declaration_rows:
        out = dict(event)
        decision = summarize_actions(event, {})
        out['policy_decision'] = dict(decision, applied=False, policy_ids=[], policy_names=[], reclassify='', reason='')
        out['declaration_decision'] = dict(decision, applied=False, declaration_ids=[], declaration_types=[], reason='', comments=[])
        for prefix in ('policy', 'declaration', 'governance'):
            attach_decision(out, prefix, decision)
            out[prefix + '_reason'] = ''
        out['policy_applied'] = False
        out['declaration_applied'] = False
        out['governance_decision'] = decision
        return out
    out = apply_event_policy(event, module, policy_rows)
    out = apply_event_declarations(out, declaration_rows)

    policy_decision = out.get('policy_decision') or {}
    declaration_decision = out.get('declaration_decision') or {}
    intervals = {}
    for key in ACTION_KEYS:
        intervals[key] = (policy_decision.get('action_intervals') or {}).get(key, []) + (declaration_decision.get('action_intervals') or {}).get(key, [])
    decision = summarize_actions(out, intervals)
    attach_decision(out, 'governance', decision)
    out['governance_decision'] = decision
    reasons = []
    if out.get('policy_reason'):
        reasons.append('Policy: ' + str(out.get('policy_reason')))
    if out.get('declaration_reason'):
        reasons.append('Déclaration: ' + str(out.get('declaration_reason')))
    out['governance_reason'] = ' · '.join(reasons)
    return out


def apply_governance(events, module='support', policies=None, declarations=None):
    policy_rows = policies if policies is not None else load_policies()
    declaration_rows = declarations if declarations is not None else load_declarations()
    return [apply_event_governance(e, module, policy_rows, declaration_rows) for e in (events or [])]


def governed_visible_events(events, module='support', policies=None, declarations=None):
    """Apply governance once and return visible KPI rows plus excluded evidence.

    Raw input is never mutated/deleted.  ``excluded`` is returned so callers can
    expose migration/audit counters while KPI-oriented collections use only
    ``visible``. Lost-time consumers should read ``governance_effective_seconds``.
    """
    governed = apply_governance(events, module, policies, declarations)
    visible = [r for r in governed if not r.get('governance_exclude_statistics')]
    excluded = [r for r in governed if r.get('governance_exclude_statistics')]
    return visible, excluded


class DetailsGovernanceCalendar:
    """Sur-ensemble temporel des regles, prive a une requete Details.

    Les cibles et priorites sont volontairement ignorees ICI : un chevauchement
    impose le moteur complet, jamais une autorisation. L'absence de chevauchement
    prouve seulement qu'aucune regle temporelle ne peut s'appliquer.
    Les fenetres viennent des fonctions historiques, y compris minuit et bornes.
    Aucune decision d'evenement n'est reutilisee par jour/groupe/minute.
    """
    def __init__(self, policies, declarations, max_days=64):
        from copy import deepcopy
        if type(max_days) is not int or max_days < 1:
            raise ValueError('Limite de calendrier invalide.')
        self.policies = deepcopy(policies)
        self.declarations = deepcopy(declarations)
        self.max_days = max_days
        self.days = {}
        self.hits = 0
        self.misses = 0
        self.bypassed_events = 0
        self.full_events = 0
        self.empty_templates = {}
        self.template_hits = 0
        self.template_misses = 0

    def _windows(self, day):
        from datetime import datetime, time, timedelta
        from governance_intervals import policy_ranges, declaration_ranges, merge_ranges
        if day in self.days:
            self.hits += 1
            return self.days[day]
        self.misses += 1
        origin = datetime.combine(day, time())
        event = {'start_text': origin.isoformat(sep=' '), 'seconds': 86400}
        ranges = []
        for policy in self.policies:
            if policy.get('enabled') and not policy.get('deleted_at'):
                ranges.extend(policy_ranges(policy, event))
        for declaration in self.declarations:
            if declaration.get('status') == 'ACTIVE' and not declaration.get('deleted_at'):
                ranges.extend(declaration_ranges(declaration, event))
        windows = tuple((origin + timedelta(seconds=lo), origin + timedelta(seconds=hi))
                        for lo, hi in merge_ranges(ranges))
        if len(self.days) >= self.max_days:
            self.days.clear()  # Plafond de memoire ; une absence impose un recalcul exact.
        self.days[day] = windows
        return windows

    def may_apply(self, event):
        from datetime import timedelta
        from governance_intervals import event_bounds
        bounds = event_bounds(event)
        if bounds is None:
            # Les moteurs historiques n'appliquent aucune plage sans date valide.
            self.bypassed_events += 1
            return False
        start, end = bounds
        day = start.date()
        if (end.date() - day).days > 1:
            # Ne pas parcourir ici des annees : le moteur complet garde ce cas.
            self.full_events += 1
            return True
        while day <= end.date():
            if any(start < hi and end > lo for lo, hi in self._windows(day)):
                self.full_events += 1
                return True
            day += timedelta(days=1)
        self.bypassed_events += 1
        return False


    def empty_event(self, event):
        """Prototype interne exact hors de TOUTE plage, par duree observee.

        L'appelant de selection ne modifie pas les annotations partagees et DOIT
        appeler detach avant de conserver une preuve pour la reponse publique.
        Les prototypes viennent du moteur historique sans regle, pas d'une
        reimplementation des formules. Aucune decision non vide n'est cachee.
        """
        from governance_intervals import observed_seconds
        seconds = observed_seconds(event)
        if seconds not in self.empty_templates:
            self.template_misses += 1
            prototype = apply_event_governance({'seconds': seconds}, 'details', [], [])
            prototype.pop('seconds', None)
            if len(self.empty_templates) >= 256:
                self.empty_templates.clear()
            self.empty_templates[seconds] = prototype
        else:
            self.template_hits += 1
        out = dict(event)
        out.update(self.empty_templates[seconds])
        return out

    @staticmethod
    def detach(decision):
        """Ne jamais exposer de liste/dictionnaire partage avec un prototype."""
        from copy import deepcopy
        return deepcopy(decision)
