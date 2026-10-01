"""Minimalist, decision-oriented PDF reporting for Nelyio Support.

The report keeps the detailed technical evidence in annexes while the first
pages stay readable for non-data-analyst users: executive overview, trend vs
the previous period, a small number of graphs, and concrete technical actions.
"""
from __future__ import annotations

import io
import math
from datetime import datetime
from xml.sax.saxutils import escape


def reportlab_available():
    try:
        import reportlab  # noqa: F401
        return True
    except Exception:
        return False


def _fmt_seconds(value):
    try:
        seconds = max(0, int(round(float(value or 0))))
    except Exception:
        seconds = 0
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} h {m:02d} min"
    if m:
        return f"{m} min {s:02d} s"
    return f"{s} s"


def _fmt_date(day):
    try:
        return datetime.strptime(str(day), "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return str(day or "-")


def _clip(text, limit=38):
    value = " ".join(str(text or "").split())
    return value if len(value) <= limit else value[: max(1, limit - 3)] + "..."


def _priority_cell(row,style):
    """Render the configured level/color rather than a positional P1/P2/P3."""
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph
    from reportlab.lib.enums import TA_CENTER
    try:color=colors.HexColor(str(row.get('priority_color') or '#667085'))
    except (ValueError,TypeError):color=colors.HexColor('#667085')
    brightness=.2126*color.red+.7152*color.green+.0722*color.blue
    sty=ParagraphStyle('SupportPriorityBadge',parent=style,alignment=TA_CENTER,
        fontName='Helvetica-Bold',textColor=colors.black if brightness>.58 else colors.white,
        backColor=color,borderPadding=2,spaceBefore=2,spaceAfter=2)
    return Paragraph(escape(str(row.get('priority') or 'NON ÉVALUÉE')),sty)


def _report_score(value):
    return '-' if value is None else f'{float(value):.2f}'


def _report_policy_flowables(data):
    """Append the exact policy AND scoring snapshot used for this PDF."""
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph,Table,TableStyle,PageBreak,Spacer
    ds=data.get('disconnects') or {};audit=data.get('priority_audit') or {}
    policies=ds.get('priority_policy') or [];cfg=ds.get('score_config') or {};declarations=ds.get('declarations') or []
    styles=getSampleStyleSheet()
    h=ParagraphStyle('AppendixNelyio',parent=styles['Heading1'],fontSize=12,leading=15,textColor=colors.HexColor('#15395B'),spaceAfter=8)
    body=ParagraphStyle('PolicyAuditBody',parent=styles['BodyText'],fontSize=8,leading=11,spaceAfter=6)
    cell=ParagraphStyle('PolicyAuditCell',parent=body,fontSize=7,leading=9,spaceAfter=0)
    head=ParagraphStyle('PolicyAuditHead',parent=cell,textColor=colors.white,fontName='Helvetica-Bold')
    def P(x,sty=body):return Paragraph(escape(str(x or '')),sty)
    def tbl(rows,widths):
        out=[]
        for i,row in enumerate(rows):out.append([v if hasattr(v,'wrap') else P(v,head if i==0 else cell) for v in row])
        table=Table(out,colWidths=[w*mm for w in widths],repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#15395B')),
            ('GRID',(0,0),(-1,-1),.25,colors.HexColor('#D7E0E8')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F7F9FB')]),
            ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
            ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
        return table
    result=[PageBreak(),P('Règles Priorités Support appliquées',h),
        P(f"Configuration chargée le {audit.get('captured_at') or data.get('generated_at','')} | Référence {audit.get('fingerprint','-')}"),
        P(audit.get('method') or 'Même moteur de calcul que Support technique Nelyio.'),
        P('Les règles sont évaluées par rang décroissant. La première règle active satisfaite détermine le niveau. ET exige toutes les conditions ; OU en exige au moins une. Le niveau par défaut s’applique si aucune règle ne correspond.')]
    rows=[['Niveau / couleur','Rang','Logique / état','Conditions appliquées']]
    for policy in policies:
        conditions=policy.get('conditions') or []
        sep=' ET ' if policy.get('match_mode')=='ALL' else ' OU '
        cond='Niveau par défaut' if policy.get('is_fallback') else sep.join(f"{c.get('label') or c.get('metric')} {c.get('operator')} {c.get('value'):g} {c.get('unit') or ''}".strip() for c in conditions)
        logic='Défaut' if policy.get('is_fallback') else ('ET' if policy.get('match_mode')=='ALL' else 'OU')
        rows.append([_priority_cell(dict(priority=policy.get('priority'),priority_color=policy.get('color')),cell),str(policy.get('rank',0)),logic+' / '+('actif' if policy.get('enabled') else 'désactivé'),cond or 'Aucune condition : non déclenchée'])
    if len(rows)==1:rows.append(['Non renseigné','-','-','Aucun instantané disponible.'])
    result.append(tbl(rows,[32,15,26,105]));result.append(Spacer(1,4*mm))
    result.append(P('Déclarations ponctuelles prises en compte',h))
    drows=[['ID / type','Cible','Période','Auteur / justification']]
    for declaration in declarations:
        targets=[]
        for target in declaration.get('targets') or []:
            prefix='Agent' if target.get('target_type')=='AGENT' else 'Groupe'
            targets.append(f"{prefix} {target.get('target_key') or '-'}")
        period=f"{declaration.get('start_at') or '-'} -> {declaration.get('end_at') or '-'}"
        author=str(declaration.get('created_by') or '-')
        comment=str(declaration.get('comment') or '').strip()
        if comment: author+=f" | {comment}"
        drows.append([f"#{declaration.get('id')} · {declaration.get('type_label') or declaration.get('declaration_type') or 'Autre'}",', '.join(targets) or '-',period,author])
    if len(drows)==1:drows.append(['Aucune','-','-','Aucune déclaration active ne chevauche cette période.'])
    result.append(tbl(drows,[28,42,48,60]));result.append(Spacer(1,4*mm))
    result.append(P('Paramètres du score et classification',h))
    def v(key):
        value=cfg.get(key)
        if isinstance(value,bool):return 'Oui' if value else 'Non'
        if isinstance(value,(float,int)):return f'{value:g}'
        return str(value) if value is not None else '-'
    details=[['Règle','Paramètres utilisés'],
        ['Points par événement',f"Déconnexion technique : {v('technical_disconnect_points')} pt ; bonus en appel : {v('in_call_bonus_points')} pt ; collectif : {v('collective_disconnect_points')} pt ; fermeture / pause probable : {v('probable_closure_points')} pt."],
        ['Fréquences', 'Les points liés aux événements et aux séries rapprochées sont ramenés au nombre de jours travaillés observés.'],
        ['Séries rapprochées',f"Au moins {v('burst_min_count')} coupures en {v('burst_window_minutes')} min ; {v('burst_points')} pt par série, normalisés par jour travaillé."],
        ['Récurrence',f"Au moins {v('recurrence_days_threshold')} jours touchés : +{v('recurrence_days_points')} pt. Au moins {v('recurrence_percent_threshold')} % des jours travaillés touchés, avec au moins {v('recurrence_percent_min_worked_days')} jours observés : +{v('recurrence_percent_points')} pt."],
        ['Temps perdu technique',f"Par jour touché : seuil bas {v('lost_minutes_low_threshold')} min, +{v('lost_minutes_low_points')} pt ; seuil haut {v('lost_minutes_high_threshold')} min, +{v('lost_minutes_high_points')} pt. Seul le palier le plus haut atteint est appliqué."],
        ['Incident collectif',f"Au moins {v('collective_min_agents')} agents distincts dans une fenêtre de {v('collective_window_seconds')} secondes."],
        ['Fermeture / pause probable',f"Détection activée : {v('probable_closure_enabled')}. Début entre {v('probable_closure_start_from')} et {v('probable_closure_start_to')}, durée {v('probable_closure_min_minutes')}-{v('probable_closure_max_minutes')} min. Hors appel, avec activité avant et après à {v('probable_closure_activity_tolerance_minutes')} min au plus : l’horaire seul ne suffit pas."],
        ['Anomalies et contexte', 'Les coupures de plus de 1 h et les contextes inactifs sont conservés séparément. Les fermetures probables et incidents collectifs suivent les points configurés ci-dessus.'],
        ['Dénominateurs des policies', 'Les mesures / jour couvert utilisent les jours avec source exploitable ; les mesures / jour travaillé utilisent l’activité observée de l’agent ; les mesures / jour touché utilisent ses jours de coupure technique. Le % des jours sélectionnés inclut tous les jours calendaires sélectionnés.'],
    ]
    result.append(tbl(details,[40,138]))
    result.append(Spacer(1,3*mm))
    result.append(P(f"Période : {data.get('period_days') or 7} jour(s), dates incluses ; maximum 30 jours. Pour une comparaison, la période précédente est contiguë, sans chevauchement et de même durée. Les deux périodes utilisent le même instantané de configuration actuel ; ce n’est pas une reconstitution des anciennes policies."))
    result.append(P('Un agent sans activité observée est NON ÉVALUÉ, pas déclaré sans incident. Le rapport oriente uniquement le diagnostic technique, jamais la performance des agents.'))
    if data.get("report_type")=="comparison":
        result.append(P("Règle : mêmes filtres sur les deux périodes. Une variation absolue inférieure à 5 % est classée stable. Les métriques sensibles au nombre de jours sont ramenées par jour couvert. Une journée manquante reste visible dans les graphiques et doit conduire à une lecture prudente."))
    return result




def _creer_histogrammes_speciaux(BLUE, Drawing, NAVY, MUTED, TEXT, String, Rect, colors, mm, stringWidth):
    """Conserve le helper graphique reel dans ce module pour ses appelants historiques."""
    def hbars(rows, title_text, max_rows=10, formatter=None, width=84*mm, accent=BLUE, compact=False):
        rows=list(rows or [])[:max_rows]
        rh=9 if compact else 10
        height=max(31,16+rh*max(1,len(rows)))
        d=Drawing(width,height)
        d.add(String(0,height-8,title_text,fontName='Helvetica-Bold',fontSize=7.7 if compact else 8.3,fillColor=NAVY))
        vals=[max(0,float(r.get('value') or 0)) for r in rows]
        mv=max(vals,default=1) or 1
        lw=31*mm if width < 100*mm else 57*mm
        label_font_size=5.5
        shown_values=[formatter(v) if formatter else (f'{v:.1f}' if abs(v-round(v))>.01 else str(int(v))) for v in vals]
        # Reserve enough room on the right for the widest value label so it
        # never overflows past this chart's own width (which previously made
        # it overlap the neighbouring chart when the bar was near its max).
        max_label_w=max([stringWidth(t,'Helvetica-Bold',label_font_size) for t in shown_values],default=10)
        reserve=max_label_w+6
        cw=max(10,width-lw-11-reserve)
        y=height-19
        if not rows:
            d.add(String(0,y,'Aucune donnée',fontName='Helvetica',fontSize=6.6,fillColor=MUTED));return d
        for idx,(row,v,shown) in enumerate(zip(rows,vals,shown_values)):
            label=_clip(row.get('label'),20 if width<100*mm else 31)
            d.add(String(0,y+1,label,fontName='Helvetica',fontSize=5.7 if compact else 6.1,fillColor=TEXT))
            d.add(Rect(lw,y,cw,5.2,fillColor=colors.HexColor('#EDF1F4'),strokeColor=None))
            bw=cw*v/mv if mv else 0
            bar_color=NAVY if idx<3 else accent
            d.add(Rect(lw,y,bw,5.2,fillColor=bar_color,strokeColor=None))
            d.add(String(lw+bw+3,y+1,shown,fontName='Helvetica-Bold',fontSize=label_font_size,fillColor=TEXT))
            y-=rh
        return d

    return hbars

def _build_detailed_pdf(data):
    """Point d'entree historique ; le chargement du rendu reste differe."""
    from weekly_reports_detailed import _build_detailed_pdf as construire
    return construire(data)


def _build_special_pdf(data, report_type):
    """Point d'entree historique pour la vue d'ensemble et la comparaison."""
    from weekly_reports_special import _build_special_pdf as construire
    return construire(data, report_type)

def build_weekly_pdf(data):
    report_type=str(data.get('report_type') or 'overview').lower()
    if report_type=='detailed':
        return _build_detailed_pdf(data)
    if report_type in ('overview','comparison'):
        return _build_special_pdf(data,report_type)
    raise ValueError('Type de rapport PDF invalide.')

