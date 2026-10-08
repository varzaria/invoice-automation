"""Score an n8n test run against the answer key.

Export the Invoices tab of the Google Sheet as CSV to results/sheet_export.csv,
then run:  py evaluate.py [path/to/export.csv]

Rows are matched to invoices by the id column: the test run reads the invoices
in file order, so id "<execution>-<n>" belongs to invoice_<n+1>.pdf.
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
TEXT_FIELDS = ["supplier", "invoice_number", "invoice_date", "due_date", "currency"]
AMOUNT_FIELDS = ["subtotal", "vat", "total"]


def flag_set(value) -> frozenset:
    if pd.isna(value) or str(value).strip() in ("", "none"):
        return frozenset()
    return frozenset(f.strip() for f in str(value).split(";"))


def main() -> None:
    export = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results" / "sheet_export.csv"
    sheet = pd.read_csv(export, dtype=str)
    sheet.columns = [c.strip() for c in sheet.columns]
    sheet = sheet.loc[:, ~sheet.columns.duplicated(keep="last")]  # tolerate a stray duplicate "id" column
    key = pd.read_csv(ROOT / "answer_key.csv", dtype=str)

    sheet["file"] = sheet["id"].str.split("-").str[-1].astype(int).map(lambda n: f"invoice_{n + 1:02d}.pdf")
    merged = key.merge(sheet, on="file", how="left", suffixes=("_true", ""))
    missing = merged["supplier"].isna()

    field_correct, wrong = {}, []
    for field in TEXT_FIELDS + AMOUNT_FIELDS:
        if field in AMOUNT_FIELDS:
            ok = (pd.to_numeric(merged[field], errors="coerce") - pd.to_numeric(merged[f"{field}_true"])).abs() < 0.01
        else:
            ok = merged[field].fillna("").str.strip() == merged[f"{field}_true"].str.strip()
        field_correct[field] = int(ok.sum())
        for _, row in merged[~ok & ~missing].iterrows():
            wrong.append((row["file"], field, row[f"{field}_true"], row[field]))

    flags_ok = merged["flags"].map(flag_set) == merged["flags_true"].map(flag_set)
    all_fields_ok = merged.apply(lambda r: all(
        (abs(float(r[f]) - float(r[f + "_true"])) < 0.01) if f in AMOUNT_FIELDS else str(r[f]).strip() == r[f + "_true"]
        for f in TEXT_FIELDS + AMOUNT_FIELDS) if not pd.isna(r["supplier"]) else False, axis=1)

    n = len(key)
    total_fields = n * len(TEXT_FIELDS + AMOUNT_FIELDS)
    print(f"Invoices in answer key: {n}   rows found in sheet: {n - missing.sum()}\n")
    print(f"Field accuracy:     {sum(field_correct.values())} / {total_fields} fields "
          f"({sum(field_correct.values()) / total_fields:.1%})")
    print(f"Invoices perfect:   {all_fields_ok.sum()} / {n} (every field correct)")
    print(f"Flags correct:      {flags_ok.sum()} / {n}\n")
    print("By field:")
    for field, correct in field_correct.items():
        print(f"  {field:<15} {correct} / {n}")

    if wrong:
        print("\nExtraction errors (file, field, expected, got):")
        for item in wrong:
            print("  " + " | ".join(str(x) for x in item))
    bad_flags = merged[~flags_ok]
    if len(bad_flags):
        print("\nFlag errors:")
        for _, r in bad_flags.iterrows():
            print(f"  {r['file']}  expected {r['flags_true']!r}, got {r['flags']!r}")

    if "status" in merged:
        print("\nStatus after approvals:", merged["status"].value_counts().to_dict())


if __name__ == "__main__":
    main()
