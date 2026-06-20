"""Export a use-case markdown brief to a styled PDF.

Pure-Python (reportlab) so it runs anywhere the app runs, with no system
binaries required. The use-case briefs have a small, predictable markdown
vocabulary (H1/H2/H3, paragraphs, bullet and numbered lists, bold/italic/code,
horizontal rules), which this converter maps to reportlab flowables.
"""
from __future__ import annotations

import html
import re
from io import BytesIO

# Brand palette (matches the app's light theme accents)
_INDIGO = "#4f46e5"
_VIOLET = "#7c3aed"
_TEXT = "#1f2937"
_MUTED = "#6b7280"
_RULE = "#e5e7eb"


def _inline(text: str) -> str:
    """Convert inline markdown to reportlab's mini-markup, safely escaped."""
    text = html.escape(text, quote=False)               # & < >
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)  # bold
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*", r"<i>\1</i>", text)  # italic
    text = re.sub(r"`(.+?)`", r'<font face="Courier">\1</font>', text)  # code
    return text


def markdown_to_pdf(md_text: str, meta_line: str = "",
                    doc_title: str = "Use Case Brief") -> bytes:
    """Render a markdown use-case brief to PDF bytes."""
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    ListFlowable, ListItem, HRFlowable)

    width, height = LETTER
    margin = 0.85 * inch

    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=20, leading=24,
                        textColor=colors.HexColor(_INDIGO), spaceBefore=2, spaceAfter=4)
    meta = ParagraphStyle("meta", fontName="Helvetica", fontSize=9, leading=13,
                          textColor=colors.HexColor(_MUTED), spaceAfter=8)
    h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13.5, leading=18,
                        textColor=colors.HexColor(_INDIGO), spaceBefore=14, spaceAfter=4)
    h3 = ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=11.5, leading=15,
                        textColor=colors.HexColor(_VIOLET), spaceBefore=10, spaceAfter=2)
    body = ParagraphStyle("body", fontName="Helvetica", fontSize=10.5, leading=15.5,
                          textColor=colors.HexColor(_TEXT), spaceAfter=6, alignment=TA_LEFT)
    bullet = ParagraphStyle("bullet", parent=body, spaceAfter=2)

    story: list = []
    first_h1_done = False
    para_buf: list[str] = []
    list_items: list[str] = []
    list_kind: str | None = None  # "ul" | "ol"

    def flush_para() -> None:
        if para_buf:
            story.append(Paragraph(_inline(" ".join(para_buf)), body))
            para_buf.clear()

    def flush_list() -> None:
        nonlocal list_kind
        if list_items:
            items = [ListItem(Paragraph(_inline(t), bullet)) for t in list_items]
            story.append(ListFlowable(
                items,
                bulletType="bullet" if list_kind == "ul" else "1",
                bulletColor=colors.HexColor(_INDIGO),
                leftIndent=16, bulletFontSize=8 if list_kind == "ul" else 10,
            ))
            story.append(Spacer(1, 6))
            list_items.clear()
            list_kind = None

    for raw in md_text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            flush_para()
            flush_list()
            continue

        if re.match(r"^-{3,}$|^_{3,}$|^\*{3,}$", stripped):
            flush_para(); flush_list()
            story.append(Spacer(1, 2))
            story.append(HRFlowable(width="100%", thickness=0.6,
                                    color=colors.HexColor(_RULE)))
            story.append(Spacer(1, 4))
            continue

        if line.startswith("# "):
            flush_para(); flush_list()
            story.append(Paragraph(_inline(line[2:].strip()), h1))
            if not first_h1_done and meta_line:
                story.append(Paragraph(_inline(meta_line), meta))
            story.append(HRFlowable(width="100%", thickness=1,
                                    color=colors.HexColor(_INDIGO)))
            story.append(Spacer(1, 8))
            first_h1_done = True
        elif line.startswith("### "):
            flush_para(); flush_list()
            story.append(Paragraph(_inline(line[4:].strip()), h3))
        elif line.startswith("## "):
            flush_para(); flush_list()
            story.append(Paragraph(_inline(line[3:].strip()), h2))
        elif re.match(r"^[-*]\s+", line):
            flush_para()
            if list_kind == "ol":
                flush_list()
            list_kind = "ul"
            list_items.append(re.sub(r"^[-*]\s+", "", line))
        elif re.match(r"^\d+\.\s+", line):
            flush_para()
            if list_kind == "ul":
                flush_list()
            list_kind = "ol"
            list_items.append(re.sub(r"^\d+\.\s+", "", line))
        else:
            flush_list()
            para_buf.append(stripped)

    flush_para()
    flush_list()

    def _decorate(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor(_MUTED))
        canvas.drawString(margin, 0.55 * inch, "Talent Miner · AI use-case brief")
        canvas.drawRightString(width - margin, 0.55 * inch, f"Page {doc.page}")
        canvas.setStrokeColor(colors.HexColor(_RULE))
        canvas.setLineWidth(0.5)
        canvas.line(margin, 0.7 * inch, width - margin, 0.7 * inch)
        canvas.restoreState()

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER,
        leftMargin=margin, rightMargin=margin,
        topMargin=0.8 * inch, bottomMargin=0.9 * inch,
        title=doc_title, author="Talent Miner",
    )
    doc.build(story, onFirstPage=_decorate, onLaterPages=_decorate)
    return buf.getvalue()
