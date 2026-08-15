import io
import os
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image, Flowable
)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from PIL import Image as PILImage


class GrayBox(Flowable):
    def __init__(self, w, h, fill_color):
        super().__init__()
        self.width = w
        self.height = h
        self.fill_color = fill_color

    def draw(self):
        self.canv.setFillColor(self.fill_color)
        self.canv.rect(0, 0, self.width, self.height, fill=1, stroke=0)


def generate_order_invoice_pdf(order) -> bytes:
    """
    Generates a PDF invoice for an Order using ReportLab.
    Formatted with the Artisanal Farm-to-Table Harvest aesthetic.
    Returns the generated PDF as raw bytes.
    """
    # ── Colour palette ──────────────────────────────────────────────────────
    FARM_GREEN = colors.HexColor('#264634')
    FARM_GREEN_DARK = colors.HexColor('#1A3325')
    FARM_CREAM = colors.HexColor('#FAF7EE')
    FARM_CREAM_DARK = colors.HexColor('#EFE8D6')
    FARM_TERRACOTTA = colors.HexColor('#C85A32')
    FARM_GOLD = colors.HexColor('#D49B4B')
    TEXT_DARK = colors.HexColor('#261E18')
    TEXT_MID = colors.HexColor('#5A4D43')
    TEXT_LIGHT = colors.HexColor('#9C8C80')
    WHITE = colors.white

    # ── Styles ───────────────────────────────────────────────────────────────
    def sty(name, **kw):
        base = {
            'fontName':  'Helvetica',
            'fontSize':  9,
            'textColor': TEXT_DARK,
            'leading':   13,
        }
        base.update(kw)
        return ParagraphStyle(name, **base)

    S_BRAND = sty('brand', fontName='Helvetica-Bold', fontSize=20, textColor=FARM_GREEN, leading=24)
    S_TAGLINE = sty('tagline', fontSize=8, textColor=TEXT_LIGHT, leading=11)
    S_SECTION = sty('section', fontName='Helvetica-Bold', fontSize=8, textColor=TEXT_LIGHT, leading=10, spaceAfter=4)
    S_BODY = sty('body', fontSize=9, textColor=TEXT_DARK, leading=13)
    S_BODY_MID = sty('bodymid', fontSize=8, textColor=TEXT_MID, leading=12)
    S_BOLD = sty('bold', fontName='Helvetica-Bold', fontSize=9, textColor=TEXT_DARK, leading=13)
    S_RIGHT_MID = sty('rightmid', fontSize=8, textColor=TEXT_MID, leading=12, alignment=TA_RIGHT)
    S_CENTER = sty('center', fontSize=8, textColor=TEXT_LIGHT, leading=11, alignment=TA_CENTER)

    # ── Helper: load product image ────────────────────────────────────────
    def load_img(product, size=(12 * mm, 12 * mm)):
        try:
            if product and product.image:
                img_path = os.path.join(settings.MEDIA_ROOT, str(product.image))
                if os.path.exists(img_path):
                    pil = PILImage.open(img_path).convert('RGB')
                    buf = io.BytesIO()
                    pil.save(buf, format='JPEG')
                    buf.seek(0)
                    img = Image(buf, width=size[0], height=size[1])
                    img.hAlign = 'CENTER'
                    return img
        except Exception:
            pass
        return GrayBox(size[0], size[1], FARM_CREAM_DARK)

    # ── Build PDF ─────────────────────────────────────────────────────────
    buf = io.BytesIO()
    page_w, page_h = A4
    margin = 18 * mm

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )

    story = []
    usable_w = page_w - 2 * margin

    # ── HEADER ───────────────────────────────────────────────────────────
    header_data = [[
        Paragraph('HARVEST <font color="#C85A32">&amp; CO.</font>', S_BRAND),
        Paragraph(
            f'<b>HARVEST INVOICE</b><br/>'
            f'<font color="#9C8C80">Order #{order.id}</font>',
            sty('inv', fontName='Helvetica-Bold', fontSize=12, textColor=FARM_GREEN_DARK, leading=16, alignment=TA_RIGHT)
        ),
    ]]
    header_tbl = Table(header_data, colWidths=[usable_w * 0.55, usable_w * 0.45])
    header_tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), FARM_CREAM),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 3 * mm))

    # tagline + divider
    story.append(Paragraph('Artisanal Farm Collective • Western Ghats &amp; Ooty Valleys • harvest@thefarmpantry.com', S_TAGLINE))
    story.append(Spacer(1, 3 * mm))
    story.append(HRFlowable(width='100%', thickness=1.5, color=FARM_GREEN, spaceAfter=4 * mm))

    # ── ORDER META ROW ────────────────────────────────────────────────────
    status_label = order.get_status_display().upper()
    pay_label = order.get_payment_method_display()
    pay_status = order.payment_status.capitalize()
    est = order.estimated_delivery.strftime('%d %b %Y') if order.estimated_delivery else '—'

    meta_data = [[
        Paragraph('HARVEST DATE', S_SECTION),
        Paragraph('STATUS', S_SECTION),
        Paragraph('PAYMENT', S_SECTION),
        Paragraph('EST. DELIVERY', S_SECTION),
    ], [
        Paragraph(order.created_at.strftime('%d %b %Y'), S_BODY),
        Paragraph(status_label, S_BOLD),
        Paragraph(f'{pay_label}<br/><font color="#9C8C80">{pay_status}</font>', S_BODY),
        Paragraph(est, S_BODY),
    ]]
    col_w = usable_w / 4
    meta_tbl = Table(meta_data, colWidths=[col_w] * 4)
    meta_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), FARM_CREAM_DARK),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, FARM_GREEN, 1, None, None, 2, 2),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 5 * mm))

    # ── BILL TO / SHIP TO ────────────────────────────────────────────────
    addr_text = (
        f'<b>{order.full_name or "Valued Member"}</b><br/>'
        f'{order.address or "Address on file"}<br/>'
        f'{order.city}, {order.state} — {order.pincode}<br/>'
        f'<font color="#9C8C80">{order.phone}</font>'
    )
    company_text = (
        '<b>Harvest &amp; Co. Artisanal Grocers</b><br/>'
        '100% Bio-Organic Farm Collective<br/>'
        'Zero Pesticides • Eco Kraft Packaging<br/>'
        '<font color="#9C8C80">GSTIN: 33AABCH9821Q1Z4</font>'
    )
    parties_data = [
        [Paragraph('DELIVERY DESTINATION', S_SECTION), Paragraph('FARM ORIGIN', S_SECTION)],
        [Paragraph(addr_text, S_BODY),                 Paragraph(company_text, S_BODY)],
    ]
    parties_tbl = Table(parties_data, colWidths=[usable_w * 0.5, usable_w * 0.5])
    parties_tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 2),
        ('TOPPADDING', (0, 1), (-1, 1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(parties_tbl)
    story.append(Spacer(1, 6 * mm))

    # ── ITEMS TABLE ───────────────────────────────────────────────────────
    col_widths = [16 * mm, usable_w - 76 * mm, 16 * mm, 22 * mm, 22 * mm]

    table_data = [[
        Paragraph('', S_SECTION),
        Paragraph('PRODUCE / ITEM', S_SECTION),
        Paragraph('QTY', sty('sh_qty', fontName='Helvetica-Bold', fontSize=8, textColor=TEXT_LIGHT, alignment=TA_CENTER)),
        Paragraph('PRICE', sty('sh_pr', fontName='Helvetica-Bold', fontSize=8, textColor=TEXT_LIGHT, alignment=TA_RIGHT)),
        Paragraph('TOTAL', sty('sh_tot', fontName='Helvetica-Bold', fontSize=8, textColor=TEXT_LIGHT, alignment=TA_RIGHT)),
    ]]

    for i, item in enumerate(order.items.all()):
        thumb = load_img(item.product)
        item_text = (
            f'<b>{item.name}</b><br/>'
            f'<font color="#9C8C80">100% Organic Farm Pack</font>'
        )
        table_data.append([
            thumb,
            Paragraph(item_text, S_BODY),
            Paragraph(str(item.quantity), sty(f'qty_{i}', fontSize=9, textColor=TEXT_DARK, alignment=TA_CENTER)),
            Paragraph(f'₹{item.price:.2f}', sty(f'pr_{i}', fontSize=9, textColor=TEXT_MID, alignment=TA_RIGHT)),
            Paragraph(f'₹{item.get_subtotal():.2f}', sty(f'tot_{i}', fontName='Helvetica-Bold', fontSize=9, textColor=TEXT_DARK, alignment=TA_RIGHT)),
        ])

    row_styles = [
        ('BACKGROUND', (0, 0), (-1, 0), FARM_GREEN_DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, 0), 1, FARM_GREEN),
        ('LINEBELOW', (0, 1), (-1, -1), 0.5, colors.HexColor('#EFE8D6')),
    ]
    for r in range(1, len(table_data)):
        bg = FARM_CREAM if r % 2 == 1 else WHITE
        row_styles.append(('BACKGROUND', (0, r), (-1, r), bg))

    items_tbl = Table(table_data, colWidths=col_widths)
    items_tbl.setStyle(TableStyle(row_styles))
    story.append(items_tbl)
    story.append(Spacer(1, 4 * mm))

    # ── TOTALS ────────────────────────────────────────────────────────────
    tot_w = [usable_w - 55 * mm, 55 * mm]
    totals_data = [
        [Paragraph('', S_BODY), Paragraph(f'Produce Subtotal:  <b>₹{order.total:.2f}</b>', S_RIGHT_MID)],
        [Paragraph('', S_BODY), Paragraph(f'Eco Refrigerated Delivery:  <b>₹{order.delivery_charge:.2f}</b>', S_RIGHT_MID)],
        [
            Paragraph('', S_BODY),
            Paragraph(
                f'<font size="11"><b>Grand Total:  </b></font>'
                f'<font size="13" color="#264634"><b>₹{order.grand_total:.2f}</b></font>',
                sty('gt', alignment=TA_RIGHT, leading=16)
            ),
        ],
    ]
    totals_tbl = Table(totals_data, colWidths=tot_w)
    totals_tbl.setStyle(TableStyle([
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('LINEABOVE', (1, 2), (1, 2), 1, FARM_GREEN),
    ]))
    story.append(totals_tbl)
    story.append(Spacer(1, 8 * mm))

    # ── FOOTER ───────────────────────────────────────────────────────────
    story.append(HRFlowable(width='100%', thickness=0.5, color=FARM_CREAM_DARK, spaceAfter=3 * mm))
    story.append(Paragraph(
        'Thank you for supporting ethical organic farming &amp; living soils! • 100% Recyclable Kraft Receipt<br/>'
        'Harvest &amp; Co. Grocers • www.thefarmpantry.com',
        S_CENTER
    ))

    # Build and return
    doc.build(story)
    buf.seek(0)
    return buf.read()
