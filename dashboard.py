"""Invoice approval dashboard for Kildare Craft Coffee.

Run with:  streamlit run dashboard.py

Reads invoices from, and sends decisions to, the n8n workflow "Invoice dashboard API"
through two webhooks. n8n holds the Google Sheets connection, so the dashboard never
talks to Google directly. Every request carries the shared token from .env.
"""

import os
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
BASE_URL = os.getenv("N8N_BASE_URL", "http://localhost:5678").rstrip("/")
HEADERS = {"X-Dashboard-Token": os.getenv("DASHBOARD_TOKEN", "")}

FLAG_REASONS = {
    "duplicate": "Same supplier and invoice number as an invoice already logged",
    "new_supplier": "Supplier is not on the approved list",
    "high_amount": "Total is over 10,000",
}

st.set_page_config(page_title="Invoice Approvals", page_icon="🧾", layout="wide")


@st.cache_data(ttl=30, show_spinner=False)
def load_invoices() -> pd.DataFrame:
    response = requests.get(f"{BASE_URL}/webhook/invoices", headers=HEADERS, timeout=20)
    response.raise_for_status()
    rows = [r for r in response.json() if r.get("invoice_number")]  # skip the empty item n8n returns for an empty sheet
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for col in ["subtotal", "vat", "total"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["invoice_date", "due_date"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in ["decided_at", "decided_by", "note"]:
        if col not in df:
            df[col] = ""
    return df.fillna({"decided_at": "", "decided_by": "", "note": ""})


def send_decision(invoice_id: str, decision: str, note: str, decided_by: str) -> None:
    response = requests.post(f"{BASE_URL}/webhook/decision", headers=HEADERS, timeout=20, json={
        "id": invoice_id, "decision": decision, "note": note, "decided_by": decided_by,
    })
    response.raise_for_status()


def money(amount: float, currency: str) -> str:
    symbol = {"EUR": "€", "GBP": "£", "USD": "$"}.get(currency, currency + " ")
    return f"{symbol}{amount:,.2f}"


# --- Sidebar ------------------------------------------------------------------

with st.sidebar:
    st.header("🧾 Invoice Approvals")
    st.caption("Kildare Craft Coffee Ltd")
    approver = st.text_input("Your name", value="Aoife Byrne", help="Recorded with every decision.")
    if st.button("Refresh", use_container_width=True):
        load_invoices.clear()
        st.rerun()
    st.caption(f"Data from n8n at {BASE_URL}")

# --- Load data ----------------------------------------------------------------

try:
    invoices = load_invoices()
except requests.RequestException as e:
    st.error("Can't reach n8n. Check that n8n is running and the **Invoice dashboard API** workflow is published.")
    st.caption(f"Details: {e}")
    st.stop()

if invoices.empty:
    st.info("No invoices logged yet. They appear here as soon as n8n processes an invoice email.")
    st.stop()

pending = invoices[invoices["status"] == "pending approval"].sort_values("due_date")
decided = invoices[invoices["decided_at"].astype(str).str.len() > 0].sort_values("decided_at", ascending=False)

st.markdown("""<style>
.block-container {padding-top: 2rem;}
/* Approve buttons green, Decline buttons red (Streamlit tags each button's container with its key) */
[class*="st-key-approved-"] button {background-color: #1e9e55; border-color: #1e9e55; color: white;}
[class*="st-key-approved-"] button:hover {background-color: #178244; border-color: #178244; color: white;}
[class*="st-key-rejected-"] button {background-color: #d64545; border-color: #d64545; color: white;}
[class*="st-key-rejected-"] button:hover {background-color: #b53434; border-color: #b53434; color: white;}
</style>""", unsafe_allow_html=True)
st.subheader("Invoice Approvals")

# --- Approval queue ---------------------------------------------------------------

tab_queue, tab_overview, tab_history = st.tabs([f"Approval queue ({len(pending)})", "Overview", "Decision history"])

QUEUE_COLUMNS = [3, 1.3, 1.4, 2, 2.4, 1.3, 1.3]  # supplier, amount, due, flag, note, approve, decline


def escape(text: str) -> str:
    return text.replace("$", "\\$")  # so Streamlit doesn't read "$" as a maths formula


with tab_queue:
    if pending.empty:
        st.success("Nothing waiting for approval.")
    else:
        header = st.columns(QUEUE_COLUMNS)
        for col, label in zip(header, ["Supplier", "Total", "Due", "Why flagged", "Note", "", ""]):
            col.caption(label)
    for _, inv in pending.iterrows():
        days_left = (inv["due_date"].date() - date.today()).days if pd.notna(inv["due_date"]) else None
        when = "" if days_left is None else "overdue" if days_left < 0 else "today" if days_left == 0 else f"in {days_left} days"
        flags = str(inv["flags"]).split(";")
        with st.container(border=True):
            c = st.columns(QUEUE_COLUMNS, vertical_alignment="center")
            c[0].markdown(f"**{inv['supplier']}**  \n:gray[{inv['invoice_number']} · {inv['invoice_date']:%d %b %Y}]")
            c[1].markdown(f"**{escape(money(inv['total'], inv['currency']))}**")
            c[2].markdown(f"{inv['due_date']:%d %b}  \n:{'red' if days_left is not None and days_left <= 0 else 'gray'}[{when}]")
            c[3].markdown(" ".join(f":orange-badge[{f.replace('_', ' ')}]" for f in flags),
                          help="  \n".join(FLAG_REASONS.get(f, f) for f in flags))
            note = c[4].text_input("Note", key=f"note-{inv['id']}", placeholder="Note (optional)", label_visibility="collapsed")
            for col, decision, label, kind in [(c[5], "approved", "Approve", "primary"), (c[6], "rejected", "Decline", "secondary")]:
                if col.button(label, key=f"{decision}-{inv['id']}", type=kind, use_container_width=True):
                    try:
                        send_decision(inv["id"], decision, note, approver)
                        st.toast(f"{inv['supplier']} {inv['invoice_number']}: {decision}")
                        load_invoices.clear()
                        st.rerun()
                    except requests.RequestException as e:
                        st.error(f"Could not save the decision: {e}")

# --- Overview -------------------------------------------------------------------

with tab_overview:
    approved = invoices[invoices["status"] == "approved"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Invoices logged", len(invoices))
    m2.metric("Auto-approved", int((invoices["flags"] == "none").sum()))
    m3.metric("Waiting for approval", len(pending))
    m4.metric("Declined", int((invoices["status"] == "rejected").sum()))

    st.subheader("Approved spend")
    by_currency = approved.groupby("currency")["total"].sum()
    cols = st.columns(max(len(by_currency), 1))
    for col, (currency, total) in zip(cols, by_currency.items()):
        col.metric(currency, money(total, currency))

    st.subheader("Due in the next 14 days (approved)")
    today = pd.Timestamp(date.today())
    due_soon = approved[(approved["due_date"] >= today) & (approved["due_date"] <= today + pd.Timedelta(days=14))]
    if due_soon.empty:
        st.caption("Nothing due in the next 14 days.")
    else:
        st.dataframe(
            due_soon.sort_values("due_date").assign(
                due=lambda d: d["due_date"].dt.strftime("%d %b %Y"),
                amount=lambda d: [money(t, c) for t, c in zip(d["total"], d["currency"])],
            )[["due", "supplier", "invoice_number", "amount"]],
            hide_index=True, use_container_width=True,
        )

    st.subheader("Approved spend by supplier (EUR)")
    eur = approved[approved["currency"] == "EUR"].groupby("supplier")["total"].sum().sort_values(ascending=False)
    if eur.empty:
        st.caption("No approved EUR invoices yet.")
    else:
        st.bar_chart(eur, horizontal=True, y_label="", x_label="EUR")

# --- History --------------------------------------------------------------------

with tab_history:
    if decided.empty:
        st.caption("No decisions yet.")
    else:
        history = decided.assign(
            decided=lambda d: pd.to_datetime(d["decided_at"], errors="coerce", utc=True)
                              .dt.tz_convert("Europe/Dublin").dt.strftime("%d %b %Y %H:%M"),  # show Irish time
            amount=lambda d: [money(t, c) for t, c in zip(d["total"], d["currency"])],
        )[["decided", "status", "decided_by", "supplier", "invoice_number", "amount", "flags", "note"]]
        st.dataframe(history, hide_index=True, use_container_width=True)
        st.download_button("Download history (CSV)", history.to_csv(index=False),
                           file_name=f"approval-history-{datetime.now():%Y%m%d}.csv", mime="text/csv")
