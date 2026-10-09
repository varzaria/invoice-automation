"""Create one fresh invoice for the demo video: a German invoice from an approved supplier, over 10,000.

It isn't in the test set or the sheet, so on camera it arrives as a new invoice and gets
flagged for approval only because of its size.

  py make_demo_invoice.py      # writes demo/invoice_schmidt_demo.pdf
"""

import random
from datetime import date
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

import generate_invoices as gen

OUT = Path(__file__).parent / "demo" / "invoice_schmidt_demo.pdf"


def main() -> None:
    supplier = next(s for s in gen.APPROVED if s[0].startswith("Kaffeerösterei"))
    inv = gen.build_invoice(random.Random(2026), supplier, "2026/912", date(2026, 10, 5), big=True)
    inv["layout"], inv["date_format"] = "modern", "%d.%m.%Y"  # German-style dates, e.g. 05.10.2026
    OUT.parent.mkdir(exist_ok=True)
    c = canvas.Canvas(str(OUT), pagesize=A4)
    c.setTitle(f"Rechnung {inv['invoice_number']}")
    gen.LAYOUTS[inv["layout"]](c, inv, german=True)
    c.save()
    print(f"Wrote {OUT.relative_to(Path(__file__).parent)}: {inv['supplier']}, {inv['invoice_number']}, "
          f"{inv['currency']} {inv['total']:,.2f}, due {inv['due_date']}")


if __name__ == "__main__":
    main()
