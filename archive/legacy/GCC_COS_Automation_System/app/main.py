import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from app.db import init_db, insert_record, query_records, get_stats, update_status, get_sources, add_source, audit_rows
from app.processing import read_tabular, map_columns, make_record, validate_hs, frame_for_export
from app.connectors import fetch_comtrade_preview

st.set_page_config(page_title="GCC COS Data Automation", page_icon="🌱", layout="wide")
init_db()

st.title("GCC Carbon Operating System")
st.caption("Data collection • HS-code decoding • Carbon-factor provenance • Human review")
st.warning("Prototype note: HS-code shape checks do not prove official validity; trade statistics are not carbon footprints; internal approval is not external verification or carbon-credit certification.")

stats = get_stats()
cols = st.columns(5)
for col, (label, value) in zip(cols, [
    ("Records", stats["total"]), ("Pending review", stats["pending"]),
    ("Approved", stats["approved"]), ("Rows with HS code", stats["hs"]),
    ("Rows with numeric factor", stats["factors"])
]):
    col.metric(label, value)

tabs = st.tabs(["Overview", "Import data", "UN Comtrade preview", "Review records", "Search & export", "Source registry", "Audit log", "Setup guide"])

with tabs[0]:
    st.subheader("System workflow")
    st.markdown("""
    1. **Collect**: import CSV/XLSX datasets or fetch limited trade statistics from UN Comtrade.
    2. **Decode**: map source columns, retain raw row data, normalize HS-code characters and expose likely issues.
    3. **Validate**: check code shape, numeric values, unit completeness and source provenance.
    4. **Review**: a human reviews uncertain or incomplete records before approval.
    5. **Store and export**: SQLite keeps structured records and audit history; export reviewed records to CSV.

    **Data boundaries:** product factors, activity factors, trade statistics, HS classifications, and project MRV observations are different record types and must not be confused.
    """)
    st.subheader("Starter source registry")
    st.dataframe(pd.DataFrame(get_sources()), use_container_width=True, hide_index=True)

with tabs[1]:
    st.subheader("Import a source file")
    upload = st.file_uploader("Choose CSV, TXT or Excel file", type=["csv","txt","xlsx","xls"], key="source_upload")
    if upload is not None:
        try:
            df = read_tabular(upload)
            st.write(f"Rows detected: **{len(df):,}** · Columns: **{len(df.columns)}**")
            st.dataframe(df.head(10), use_container_width=True)
            suggested = map_columns(df.columns)
            st.caption("Automatic column mapping is a suggestion. Confirm it before import.")
            options = ["(not mapped)"] + list(df.columns)
            chosen = {}
            targets = [
                ("product_name","Product / description"),("hs_code","HS code"),
                ("sector","Sector"),("country","Country / region"),
                ("footprint_value","Numeric factor / value"),("impact_unit","Impact unit (e.g. kg CO2e)"),
                ("functional_unit","Functional unit (e.g. per kg product)"),("boundary","Lifecycle boundary"),
                ("data_year","Data year"),("source_name","Source name"),("source_url","Source URL / DOI"),
                ("evidence_type","Evidence type"),("notes","Notes")
            ]
            with st.form("mapping_form"):
                for key, label in targets:
                    default = suggested.get(key)
                    default_idx = options.index(default) if default in options else 0
                    chosen[key] = st.selectbox(label, options, index=default_idx, key=f"map_{key}")
                submitted = st.form_submit_button("Import mapped rows into review queue")
            if submitted:
                mapping = {k:v for k,v in chosen.items() if v != "(not mapped)"}
                if not mapping.get("product_name") and not mapping.get("hs_code"):
                    st.error("Map at least a product description or HS code.")
                else:
                    count = 0
                    for _, row in df.iterrows():
                        rec = make_record(row.to_dict(), mapping, upload.name)
                        insert_record(rec)
                        count += 1
                    st.success(f"Imported {count:,} rows. Records are stored with review statuses; nothing was silently marked as verified.")
        except Exception as e:
            st.error(f"Could not read/import file: {e}")

with tabs[2]:
    st.subheader("UN Comtrade — limited API preview")
    st.info("This connector retrieves trade statistics with commodity codes and values. It does not supply carbon-footprint factors. Use the preview conservatively; API coverage and limits vary.")
    with st.form("comtrade_form"):
        reporter = st.text_input("Reporter M49 code", value="586", help="586 is commonly used for Pakistan; confirm API metadata.")
        period = st.text_input("Year", value="2023")
        flow = st.selectbox("Trade flow", ["X","M"], format_func=lambda x: "Exports (X)" if x=="X" else "Imports (M)")
        max_records = st.slider("Maximum preview records", min_value=10, max_value=500, value=100, step=10)
        fetch = st.form_submit_button("Fetch preview")
    if fetch:
        try:
            df, request_url = fetch_comtrade_preview(reporter, period, flow, max_records)
            st.caption("Request URL (no secret key shown): " + request_url)
            if df.empty:
                st.warning("No rows returned. Check API availability and parameters.")
            else:
                st.dataframe(df, use_container_width=True)
                st.download_button("Download preview CSV", df.to_csv(index=False).encode("utf-8"), file_name=f"comtrade_preview_{reporter}_{period}_{flow}.csv", mime="text/csv")
                st.markdown("**Next step:** map this trade dataset separately. Do not import trade values as carbon factors.")
        except Exception as e:
            st.error(f"API request failed: {e}")

with tabs[3]:
    st.subheader("Human review queue")
    review_status = st.selectbox("Filter status", ["All","pending","needs_source","needs_unit_review","approved","rejected"], key="review_filter")
    records = query_records(status=review_status, limit=2000)
    if not records:
        st.info("No records match this filter.")
    else:
        display = pd.DataFrame(records)
        show_cols = ["id","product_name","hs_code","sector","country","footprint_value","impact_unit","functional_unit","boundary","source_name","source_url","evidence_type","review_status","notes"]
        st.dataframe(display[[c for c in show_cols if c in display.columns]], use_container_width=True, hide_index=True)
        ids = [int(r["id"]) for r in records]
        selected = st.selectbox("Select record ID", ids)
        decision = st.selectbox("Review decision", ["approved","pending","needs_source","needs_unit_review","rejected"])
        review_note = st.text_input("Review note (required for rejection or approval explanation)")
        if st.button("Save review decision"):
            update_status(selected, decision, review_note)
            st.success(f"Saved review status for record {selected}.")
            st.rerun()

with tabs[4]:
    st.subheader("Search and export")
    search = st.text_input("Search product, HS code, source or sector")
    status = st.selectbox("Status to export", ["All","approved","pending","needs_source","needs_unit_review","rejected"], key="export_status")
    results = query_records(search=search, status=status, limit=10000)
    st.write(f"Matching records: {len(results):,}")
    if results:
        out = pd.DataFrame(results)
        st.dataframe(out.drop(columns=["raw_json"], errors="ignore").head(300), use_container_width=True)
        st.download_button("Export results to CSV", out.drop(columns=["raw_json"], errors="ignore").to_csv(index=False).encode("utf-8"), file_name="cos_records_export.csv", mime="text/csv")
    st.caption("Exports preserve source fields and review status. Review approved rows for intended use; approval is not third-party verification.")

with tabs[5]:
    st.subheader("Manage source registry")
    with st.form("source_form"):
        name = st.text_input("Source name")
        source_type = st.selectbox("Source type", ["API","download","dataset","methodology","classification","facility data","other"])
        url = st.text_input("Official URL")
        licence = st.text_input("Licence / terms notes")
        coverage = st.text_area("Coverage and limitations")
        add = st.form_submit_button("Add source")
    if add:
        if name.strip() and url.strip():
            add_source(name.strip(), source_type, url.strip(), licence.strip(), coverage.strip())
            st.success("Source added.")
            st.rerun()
        else:
            st.error("Source name and URL are required.")
    st.dataframe(pd.DataFrame(get_sources()), use_container_width=True, hide_index=True)

with tabs[6]:
    st.subheader("Audit history")
    audit = audit_rows()
    st.dataframe(pd.DataFrame(audit), use_container_width=True, hide_index=True) if audit else st.info("No audit events yet.")

with tabs[7]:
    st.subheader("First-run checklist")
    st.markdown("""
    - [ ] Back up the original HS6 workbook before import.
    - [ ] Inspect the workbook's guide/data dictionary and resolve factor/unit columns.
    - [ ] Import a small sample first and confirm the column mapping.
    - [ ] Add the original source URL and publication date for each dataset.
    - [ ] Review every record with missing units or source provenance.
    - [ ] Use an HS nomenclature edition and country extension appropriate to the use case.
    - [ ] Keep trade statistics separate from emissions factors.
    - [ ] Do not calculate carbon-credit revenue until net eligible removals and market assumptions are documented.
    - [ ] For production use, add user authentication, role permissions, scheduled jobs, backups and tests.
    """)
    st.markdown("**Windows command:** `streamlit run app/main.py`")
