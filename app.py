import io
import os
import re
import time

import pandas as pd
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")

PROMPT = """You are extracting data from an Indian business invoice.
Return only values that are visible in the document. If a field is missing, use null.
Dates must be in YYYY-MM-DD format. Amounts must be plain numbers without currency symbols or commas.
Extract every line item."""


class LineItem(BaseModel):
    description: str | None = None
    hsn_code: str | None = None
    quantity: float | None = None
    rate: float | None = None
    amount: float | None = None


class Invoice(BaseModel):
    vendor_name: str | None = None
    vendor_gstin: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    subtotal: float | None = None
    cgst: float | None = None
    sgst: float | None = None
    igst: float | None = None
    total: float | None = None
    line_items: list[LineItem] = []


def extract(client, data: bytes, mime: str) -> Invoice:
    resp = client.models.generate_content(
        model=MODEL,
        contents=[types.Part.from_bytes(data=data, mime_type=mime), PROMPT],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Invoice,
            temperature=0,
            thinking_config=types.ThinkingConfig(thinking_level="low"),
        ),
    )
    return resp.parsed if resp.parsed else Invoice.model_validate_json(resp.text)


def validate(inv: dict) -> list[str]:
    """Rule-based checks. This is where the product value is, not just OCR."""
    flags = []
    for f in ["vendor_name", "invoice_number", "invoice_date", "total"]:
        if not inv.get(f):
            flags.append(f"Missing: {f}")
    gstin = inv.get("vendor_gstin")
    if gstin and not GSTIN_RE.match(gstin.strip().upper()):
        flags.append("GSTIN format looks invalid")
    items = inv.get("line_items") or []
    item_sum = sum((i.get("amount") or 0) for i in items)
    sub = inv.get("subtotal")
    if sub is not None and items and abs(item_sum - sub) > 1:
        flags.append(f"Line items sum ({item_sum:.2f}) != subtotal ({sub:.2f})")
    tax = sum((inv.get(k) or 0) for k in ["cgst", "sgst", "igst"])
    total = inv.get("total")
    if sub is not None and total is not None and abs(sub + tax - total) > 1:
        flags.append(f"Subtotal + tax ({sub + tax:.2f}) != total ({total:.2f})")
    return flags


def to_excel(rows: list[dict]) -> bytes:
    inv_rows, item_rows = [], []
    for r in rows:
        inv_rows.append({k: v for k, v in r.items() if k != "line_items"})
        for it in r.get("line_items") or []:
            item_rows.append({"invoice_number": r.get("invoice_number"), **it})
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame(inv_rows).to_excel(w, sheet_name="Invoices", index=False)
        pd.DataFrame(item_rows).to_excel(w, sheet_name="Line items", index=False)
        for ws in w.book.worksheets:
            for col in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(width + 2, 60)
    return buf.getvalue()


st.set_page_config(page_title="Invoice AI", layout="wide")
st.title("Invoice AI: upload, verify, export")

api_key = os.getenv("GEMINI_API_KEY") or st.sidebar.text_input("Gemini API key", type="password")
if not api_key:
    st.info("Add your Gemini API key in the sidebar (or set GEMINI_API_KEY).")
    st.stop()
client = genai.Client(api_key=api_key)

files = st.file_uploader(
    "Upload invoices (PDF / JPG / PNG)", type=["pdf", "jpg", "jpeg", "png"], accept_multiple_files=True
)

if "results" not in st.session_state:
    st.session_state.results = {}

for f in files or []:
    key = f"{f.name}-{f.size}"
    if key not in st.session_state.results:
        with st.spinner(f"Reading {f.name}..."):
            try:
                t0 = time.time()
                inv = extract(client, f.getvalue(), f.type or "application/pdf")
                st.session_state.results[key] = {
                    "file": f.name,
                    "data": inv.model_dump(),
                    "secs": round(time.time() - t0, 1),
                }
            except Exception as e:
                st.error(f"{f.name}: extraction failed ({e})")

final_rows = []
for key, res in st.session_state.results.items():
    data = res["data"]
    flags = validate(data)
    with st.expander(f"{res['file']}  |  {res.get('secs', '?')}s  |  {'⚠️ ' + str(len(flags)) + ' flag(s)' if flags else '✅ looks consistent'}", expanded=bool(flags)):
        for fl in flags:
            st.warning(fl)
        header = {k: v for k, v in data.items() if k != "line_items"}
        edited = st.data_editor(pd.DataFrame([header]), key=f"h-{key}", use_container_width=True)
        items = st.data_editor(
            pd.DataFrame(data["line_items"] or [{}]), key=f"i-{key}", num_rows="dynamic", use_container_width=True
        )
        row = edited.iloc[0].where(edited.iloc[0].notna(), None).to_dict()
        row["line_items"] = items.dropna(how="all").where(items.notna(), None).to_dict("records")
        final_rows.append(row)

if final_rows:
    st.download_button(
        "Download Excel",
        to_excel(final_rows),
        file_name="invoices.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )