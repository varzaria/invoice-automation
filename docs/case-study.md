# Case study: automating supplier invoice intake for a small business

**Client (fictional):** Kildare Craft Coffee Ltd, a café business with about 8 regular suppliers
**Tools:** n8n, Claude (AI), Gmail, Google Sheets, a Streamlit dashboard
**Outcome:** invoices logged in about 2 seconds each, 100% field accuracy on the test set, and a manager approves only the exceptions, from one dashboard

## 1. The problem

Supplier invoices arrive by email as PDFs in different layouts, currencies and languages. A staff member types each one into a spreadsheet, checks it, and asks the owner to approve anything unusual. The risks:

- **Time:** a few minutes per invoice, every week
- **Errors:** typos in amounts or dates
- **Money lost:** duplicate invoices paid twice; invoices from unknown suppliers paid without checks

## 2. The current process

Email arrives → staff open the PDF → type 8 fields into a spreadsheet → judge whether it looks unusual → message the owner → wait → update the spreadsheet.

## 3. The solution

A workflow in n8n that runs whenever an invoice email arrives:

1. **Read:** the PDF is converted to text.
2. **Extract:** AI pulls out supplier, invoice number, dates, currency, subtotal, VAT and total, in a fixed format.
3. **Check:** three business rules flag duplicates, unapproved suppliers, and totals over 10,000.
4. **Log:** every invoice is added to the Google Sheet the business already uses.
5. **Notify:** if any invoices are flagged, the owner gets one short email listing them.
6. **Approve:** the owner opens an approval dashboard showing each flagged invoice in one row, with the reason it was flagged, and clicks **Approve** or **Decline**, optionally adding a note. The decision, the approver's name and the time are written back to the sheet.

Normal invoices need no human action. The owner only sees exceptions.

**Why a dashboard instead of approval emails:** the first version emailed the owner about each flagged invoice, with buttons in the email. That works for one or two invoices, but a busy week means a stream of emails, no overview, and no record of who decided what. The dashboard puts every pending invoice in one place, shows what is due soon, and keeps an audit trail that can be exported for the accountant.

**Why these tools:** the business already uses Gmail and Google Sheets, so staff learn nothing new. n8n is free to self-host, and its visual workflow can be read and changed by non-developers.

## 4. Results

Tested on 20 realistic invoices with a known answer key: 3 layouts, 4 date formats, EUR/GBP/USD, and 4 invoices in German.

| Measure | Result |
| --- | --- |
| Fields extracted correctly | 160 / 160 (100%) |
| Invoices routed correctly (auto-logged vs sent for approval) | 20 / 20 |
| Approval decisions recorded | 5 / 5 |
| Processing time | about 2 seconds per invoice (excluding the owner's approval) |

The first run scored 158 / 160: the AI misread one supplier name written in capitals, which made an approved supplier look new and hid a duplicate. On a second run the AI read the same name correctly, which shows its small mistakes are intermittent. The fix was a safety net in the checks, not a better prompt: supplier names are matched to the approved list allowing small spelling differences.

## 5. Risks and how they are handled

| Risk | Mitigation |
| --- | --- |
| AI misreads a field | Business rules run on every invoice; anything unusual goes to a person. Extraction accuracy is measured against an answer key before go-live. |
| AI misreads a supplier name | Names are matched to the approved supplier list, tolerating small spelling differences. |
| Duplicate invoice paid twice | Supplier + invoice number is checked against every invoice already logged, and within the same batch. |
| Someone else changes invoice data through the dashboard | The dashboard reaches the data only through two n8n webhooks that reject any request without the secret token; every decision records who made it and when. |
| Workflow stops (e.g. the computer is off) | For production, run n8n on a small cloud server or use n8n Cloud, so emails are processed 24/7. |
| Data privacy | Invoice text is sent to the AI provider; check its data-retention terms and the client's GDPR obligations before go-live. |

## 6. Next steps for a real deployment

1. Measure the client's current volume and time per invoice to estimate savings.
2. Run in parallel with the manual process for 2–4 weeks and compare results.
3. Move n8n to an always-on server.
4. Add a weekly summary email (invoices processed, amounts due, pending approvals).
