import csv
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas.attempt import AttemptReportOut

_CSV_HEADER = [
    "Question",
    "Type",
    "Difficulty",
    "Bloom Level",
    "Your Answer",
    "Correct",
    "Marks Awarded",
    "Marks",
    "Explanation",
]


def render_csv(report: AttemptReportOut) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_CSV_HEADER)
    for q in report.questions:
        writer.writerow(
            [
                q.prompt,
                q.type,
                q.difficulty,
                q.bloom_level or "",
                q.your_answer or "",
                "" if q.is_correct is None else ("Yes" if q.is_correct else "No"),
                "" if q.marks_awarded is None else q.marks_awarded,
                q.marks,
                q.explanation or "",
            ]
        )
    return buffer.getvalue().encode("utf-8")


def render_pdf(report: AttemptReportOut) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER)
    styles = getSampleStyleSheet()

    elements = [
        Paragraph("Quiz Attempt Report", styles["Title"]),
        Spacer(1, 12),
        Paragraph(
            f"Score: {report.score}/{report.total_marks} ({report.accuracy}%)", styles["Normal"]
        ),
        Spacer(1, 12),
    ]

    table_data = [["Question", "Your Answer", "Correct", "Marks", "Bloom Level"]]
    for q in report.questions:
        table_data.append(
            [
                Paragraph(q.prompt, styles["Normal"]),
                Paragraph(q.your_answer or "-", styles["Normal"]),
                "-" if q.is_correct is None else ("Yes" if q.is_correct else "No"),
                f"{'-' if q.marks_awarded is None else q.marks_awarded}/{q.marks}",
                q.bloom_level or "-",
            ]
        )

    table = Table(table_data, colWidths=[190, 140, 45, 55, 70])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(table)

    doc.build(elements)
    return buffer.getvalue()
