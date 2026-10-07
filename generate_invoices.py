"""Generate realistic test invoices (PDF) for the n8n invoice-intake workflow.

The client is a fictional small business, Kildare Craft Coffee Ltd, which receives
supplier invoices by email. Invoices vary like real ones do: three layouts,
different labels and date formats, three currencies, one in German.

Outputs:
  invoices/*.pdf            the test invoices
  suppliers.csv             the approved supplier list (goes into the Google Sheet)
  answer_key.csv            the correct fields and flags for every invoice

Flags the workflow should raise:
  duplicate       same supplier + invoice number as an earlier invoice
  new_supplier    supplier is not on the approved list
  high_amount     total is above 10,000 (in any currency)
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).parent
OUT_DIR = ROOT / "invoices"
SEED = 11
HIGH_AMOUNT = 10_000

CLIENT = ("Kildare Craft Coffee Ltd", "Unit 4, Main Street", "Kilcock, Co. Kildare, W23 X2K7", "Ireland")

APPROVED = [
    # name, address, currency, VAT rate, items (description, unit price)
    ("Bean & Leaf Importers Ltd", "12 Harbour Road, Dublin 1, Ireland", "EUR", 0.23,
     [("Colombian Supremo beans, 5 kg", 92.00), ("Ethiopian Yirgacheffe beans, 5 kg", 118.50), ("Decaf Swiss Water beans, 5 kg", 104.00)]),
    ("Leinster Dairy Co-op", "Naas Business Park, Naas, Co. Kildare", "EUR", 0.0,
     [("Whole milk, 10 L crate", 11.80), ("Oat milk, 12 x 1 L", 21.60), ("Cream, 5 L", 19.25)]),
    ("Cupworks Packaging", "88 Ormeau Road, Belfast BT7 1SH, UK", "GBP", 0.20,
     [("Compostable cups 12oz, case of 1,000", 74.00), ("Lids 12oz, case of 1,000", 31.00), ("Paper bags, case of 500", 22.50)]),
    ("Eireann Espresso Services", "Unit 9, Ballymount, Dublin 12", "EUR", 0.23,
     [("Espresso machine service visit", 145.00), ("Grinder burr replacement", 89.00), ("Water filter cartridge", 38.00)]),
    ("Brew Tech Inc", "400 Pine Street, Seattle, WA 98101, USA", "USD", 0.0,
     [("Cold brew system, 20 L", 2_450.00), ("Pour-over station, 4-way", 680.00), ("Digital brew scale", 129.00)]),
    ("Kaffeerösterei Schmidt GmbH", "Hafenstraße 21, 20457 Hamburg, Deutschland", "EUR", 0.0,
     [("Röstkaffee Hausmischung, 5 kg", 86.00), ("Espresso Blend Nr. 3, 5 kg", 97.00)]),
]

UNAPPROVED = [
    ("QuickClean Supplies", "3 Fonthill Retail Park, Dublin 22", "EUR", 0.23,
     [("Degreaser concentrate, 5 L", 24.00), ("Microfibre cloths, pack of 50", 18.00)]),
    ("Fresh Bakes Wholesale", "Industrial Estate, Newbridge, Co. Kildare", "EUR", 0.135,
     [("Croissants, tray of 48", 39.00), ("Scones, tray of 36", 31.50), ("Brownies, tray of 24", 28.00)]),
]

DATE_FORMATS = ["%d/%m/%Y", "%d %b %Y", "%Y-%m-%d", "%B %d, %Y"]


def money(value: float, currency: str) -> str:
    symbol = {"EUR": "€", "GBP": "£", "USD": "$"}[currency]
    return f"{symbol}{value:,.2f}"


def build_invoice(rng: random.Random, supplier: tuple, number: str, issued: date, *, big: bool = False) -> dict:
    name, address, currency, vat_rate, catalogue = supplier
    lines = []
    for desc, price in rng.sample(catalogue, k=rng.randint(1, len(catalogue))):
        qty = rng.randint(1, 6)
        if big:
            qty *= rng.randint(4, 8)
        lines.append((desc, qty, price, round(qty * price, 2)))
    subtotal = round(sum(l[3] for l in lines), 2)
    if big and subtotal < HIGH_AMOUNT:  # make sure "big" invoices cross the threshold
        desc, qty, price, _ = lines[0]
        qty = int(HIGH_AMOUNT / price) + rng.randint(2, 10)
        lines[0] = (desc, qty, price, round(qty * price, 2))
        subtotal = round(sum(l[3] for l in lines), 2)
    vat = round(subtotal * vat_rate, 2)
    terms = rng.choice([14, 30, 30, 45])
    return {
        "supplier": name, "address": address, "currency": currency, "vat_rate": vat_rate,
        "invoice_number": number, "invoice_date": issued, "due_date": issued + timedelta(days=terms),
        "lines": lines, "subtotal": subtotal, "vat": vat, "total": round(subtotal + vat, 2),
        "date_format": rng.choice(DATE_FORMATS), "layout": rng.choice(["classic", "modern", "compact"]),
    }


# --- Layouts ----------------------------------------------------------------

def draw_classic(c: canvas.Canvas, inv: dict, german: bool) -> None:
    L = GERMAN if german else ENGLISH
    fmt = inv["date_format"]
    w, h = A4
    c.setFont("Helvetica-Bold", 20)
    c.drawString(40, h - 60, inv["supplier"])
    c.setFont("Helvetica", 9)
    c.drawString(40, h - 76, inv["address"])
    c.setFont("Helvetica-Bold", 16)
    c.drawRightString(w - 40, h - 60, L["title"])
    c.setFont("Helvetica", 10)
    c.drawRightString(w - 40, h - 80, f"{L['number']}: {inv['invoice_number']}")
    c.drawRightString(w - 40, h - 94, f"{L['date']}: {inv['invoice_date'].strftime(fmt)}")
    c.drawRightString(w - 40, h - 108, f"{L['due']}: {inv['due_date'].strftime(fmt)}")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, h - 130, L["bill_to"])
    c.setFont("Helvetica", 10)
    for i, line in enumerate(CLIENT):
        c.drawString(40, h - 144 - 13 * i, line)
    y = h - 220
    c.setFillColor(colors.HexColor("#E8E8E8"))
    c.rect(40, y - 4, w - 80, 18, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(46, y, L["desc"]); c.drawRightString(360, y, L["qty"])
    c.drawRightString(450, y, L["price"]); c.drawRightString(w - 46, y, L["amount"])
    c.setFont("Helvetica", 10)
    for desc, qty, price, amount in inv["lines"]:
        y -= 20
        c.drawString(46, y, desc); c.drawRightString(360, y, str(qty))
        c.drawRightString(450, y, money(price, inv["currency"])); c.drawRightString(w - 46, y, money(amount, inv["currency"]))
    y -= 30
    draw_totals(c, inv, L, w - 46, y)


def draw_modern(c: canvas.Canvas, inv: dict, german: bool) -> None:
    L = GERMAN if german else ENGLISH
    fmt = inv["date_format"]
    w, h = A4
    c.setFillColor(colors.HexColor("#1F3A5F"))
    c.rect(0, h - 110, w, 110, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 26)
    c.drawString(40, h - 60, L["title"].upper())
    c.setFont("Helvetica", 11)
    c.drawString(40, h - 85, f"{inv['supplier']}  ·  {inv['address']}")
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 10)
    c.drawString(40, h - 140, f"{L['ref']} {inv['invoice_number']}")
    c.drawString(40, h - 155, f"{L['issued']} {inv['invoice_date'].strftime(fmt)}")
    c.drawString(40, h - 170, f"{L['payable_by']} {inv['due_date'].strftime(fmt)}")
    c.drawRightString(w - 40, h - 140, L["customer"])
    for i, line in enumerate(CLIENT[:3]):
        c.drawRightString(w - 40, h - 155 - 15 * i, line)
    y = h - 230
    c.setFont("Helvetica-Bold", 9)
    c.drawString(40, y, L["desc"].upper()); c.drawRightString(w - 40, y, L["amount"].upper())
    c.line(40, y - 6, w - 40, y - 6)
    c.setFont("Helvetica", 10)
    for desc, qty, price, amount in inv["lines"]:
        y -= 22
        c.drawString(40, y, f"{qty} x {desc} @ {money(price, inv['currency'])}")
        c.drawRightString(w - 40, y, money(amount, inv["currency"]))
    y -= 36
    draw_totals(c, inv, L, w - 40, y, big_total=True)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(40, 50, L["footer"])


def draw_compact(c: canvas.Canvas, inv: dict, german: bool) -> None:
    L = GERMAN if german else ENGLISH
    fmt = inv["date_format"]
    w, h = A4
    c.setFont("Courier-Bold", 12)
    c.drawString(60, h - 60, inv["supplier"].upper())
    c.setFont("Courier", 9)
    c.drawString(60, h - 74, inv["address"])
    c.drawString(60, h - 100, "-" * 70)
    c.setFont("Courier", 10)
    c.drawString(60, h - 116, f"{L['inv_short']} {inv['invoice_number']}   {L['date']}: {inv['invoice_date'].strftime(fmt)}")
    c.drawString(60, h - 130, f"{L['to']}: {CLIENT[0]}, {CLIENT[2]}")
    c.drawString(60, h - 146, "-" * 70)
    y = h - 166
    for desc, qty, price, amount in inv["lines"]:
        c.drawString(60, y, f"{desc[:40]:<40} {qty:>3} {amount:>12,.2f}")
        y -= 14
    c.drawString(60, y - 4, "-" * 70)
    y -= 22
    c.drawString(60, y, f"{L['subtotal']:<44} {inv['subtotal']:>12,.2f}")
    if inv["vat_rate"]:
        y -= 14
        c.drawString(60, y, f"{L['vat']} {inv['vat_rate']:.1%}".ljust(44) + f" {inv['vat']:>12,.2f}")
    y -= 14
    c.setFont("Courier-Bold", 10)
    c.drawString(60, y, f"{L['total']} {inv['currency']}".ljust(44) + f" {inv['total']:>12,.2f}")
    c.setFont("Courier", 10)
    c.drawString(60, y - 24, f"{L['terms']} {inv['due_date'].strftime(fmt)}")


def draw_totals(c, inv, L, x, y, big_total=False):
    cur = inv["currency"]
    c.setFont("Helvetica", 10)
    c.drawRightString(x - 110, y, L["subtotal"]); c.drawRightString(x, y, money(inv["subtotal"], cur))
    if inv["vat_rate"]:
        y -= 16
        c.drawRightString(x - 110, y, f"{L['vat']} ({inv['vat_rate']:.1%})"); c.drawRightString(x, y, money(inv["vat"], cur))
    y -= 22
    c.setFont("Helvetica-Bold", 14 if big_total else 11)
    c.drawRightString(x - 110, y, L["total"]); c.drawRightString(x, y, money(inv["total"], cur))


ENGLISH = {
    "title": "Invoice", "number": "Invoice No.", "date": "Date", "due": "Due date", "bill_to": "Bill to",
    "desc": "Description", "qty": "Qty", "price": "Unit price", "amount": "Amount", "subtotal": "Subtotal",
    "vat": "VAT", "total": "Total due", "ref": "Reference:", "issued": "Issued:", "payable_by": "Payable by:",
    "customer": "Customer", "footer": "Please quote the reference number with your payment. Thank you for your business.",
    "inv_short": "INV #", "to": "TO", "terms": "PAYMENT DUE BY",
}
GERMAN = {
    "title": "Rechnung", "number": "Rechnungsnummer", "date": "Datum", "due": "Fällig am", "bill_to": "Rechnungsempfänger",
    "desc": "Beschreibung", "qty": "Menge", "price": "Einzelpreis", "amount": "Betrag", "subtotal": "Zwischensumme",
    "vat": "MwSt.", "total": "Gesamtbetrag", "ref": "Rechnungsnr.:", "issued": "Datum:", "payable_by": "Zahlbar bis:",
    "customer": "Kunde", "footer": "Steuerfreie innergemeinschaftliche Lieferung (Reverse Charge).",
    "inv_short": "RE-NR.", "to": "AN", "terms": "ZAHLBAR BIS",
}
LAYOUTS = {"classic": draw_classic, "modern": draw_modern, "compact": draw_compact}


def main() -> None:
    rng = random.Random(SEED)
    OUT_DIR.mkdir(exist_ok=True)
    for old in OUT_DIR.glob("*.pdf"):
        old.unlink()

    plan = []  # (supplier, big)
    counts = {"Brew Tech Inc": 1, "Leinster Dairy Co-op": 2}    # 3 invoices from every other supplier
    for supplier in APPROVED:
        plan += [(supplier, False)] * counts.get(supplier[0], 3)
    plan += [(APPROVED[0], True), (APPROVED[4], True)]          # high amounts
    plan += [(UNAPPROVED[0], False), (UNAPPROVED[1], False)]    # new suppliers
    rng.shuffle(plan)                                           # 19 invoices + 1 re-sent duplicate = 20

    invoices, start = [], date(2026, 9, 1)
    for i, (supplier, big) in enumerate(plan):
        prefix = "".join(word[0] for word in supplier[0].split() if word.isalpha())[:2].upper()
        number = rng.choice([f"{prefix}-{rng.randint(1000, 9999)}", f"INV{rng.randint(20000, 29999)}",
                             f"2026/{rng.randint(100, 999)}"])
        issued = start + timedelta(days=int(i * 1.5) + rng.randint(0, 1))
        invoices.append(build_invoice(rng, supplier, number, issued, big=big))

    # The duplicate: an earlier invoice re-sent a week later with a different layout.
    original = invoices[4]
    resent = dict(original, layout="compact" if original["layout"] != "compact" else "modern")
    invoices.append(resent)

    approved_names = {s[0] for s in APPROVED}
    seen, rows = set(), []
    for n, inv in enumerate(invoices, 1):
        german = inv["supplier"].startswith("Kaffeerösterei")
        file_name = f"invoice_{n:02d}.pdf"
        c = canvas.Canvas(str(OUT_DIR / file_name), pagesize=A4)
        c.setTitle(f"{'Rechnung' if german else 'Invoice'} {inv['invoice_number']}")
        LAYOUTS[inv["layout"]](c, inv, german)
        c.save()

        flags = []
        key = (inv["supplier"], inv["invoice_number"])
        if key in seen:
            flags.append("duplicate")
        seen.add(key)
        if inv["supplier"] not in approved_names:
            flags.append("new_supplier")
        if inv["total"] > HIGH_AMOUNT:
            flags.append("high_amount")
        rows.append({
            "file": file_name, "supplier": inv["supplier"], "invoice_number": inv["invoice_number"],
            "invoice_date": inv["invoice_date"].isoformat(), "due_date": inv["due_date"].isoformat(),
            "currency": inv["currency"], "subtotal": f"{inv['subtotal']:.2f}", "vat": f"{inv['vat']:.2f}",
            "total": f"{inv['total']:.2f}", "flags": ";".join(flags) or "none", "layout": inv["layout"],
            "language": "de" if german else "en",
        })

    with open(ROOT / "answer_key.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with open(ROOT / "suppliers.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["supplier", "default_currency"])
        writer.writerows([s[0], s[2]] for s in APPROVED)

    print(f"Wrote {len(rows)} invoices to {OUT_DIR.name}/")
    for r in rows:
        print(f"  {r['file']}  {r['layout']:<8} {r['language']}  {r['supplier'][:28]:<28} {r['currency']} {float(r['total']):>11,.2f}  {r['flags']}")


if __name__ == "__main__":
    main()
