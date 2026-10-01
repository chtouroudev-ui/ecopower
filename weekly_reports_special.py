"""Sections du rapport special ; extraction sans changement du rendu V56.8."""
from __future__ import annotations

import io
import math
from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import escape

from weekly_reports import (
    _fmt_seconds, _fmt_date, _clip, _priority_cell, _report_score, _report_policy_flowables, _creer_histogrammes_speciaux,
)

@dataclass(frozen=True)
class _RenduSpecial:
    """Dependances de rendu explicites, creees pour un seul document."""

    AMBER: Any
    GREEN: Any
    GREEN_BG: Any
    GREY_DARK: Any
    P: Any
    Paragraph: Any
    ParagraphStyle: Any
    RED: Any
    RED_BG: Any
    Spacer: Any
    TEAL: Any
    Table: Any
    TableStyle: Any
    body: Any
    buf: Any
    bullet: Any
    cellstyle: Any
    doc: Any
    dominant_signal: Any
    grouped: Any
    h2: Any
    hbars: Any
    info_strip: Any
    kicker: Any
    kpi: Any
    mm: Any
    note: Any
    page_chrome: Any
    plan_table: Any
    section_band: Any
    small: Any
    status_banner: Any
    sub: Any
    subtitle: Any
    table: Any
    title: Any
    top_summary: Any
    tstyle: Any


def _preparer_rendu_special(data, report_type) -> _RenduSpecial:
    """Prepare les styles, fabriques et callbacks historiques sans assembler les sections."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable, KeepTogether
        from reportlab.graphics.shapes import Drawing, Rect, String, Line
        from reportlab.pdfbase.pdfmetrics import stringWidth
    except Exception as exc:
        raise RuntimeError("ReportLab n'est pas installe. Installer avec : py -3 -m pip install reportlab") from exc

    # Presentation palette: restrained, high-contrast and projector friendly.
    NAVY = colors.HexColor('#143A5A')
    BLUE = colors.HexColor('#2F6B9A')
    BLUE_MID = colors.HexColor('#6F9FBD')
    BLUE_LIGHT = colors.HexColor('#EAF2F8')
    TEAL = colors.HexColor('#3A7D78')
    GREEN = colors.HexColor('#2F7D59')
    GREEN_BG = colors.HexColor('#EAF6EF')
    AMBER = colors.HexColor('#A66A12')
    AMBER_BG = colors.HexColor('#FFF4E2')
    RED = colors.HexColor('#B54747')
    RED_BG = colors.HexColor('#FCECEB')
    TEXT = colors.HexColor('#1F2933')
    MUTED = colors.HexColor('#667085')
    GRID = colors.HexColor('#D7E0E8')
    LIGHT = colors.HexColor('#F6F8FA')
    WHITE = colors.white
    GREY = colors.HexColor('#B9C4CE')
    GREY_DARK = colors.HexColor('#7B8794')

    title = 'Vue d\'ensemble technique' if report_type == 'overview' else 'Comparaison de périodes'
    subtitle = 'Priorités de diagnostic - Nelyio' if report_type == 'overview' else 'Évolution technique - Nelyio'
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=14*mm, rightMargin=14*mm, topMargin=16*mm, bottomMargin=15*mm,
        title=f"{title} - {data.get('period_label','')}", author=str(data.get('generated_by') or 'Nelyio')
    )
    styles = getSampleStyleSheet()
    kicker = ParagraphStyle('PRKicker', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=7.1, leading=8.5,
                            textColor=BLUE, alignment=TA_CENTER, spaceAfter=2)
    tstyle = ParagraphStyle('PRTitle', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=21, leading=24,
                            alignment=TA_CENTER, textColor=NAVY, spaceAfter=3)
    sub = ParagraphStyle('PRSub', parent=styles['BodyText'], fontName='Helvetica', fontSize=8.4, leading=10.5,
                         alignment=TA_CENTER, textColor=MUTED, spaceAfter=7)
    sec = ParagraphStyle('PRSec', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=12.4, leading=15,
                         textColor=NAVY, spaceBefore=4, spaceAfter=5)
    h2 = ParagraphStyle('PRH2', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=9.5, leading=12,
                        textColor=NAVY, spaceBefore=3, spaceAfter=4)
    body = ParagraphStyle('PRBody', parent=styles['BodyText'], fontName='Helvetica', fontSize=8.0, leading=10.6,
                          textColor=TEXT, spaceAfter=3)
    small = ParagraphStyle('PRSmall', parent=body, fontSize=6.8, leading=8.5, textColor=MUTED)
    note = ParagraphStyle('PRNote', parent=body, fontSize=7.2, leading=9.4, textColor=MUTED,
                          backColor=LIGHT, borderColor=GRID, borderWidth=.45, borderPadding=6, spaceBefore=3, spaceAfter=5)
    cellstyle = ParagraphStyle('PRCell', parent=body, fontSize=6.7, leading=8.2)
    headstyle = ParagraphStyle('PRHead', parent=cellstyle, fontName='Helvetica-Bold', textColor=WHITE)
    center_cell = ParagraphStyle('PRCenter', parent=cellstyle, alignment=TA_CENTER)
    klabel = ParagraphStyle('PRKLabel', parent=body, fontSize=6.6, leading=8, alignment=TA_CENTER, textColor=MUTED)
    kval = ParagraphStyle('PRKVal', parent=body, fontName='Helvetica-Bold', fontSize=14, leading=16, alignment=TA_CENTER, textColor=NAVY)
    ksub = ParagraphStyle('PRKSub', parent=body, fontSize=6.2, leading=7.5, alignment=TA_CENTER, textColor=MUTED)
    bullet = ParagraphStyle('PRBullet', parent=body, fontSize=8.0, leading=10.5, leftIndent=8, firstLineIndent=-8, spaceAfter=4)

    def P(x, sty=body):
        return Paragraph(escape(str(x or '')), sty)

    def cell(x, head=False, center=False):
        if isinstance(x, Flowable):
            return x
        st = headstyle if head else (center_cell if center else cellstyle)
        return Paragraph(escape(str(x if x is not None else '')), st)

    def table(rows, widths, header=True, center_cols=None, row_backgrounds=True):
        center_cols = set(center_cols or [])
        converted = []
        for i, row in enumerate(rows):
            converted.append([cell(v, head=(header and i == 0), center=(j in center_cols and not (header and i == 0))) for j, v in enumerate(row)])
        t = Table(converted, colWidths=widths, repeatRows=1 if header else 0, hAlign='LEFT')
        cmds = [
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('LEFTPADDING',(0,0),(-1,-1),4.5),('RIGHTPADDING',(0,0),(-1,-1),4.5),
            ('TOPPADDING',(0,0),(-1,-1),4.2),('BOTTOMPADDING',(0,0),(-1,-1),4.2),
            ('LINEBELOW',(0,0),(-1,-1),.25,GRID),
        ]
        if row_backgrounds:
            cmds.append(('ROWBACKGROUNDS',(0,1 if header else 0),(-1,-1),[WHITE,LIGHT]))
        if header:
            cmds += [('BACKGROUND',(0,0),(-1,0),NAVY),('ALIGN',(0,0),(-1,0),'CENTER'),('LINEBELOW',(0,0),(-1,0),.6,NAVY)]
        for c in center_cols:
            cmds.append(('ALIGN',(c,1 if header else 0),(c,-1),'CENTER'))
        t.setStyle(TableStyle(cmds))
        return t

    def info_strip(items):
        # Compact meta information instead of a large form-like table.
        cells=[]
        for label, value in items:
            content = Paragraph(f"<font color='#667085' size='6.3'>{escape(str(label).upper())}</font><br/><b>{escape(str(value or '-'))}</b>", body)
            cells.append(content)
        widths=[178*mm/len(cells)]*len(cells)
        t=Table([cells],colWidths=widths)
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,-1),LIGHT),('BOX',(0,0),(-1,-1),.4,GRID),('INNERGRID',(0,0),(-1,-1),.25,GRID),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
            ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
        ]))
        return t

    def kpi(label, value, caption='', accent=BLUE, delta=None, status=None):
        cap = caption
        if delta is not None:
            cap = f"{delta:+.1f} % vs avant" if delta is not None else caption
        value_style = ParagraphStyle(f'KVal{str(label)[:8]}{id(label)}', parent=kval, textColor=accent)
        rows = [[Paragraph(escape(str(label)),klabel)], [Paragraph(escape(str(value)),value_style)], [Paragraph(escape(str(cap or '')),ksub)]]
        t=Table(rows,colWidths=[42.5*mm],rowHeights=[9*mm,10*mm,7*mm])
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,-1),WHITE),('BOX',(0,0),(-1,-1),.45,GRID),('LINEABOVE',(0,0),(-1,0),2.1,accent),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(0,0),(-1,-1),'CENTER'),('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),
        ]))
        return t

    def status_banner(label, detail, code='stable'):
        accent={'improved':GREEN,'degraded':RED,'stable':AMBER,'unavailable':GREY_DARK}.get(code,AMBER)
        bg={'improved':GREEN_BG,'degraded':RED_BG,'stable':AMBER_BG,'unavailable':LIGHT}.get(code,LIGHT)
        lbl=ParagraphStyle('StatusLabel'+code,parent=body,fontName='Helvetica-Bold',fontSize=14,leading=17,textColor=accent,alignment=TA_CENTER)
        det=ParagraphStyle('StatusDetail'+code,parent=body,fontSize=7.6,leading=9.6,textColor=TEXT,alignment=TA_CENTER)
        t=Table([[Paragraph(escape(str(label)),lbl)],[Paragraph(escape(str(detail or '')),det)]],colWidths=[178*mm])
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,-1),bg),('BOX',(0,0),(-1,-1),.6,accent),('LINEABOVE',(0,0),(-1,0),3,accent),
            ('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
        ]))
        return t

    def section_band(number, label, subtitle_text=''):
        left=Paragraph(f"<b>{escape(str(number))}</b>", ParagraphStyle('BandNum'+str(number),parent=body,fontSize=10,leading=12,textColor=WHITE,alignment=TA_CENTER))
        right=Paragraph(f"<b>{escape(str(label))}</b>" + (f"<br/><font size='7' color='#667085'>{escape(str(subtitle_text))}</font>" if subtitle_text else ''), body)
        t=Table([[left,right]],colWidths=[13*mm,165*mm])
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(0,0),NAVY),('BACKGROUND',(1,0),(1,0),BLUE_LIGHT),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('LEFTPADDING',(0,0),(0,0),2),('RIGHTPADDING',(0,0),(0,0),2),('LEFTPADDING',(1,0),(1,0),8),('RIGHTPADDING',(1,0),(1,0),6),
            ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('BOX',(0,0),(-1,-1),.35,GRID),
        ]))
        return t

    hbars = _creer_histogrammes_speciaux(BLUE=BLUE, Drawing=Drawing, NAVY=NAVY, MUTED=MUTED, TEXT=TEXT, String=String, Rect=Rect, colors=colors, mm=mm, stringWidth=stringWidth)

    def grouped(rows, title_text, keya='current', keyb='previous', width=178*mm, height=38*mm):
        d=Drawing(width,height)
        d.add(String(0,height-8,title_text,fontName='Helvetica-Bold',fontSize=8.4,fillColor=NAVY))
        d.add(Rect(width-51,height-11,6,6,fillColor=BLUE,strokeColor=None));d.add(String(width-42,height-10,'Actuel',fontSize=5.7,fillColor=MUTED))
        d.add(Rect(width-24,height-11,6,6,fillColor=GREY,strokeColor=None));d.add(String(width-15,height-10,'Avant',fontSize=5.7,fillColor=MUTED))
        vals=[]
        for r in rows:
            for k in (keya,keyb):
                if r.get(k) is not None:
                    vals.append(max(0,float(r[k])))
        mv=max(vals,default=1) or 1
        pb=12;pt=height-18;ph=pt-pb;n=max(1,len(rows));gw=(width-8)/n;bw=max(4,min(11,(gw-5)/2))
        for i,r in enumerate(rows):
            center=4+i*gw+gw/2
            for key,color,off in ((keyb,GREY,-bw/2-1),(keya,BLUE,bw/2+1)):
                val=r.get(key);x=center+off-bw/2
                if val is None:continue
                v=max(0,float(val));bh=ph*v/mv
                d.add(Rect(x,pb,bw,bh,fillColor=color,strokeColor=None))
            if i%max(1,math.ceil(n/12))==0 or i==n-1:d.add(String(center,1,str(r.get('label') or ''),textAnchor='middle',fontName='Helvetica-Bold',fontSize=5.8,fillColor=MUTED))
        d.add(Line(4,pb,width-4,pb,strokeColor=GRID,strokeWidth=.5))
        return d

    def dominant_signal(r):
        if int(r.get('anomaly_count') or 0) >= 2:
            return 'Anomalies longues'
        if float(r.get('inactive_seconds') or 0) >= 1800:
            return 'Contexte inactif'
        if float(r.get('lost_seconds') or 0) >= 7200:
            return 'Temps de coupure'
        if int(r.get('deco_call') or 0) >= 10:
            return 'Coupures en appel'
        return 'Décos récurrentes'

    def top_summary(agent_rows, ds, sig):
        touched=int(ds.get('impacted_agents') or 0);total=max(1,int(data.get('scope_agent_count') or len(agent_rows) or 1))
        top=agent_rows[0] if agent_rows else {}
        return [
            f"{touched} agent(s)/poste(s) touché(s) sur {total} dans le périmètre ({100.0*touched/total:.0f} %).",
            f"Temps de coupure cumulé : {_fmt_seconds(ds.get('total_lost',0))}. Premier poste selon Support : {top.get('name') or top.get('agent') or '-'} avec {_fmt_seconds(top.get('lost_seconds',0))}.",
            f"Signaux sensibles : {int(ds.get('total_deco_call') or 0)} coupure(s) pendant appel, {int(ds.get('anomalies_over_1h') or 0)} anomalie(s) > 1 h et {int(sig.get('inactive_count') or 0)} contexte(s) inactif(s).",
        ]

    def plan_table(items):
        cells=[]
        for num,label in items:
            cells.append(Paragraph(f"<font color='#2F6B9A'><b>{escape(str(num))}</b></font><br/><font size='7'>{escape(str(label))}</font>", body))
        t=Table([cells],colWidths=[178*mm/len(cells)]*len(cells))
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,-1),LIGHT),('BOX',(0,0),(-1,-1),.4,GRID),('INNERGRID',(0,0),(-1,-1),.2,GRID),
            ('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
        ]));return t

    def page_chrome(canvas, docobj):
        canvas.saveState()
        canvas.setStrokeColor(GRID);canvas.setLineWidth(.45)
        if docobj.page > 1:
            canvas.line(14*mm,A4[1]-9*mm,A4[0]-14*mm,A4[1]-9*mm)
            canvas.setFont('Helvetica-Bold',6.7);canvas.setFillColor(NAVY)
            canvas.drawString(14*mm,A4[1]-7*mm,'NELYIO | SUPPORT TECHNIQUE')
            canvas.setFont('Helvetica',6.5);canvas.setFillColor(MUTED)
            canvas.drawRightString(A4[0]-14*mm,A4[1]-7*mm,f"{title} | {data.get('period_label','')}")
        canvas.setFont('Helvetica',6.5);canvas.setFillColor(MUTED)
        canvas.drawString(14*mm,8*mm,f"Nelyio - {data.get('period_label','')} - Confidentiel")
        canvas.drawRightString(A4[0]-14*mm,8*mm,f'Page {docobj.page}')
        canvas.restoreState()

    return _RenduSpecial(
        AMBER=AMBER,
        GREEN=GREEN,
        GREEN_BG=GREEN_BG,
        GREY_DARK=GREY_DARK,
        P=P,
        Paragraph=Paragraph,
        ParagraphStyle=ParagraphStyle,
        RED=RED,
        RED_BG=RED_BG,
        Spacer=Spacer,
        TEAL=TEAL,
        Table=Table,
        TableStyle=TableStyle,
        body=body,
        buf=buf,
        bullet=bullet,
        cellstyle=cellstyle,
        doc=doc,
        dominant_signal=dominant_signal,
        grouped=grouped,
        h2=h2,
        hbars=hbars,
        info_strip=info_strip,
        kicker=kicker,
        kpi=kpi,
        mm=mm,
        note=note,
        page_chrome=page_chrome,
        plan_table=plan_table,
        section_band=section_band,
        small=small,
        status_banner=status_banner,
        sub=sub,
        subtitle=subtitle,
        table=table,
        title=title,
        top_summary=top_summary,
        tstyle=tstyle,
    )


def _section_entete_speciale(rendu: _RenduSpecial, data, excluded) -> list[Any]:
    """Produit les flowables de section entete speciale dans leur ordre historique."""
    P = rendu.P
    Spacer = rendu.Spacer
    info_strip = rendu.info_strip
    kicker = rendu.kicker
    mm = rendu.mm
    sub = rendu.sub
    subtitle = rendu.subtitle
    title = rendu.title
    tstyle = rendu.tstyle
    story = []
    story.append(P('NELYIO | RAPPORT TECHNIQUE', kicker))
    story.append(P(title, tstyle))
    story.append(P(f"{subtitle} | {data.get('period_label','')} | {_fmt_date(data.get('date_from'))} au {_fmt_date(data.get('date_to'))}", sub))
    story.append(info_strip([
        ('Périmètre', data.get('scope_label') or 'Global'),
        ('Plage', data.get('time_label') or '-'),
        ('Exclusions', excluded),
    ]))
    story.append(Spacer(1,4*mm))
    return story


def _section_synthese_vue_ensemble(rendu: _RenduSpecial, active, agents, ds, sig) -> list[Any]:
    """Produit les flowables de section synthese vue ensemble dans leur ordre historique."""
    AMBER = rendu.AMBER
    P = rendu.P
    RED = rendu.RED
    Spacer = rendu.Spacer
    TEAL = rendu.TEAL
    Table = rendu.Table
    TableStyle = rendu.TableStyle
    bullet = rendu.bullet
    cellstyle = rendu.cellstyle
    dominant_signal = rendu.dominant_signal
    h2 = rendu.h2
    info_strip = rendu.info_strip
    kpi = rendu.kpi
    mm = rendu.mm
    plan_table = rendu.plan_table
    section_band = rendu.section_band
    table = rendu.table
    top_summary = rendu.top_summary
    story = []
    summary=top_summary(agents,ds,sig)
    cards=[
        kpi('Temps de coupure',_fmt_seconds(ds.get('total_lost',0)),f"{_fmt_seconds(float(ds.get('total_lost') or 0)/active)} / jour",RED),
        kpi('Coupures en appel',ds.get('total_deco_call',0),f"{float(ds.get('total_call_percent') or 0):.1f} % des décos",AMBER),
        kpi('Anomalies > 1 h',ds.get('anomalies_over_1h',0),'hors stats normales',RED),
        kpi('Contexte inactif',_fmt_seconds(sig.get('inactive_seconds',0)),f"{sig.get('inactive_count',0)} épisode(s)",TEAL),
    ]
    grid=Table([cards],colWidths=[44.5*mm]*4);grid.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2)]))
    story.append(grid);story.append(Spacer(1,3*mm))
    raw_deco=int(ds.get('raw_total_deco',ds.get('total_deco',0)) or 0)
    raw_lost=float(ds.get('raw_total_lost',ds.get('total_lost',0)) or 0)
    story.append(info_strip([
        ('Brut',f"{raw_deco} coupure(s) | {_fmt_seconds(raw_lost)}"),
        ('Corrigé',f"{int(ds.get('total_deco') or 0)} coupure(s) | {_fmt_seconds(ds.get('total_lost',0))}"),
        ('Traitement','Policies + Déclarations, logs bruts conservés'),
    ]))
    story.append(Spacer(1,4*mm))
    story.append(section_band('01','Synthèse en 30 secondes','Les éléments à connaître avant d’entrer dans le détail'))
    story.append(Spacer(1,2*mm))
    for s in summary: story.append(P(f"- {s}",bullet))
    top5_rows=[['Priorité','Agent / poste','Signal dominant','Temps coupure','En appel']]
    for i,r in enumerate(agents[:5],1):
        top5_rows.append([_priority_cell(r,cellstyle),_clip(r.get('name') or r.get('agent'),29),dominant_signal(r),_fmt_seconds(r.get('lost_seconds',0)),r.get('deco_call',0)])
    if len(top5_rows)==1: top5_rows.append(['-','Aucun','-','0 s',0])
    story.append(P('5 priorités techniques',h2));story.append(table(top5_rows,[28*mm,41*mm,42*mm,37*mm,30*mm],center_cols=[0,3,4]))
    story.append(Spacer(1,4*mm))
    story.append(P('Plan du rapport',h2))
    story.append(plan_table([('01','Synthèse'),('02','Panorama des signaux'),('03','Top 20 à investiguer'),('04','Actions techniques')]))
    return story


def _section_panorama_signaux(rendu: _RenduSpecial, agents) -> list[Any]:
    """Produit les flowables de section panorama signaux dans leur ordre historique."""
    AMBER = rendu.AMBER
    P = rendu.P
    RED = rendu.RED
    Spacer = rendu.Spacer
    TEAL = rendu.TEAL
    Table = rendu.Table
    TableStyle = rendu.TableStyle
    hbars = rendu.hbars
    mm = rendu.mm
    note = rendu.note
    section_band = rendu.section_band
    story = []
    # Page 2 - visual panorama
    story.append(Spacer(1,14));story.append(section_band('02','Panorama des signaux','Quatre angles complémentaires pour éviter un classement trompeur'))
    loss=sorted(agents,key=lambda r:-float(r.get('lost_seconds') or 0))
    incall=sorted([r for r in agents if int(r.get('deco_call') or 0)>0],key=lambda r:-int(r.get('deco_call') or 0))
    anom=sorted([r for r in agents if int(r.get('anomaly_count') or 0)>0],key=lambda r:-int(r.get('anomaly_count') or 0))
    inactive=sorted([r for r in agents if int(r.get('inactive_seconds') or 0)>0],key=lambda r:-int(r.get('inactive_seconds') or 0))
    c1=hbars([{'label':r.get('name') or r.get('agent'),'value':r.get('lost_seconds',0)} for r in loss],'Temps de coupure - Top 8',8,_fmt_seconds,84*mm,RED,True)
    c2=hbars([{'label':r.get('name') or r.get('agent'),'value':r.get('deco_call',0)} for r in incall],'Coupures en appel - Top 8',8,None,84*mm,AMBER,True)
    row=Table([[c1,c2]],colWidths=[88.5*mm,88.5*mm]);row.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),1),('RIGHTPADDING',(0,0),(-1,-1),1)]));story.append(row);story.append(Spacer(1,4*mm))
    c3=hbars([{'label':r.get('name') or r.get('agent'),'value':r.get('anomaly_count',0)} for r in anom],'Anomalies > 1 h - Top 8',8,None,84*mm,RED,True)
    c4=hbars([{'label':r.get('name') or r.get('agent'),'value':r.get('inactive_seconds',0)} for r in inactive],'Contexte inactif - Top 8',8,_fmt_seconds,84*mm,TEAL,True)
    row=Table([[c3,c4]],colWidths=[88.5*mm,88.5*mm]);row.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),1),('RIGHTPADDING',(0,0),(-1,-1),1)]));story.append(row)
    story.append(Spacer(1,3*mm));story.append(P("Lecture : ces graphiques décrivent les signaux des postes retenus. Ils ne remplacent pas les policies Support. Les anomalies longues et contextes inactifs restent distincts du score technique.",note))
    return story


def _section_postes_prioritaires(rendu: _RenduSpecial, agents) -> list[Any]:
    """Produit les flowables de section postes prioritaires dans leur ordre historique."""
    P = rendu.P
    Spacer = rendu.Spacer
    cellstyle = rendu.cellstyle
    mm = rendu.mm
    note = rendu.note
    section_band = rendu.section_band
    table = rendu.table
    story = []
    # Page 3 - top 20 table, still readable on one page.
    story.append(Spacer(1,14));story.append(section_band('03','Top 20 à investiguer','Classement selon les policies et le score Support configuré'))
    rows=[['#','Priorité','Agent / groupe','Score','Temps','Décos','Appel','Anom.','Inactif']]
    for i,r in enumerate(agents[:20],1):
        rows.append([i,_priority_cell(r,cellstyle),f"{r.get('name') or r.get('agent')} / {r.get('group_name') or '-'}",_report_score(r.get('technical_score')),_fmt_seconds(r.get('lost_seconds',0)),r.get('deco',0),r.get('deco_call',0),r.get('anomaly_count',0),_fmt_seconds(r.get('inactive_seconds',0))])
    if len(rows)==1: rows.append(['-','-','Aucun','-','0 s',0,0,0,'0 s'])
    t=table(rows,[8*mm,29*mm,34*mm,14*mm,25*mm,12*mm,13*mm,13*mm,20*mm],center_cols=[0,1,5,6,7])
    # Configured priority colors are shown in each badge, never by row rank.
    story.append(t);story.append(Spacer(1,3*mm))
    story.append(P("Les niveaux et couleurs sont ceux de Priorités Support. Le rang de la policy puis le score déterminent l’ordre ; la position dans le Top 20 ne crée pas un autre niveau.",note))
    return story


def _section_actions_techniques(rendu: _RenduSpecial, agents, integrity) -> list[Any]:
    """Produit les flowables de section actions techniques dans leur ordre historique."""
    P = rendu.P
    Spacer = rendu.Spacer
    cellstyle = rendu.cellstyle
    dominant_signal = rendu.dominant_signal
    mm = rendu.mm
    note = rendu.note
    section_band = rendu.section_band
    status_banner = rendu.status_banner
    table = rendu.table
    story = []
    # Page 4 - actions and interpretation.
    story.append(Spacer(1,14));story.append(section_band('04','Actions techniques recommandées','Transformer le constat en plan de vérification'))
    act=[['Prio.','Agent / poste','Signal principal','Cause probable / piste','Action recommandée']]
    for i,r in enumerate(agents[:6],1):
        act.append([_priority_cell(r,cellstyle),_clip(r.get('name') or r.get('agent'),23),dominant_signal(r),r.get('likely_cause') or 'À qualifier',r.get('suggested_action') or 'Vérifier le contexte technique.'])
    if len(act)==1:act.append(['-','Aucun','-','-','Aucune action particulière.'])
    story.append(table(act,[29*mm,29*mm,31*mm,38*mm,51*mm],center_cols=[0]))
    story.append(Spacer(1,4*mm))
    cov_label=f"Fiabilité des données : {integrity.get('score','-')}/100 - {integrity.get('label','-')}"
    story.append(status_banner(cov_label, 'La lecture des priorités doit toujours être rapprochée de la couverture des jours et des exclusions appliquées.', 'stable' if int(integrity.get('score') or 0)>=90 else 'unavailable'))
    story.append(Spacer(1,3*mm));story.append(P("Méthode : le score, les niveaux, les conditions ET/OU et les couleurs proviennent du même moteur que Support technique Nelyio. La configuration utilisée figure en fin de rapport. Aucune note de productivité ou de performance n’est calculée.",note))
    return story


def _section_verdict_comparaison(rendu: _RenduSpecial, comparison, metrics) -> list[Any]:
    """Produit les flowables de section verdict comparaison dans leur ordre historique."""
    AMBER = rendu.AMBER
    GREEN = rendu.GREEN
    GREEN_BG = rendu.GREEN_BG
    GREY_DARK = rendu.GREY_DARK
    P = rendu.P
    Paragraph = rendu.Paragraph
    ParagraphStyle = rendu.ParagraphStyle
    RED = rendu.RED
    RED_BG = rendu.RED_BG
    Spacer = rendu.Spacer
    Table = rendu.Table
    TableStyle = rendu.TableStyle
    body = rendu.body
    h2 = rendu.h2
    kpi = rendu.kpi
    mm = rendu.mm
    plan_table = rendu.plan_table
    small = rendu.small
    status_banner = rendu.status_banner
    story = []
    verdict=comparison.get('verdict') or {};code=verdict.get('code') or 'unavailable'
    story.append(status_banner(verdict.get('label') or 'Comparaison indisponible',verdict.get('detail') or '',code));story.append(Spacer(1,4*mm))
    # Show the six most decision-useful indicators as cards.
    cards=[]
    for m in metrics[:6]:
        status=m.get('status') or 'unknown';accent={'improved':GREEN,'degraded':RED,'stable':AMBER}.get(status,GREY_DARK)
        key=m.get('key','');cur=m.get('current');delta=m.get('delta_pct')
        if cur is None: val='-'
        elif key in ('lost_minutes_per_day','inactive_minutes_per_day'): val=_fmt_seconds(float(cur)*60)+'/j'
        else: val=f"{float(cur):.1f}"
        cards.append(kpi(m.get('label') or '-',val,'n/a vs avant' if delta is None else f"{delta:+.1f} % vs avant",accent))
    while len(cards)<6:cards.append(kpi('-','-','',GREY_DARK))
    for start in (0,3):
        g=Table([cards[start:start+3]],colWidths=[59.3*mm]*3);g.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2)]));story.append(g);story.append(Spacer(1,2.5*mm))
    improved=[m for m in metrics if m.get('status')=='improved'];degraded=[m for m in metrics if m.get('status')=='degraded']
    def list_box(title_txt, arr, accent, bg):
        rows=[[Paragraph(escape(title_txt),ParagraphStyle('LB'+title_txt,parent=body,fontName='Helvetica-Bold',fontSize=8.3,textColor=accent))]]
        for m in arr[:4]:
            d=m.get('delta_pct');rows.append([P(f"- {m.get('label')} : {'n/a' if d is None else f'{d:+.1f} %'}",small)])
        if len(rows)==1:rows.append([P('- Aucun indicateur',small)])
        t=Table(rows,colWidths=[86*mm]);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),bg),('BOX',(0,0),(-1,-1),.45,accent),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]));return t
    boxes=Table([[list_box('Ce qui s’améliore',improved,GREEN,GREEN_BG),list_box('Ce qui se dégrade',degraded,RED,RED_BG)]],colWidths=[89*mm,89*mm]);boxes.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),1),('RIGHTPADDING',(0,0),(-1,-1),1)]));story.append(boxes)
    story.append(Spacer(1,4*mm));story.append(P('Plan du rapport',h2));story.append(plan_table([('01','Verdict & écarts'),('02','Évolution quotidienne'),('03','Agents en évolution'),('04','Méthode & couverture')]))
    return story


def _section_evolution_quotidienne(rendu: _RenduSpecial, comparison) -> list[Any]:
    """Produit les flowables de section evolution quotidienne dans leur ordre historique."""
    P = rendu.P
    Spacer = rendu.Spacer
    grouped = rendu.grouped
    mm = rendu.mm
    note = rendu.note
    section_band = rendu.section_band
    story = []
    # Page 2 - daily evolution.
    story.append(Spacer(1,14));story.append(section_band('02','Évolution quotidienne','Comparer les journées équivalentes, sans masquer les jours manquants'))
    daily=comparison.get('daily') or []
    story.append(grouped(daily,'Déconnexions par jour - actuel vs période précédente'));story.append(Spacer(1,4*mm))
    lost=[{'label':r.get('label'),'current':(r.get('current_lost_seconds') or 0)/60 if r.get('current_lost_seconds') is not None else None,'previous':(r.get('previous_lost_seconds') or 0)/60 if r.get('previous_lost_seconds') is not None else None} for r in daily]
    story.append(grouped(lost,'Temps de coupure par jour (minutes)'));story.append(Spacer(1,3*mm))
    cov_current=int(comparison.get('current_active_days') or 0);cov_prev=int(comparison.get('previous_active_days') or 0)
    story.append(P(f"Couverture : période actuelle {cov_current} jour(s) couvert(s), période précédente {cov_prev} jour(s) couvert(s). Les indicateurs agrégés sont ramenés par jour couvert lorsque nécessaire.",note))
    return story


def _section_evolution_agents(rendu: _RenduSpecial, data) -> list[Any]:
    """Produit les flowables de section evolution agents dans leur ordre historique."""
    P = rendu.P
    Spacer = rendu.Spacer
    cellstyle = rendu.cellstyle
    h2 = rendu.h2
    mm = rendu.mm
    note = rendu.note
    section_band = rendu.section_band
    table = rendu.table
    story = []
    # Page 3 - agent movements.
    story.append(Spacer(1,14));story.append(section_band('03','Agents en évolution','Repérer les postes dont le profil technique change le plus'))
    ac=list(data.get('agent_comparison') or [])
    worse=[r for r in ac if float(r.get('delta_score') or 0)>0][:8]
    better=sorted([r for r in ac if float(r.get('delta_score') or 0)<0],key=lambda r:r.get('delta_score',0))[:8]
    wrows=[['Agent','Ecart score','Temps actuel','Avant','En appel','Anom.']]
    for r in worse:wrows.append([_clip(r.get('name') or r.get('agent'),28),f"+{r.get('delta_score',0):.1f}",_fmt_seconds(r.get('current_lost',0)),_fmt_seconds(r.get('previous_lost',0)),f"{r.get('current_call',0)} / {r.get('previous_call',0)}",f"{r.get('current_anomaly',0)} / {r.get('previous_anomaly',0)}"])
    if len(wrows)==1:wrows.append(['Aucune dégradation nette','-','-','-','-','-'])
    brows=[['Agent','Ecart score','Temps actuel','Avant','En appel','Anom.']]
    for r in better:brows.append([_clip(r.get('name') or r.get('agent'),28),f"{r.get('delta_score',0):.1f}",_fmt_seconds(r.get('current_lost',0)),_fmt_seconds(r.get('previous_lost',0)),f"{r.get('current_call',0)} / {r.get('previous_call',0)}",f"{r.get('current_anomaly',0)} / {r.get('previous_anomaly',0)}"])
    if len(brows)==1:brows.append(['Aucune amélioration nette','-','-','-','-','-'])
    story.append(P('Dégradations techniques à vérifier',h2));story.append(table(wrows,[53*mm,20*mm,31*mm,31*mm,22*mm,21*mm],center_cols=[1,4,5]));story.append(Spacer(1,4*mm))
    story.append(P('Améliorations techniques observées',h2));story.append(table(brows,[53*mm,20*mm,31*mm,31*mm,22*mm,21*mm],center_cols=[1,4,5]))
    story.append(Spacer(1,3*mm));story.append(P("Le score Support sert uniquement à détecter une évolution technique du poste. Les agents ne sont pas comparés entre eux sur la performance métier.",note))

    story.append(Spacer(1,4*mm));story.append(P('Priorités Support par période',h2))
    changes={str(r.get('agent')):r for r in ac}
    prows=[['Agent / poste','Priorité actuelle','Score actuel','Priorité avant','Score avant','Lecture']]
    for agent in data.get('report_agents') or []:
        r=changes.get(str(agent.get('agent'))) or {}
        if not r:continue
        prows.append([agent.get('name') or agent.get('agent'),_priority_cell(dict(priority=r.get('current_priority'),priority_color=r.get('current_priority_color')),cellstyle),_report_score(agent.get('technical_score')),_priority_cell(dict(priority=r.get('previous_priority'),priority_color=r.get('previous_priority_color')),cellstyle),_report_score(r.get('previous_score')),'Comparable' if r.get('comparable') else 'Données insuffisantes'])
    if len(prows)==1:prows.append(['Aucun','-','-','-','-','Non comparable'])
    story.append(table(prows,[43*mm,31*mm,18*mm,31*mm,18*mm,37*mm]))
    story.append(P('Sans activité observée sur une période, aucun écart de score n’est interprété comme une amélioration ou une dégradation.',note))
    return story


def _section_methode_comparaison(rendu: _RenduSpecial, comparison, metrics) -> list[Any]:
    """Produit les flowables de section methode comparaison dans leur ordre historique."""
    Spacer = rendu.Spacer
    grouped = rendu.grouped
    mm = rendu.mm
    section_band = rendu.section_band
    table = rendu.table
    story = []
    # Page 4 - inactive context + full metric table + method.
    story.append(Spacer(1,14));story.append(section_band('04','Méthode & couverture','Conserver une lecture fiable et explicable'))
    inactive=[{'label':r.get('label'),'current':(r.get('current_inactive_seconds') or 0)/60,'previous':(r.get('previous_inactive_seconds') or 0)/60} for r in (comparison.get('daily') or [])]
    story.append(grouped(inactive,'Temps en contexte inactif par jour (minutes)'));story.append(Spacer(1,4*mm))
    mrows=[['Indicateur','Actuel','Avant','Écart','Lecture']]
    for m in metrics:
        cur=m.get('current');pre=m.get('previous');key=m.get('key','')
        def fmt(v):
            if v is None:return '-'
            if key in ('lost_minutes_per_day','inactive_minutes_per_day'):return _fmt_seconds(float(v)*60)+'/j'
            return f"{float(v):.1f}"
        delta=m.get('delta_pct');status={'improved':'Amélioration','degraded':'Dégradation','stable':'Stable','unknown':'Non comparable'}.get(m.get('status'),'Non comparable')
        mrows.append([m.get('label'),fmt(cur),fmt(pre),'n/a' if delta is None else f"{delta:+.1f} %",status])
    story.append(table(mrows,[56*mm,29*mm,29*mm,25*mm,39*mm],center_cols=[1,2,3,4]))
    return story


def _build_special_pdf(data, report_type):
    """Assemble les sections du type demande sans modifier la mise en page."""
    rendu = _preparer_rendu_special(data, report_type)
    ds=(data.get('disconnects') or {}).get('summary') or {}
    sig=(data.get('signals') or {}).get('summary') or {}
    agents=list(data.get('top_unstable') or [])
    comparison=data.get('comparison') or {}
    integrity=data.get('integrity') or {}
    active=max(1,int(ds.get('active_days') or 0))
    excluded=', '.join(((data.get('filters') or {}).get('excluded_slots') or [])) or 'Aucune'

    story = []
    story.extend(_section_entete_speciale(rendu, data=data, excluded=excluded))
    if report_type == 'overview':
        story.extend(_section_synthese_vue_ensemble(rendu, active=active, agents=agents, ds=ds, sig=sig))
        story.extend(_section_panorama_signaux(rendu, agents=agents))
        story.extend(_section_postes_prioritaires(rendu, agents=agents))
        story.extend(_section_actions_techniques(rendu, agents=agents, integrity=integrity))
    else:
        metrics=list(comparison.get('metrics') or [])
        story.extend(_section_verdict_comparaison(rendu, comparison=comparison, metrics=metrics))
        story.extend(_section_evolution_quotidienne(rendu, comparison=comparison))
        story.extend(_section_evolution_agents(rendu, data=data))
        story.extend(_section_methode_comparaison(rendu, comparison=comparison, metrics=metrics))
    story.extend(_report_policy_flowables(data))
    rendu.doc.build(story,onFirstPage=rendu.page_chrome,onLaterPages=rendu.page_chrome)
    return rendu.buf.getvalue()
