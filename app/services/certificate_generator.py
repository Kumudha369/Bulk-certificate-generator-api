"""PDF generation using ONE predefined template (drawn with ReportLab).

Keeping the template in a single function means every certificate has the
same look; only name / event / date change.
"""
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

NAVY = colors.HexColor("#1F3A5F")
GOLD = colors.HexColor("#B8860B")


def _fit_font_size(text: str, font: str, max_width: float, start: int, minimum: int = 14) -> int:
    """Shrink the font until the text fits inside max_width (long names)."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    size = start
    while size > minimum and stringWidth(text, font, size) > max_width:
        size -= 1
    return size


def generate_certificate_pdf(
    output_path: Path, recipient_name: str, event_name: str, event_date: date
) -> Path:
    """Render one certificate to `output_path` and return the path."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    width, height = landscape(A4)
    c = canvas.Canvas(str(output_path), pagesize=(width, height))
    c.setTitle(f"Certificate - {recipient_name}")

    # Double border
    c.setStrokeColor(NAVY)
    c.setLineWidth(6)
    c.rect(25, 25, width - 50, height - 50)
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.rect(40, 40, width - 80, height - 80)

    mid = width / 2
    max_text_width = width - 160

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 38)
    c.drawCentredString(mid, height - 120, "CERTIFICATE OF PARTICIPATION")

    c.setFillColor(colors.black)
    c.setFont("Helvetica", 16)
    c.drawCentredString(mid, height - 175, "This is proudly presented to")

    name_size = _fit_font_size(recipient_name, "Helvetica-Bold", max_text_width, 40)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", name_size)
    c.drawCentredString(mid, height - 245, recipient_name)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(mid - 220, height - 258, mid + 220, height - 258)

    c.setFillColor(colors.black)
    c.setFont("Helvetica", 16)
    c.drawCentredString(mid, height - 305, "for successfully participating in")

    event_size = _fit_font_size(event_name, "Helvetica-Bold", max_text_width, 26)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", event_size)
    c.drawCentredString(mid, height - 345, event_name)

    c.setFillColor(colors.black)
    c.setFont("Helvetica", 14)
    c.drawCentredString(mid, height - 385, f"Date: {event_date.strftime('%d %B %Y')}")

    c.setFont("Helvetica-Oblique", 11)
    c.setFillColor(colors.grey)
    c.drawCentredString(mid, 70, "Authorised Signatory")
    c.line(mid - 90, 88, mid + 90, 88)

    c.showPage()
    c.save()
    return output_path
