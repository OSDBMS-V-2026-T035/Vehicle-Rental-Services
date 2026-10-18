"""Branded PDF documents for confirmed RideHub rides.

Documents are generated on demand so they always show the authoritative
payment, vehicle and shop information without storing customer data in files.
"""

from io import BytesIO
from xml.sax.saxutils import escape as xml_escape

from django.http import FileResponse, Http404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.pdfgen import canvas

from apps.accounts.models import User
from apps.payments.models import PaymentTransaction
from .models import Booking


NAVY = colors.HexColor("#102A43")
BLUE = colors.HexColor("#1677FF")
INK = colors.HexColor("#243B53")
MUTED = colors.HexColor("#627D98")
MIST = colors.HexColor("#F0F5FA")
LINE = colors.HexColor("#D9E2EC")
GREEN = colors.HexColor("#087F5B")


def _text(value, fallback="-"):
    value = str(value or "").strip()
    return xml_escape(value) if value else fallback


def _date(value):
    return value.strftime("%d %b %Y") if value else "-"


def _money(value, currency="INR"):
    symbol = "Rs." if str(currency).upper() == "INR" else str(currency).upper()
    return f"{symbol} {value:,.2f}"


def _ride_reference(booking):
    return f"RH-{booking.id:06d}"


def _draw_landing_mark(pdf, x, y, size=12 * mm, color=colors.white):
    """Vector rendition of the R mark used in the landing-page masthead."""
    pdf.saveState()
    pdf.setStrokeColor(color)
    pdf.setLineWidth(max(1.1, size / 22))
    pdf.setLineCap(1)
    path = pdf.beginPath()
    path.moveTo(x, y)
    path.lineTo(x + size * .26, y)
    path.curveTo(x + size * .58, y, x + size * .72, y + size * .16, x + size * .72, y + size * .43)
    path.lineTo(x + size * .72, y + size)
    pdf.drawPath(path, fill=0, stroke=1)
    path = pdf.beginPath()
    path.moveTo(x, y + size * .42)
    path.lineTo(x + size * .23, y + size * .42)
    path.curveTo(x + size * .40, y + size * .42, x + size * .47, y + size * .53, x + size * .47, y + size * .72)
    path.lineTo(x + size * .47, y + size)
    pdf.drawPath(path, fill=0, stroke=1)
    pdf.setFillColor(colors.HexColor("#8ED4FF") if color == colors.white else color)
    pdf.circle(x + size * .91, y + size * .91, size * .085, fill=1, stroke=0)
    pdf.setStrokeColor(colors.HexColor("#8ED4FF") if color == colors.white else color)
    pdf.line(x + size * .72, y + size * .05, x + size, y + size * .05)
    pdf.restoreState()


def _draw_landing_watermark(pdf, x, y):
    """Draw a centered, legible brand watermark without competing with content."""
    # Keep the watermark behind the content and footer, but make it dark enough
    # to remain visible in ordinary PDF viewers and on a printed page.
    pale = colors.Color(.80, .87, .95, alpha=.52)
    pdf.saveState()
    pdf.translate(x, y)
    pdf.rotate(35)
    # The combined mark and wordmark are centred around the page origin before
    # rotation, instead of being visually pulled toward the lower-left corner.
    _draw_landing_mark(pdf, -48 * mm, -6 * mm, 16 * mm, color=pale)
    pdf.setFillColor(pale)
    pdf.setFont("Helvetica-Bold", 30)
    pdf.drawString(-26 * mm, -1 * mm, "RideHub")
    pdf.restoreState()


class RideHubCanvas(canvas.Canvas):
    """Shared visual treatment: brand masthead, watermark and legal footer."""

    def __init__(self, *args, document_kind, reference, **kwargs):
        super().__init__(*args, **kwargs)
        self.document_kind = document_kind
        self.reference = reference
        self._saved_page_states = []

    def showPage(self):
        # Defer page decorations until the document is complete. This lets the
        # header/footer draw over every finished page, including page one.
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_brand()
            self.draw_footer(self._pageNumber)
            super().showPage()
        super().save()

    def draw_brand(self):
        width, height = A4
        self.saveState()
        self.setStrokeColor(colors.HexColor("#4F80B8"))
        self.setLineWidth(.8)
        self.rect(10 * mm, 10 * mm, width - 20 * mm, height - 20 * mm, fill=0, stroke=1)
        self.setFillColor(NAVY)
        self.rect(0, height - 31 * mm, width, 31 * mm, fill=1, stroke=0)
        _draw_landing_mark(self, 17 * mm, height - 23 * mm, 13 * mm)
        self.setFont("Helvetica-Bold", 18)
        self.setFillColor(colors.white)
        self.drawString(33 * mm, height - 17.3 * mm, "RideHub")
        self.setFont("Helvetica", 7.8)
        self.setFillColor(colors.HexColor("#D9EFFF"))
        self.drawString(33 * mm, height - 22.3 * mm, "YOUR TRUSTED RIDE PARTNER")
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.white)
        self.drawRightString(width - 18 * mm, height - 13 * mm, self.document_kind.upper())
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#D9EFFF"))
        self.drawRightString(width - 18 * mm, height - 18.2 * mm, self.reference)
        # A deliberately subtle, vector watermark remains readable when printed.
        _draw_landing_watermark(self, width / 2, height / 2)
        self.restoreState()

    def draw_footer(self, page_number=1):
        width, _ = A4
        self.saveState()
        if self.document_kind == "Payment Receipt":
            self.setFillColor(MUTED)
            self.setFont("Helvetica", 7.2)
            self.drawCentredString(width / 2, 21 * mm, "This is a computer-generated payment receipt.")
        self.setStrokeColor(LINE)
        self.line(18 * mm, 17 * mm, width - 18 * mm, 17 * mm)
        self.setFillColor(MUTED)
        self.setFont("Helvetica", 7.2)
        self.drawString(18 * mm, 11.5 * mm, "RideHub - secure vehicle rentals | Support: support@ridehub.in")
        self.drawRightString(width - 18 * mm, 11.5 * mm, f"{self.reference}  |  Page {page_number}")
        self.restoreState()


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("doc-title", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=21, leading=25, textColor=NAVY, spaceAfter=3),
        "subtitle": ParagraphStyle("doc-subtitle", parent=base["Normal"], fontName="Helvetica", fontSize=9.2, leading=13, textColor=MUTED),
        "section": ParagraphStyle("section", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=NAVY, spaceBefore=0, spaceAfter=6),
        "label": ParagraphStyle("label", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=7.1, leading=9, textColor=MUTED),
        "value": ParagraphStyle("value", parent=base["Normal"], fontName="Helvetica", fontSize=9, leading=12, textColor=INK),
        "value_right": ParagraphStyle("value-right", parent=base["Normal"], alignment=TA_RIGHT, fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=INK),
        "note": ParagraphStyle("note", parent=base["Normal"], fontName="Helvetica", fontSize=8, leading=11.5, textColor=MUTED),
        "center": ParagraphStyle("center", parent=base["Normal"], alignment=TA_CENTER, fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=NAVY),
    }


def _field(label, value, styles, right=False):
    value_style = styles["value_right"] if right else styles["value"]
    return [Paragraph(_text(label).upper(), styles["label"]), Paragraph(_text(value), value_style)]


def _section(title, rows, styles, widths=(84 * mm, 84 * mm)):
    cells = []
    for left, right in rows:
        cells.append([_field(*left, styles), _field(*right, styles)])
    table = Table(cells, colWidths=list(widths), hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), .35, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    # Keep each titled section together without relying on a DocTemplate.  The
    # PDF is drawn directly so the same branded canvas controls every page.
    container = Table(
        [[Paragraph(title.upper(), styles["section"])], [table]],
        colWidths=[sum(widths)],
        hAlign="LEFT",
    )
    container.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1 * mm),
    ]))
    return container


def _confirmation_bytes(booking):
    """Four-page, travel-ticket style confirmation for vehicle handover."""
    payment, vehicle, shop, customer = booking.payment, booking.vehicle, booking.vehicle.shopkeeper, booking.customer
    reference = _ride_reference(booking)
    stream = BytesIO()
    pdf = canvas.Canvas(stream, pagesize=A4)
    pdf.setTitle(f"RideHub Ride Confirmation {reference}")
    pdf.setAuthor("RideHub")
    x, right = 16 * mm, A4[0] - 16 * mm
    panel_width = right - x

    def plain(value, fallback="-"):
        return str(value or fallback).strip() or fallback

    def text(value, x_pos, y_pos, font="Helvetica", size=9, color=INK):
        pdf.setFillColor(color)
        pdf.setFont(font, size)
        pdf.drawString(x_pos, y_pos, plain(value))

    def label(value, y_pos):
        text(value, x + 8 * mm, y_pos, "Helvetica", 7.6, MUTED)

    red = colors.HexColor("#E34B55")

    def icon(x_pos, y_pos, kind):
        """Compact vector icons: no font glyphs or stray 0/+ characters."""
        pdf.saveState(); pdf.setStrokeColor(red); pdf.setFillColor(red); pdf.setLineWidth(1)
        if kind == "pin":
            pdf.circle(x_pos, y_pos + 2.5 * mm, 2.1 * mm, fill=0, stroke=1)
            pdf.circle(x_pos, y_pos + 2.5 * mm, .55 * mm, fill=0, stroke=1)
            path = pdf.beginPath(); path.moveTo(x_pos - 1.55 * mm, y_pos + 1.2 * mm); path.lineTo(x_pos, y_pos - 3 * mm); path.lineTo(x_pos + 1.55 * mm, y_pos + 1.2 * mm); pdf.drawPath(path, fill=0, stroke=1)
        elif kind == "person":
            pdf.circle(x_pos, y_pos + 3 * mm, 1.5 * mm, fill=0, stroke=1)
            pdf.roundRect(x_pos - 3 * mm, y_pos - 3 * mm, 6 * mm, 4.3 * mm, .8 * mm, fill=0, stroke=1)
        elif kind == "calendar":
            pdf.roundRect(x_pos - 3.2 * mm, y_pos - 2 * mm, 6.4 * mm, 5.7 * mm, .6 * mm, fill=0, stroke=1)
            pdf.line(x_pos - 3.2 * mm, y_pos + 1.7 * mm, x_pos + 3.2 * mm, y_pos + 1.7 * mm)
            pdf.line(x_pos - 1.6 * mm, y_pos + 4.4 * mm, x_pos - 1.6 * mm, y_pos + 2.5 * mm); pdf.line(x_pos + 1.6 * mm, y_pos + 4.4 * mm, x_pos + 1.6 * mm, y_pos + 2.5 * mm)
        elif kind == "car":
            pdf.roundRect(x_pos - 3.5 * mm, y_pos - .5 * mm, 7 * mm, 3.8 * mm, .7 * mm, fill=0, stroke=1)
            pdf.line(x_pos - 2.1 * mm, y_pos + 3.3 * mm, x_pos - .9 * mm, y_pos + 5 * mm); pdf.line(x_pos - .9 * mm, y_pos + 5 * mm, x_pos + 2 * mm, y_pos + 5 * mm); pdf.line(x_pos + 2 * mm, y_pos + 5 * mm, x_pos + 3.1 * mm, y_pos + 3.3 * mm)
            pdf.circle(x_pos - 2.2 * mm, y_pos - .5 * mm, .75 * mm, fill=0, stroke=1); pdf.circle(x_pos + 2.2 * mm, y_pos - .5 * mm, .75 * mm, fill=0, stroke=1)
        else:  # payment/card
            pdf.roundRect(x_pos - 3.4 * mm, y_pos - 1.5 * mm, 6.8 * mm, 4.8 * mm, .5 * mm, fill=0, stroke=1); pdf.line(x_pos - 3.2 * mm, y_pos + 1.6 * mm, x_pos + 3.2 * mm, y_pos + 1.6 * mm)
        pdf.restoreState()

    def detail(title, primary, secondary=None, extra=None, icon_kind="o"):
        nonlocal y
        label(title, y)
        icon(x + 10 * mm, y - 7 * mm, icon_kind)
        text(primary, x + 15 * mm, y - 7.2 * mm, "Helvetica-Bold", 8.9, INK)
        if secondary:
            text(secondary, x + 15 * mm, y - 11.5 * mm, "Helvetica", 7.5, MUTED)
        if extra:
            text(extra, x + 15 * mm, y - 15.2 * mm, "Helvetica", 7.5, BLUE)
        y -= 19 * mm if extra else 15 * mm

    # Same broad navy masthead and light-blue detail band as the supplied ticket.
    header_y, header_h = A4[1] - 40 * mm, 31 * mm
    pdf.setFillColor(colors.HexColor("#073E82"))
    pdf.rect(x, header_y, panel_width, header_h, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setStrokeColor(colors.white)
    _draw_landing_mark(pdf, x + 6 * mm, header_y + 10 * mm, 14 * mm)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(x + 37 * mm, header_y + 21 * mm, "Ticket Information")
    pdf.setFont("Helvetica-Bold", 8.7)
    pdf.drawString(x + 37 * mm, header_y + 14.5 * mm, f"{vehicle.display_name} at {shop.shop_name}")
    pdf.setFont("Helvetica", 8.1)
    pdf.drawString(x + 37 * mm, header_y + 9 * mm, f"Pickup on {_date(booking.pickup_date)}")
    pdf.setFont("Helvetica-BoldOblique", 13)
    pdf.drawRightString(right - 8 * mm, header_y + 18 * mm, "RideHub")
    pdf.setStrokeColor(colors.HexColor("#4F80B8"))
    pdf.line(x, header_y + 7 * mm, right, header_y + 7 * mm)
    pdf.setFillColor(colors.white); pdf.setFont("Helvetica", 7.4)
    pdf.drawCentredString(x + panel_width / 2, header_y + 3.2 * mm, f"Ticket Number: {reference}    |    Payment ID: {plain(payment.provider_payment_id)}")

    y = header_y - 7 * mm
    customer_name = booking.renter_full_name or customer.get_full_name() or customer.email
    text(f"Hey {customer_name},", x, y, "Helvetica", 9.2, INK)
    y -= 11 * mm
    text("Thank you for choosing RideHub. Here are the details for your confirmed vehicle rental.", x, y, "Helvetica", 8.9, INK)
    y -= 8 * mm
    pdf.setFillColor(colors.HexColor("#E2EAF8"))
    pdf.rect(x, y - 8 * mm, panel_width, 8 * mm, fill=1, stroke=0)
    text("Ticket Details", x + 5 * mm, y - 5.2 * mm, "Helvetica-Bold", 10, INK)
    y -= 15 * mm

    customer_name = booking.renter_full_name or customer.get_full_name() or customer.email
    duration = (booking.return_date - booking.pickup_date).days + 1
    detail("Journey date and time", f"{_date(booking.pickup_date)} - rental start", f"Return: {_date(booking.return_date)} | {duration} day{'s' if duration != 1 else ''}", icon_kind="calendar")
    detail("Vehicle", vehicle.display_name, f"{vehicle.get_vehicle_type_display()} / {plain(vehicle.body_style).title()} / {plain(vehicle.fuel_type).title()}", f"Registration: {vehicle.registration_number}", "car")
    detail("Ticket price", _money(payment.amount, payment.currency), "Paid online via RideHub", icon_kind="card")
    detail("Pickup point", shop.shop_name, shop.shop_address, f"Proprietor: {plain(shop.proprietor_name)} | Contact: {plain(shop.user.phone_number)}", "pin")
    detail("Drop point", "Return vehicle to the same rental partner", f"Expected return: {_date(booking.return_date)}", icon_kind="pin")
    label("Passenger details", y)
    text("Booking status", right - 33 * mm, y, "Helvetica", 7.6, MUTED)
    text("CONFIRMED", right - 28 * mm, y, "Helvetica-Bold", 8, GREEN)
    y -= 7 * mm
    icon(x + 10 * mm, y - 2 * mm, "person")
    text(customer_name, x + 15 * mm, y - 2 * mm, "Helvetica-Bold", 8.7, INK)
    text(f"{booking.renter_age or '-'} Yrs, {plain(booking.renter_gender).upper()} | +91 {plain(booking.renter_phone or customer.phone_number)}", x + 15 * mm, y - 6 * mm, "Helvetica", 7.4, MUTED)
    text(booking.renter_email or customer.email, x + 15 * mm, y - 10 * mm, "Helvetica", 7.4, MUTED)
    y -= 16 * mm
    _draw_landing_watermark(pdf, A4[0] / 2, A4[1] / 2)
    pdf.setStrokeColor(colors.HexColor("#4F80B8")); pdf.setLineWidth(.8); pdf.rect(10 * mm, 10 * mm, A4[0] - 20 * mm, A4[1] - 20 * mm, fill=0, stroke=1)
    pdf.setStrokeColor(LINE); pdf.line(x, 17 * mm, right, 17 * mm)
    text("RideHub - secure vehicle rentals | Support: support@ridehub.in", x, 11 * mm, "Helvetica", 7, MUTED)
    pdf.setFillColor(MUTED); pdf.setFont("Helvetica", 7); pdf.drawRightString(right, 11 * mm, f"{reference} | Page 1")
    def page_shell(page_number, heading):
        pdf.showPage()
        pdf.setStrokeColor(colors.HexColor("#4F80B8")); pdf.setLineWidth(.8); pdf.rect(10 * mm, 10 * mm, A4[0] - 20 * mm, A4[1] - 20 * mm, fill=0, stroke=1)
        pdf.setFillColor(colors.HexColor("#073E82")); pdf.rect(x, header_y, panel_width, header_h, fill=1, stroke=0)
        _draw_landing_mark(pdf, x + 8 * mm, header_y + 10 * mm, 13 * mm)
        pdf.setFillColor(colors.white); pdf.setFont("Helvetica-Bold", 16); pdf.drawString(x + 27 * mm, header_y + 18 * mm, "RideHub")
        pdf.setFont("Helvetica", 8); pdf.drawString(x + 27 * mm, header_y + 12 * mm, "MOVE FREELY. LIVE MORE.")
        pdf.setFont("Helvetica-Bold", 12); pdf.drawRightString(right - 8 * mm, header_y + 18 * mm, "Ride Confirmation")
        pdf.setFont("Helvetica", 8); pdf.drawRightString(right - 8 * mm, header_y + 12 * mm, reference)
        pdf.setFillColor(colors.HexColor("#E2EAF8")); pdf.rect(x, header_y - 15 * mm, panel_width, 9 * mm, fill=1, stroke=0)
        text(heading, x + 5 * mm, header_y - 11.5 * mm, "Helvetica-Bold", 10, INK)
        return header_y - 29 * mm

    def page_footer(page_number):
        _draw_landing_watermark(pdf, A4[0] / 2, A4[1] / 2)
        pdf.setStrokeColor(LINE); pdf.line(x, 17 * mm, right, 17 * mm); text("RideHub - secure vehicle rentals | Support: support@ridehub.in", x, 11 * mm, "Helvetica", 7, MUTED); pdf.setFillColor(MUTED); pdf.setFont("Helvetica", 7); pdf.drawRightString(right, 11 * mm, f"{reference} | Page {page_number}")

    # Page 2 - feature cards and change table, aligned with the bus-ticket reference.
    page_y = page_shell(2, "Rental experience and booking changes")
    text("Congratulations on your RideHub booking!", x + 5 * mm, page_y, "Helvetica-Bold", 12, INK)
    text("Everything you need for a smooth pickup and return.", x + 5 * mm, page_y - 6 * mm, "Helvetica", 8.4, MUTED)
    card_y = page_y - 28 * mm
    for pos, title, desc, kind in [(x + 15 * mm, "Verified listing", "Rental partner details", "car"), (x + 73 * mm, "Clear handover", "Inspect before you ride", "calendar"), (x + 131 * mm, "Support", "Help when you need it", "person")]:
        pdf.setFillColor(colors.HexColor("#F5F7FA")); pdf.roundRect(pos - 9 * mm, card_y - 8 * mm, 53 * mm, 20 * mm, 2 * mm, fill=1, stroke=0)
        icon(pos, card_y, kind); text(title, pos + 7 * mm, card_y + 2 * mm, "Helvetica-Bold", 9, INK); text(desc, pos + 7 * mm, card_y - 3 * mm, "Helvetica", 7.2, MUTED)
    page_y = card_y - 29 * mm
    text("Booking date change", x + 8 * mm, page_y, "Helvetica-Bold", 11, INK)
    text("Request any change with the rental partner before the pickup time.", x + 8 * mm, page_y - 7 * mm, "Helvetica", 8.5, INK)
    data = [["Change window", "Charges"], [f"Before {_date(booking.pickup_date)}", "Contact rental partner"], ["After pickup time", "Not available"]]
    table = Table(data, colWidths=[108 * mm, 62 * mm], rowHeights=[8 * mm, 10 * mm, 10 * mm])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2EAF8")), ("GRID", (0, 0), (-1, -1), .45, LINE), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTNAME", (0, 1), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 8), ("TEXTCOLOR", (0, 0), (-1, -1), INK), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 7)]))
    table.wrapOn(pdf, panel_width, 40 * mm); table.drawOn(pdf, x + 5 * mm, page_y - 34 * mm)
    text("To request a date change, open your booking and contact the rental partner using the displayed phone number.", x + 8 * mm, page_y - 46 * mm, "Helvetica", 8.2, MUTED)
    page_footer(2)

    # Page 3 - cancellation policy in the requested table-led format.
    page_y = page_shell(3, "Cancellation policy")
    text("Cancellation charges depend on how close the cancellation is to the rental pickup date.", x + 8 * mm, page_y, "Helvetica", 8.7, INK)
    policy = [["Cancellation time", "Cancellation charge"], ["7 days or more before pickup", "0%"], ["3 to 6 days before pickup", "25%"], ["1 to 2 days before pickup", "50%"], ["Less than 24 hours before pickup", "100%"]]
    policy_table = Table(policy, colWidths=[108 * mm, 62 * mm], rowHeights=[9 * mm] * 5)
    policy_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2EAF8")), ("BACKGROUND", (1, 1), (1, -1), colors.HexColor("#FAF7F7")), ("GRID", (0, 0), (-1, -1), .5, LINE), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8.2), ("TEXTCOLOR", (0, 0), (-1, -1), INK), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 7)]))
    policy_table.wrapOn(pdf, panel_width, 50 * mm); policy_table.drawOn(pdf, x + 5 * mm, page_y - 55 * mm)
    notes = ["Cancellation requests must be raised before the scheduled pickup time.", "Refunds, where applicable, are initiated after confirmation from the rental partner.", "The final rental agreement and any documented partner policy take precedence."]
    cursor = page_y - 70 * mm
    for note in notes:
        pdf.setFillColor(MUTED); pdf.circle(x + 9 * mm, cursor + 1.5, 1.1, fill=1, stroke=0); text(note, x + 14 * mm, cursor, "Helvetica", 8.4, MUTED); cursor -= 13 * mm
    text("How to cancel your RideHub booking", x + 8 * mm, cursor - 4 * mm, "Helvetica-Bold", 8.7, INK)
    text("Open My Bookings, select the booking and use the cancellation option before pickup.", x + 8 * mm, cursor - 12 * mm, "Helvetica", 8.4, INK)
    page_footer(3)

    # Page 4 - the actual Terms of Use text shown on the RideHub landing page.
    page_y = page_shell(4, "Terms and conditions")
    terms = [
        ("Platform role.", "RideHub helps users discover shops and vehicle listings. The rental agreement is between the customer and the shopkeeper."),
        ("Accurate information.", "Users and shopkeepers are responsible for keeping account, listing and contact details accurate and lawful."),
        ("Availability and pricing.", "Search results are indicative until the shop confirms the requested dates and final terms. Review the displayed price, deposit, documents and cancellation conditions before confirming."),
        ("Safe use.", "Do not misuse accounts, submit false documents, bypass eligibility requirements or use a vehicle unlawfully. Shops may set reasonable rental and handover requirements."),
        ("Project status.", "RideHub is an academic project; features may change during development. This summary is informational and is not a substitute for a signed rental agreement or legal advice."),
    ]
    cursor = page_y
    for number, (term_title, term_body) in enumerate(terms, start=1):
        p = Paragraph(f"<b>{number}. {term_title}</b> {term_body}", ParagraphStyle("term", fontName="Helvetica", fontSize=8.5, leading=12, textColor=INK))
        _, height = p.wrap(panel_width - 16 * mm, 50 * mm); p.drawOn(pdf, x + 8 * mm, cursor - height); cursor -= height + 8 * mm
    text("Contact: business.starkindustries@gmail.com | Dehradun, Uttarakhand", x + 8 * mm, 35 * mm, "Helvetica", 8, MUTED)
    page_footer(4)
    pdf.save()
    return stream.getvalue()


def _document_bytes(booking, kind):
    if kind == "confirmation":
        return _confirmation_bytes(booking)
    payment = booking.payment
    vehicle = booking.vehicle
    shop = vehicle.shopkeeper
    customer = booking.customer
    reference = _ride_reference(booking)
    title = "Payment Receipt" if kind == "receipt" else "Ride Confirmation"
    stream = BytesIO()
    styles = _styles()
    # The explicit spacer keeps content below the masthead even with ReportLab's
    # first-page frame setup, which otherwise differs from continuation pages.
    story = [Spacer(1, 35 * mm)]

    paid_on = timezone.localtime(payment.updated_at).strftime("%d %b %Y, %I:%M %p")
    header = [
        Paragraph(title, styles["title"]),
        Paragraph(
            "Payment received and booking confirmed." if kind == "receipt" else "Your vehicle is reserved. Please carry this confirmation at pickup.",
            styles["subtitle"],
        ),
        Spacer(1, 5 * mm),
    ]
    banner = Table([[Paragraph(f"<b>{'PAID' if kind == 'receipt' else 'CONFIRMED'}</b><br/><font size=8>{reference}</font>", styles["center"]),
                     Paragraph(f"<b>{_money(payment.amount, payment.currency)}</b><br/><font size=8>Amount paid</font>", styles["center"]),
                     Paragraph(f"<b>{_date(booking.pickup_date)}</b><br/><font size=8>Pickup date</font>", styles["center"])]], colWidths=[58 * mm] * 3)
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EAF4FF")),
        ("BOX", (0, 0), (-1, -1), .7, colors.HexColor("#B7D7FF")),
        ("INNERGRID", (0, 0), (-1, -1), .5, colors.HexColor("#B7D7FF")),
        ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story.extend(header + [banner, Spacer(1, 6 * mm)])

    customer_name = booking.renter_full_name or customer.get_full_name() or customer.email
    story.append(_section("Customer details", [
        (("Renter", customer_name), ("Mobile", f"+91 {_text(booking.renter_phone or customer.phone_number)}")),
        (("Email", booking.renter_email or customer.email), ("Age / gender", f"{booking.renter_age or '-'} / {_text(booking.renter_gender)}")),
    ], styles))

    if kind == "receipt":
        story.append(_section("Payment details", [
            (("Receipt number", f"RHP-{payment.id:08d}"), ("Payment status", "PAID")),
            (("Amount paid", _money(payment.amount, payment.currency)), ("Payment method", _text(payment.provider, "Online payment").title())),
            (("Transaction ID", _text(payment.provider_payment_id)), ("Paid on", paid_on)),
            (("Gateway order ID", _text(payment.provider_reference)), ("Booking reference", reference)),
        ], styles))
        story.append(_section("Rental partner", [
            (("Shop", shop.shop_name), ("Proprietor", _text(shop.proprietor_name))),
            (("Shop address", shop.shop_address), ("GSTIN", _text(shop.gstin, "Not provided"))),
        ], styles))
    else:
        duration = (booking.return_date - booking.pickup_date).days + 1
        story.append(_section("Ride details", [
            (("Booking reference", reference), ("Ride status", "CONFIRMED")),
            (("Pickup", _date(booking.pickup_date)), ("Return", _date(booking.return_date))),
            (("Rental duration", f"{duration} day{'s' if duration != 1 else ''}"), ("Booking created", timezone.localtime(booking.created_at).strftime("%d %b %Y"))),
        ], styles))
        story.append(_section("Vehicle details", [
            (("Vehicle", vehicle.display_name), ("Registration", vehicle.registration_number)),
            (("Type / body", f"{vehicle.get_vehicle_type_display()} / {_text(vehicle.body_style).title()}"), ("Fuel", _text(vehicle.fuel_type).title())),
            (("Year / seats", f"{vehicle.manufacturing_year} / {vehicle.seating_capacity}"), ("Daily rate", _money(vehicle.daily_rate))),
        ], styles))
        story.append(_section("Rental partner", [
            (("Shop", shop.shop_name), ("Proprietor", _text(shop.proprietor_name))),
            (("Shop address", shop.shop_address), ("Contact", _text(shop.user.phone_number))),
            (("RideHub", "Secure online vehicle rentals"), ("Support", "support@ridehub.in")),
        ], styles))

    if kind != "receipt":
        note = "Pickup reminder: carry a valid driving licence, this confirmation, and the identity document submitted during checkout. Inspect the vehicle with the rental partner before handover."
        note_box = Table([[Paragraph(note, styles["note"])]], colWidths=[174 * mm])
        note_box.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), MIST), ("BOX", (0, 0), (-1, -1), .5, LINE), ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
        story.append(note_box)

    document = SimpleDocTemplate(
        stream, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=8 * mm, bottomMargin=25 * mm, title=f"RideHub {title} {reference}",
        author="RideHub", subject=f"{title} for {reference}",
    )
    document.build(story, canvasmaker=lambda *args, **kwargs: RideHubCanvas(
                       *args, document_kind=title, reference=reference, **kwargs
                   ))
    return stream.getvalue()


@login_required
def download_booking_document(request, booking_id, kind):
    """Serve a paid booking's receipt or confirmation to an authorised party."""
    if kind not in {"receipt", "confirmation"}:
        raise Http404
    try:
        booking = Booking.objects.select_related(
            "customer", "payment", "vehicle", "vehicle__shopkeeper", "vehicle__shopkeeper__user"
        ).get(pk=booking_id)
    except Booking.DoesNotExist as exc:
        raise Http404("Booking not found.") from exc
    is_customer = booking.customer_id == request.user.id
    is_shopkeeper = request.user.role == User.Role.SHOPKEEPER and booking.vehicle.shopkeeper.user_id == request.user.id
    if not (is_customer or is_shopkeeper or request.user.role == User.Role.ADMIN):
        raise Http404("Booking not found.")
    if booking.payment.status != PaymentTransaction.Status.PAID:
        raise Http404("This document is available after confirmed payment.")
    if kind == "confirmation" and booking.status == Booking.Status.CANCELLED:
        raise Http404("Ride confirmation is not available for a cancelled booking.")
    document_kind = "receipt" if kind == "receipt" else "confirmation"
    filename = f"ridehub-{document_kind}-{_ride_reference(booking).lower()}.pdf"
    return FileResponse(BytesIO(_document_bytes(booking, document_kind)), as_attachment=True, filename=filename, content_type="application/pdf")
