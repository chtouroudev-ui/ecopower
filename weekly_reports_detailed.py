"""Sections du rapport detaille ; extraction sans changement du rendu V56.8."""
from __future__ import annotations

import io
import math
from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import escape

from weekly_reports import (
    _fmt_seconds, _fmt_date, _clip, _priority_cell, _report_score, _report_policy_flowables,
)

@dataclass(frozen=True)
class _RenduDetaille:
    """Dependances de rendu explicites, creees pour un seul document."""

    AMBER: Any
    BLUE: Any
    GRID: Any
    KeepTogether: Any
    LIGHT: Any
    MUTED: Any
    NAVY: Any
    P: Any
    PageBreak: Any
    ParagraphStyle: Any
    RED: Any
    Spacer: Any
    Table: Any
    TableOfContents: Any
    TableStyle: Any
    appendix_style: Any
    buf: Any
    cell: Any
    cell_style: Any
    doc: Any
    h2_style: Any
    horizontal_bars: Any
    info_table: Any
    kicker_style: Any
    kpi_card: Any
    make_table: Any
    mm: Any
    note_style: Any
    overview_style: Any
    page_footer: Any
    section_style: Any
    simple_bar_chart: Any
    small_style: Any
    subtitle_style: Any
    title_style: Any


def _preparer_rendu_detaille(data) -> _RenduDetaille:
    """Prepare les styles, fabriques et callbacks historiques sans assembler les sections."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
            KeepTogether, Flowable,
        )
        from reportlab.platypus.tableofcontents import TableOfContents
        from reportlab.graphics.shapes import Drawing, Rect, String, Line
    except Exception as exc:
        raise RuntimeError("ReportLab n'est pas installe. Installer avec : py -3 -m pip install reportlab") from exc

    NAVY = colors.HexColor("#15395B")
    BLUE = colors.HexColor("#2F6B9A")
    PALE_BLUE = colors.HexColor("#EAF2F8")
    TEXT = colors.HexColor("#1F2933")
    MUTED = colors.HexColor("#667085")
    GRID = colors.HexColor("#D7E0E8")
    LIGHT = colors.HexColor("#F7F9FB")
    WHITE = colors.white
    GREEN = colors.HexColor("#2F7D59")
    GREEN_BG = colors.HexColor("#EAF6EF")
    RED = colors.HexColor("#A94442")
    RED_BG = colors.HexColor("#FCECEB")
    AMBER = colors.HexColor("#A66A12")
    AMBER_BG = colors.HexColor("#FFF5E5")
    GREY_BAR = colors.HexColor("#B8C3CC")

    class NelyioDocTemplate(SimpleDocTemplate):
        def afterFlowable(self, flowable):
            if isinstance(flowable, Paragraph):
                name = getattr(flowable.style, "name", "")
                if name == "SectionNelyio":
                    self.notify("TOCEntry", (0, flowable.getPlainText(), self.page))
                elif name == "AppendixNelyio":
                    self.notify("TOCEntry", (0, flowable.getPlainText(), self.page))

    buf = io.BytesIO()
    doc = NelyioDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=15 * mm,
        title=f"Rapport Nelyio - {data.get('period_label', data.get('week_label',''))}",
        author=str(data.get("generated_by") or "Nelyio"),
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleNelyio", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=18, leading=21, alignment=TA_CENTER, textColor=NAVY,
        spaceAfter=3,
    )
    subtitle_style = ParagraphStyle(
        "SubtitleNelyio", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=8.2, leading=10.5, alignment=TA_CENTER, textColor=MUTED,
        spaceAfter=8,
    )
    kicker_style = ParagraphStyle(
        "KickerNelyio", parent=styles["BodyText"], fontName="Helvetica-Bold",
        fontSize=7.1, leading=8.5, alignment=TA_CENTER, textColor=BLUE,
        spaceAfter=2,
    )
    section_style = ParagraphStyle(
        "SectionNelyio", parent=styles["Heading1"], fontName="Helvetica-Bold",
        fontSize=12, leading=15, textColor=NAVY, spaceBefore=7, spaceAfter=6,
    )
    appendix_style = ParagraphStyle(
        "AppendixNelyio", parent=section_style, fontSize=11.2, leading=14,
    )
    h2_style = ParagraphStyle(
        "H2Nelyio", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=9.5, leading=12, textColor=NAVY, spaceBefore=5, spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "BodyNelyio", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=8.1, leading=10.8, textColor=TEXT, spaceAfter=4,
    )
    small_style = ParagraphStyle(
        "SmallNelyio", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=6.9, leading=8.6, textColor=MUTED,
    )
    cell_style = ParagraphStyle(
        "CellNelyio", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=6.8, leading=8.5, textColor=TEXT,
    )
    cell_head_style = ParagraphStyle(
        "CellHeadNelyio", parent=cell_style, fontName="Helvetica-Bold", textColor=WHITE,
    )
    kpi_label_style = ParagraphStyle(
        "KpiLabelNelyio", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=6.8, leading=8.2, alignment=TA_CENTER, textColor=MUTED,
    )
    kpi_value_style = ParagraphStyle(
        "KpiValueNelyio", parent=styles["BodyText"], fontName="Helvetica-Bold",
        fontSize=14, leading=16, alignment=TA_CENTER, textColor=NAVY,
    )
    kpi_sub_style = ParagraphStyle(
        "KpiSubNelyio", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=6.3, leading=7.6, alignment=TA_CENTER, textColor=MUTED,
    )
    note_style = ParagraphStyle(
        "NoteNelyio", parent=body_style, fontSize=7.3, leading=9.5,
        textColor=MUTED, backColor=LIGHT, borderColor=GRID, borderWidth=0.5,
        borderPadding=6, spaceBefore=3, spaceAfter=5,
    )
    overview_style = ParagraphStyle(
        "OverviewNelyio", parent=body_style, fontSize=7.8, leading=10.2,
        leftIndent=7, firstLineIndent=-7, spaceAfter=3,
    )
    toc_title_style = ParagraphStyle(
        "TocTitleNelyio", parent=h2_style, fontSize=9, spaceBefore=4, spaceAfter=2,
    )

    def P(text, style=body_style):
        return Paragraph(escape(str(text or "")), style)

    def PC(text, style=body_style):
        return Paragraph(str(text or ""), style)

    def cell(value, head=False):
        if isinstance(value, Flowable):
            return value
        return Paragraph(escape(str(value if value is not None else "")), cell_head_style if head else cell_style)

    def make_table(rows, widths, header=True, repeat_rows=1, row_backgrounds=True):
        converted=[]
        for idx,row in enumerate(rows):
            converted.append([cell(v, head=(header and idx==0)) for v in row])
        table=Table(converted,colWidths=widths,repeatRows=repeat_rows if header else 0,hAlign="LEFT")
        commands=[
            ("GRID",(0,0),(-1,-1),0.25,GRID),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("LEFTPADDING",(0,0),(-1,-1),4.5),
            ("RIGHTPADDING",(0,0),(-1,-1),4.5),
            ("TOPPADDING",(0,0),(-1,-1),4),
            ("BOTTOMPADDING",(0,0),(-1,-1),4),
        ]
        if row_backgrounds:
            commands.append(("ROWBACKGROUNDS",(0,1 if header else 0),(-1,-1),[WHITE,LIGHT]))
        if header:
            commands += [
                ("BACKGROUND",(0,0),(-1,0),NAVY),
                ("TEXTCOLOR",(0,0),(-1,0),WHITE),
                ("ALIGN",(0,0),(-1,0),"CENTER"),
            ]
        table.setStyle(TableStyle(commands))
        return table

    def info_table(rows):
        table=Table([[cell(k),cell(v)] for k,v in rows],colWidths=[38*mm,140*mm],hAlign="LEFT")
        table.setStyle(TableStyle([
            ("GRID",(0,0),(-1,-1),0.25,GRID),
            ("BACKGROUND",(0,0),(0,-1),PALE_BLUE),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),
            ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ]))
        return table

    def kpi_card(label,value,sub="",accent=NAVY):
        value_style=ParagraphStyle(
            "KpiValueDynamic"+str(abs(hash((str(label),str(value)))))[:8],
            parent=kpi_value_style,textColor=accent,
        )
        rows=[
            [Paragraph(escape(str(label)),kpi_label_style)],
            [Paragraph(escape(str(value)),value_style)],
            [Paragraph(escape(str(sub or "")),kpi_sub_style)],
        ]
        table=Table(rows,colWidths=[43.5*mm],rowHeights=[7*mm,10*mm,7*mm])
        table.setStyle(TableStyle([
            ("BOX",(0,0),(-1,-1),0.5,GRID),("BACKGROUND",(0,0),(-1,-1),WHITE),
            ("LINEABOVE",(0,0),(-1,0),2.0,accent),
            ("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3),
        ]))
        return table

    def verdict_box(comparison):
        verdict=(comparison or {}).get("verdict") or {}
        code=verdict.get("code") or "unavailable"
        label=verdict.get("label") or "Sans comparaison"
        detail=verdict.get("detail") or "Aucune période précédente exploitable."
        if code=="improved":bg,border,fg=GREEN_BG,GREEN,GREEN
        elif code=="degraded":bg,border,fg=RED_BG,RED,RED
        elif code=="stable":bg,border,fg=AMBER_BG,AMBER,AMBER
        else:bg,border,fg=LIGHT,GRID,MUTED
        label_style=ParagraphStyle("VerdictLabel",parent=body_style,fontName="Helvetica-Bold",fontSize=12,leading=14,textColor=fg)
        detail_style=ParagraphStyle("VerdictDetail",parent=small_style,fontSize=7.2,leading=9.2,textColor=TEXT)
        table=Table([[Paragraph(escape(label),label_style),Paragraph(escape(detail),detail_style)]],colWidths=[42*mm,136*mm])
        table.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1),bg),("BOX",(0,0),(-1,-1),0.65,border),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),
            ("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
        ]))
        return table

    def status_text(metric):
        status=metric.get("status")
        label={"improved":"Amélioration","degraded":"À surveiller","stable":"Stable","unknown":"Non comparable"}.get(status,"Non comparable")
        color={"improved":"#2F7D59","degraded":"#A94442","stable":"#A66A12","unknown":"#667085"}.get(status,"#667085")
        return PC(f'<font color="{color}"><b>{escape(label)}</b></font>',cell_style)

    def metric_value(metric,key):
        value=metric.get(key)
        if value is None:return "-"
        metric_key=metric.get("key") or ""
        if metric_key=="lost_minutes_per_day":return f"{float(value):.1f} min/j"
        if metric_key in ("disconnects_per_day","during_call_per_day","anomalies_per_day"):return f"{float(value):.2f}/j"
        if metric_key=="short_per_1000":return f"{float(value):.1f}/1000"
        return str(value)

    def comparison_table(comparison):
        rows=[["Indicateur","Période actuelle","Semaine précédente","Écart","Lecture"]]
        for metric in (comparison or {}).get("metrics") or []:
            delta=metric.get("delta_pct")
            delta_text="n/a" if delta is None else f"{delta:+.1f} %"
            rows.append([metric.get("label"),metric_value(metric,"current"),metric_value(metric,"previous"),delta_text,status_text(metric)])
        if len(rows)==1:rows.append(["Comparaison","-","-","-",status_text({"status":"unknown"})])
        return make_table(rows,[55*mm,31*mm,34*mm,24*mm,34*mm])

    def simple_bar_chart(rows,value_key="total",title="",width=178*mm,height=45*mm):
        d=Drawing(width,height)
        d.add(String(0,height-9,title,fontName="Helvetica-Bold",fontSize=8.5,fillColor=NAVY))
        plot_top=height-19;plot_bottom=12;plot_h=max(10,plot_top-plot_bottom)
        values=[r.get(value_key) for r in rows]
        numeric=[max(0,float(v)) for v in values if v is not None]
        max_v=max(numeric,default=1) or 1
        n=max(1,len(rows));gap=4;bar_w=max(4,(width-8-gap*(n-1))/n)
        for i,row in enumerate(rows):
            val=row.get(value_key);x=4+i*(bar_w+gap)
            label=str(row.get("label") or "")
            if len(label)>=10 and "-" in label:label=label[5:]
            if val is None:
                d.add(String(x+bar_w/2,plot_bottom+3,"-",textAnchor="middle",fontName="Helvetica",fontSize=7,fillColor=MUTED))
            else:
                v=max(0,float(val));bar_h=plot_h*v/max_v if max_v else 0
                d.add(Rect(x,plot_bottom,bar_w,bar_h,fillColor=BLUE,strokeColor=None))
                d.add(String(x+bar_w/2,min(height-17,plot_bottom+bar_h+2),str(int(v)),textAnchor="middle",fontName="Helvetica-Bold",fontSize=5.4,fillColor=TEXT))
            if i%max(1,math.ceil(n/12))==0 or i==n-1:d.add(String(x+bar_w/2,2,label,textAnchor="middle",fontName="Helvetica",fontSize=5.7,fillColor=MUTED))
        return d

    def comparison_chart(rows,title="",width=178*mm,height=43*mm):
        d=Drawing(width,height)
        d.add(String(0,height-9,title,fontName="Helvetica-Bold",fontSize=8.5,fillColor=NAVY))
        d.add(Rect(width-53, height-12, 6, 6, fillColor=BLUE, strokeColor=None))
        d.add(String(width-44,height-11,"Actuel",fontName="Helvetica",fontSize=5.8,fillColor=MUTED))
        d.add(Rect(width-25, height-12, 6, 6, fillColor=GREY_BAR, strokeColor=None))
        d.add(String(width-16,height-11,"Avant",fontName="Helvetica",fontSize=5.8,fillColor=MUTED))
        plot_top=height-20;plot_bottom=11;plot_h=max(10,plot_top-plot_bottom)
        vals=[]
        for r in rows:
            for key in ("current","previous"):
                if r.get(key) is not None:vals.append(max(0,float(r[key])))
        max_v=max(vals,default=1) or 1
        n=max(1,len(rows));group_w=(width-8)/n;bar_w=max(4,min(12,(group_w-5)/2))
        for i,row in enumerate(rows):
            center=4+i*group_w+group_w/2
            for key,color,offset in (("previous",GREY_BAR,-bar_w/2-1),("current",BLUE,bar_w/2+1)):
                val=row.get(key);x=center+offset-bar_w/2
                if val is None:
                    d.add(String(center+offset,plot_bottom+2,"-",textAnchor="middle",fontName="Helvetica",fontSize=5.5,fillColor=MUTED))
                    continue
                v=max(0,float(val));bar_h=plot_h*v/max_v if max_v else 0
                d.add(Rect(x,plot_bottom,bar_w,bar_h,fillColor=color,strokeColor=None))
            if i%max(1,math.ceil(n/12))==0 or i==n-1:d.add(String(center,1,str(row.get("label") or ""),textAnchor="middle",fontName="Helvetica-Bold",fontSize=6,fillColor=MUTED))
        d.add(Line(4,plot_bottom,width-4,plot_bottom,strokeColor=GRID,strokeWidth=.5))
        return d

    def horizontal_bars(rows,title="",width=178*mm,max_rows=10,value_formatter=None):
        rows=list(rows or [])[:max_rows];row_h=11;height=max(34,18+row_h*max(1,len(rows)))
        d=Drawing(width,height);d.add(String(0,height-9,title,fontName="Helvetica-Bold",fontSize=8.5,fillColor=NAVY))
        vals=[max(0,float(r.get("value") or 0)) for r in rows];max_v=max(vals,default=1) or 1
        label_w=58*mm
        from reportlab.pdfbase.pdfmetrics import stringWidth
        value_w=max((stringWidth(value_formatter(v) if value_formatter else str(int(v)),"Helvetica-Bold",6.2) for v in vals),default=10)+5
        chart_w=max(1,width-label_w-value_w);y=height-22
        if not rows:
            d.add(String(0,y,"Aucune donnée",fontName="Helvetica",fontSize=7,fillColor=MUTED));return d
        for row,val in zip(rows,vals):
            d.add(String(0,y+1,_clip(row.get("label"),34),fontName="Helvetica",fontSize=6.4,fillColor=TEXT))
            bar_w=chart_w*val/max_v if max_v else 0
            d.add(Rect(label_w,y,bar_w,6,fillColor=BLUE,strokeColor=None))
            shown=value_formatter(val) if value_formatter else str(int(val))
            d.add(String(label_w+bar_w+3,y+1,shown,fontName="Helvetica-Bold",fontSize=6.2,fillColor=TEXT));y-=row_h
        return d

    def page_footer(canvas,doc_obj):
        canvas.saveState()
        if doc_obj.page > 1:
            canvas.setStrokeColor(GRID);canvas.setLineWidth(.45)
            canvas.line(14*mm,A4[1]-9*mm,A4[0]-14*mm,A4[1]-9*mm)
            canvas.setFont("Helvetica-Bold",6.7);canvas.setFillColor(NAVY)
            canvas.drawString(14*mm,A4[1]-7*mm,"NELYIO | RAPPORT TECHNIQUE COMPLET")
            canvas.setFont("Helvetica",6.5);canvas.setFillColor(MUTED)
            canvas.drawRightString(A4[0]-14*mm,A4[1]-7*mm,str(data.get('period_label',data.get('week_label',''))))
        canvas.setFont("Helvetica",6.8);canvas.setFillColor(MUTED)
        canvas.drawString(14*mm,8*mm,f"Nelyio - {data.get('period_label',data.get('week_label',''))} - Confidentiel")
        canvas.drawRightString(A4[0]-14*mm,8*mm,f"Page {doc_obj.page}")
        canvas.restoreState()

    return _RenduDetaille(
        AMBER=AMBER,
        BLUE=BLUE,
        GRID=GRID,
        KeepTogether=KeepTogether,
        LIGHT=LIGHT,
        MUTED=MUTED,
        NAVY=NAVY,
        P=P,
        PageBreak=PageBreak,
        ParagraphStyle=ParagraphStyle,
        RED=RED,
        Spacer=Spacer,
        Table=Table,
        TableOfContents=TableOfContents,
        TableStyle=TableStyle,
        appendix_style=appendix_style,
        buf=buf,
        cell=cell,
        cell_style=cell_style,
        doc=doc,
        h2_style=h2_style,
        horizontal_bars=horizontal_bars,
        info_table=info_table,
        kicker_style=kicker_style,
        kpi_card=kpi_card,
        make_table=make_table,
        mm=mm,
        note_style=note_style,
        overview_style=overview_style,
        page_footer=page_footer,
        section_style=section_style,
        simple_bar_chart=simple_bar_chart,
        small_style=small_style,
        subtitle_style=subtitle_style,
        title_style=title_style,
    )


def _section_couverture_detaillee(rendu: _RenduDetaille, agents, calls, data, ds, excluded_slots, integrity, overview, report_agents) -> list[Any]:
    """Produit les flowables de section couverture detaillee dans leur ordre historique."""
    AMBER = rendu.AMBER
    BLUE = rendu.BLUE
    GRID = rendu.GRID
    LIGHT = rendu.LIGHT
    P = rendu.P
    RED = rendu.RED
    Spacer = rendu.Spacer
    Table = rendu.Table
    TableStyle = rendu.TableStyle
    cell = rendu.cell
    h2_style = rendu.h2_style
    horizontal_bars = rendu.horizontal_bars
    info_table = rendu.info_table
    kicker_style = rendu.kicker_style
    kpi_card = rendu.kpi_card
    mm = rendu.mm
    overview_style = rendu.overview_style
    subtitle_style = rendu.subtitle_style
    title_style = rendu.title_style
    story = []
    story.append(P("NELYIO | AUDIT TECHNIQUE COMPLET",kicker_style))
    story.append(P("Rapport technique complet",title_style))
    story.append(P(
        f"{data.get('period_label',data.get('week_label',''))} | {_fmt_date(data.get('date_from'))} au {_fmt_date(data.get('date_to'))} | Généré le {data.get('generated_at','')} | {data.get('generated_by','')}",
        subtitle_style,
    ))
    filter_parts=[data.get("time_label") or "08:00-19:00",data.get("source_label") or "Référence automatique",data.get("disconnect_context_label") or "Toutes les déconnexions",data.get("call_issue_label") or "Tous les appels"]
    story.append(info_table([
        ("Périmètre",data.get("scope_label") or "Global"),
        ("Filtres"," | ".join(filter_parts)),
        ("Exclusions",", ".join(excluded_slots) if excluded_slots else "Aucune"),
        ("Usage","Audit support : synthèse d'abord, preuves complètes en annexes"),
    ]))
    story.append(Spacer(1,4*mm))

    active=max(1,int(ds.get("active_days") or 0))
    cards=[
        kpi_card("Temps de coupure",_fmt_seconds(ds.get("total_lost",0)),f"{_fmt_seconds(float(ds.get('total_lost') or 0)/active)} / jour",RED),
        kpi_card("Déconnexions normales",ds.get("total_deco",0),f"{float(ds.get('total_deco',0))/active:.1f} / jour couvert",BLUE),
        kpi_card("Pendant appel",ds.get("total_deco_call",0),f"{float(ds.get('total_call_percent') or 0):.1f} % des déconnexions",AMBER),
        kpi_card("Anomalies > 1 h",ds.get("anomalies_over_1h",0),"hors statistiques normales",RED),
    ]
    grid=Table([cards],colWidths=[44.5*mm]*4,hAlign="CENTER")
    grid.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),2),("RIGHTPADDING",(0,0),(-1,-1),2)]))
    story.append(grid);story.append(Spacer(1,3*mm))
    raw_deco=int(ds.get('raw_total_deco',ds.get('total_deco',0)) or 0)
    raw_lost=float(ds.get('raw_total_lost',ds.get('total_lost',0)) or 0)
    story.append(info_table([
        ('Brut avant Policies / Déclarations',f"{raw_deco} incident(s) | {_fmt_seconds(raw_lost)}"),
        ('Corrigé utilisé par les KPI',f"{int(ds.get('total_deco') or 0)} incident(s) | {_fmt_seconds(ds.get('total_lost',0))}"),
    ]))
    story.append(Spacer(1,3*mm))

    context_rows=[["Agents périmètre",str(len(report_agents)),"Agents touchés",str(ds.get("impacted_agents",0)),"Appels analysés",str(calls.get("records",0)),"Fiabilité",f"{integrity.get('score','-')}/100 - {integrity.get('label','-')}"]]
    context=Table([[cell(x) for x in context_rows[0]]],colWidths=[25*mm,18*mm,23*mm,18*mm,24*mm,22*mm,19*mm,29*mm])
    context.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),LIGHT),("BOX",(0,0),(-1,-1),0.4,GRID),("INNERGRID",(0,0),(-1,-1),0.2,GRID),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(1,0),(1,0),"CENTER"),("ALIGN",(3,0),(3,0),"CENTER"),("ALIGN",(5,0),(5,0),"CENTER"),("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    story.append(context);story.append(Spacer(1,4*mm))

    story.append(P("À retenir",h2_style))
    detailed_overview=[x for x in overview if not str(x).startswith('Tendance globale')]
    for item in detailed_overview:
        story.append(P(f"- {item}",overview_style))
    if agents:
        story.append(Spacer(1,2*mm))
        story.append(P("5 postes à contrôler en premier",h2_style))
        story.append(horizontal_bars(
            [dict(label=(r.get("name") or r.get("agent")),value=r.get("lost_seconds",0)) for r in agents[:5]],
            "Temps de coupure cumulé",max_rows=5,value_formatter=lambda v:_fmt_seconds(v),
        ))

    return story


def _section_sommaire_detaille(rendu: _RenduDetaille) -> list[Any]:
    """Produit les flowables de section sommaire detaille dans leur ordre historique."""
    GRID = rendu.GRID
    MUTED = rendu.MUTED
    NAVY = rendu.NAVY
    P = rendu.P
    PageBreak = rendu.PageBreak
    ParagraphStyle = rendu.ParagraphStyle
    Spacer = rendu.Spacer
    Table = rendu.Table
    TableOfContents = rendu.TableOfContents
    TableStyle = rendu.TableStyle
    cell = rendu.cell
    mm = rendu.mm
    note_style = rendu.note_style
    small_style = rendu.small_style
    subtitle_style = rendu.subtitle_style
    title_style = rendu.title_style
    story = []
    # Give the table of contents its own page. In v22.5 it could be
    # visually lost at the bottom of the executive page; here it is explicit.
    story.append(PageBreak())
    story.append(P("Sommaire du rapport",title_style))
    story.append(P("Vue d'ensemble d'abord, puis analyse et preuves techniques en annexes.",subtitle_style))
    summary_row=Table([[cell("Vue d'ensemble exécutive"),cell("1")]],colWidths=[160*mm,18*mm])
    summary_row.setStyle(TableStyle([("LINEBELOW",(0,0),(-1,0),0.35,GRID),("ALIGN",(1,0),(1,0),"RIGHT"),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story.append(summary_row);story.append(Spacer(1,2*mm))
    toc=TableOfContents();toc.levelStyles=[
        ParagraphStyle("TOCLevel1",parent=small_style,fontName="Helvetica-Bold",fontSize=8.1,leading=12,leftIndent=0,rightIndent=5,textColor=NAVY,spaceBefore=2),
        ParagraphStyle("TOCLevel2",parent=small_style,fontSize=7.2,leading=9.5,leftIndent=8,rightIndent=5,textColor=MUTED),
    ]
    story.append(toc)
    story.append(Spacer(1,5*mm))
    story.append(P("Lecture recommandée : pages de synthèse pour comprendre rapidement la situation ; annexes pour retrouver tous les agents et tous les événements ayant servi au rapport.",note_style))

    return story


def _section_qualite_donnees(rendu: _RenduDetaille, calls, disconnects, excluded_logs, excluded_slots, integrity) -> list[Any]:
    """Produit les flowables de section qualite donnees dans leur ordre historique."""
    P = rendu.P
    PageBreak = rendu.PageBreak
    Spacer = rendu.Spacer
    make_table = rendu.make_table
    mm = rendu.mm
    note_style = rendu.note_style
    section_style = rendu.section_style
    simple_bar_chart = rendu.simple_bar_chart
    small_style = rendu.small_style
    story = []
    story.append(PageBreak())
    story.append(P("1. Évolution et qualité des données",section_style))
    story.append(P("Cette page répond à deux questions simples : comment les incidents évoluent-ils au fil des jours, et peut-on faire confiance aux chiffres ?",note_style))
    story.append(simple_bar_chart(disconnects.get("daily") or [],"total","Déconnexions normales par jour"))
    story.append(Spacer(1,3*mm))
    cov_rows=[["Jour","Source","Déconnexions","En appel","Temps","Agents"]]
    for row in disconnects.get("daily") or []:
        src={"export":"Export SIMPLIFY2","capture":"Capture","missing":"Manquant"}.get(row.get("source"),row.get("source") or "-")
        cov_rows.append([_fmt_date(row.get("label")),src,"-" if row.get("total") is None else row.get("total"),"-" if row.get("call") is None else row.get("call"),"-" if row.get("lost_seconds") is None else _fmt_seconds(row.get("lost_seconds")),"-" if row.get("agents") is None else row.get("agents")])
    story.append(make_table(cov_rows,[27*mm,39*mm,29*mm,25*mm,35*mm,23*mm]))
    issues=integrity.get("issues") or []
    story.append(Spacer(1,2*mm))
    if issues:
        for issue in issues[:5]:story.append(P(f"- {issue.get('label','Vérification')} : {issue.get('detail','')}",small_style))
    else:
        story.append(P("Aucune anomalie majeure de couverture détectée sur la période.",small_style))
    story.append(Spacer(1,1.5*mm))
    if excluded_slots:
        story.append(P(
            f"Exclusions appliquées par chevauchement : {', '.join(excluded_slots)}. Elles ont retiré {int(excluded_logs.get('normal_disconnects') or 0)} coupure(s) normale(s), {int(excluded_logs.get('anomalies') or 0)} anomalie(s) > 1 h et {int(calls.get('excluded_by_time') or 0)} appel(s) ODCalls.",
            note_style,
        ))

    return story


def _section_postes_a_examiner(rendu: _RenduDetaille, agents) -> list[Any]:
    """Produit les flowables de section postes a examiner dans leur ordre historique."""
    KeepTogether = rendu.KeepTogether
    P = rendu.P
    PageBreak = rendu.PageBreak
    Spacer = rendu.Spacer
    cell_style = rendu.cell_style
    h2_style = rendu.h2_style
    horizontal_bars = rendu.horizontal_bars
    make_table = rendu.make_table
    mm = rendu.mm
    note_style = rendu.note_style
    section_style = rendu.section_style
    story = []
    story.append(PageBreak())
    story.append(P("2. Agents et postes à examiner",section_style))
    story.append(P("Priorisation technique : le rang des policies et le score configuré dans Priorités Support déterminent l’ordre. Les durées et coupures en appel restent visibles. Tous les agents du périmètre figurent dans l’annexe A ; la configuration appliquée est reproduite en fin de rapport.",note_style))

    loss_bars=[dict(label=(r.get("name") or r.get("agent")),value=r.get("lost_seconds",0)) for r in agents[:12]]
    story.append(horizontal_bars(loss_bars,"Temps de coupure des postes prioritaires selon Support",max_rows=12,value_formatter=lambda v:_fmt_seconds(v)))
    story.append(Spacer(1,2*mm))
    call_agents=sorted(agents,key=lambda r:(-int(r.get("deco_call") or 0),-float(r.get("lost_seconds") or 0),-int(r.get("deco") or 0),str(r.get("name") or r.get("agent")).casefold()))
    call_bars=[dict(label=(r.get("name") or r.get("agent")),value=r.get("deco_call",0)) for r in call_agents if int(r.get("deco_call") or 0)>0][:12]
    story.append(horizontal_bars(call_bars,"Coupures pendant appel - nombre d'incidents",max_rows=12))
    story.append(Spacer(1,3*mm))

    agent_rows=[["Agent","Groupe","Priorité","Score","Temps","Décos","En appel","Max","Jours"]]
    for row in agents[:15]:
        agent_rows.append([row.get('name') or row.get('agent'),row.get('group_name') or '-',_priority_cell(row,cell_style),_report_score(row.get('technical_score')),_fmt_seconds(row.get('lost_seconds')),row.get('deco',0),row.get('deco_call',0),_fmt_seconds(row.get('max_seconds')),row.get('days_affected',0)])
    if len(agent_rows)==1:agent_rows.append(['Aucun','-','-','-','0 s',0,0,'0 s',0])
    story.append(make_table(agent_rows,[29*mm,24*mm,27*mm,14*mm,24*mm,12*mm,14*mm,20*mm,14*mm]))
    action_rows=[["Priorité","Agent / poste","Action technique recommandée"]]
    for row in agents[:5]:
        action_rows.append([_priority_cell(row,cell_style),_clip(row.get("name") or row.get("agent"),26),row.get("suggested_action") or "Vérifier le contexte technique."])
    if len(action_rows)==1:action_rows.append(["-","Aucun","Aucune action particulière sur cette période."])
    story.append(KeepTogether([P("Actions prioritaires",h2_style),make_table(action_rows,[24*mm,39*mm,115*mm])]))

    return story


def _section_anomalies(rendu: _RenduDetaille, anomalies, disconnects) -> list[Any]:
    """Produit les flowables de section anomalies dans leur ordre historique."""
    P = rendu.P
    Spacer = rendu.Spacer
    h2_style = rendu.h2_style
    make_table = rendu.make_table
    mm = rendu.mm
    note_style = rendu.note_style
    section_style = rendu.section_style
    story = []
    story.append(Spacer(1,3*mm))
    story.append(P("3. Anomalies et incidents simultanés",section_style))
    story.append(P("Les coupures > 1 h sont isolées des statistiques normales afin de ne pas fausser la vue d'ensemble, mais elles restent visibles ici et dans les annexes du mode complet.",note_style))
    clusters=disconnects.get("clusters") or []
    cluster_rows=[["Début","Agents","Incidents","Groupes","Lecture"]]
    for row in clusters[:6]:cluster_rows.append([row.get("start_text") or "-",row.get("agent_count",0),row.get("incident_count",0),_clip(", ".join(row.get("groups") or []) or "Non renseigné",34),"Cause partagée à investiguer"])
    if len(cluster_rows)==1:cluster_rows.append(["Aucun",0,0,"-","Aucun regroupement significatif"])
    story.append(make_table(cluster_rows,[37*mm,19*mm,21*mm,48*mm,53*mm]))
    anomaly_rows=[["Début","Agent","Groupe","Durée","En appel"]]
    for row in anomalies[:10]:anomaly_rows.append([row.get("start_text") or "-",_clip(row.get("name") or row.get("agent"),25),_clip(row.get("group_name") or "-",20),_fmt_seconds(row.get("seconds",0)),"Oui" if row.get("during_call") else "Non"])
    if len(anomaly_rows)==1:anomaly_rows.append(["Aucune","-","-","0 s","Non"])
    story.append(P("Anomalies > 1 h - aperçu",h2_style));story.append(make_table(anomaly_rows,[38*mm,38*mm,32*mm,34*mm,26*mm]))

    return story


def _section_signaux_appels(rendu: _RenduDetaille, calls, data) -> list[Any]:
    """Produit les flowables de section signaux appels dans leur ordre historique."""
    P = rendu.P
    Spacer = rendu.Spacer
    horizontal_bars = rendu.horizontal_bars
    make_table = rendu.make_table
    mm = rendu.mm
    section_style = rendu.section_style
    story = []
    story.append(P("4. Signaux issus des appels",section_style))
    call_rows=[
        ["Indicateur","Valeur","Lecture"],
        ["Appels analysés",calls.get("records",0),"Contexte de volume sur le périmètre filtré"],
        ["Conversations courtes 1-10 s",calls.get("short",0),"Signal à vérifier en contexte, pas une preuve d'incident"],
        ["Codes EndReason non nuls",calls.get("end_codes",0),"Codes à qualifier selon la téléphonie"],
        ["Sans agent déclaré",calls.get("no_agent",0),"Appels sans agent dans l'export"],
        ["Abandons déclarés",calls.get("abandons",0),"Indicateur ODCalls"],
        ["Conversation moyenne",_fmt_seconds(calls.get("average_conversation") or 0),"Moyenne des conversations positives"],
    ]
    story.append(make_table(call_rows,[54*mm,31*mm,93*mm]))
    reasons=data.get("top_end_reasons") or []
    if reasons:
        story.append(Spacer(1,3*mm));story.append(horizontal_bars([dict(label=f"EndReason {r.get('label')}",value=r.get('value')) for r in reasons[:8]],"Principaux codes EndReason non nuls",max_rows=8))

    return story


def _annexe_agents(rendu: _RenduDetaille, impacted, report_agents) -> list[Any]:
    """Produit les flowables de annexe agents dans leur ordre historique."""
    P = rendu.P
    PageBreak = rendu.PageBreak
    appendix_style = rendu.appendix_style
    cell_style = rendu.cell_style
    h2_style = rendu.h2_style
    make_table = rendu.make_table
    mm = rendu.mm
    note_style = rendu.note_style
    story = []
    # intentional: management can stop after the synthesis, while support can
    # continue into a complete audit trail without generating a second report.
    story.append(PageBreak())
    story.append(P("Annexe A - Tous les agents du périmètre",appendix_style))
    impacted_ids={str(r.get('agent')) for r in impacted}
    unaffected=[r for r in report_agents if str(r.get('agent')) not in impacted_ids]
    story.append(P(f"{len(report_agents)} agent(s) inclus : {len(impacted)} avec signal technique ou statut séparé et {len(unaffected)} autres. L’ordre suit les policies Support, puis le score. Les jours sans données ne prouvent pas une absence d’incident.",note_style))
    all_agents=[["Agent / ID","Groupe","Priorité","Score","Temps","Décos","Appel","Max","Jours"]]
    for row in impacted:
        all_agents.append([f"{row.get('name') or row.get('agent')} ({row.get('agent')})",row.get('group_name') or '-',_priority_cell(row,cell_style),_report_score(row.get('technical_score')),_fmt_seconds(row.get('lost_seconds')),row.get('deco',0),row.get('deco_call',0),_fmt_seconds(row.get('max_seconds')),row.get('days_affected',0)])
    if len(all_agents)==1:all_agents.append(['Aucun','-','-','-','0 s',0,0,'0 s',0])
    story.append(make_table(all_agents,[33*mm,24*mm,28*mm,14*mm,23*mm,12*mm,13*mm,19*mm,12*mm]))
    if unaffected:
        story.append(P("Autres agents : sans signal retenu ou sans données",h2_style))
        clean_rows=[["Agent","Identifiant","Groupe","Priorité / données"]]
        for row in sorted(unaffected,key=lambda r:(str(r.get("group_name") or "").casefold(),str(r.get("name") or r.get("agent")).casefold())):
            clean_rows.append([_clip(row.get("name") or row.get("agent"),42),row.get("agent") or "-",_clip(row.get("group_name") or "Non affecté",35),_priority_cell(row,cell_style)])
        story.append(make_table(clean_rows,[58*mm,25*mm,50*mm,45*mm]))
    return story


def _annexe_deconnexions(rendu: _RenduDetaille, disconnects) -> list[Any]:
    """Produit les flowables de annexe deconnexions dans leur ordre historique."""
    P = rendu.P
    PageBreak = rendu.PageBreak
    appendix_style = rendu.appendix_style
    make_table = rendu.make_table
    mm = rendu.mm
    story = []
    story.append(PageBreak())
    story.append(P("Annexe B - Détail des déconnexions normales",appendix_style))
    incident_rows=[["Début","Fin","Agent","Groupe","Durée","En appel","Source","Indice"]]
    for row in disconnects.get("incidents") or []:
        incident_rows.append([row.get("start_text") or "-",row.get("end_text") or "-",_clip(row.get("name") or row.get("agent"),23),_clip(row.get("group_name") or "-",18),_fmt_seconds(row.get("seconds",0)),"Oui" if row.get("during_call") else "Non",row.get("source") or "-",row.get("indice") or "-"])
    if len(incident_rows)==1:incident_rows.append(["Aucune","-","-","-","0 s","Non","-","-"])
    story.append(make_table(incident_rows,[29*mm,29*mm,29*mm,24*mm,21*mm,17*mm,18*mm,14*mm]))
    return story


def _annexe_anomalies(rendu: _RenduDetaille, anomalies, disconnects) -> list[Any]:
    """Produit les flowables de annexe anomalies dans leur ordre historique."""
    P = rendu.P
    PageBreak = rendu.PageBreak
    appendix_style = rendu.appendix_style
    make_table = rendu.make_table
    mm = rendu.mm
    story = []
    story.append(PageBreak())
    story.append(P("Annexe C - Détail des anomalies > 1 h",appendix_style))
    all_anomalies=disconnects.get("all_anomalies") or anomalies
    full_anom_rows=[["Début","Fin","Agent","Groupe","Durée","En appel","Source"]]
    for row in all_anomalies:
        full_anom_rows.append([row.get("start_text") or "-",row.get("end_text") or "-",_clip(row.get("name") or row.get("agent"),23),_clip(row.get("group_name") or "-",18),_fmt_seconds(row.get("seconds",0)),"Oui" if row.get("during_call") else "Non",row.get("source") or "-"])
    if len(full_anom_rows)==1:full_anom_rows.append(["Aucune","-","-","-","0 s","Non","-"])
    story.append(make_table(full_anom_rows,[31*mm,31*mm,31*mm,27*mm,24*mm,18*mm,16*mm]))
    return story


def _annexe_contextes_inactifs(rendu: _RenduDetaille, signals) -> list[Any]:
    """Produit les flowables de annexe contextes inactifs dans leur ordre historique."""
    P = rendu.P
    PageBreak = rendu.PageBreak
    appendix_style = rendu.appendix_style
    make_table = rendu.make_table
    mm = rendu.mm
    story = []
    story.append(PageBreak())
    story.append(P("Annexe D - Contextes inactifs",appendix_style))
    inactive_rows=[["Début","Fin","Agent","Groupe","Durée","Source","Contexte"]]
    for row in signals.get("inactive_incidents") or []:
        inactive_rows.append([row.get("start_text") or "-",row.get("end_text") or "-",_clip(row.get("name") or row.get("agent"),23),_clip(row.get("group_name") or "-",18),_fmt_seconds(row.get("seconds",0)),row.get("source") or "-",_clip(row.get("detail") or "Contexte inactif",34)])
    if len(inactive_rows)==1:inactive_rows.append(["Aucun","-","-","-","0 s","-","-"])
    story.append(make_table(inactive_rows,[28*mm,28*mm,28*mm,24*mm,22*mm,18*mm,30*mm]))
    return story


def _annexe_signaux_techniques(rendu: _RenduDetaille, signals) -> list[Any]:
    """Produit les flowables de annexe signaux techniques dans leur ordre historique."""
    P = rendu.P
    PageBreak = rendu.PageBreak
    appendix_style = rendu.appendix_style
    make_table = rendu.make_table
    mm = rendu.mm
    story = []
    story.append(PageBreak())
    story.append(P("Annexe E - Autres signaux techniques",appendix_style))
    tech_rows=[["Date / heure","Agent","Groupe","Signal","Source","Détail"]]
    for row in signals.get("technical_incidents") or []:
        tech_rows.append([row.get("start_text") or "-",_clip(row.get("name") or row.get("agent"),24),_clip(row.get("group_name") or "-",18),_clip(row.get("label") or row.get("category") or "Signal",25),row.get("source") or "-",_clip(row.get("detail") or "-",58)])
    if len(tech_rows)==1:tech_rows.append(["Aucun","-","-","-","-","Aucun autre signal technique retenu."])
    story.append(make_table(tech_rows,[30*mm,31*mm,24*mm,30*mm,17*mm,46*mm]))
    return story


def _annexe_diagnostic_agents(rendu: _RenduDetaille, impacted, report_mode) -> list[Any]:
    """Produit les flowables de annexe diagnostic agents dans leur ordre historique."""
    P = rendu.P
    PageBreak = rendu.PageBreak
    appendix_style = rendu.appendix_style
    cell_style = rendu.cell_style
    make_table = rendu.make_table
    mm = rendu.mm
    note_style = rendu.note_style
    story = []
    if report_mode=="complete":
        story.append(PageBreak())
        story.append(P("Annexe F - Diagnostic détaillé par agent",appendix_style))
        story.append(P("Cette annexe étendue reprend la cause probable et l'action suggérée pour chaque agent ayant au moins une coupure retenue. Elle reste une aide au diagnostic technique, pas une mesure de performance.",note_style))
        diag_rows=[["Priorité / score","Agent","Temps","Décos","En appel","Justification / diagnostic / action"]]
        for row in impacted:
            narrative=" ; ".join(row.get("priority_reasons") or [])+" | "+(row.get("likely_cause") or "À qualifier")+" - "+(row.get("suggested_action") or "Vérifier le contexte technique.")+" | Score : "+" ; ".join(f"{c.get('label')} : {c.get('points')} pt ({c.get('detail')})" for c in (row.get("score_components") or []))
            diag_rows.append([_priority_cell(dict(row,priority=f"{row.get('priority')} / {_report_score(row.get('technical_score'))}"),cell_style),_clip(row.get("name") or row.get("agent"),24),_fmt_seconds(row.get("lost_seconds",0)),row.get("deco",0),row.get("deco_call",0),narrative])
        if len(diag_rows)==1:diag_rows.append(["-","Aucun","0 s",0,0,"Aucun incident retenu."])
        story.append(make_table(diag_rows,[20*mm,31*mm,25*mm,14*mm,16*mm,72*mm]))
    return story


def _section_regles_lecture_detaillee(rendu: _RenduDetaille) -> list[Any]:
    """Produit les flowables de section regles lecture detaillee dans leur ordre historique."""
    P = rendu.P
    Spacer = rendu.Spacer
    mm = rendu.mm
    note_style = rendu.note_style
    story = []
    story.append(Spacer(1,4*mm))
    story.append(P(
        "Règles de lecture : maximum 30 jours, dates incluses. Le classement reprend les policies et le score Support, sans ancien indice relatif. La comparaison utilise la période précédente de même durée, sans chevauchement. Les plages exclues retirent les événements qui les chevauchent. Les anomalies de plus de 1 h restent séparées.",
        note_style,
    ))
    return story


def _build_detailed_pdf(data):
    """Assemble les sections, puis conserve le multiBuild et ses deux callbacks."""
    rendu = _preparer_rendu_detaille(data)
    disconnects=data.get("disconnects") or {};ds=disconnects.get("summary") or {}
    calls=data.get("calls_summary") or {};integrity=data.get("integrity") or {}
    comparison=data.get("comparison") or {};overview=data.get("overview") or []
    report_mode=data.get("mode") or "summary"
    raw_agents=disconnects.get("agents") or []
    report_agents=list(data.get('report_agents') or raw_agents)
    by_id={str(r.get('agent')):r for r in report_agents}
    agents=[by_id.get(str(r.get('agent')),r) for r in raw_agents]
    excluded_slots=ds.get("excluded_slots") or [];excluded_logs=ds.get("excluded_logs") or {}

    story = []
    story.extend(_section_couverture_detaillee(rendu, agents=agents, calls=calls, data=data, ds=ds, excluded_slots=excluded_slots, integrity=integrity, overview=overview, report_agents=report_agents))
    story.extend(_section_sommaire_detaille(rendu))
    story.extend(_section_qualite_donnees(rendu, calls=calls, disconnects=disconnects, excluded_logs=excluded_logs, excluded_slots=excluded_slots, integrity=integrity))
    story.extend(_section_postes_a_examiner(rendu, agents=agents))
    anomalies=disconnects.get("anomalies") or []
    story.extend(_section_anomalies(rendu, anomalies=anomalies, disconnects=disconnects))
    story.extend(_section_signaux_appels(rendu, calls=calls, data=data))
    impacted=[r for r in report_agents if r.get('priority_evaluated') and any(float(r.get(k) or 0)>0 for k in ('deco','anomaly_count','collective_count','probable_closure_count','technical_score'))]
    story.extend(_annexe_agents(rendu, impacted=impacted, report_agents=report_agents))
    story.extend(_annexe_deconnexions(rendu, disconnects=disconnects))
    story.extend(_annexe_anomalies(rendu, anomalies=anomalies, disconnects=disconnects))
    signals=data.get("signals") or {}
    story.extend(_annexe_contextes_inactifs(rendu, signals=signals))
    story.extend(_annexe_signaux_techniques(rendu, signals=signals))
    story.extend(_annexe_diagnostic_agents(rendu, impacted=impacted, report_mode=report_mode))
    story.extend(_section_regles_lecture_detaillee(rendu))
    story.extend(_report_policy_flowables(data))
    rendu.doc.multiBuild(story,onFirstPage=rendu.page_footer,onLaterPages=rendu.page_footer)
    return rendu.buf.getvalue()
