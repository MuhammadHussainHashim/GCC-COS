"""Run from the repository root: python -m streamlit run dashboard.py"""
import json
import pandas as pd
import streamlit as st
from gcc_cos.storage import connect, records, review
from gcc_cos.ingest import load_registry
from gcc_cos.export import frame, excel_bytes
from gcc_cos.query import select
from gcc_cos.model import is_product
from gcc_cos.audit import build_audit

st.set_page_config(page_title="GCC-COS", layout="wide")
st.title("Green Carbon Corridor — Carbon Data Collection")
st.caption("Quality checks do not verify a footprint. Annual inventories are not product factors.")
db = connect("data/carbon.sqlite")
try:
    rows = records(db)
    filters = {}
    filters['products_only'] = st.checkbox("Products only", value=False)
    filters['search'] = st.text_input("Search products, manufacturers, materials, EPD IDs or HS6")
    for label, key, field in [("Category", "category", "category"), ("Manufacturer", "manufacturer", "manufacturer"),
                              ("Geography", "geography", "geography"), ("Review status", "status", "review_status"),
                              ("Source-reported verification status", "verification_status", "verification_status")]:
        values = sorted({str(r[field]) for r in rows if r.get(field)})
        filters[key] = st.selectbox(label, [None] + values, format_func=lambda v: "All" if v is None else v)
    filters['warnings_only'] = st.checkbox("Only records with validation warnings", value=False)
    warnings = sorted({issue for row in rows for issue in row.get('issues', [])})
    filters['warning'] = st.selectbox("Validation warning", [None] + warnings, format_func=lambda v: 'All warnings' if v is None else v)
    selected = select(rows, **filters)
    tabs = st.tabs(["Records", "Sources", "Review queue", "Documents", "Exports", "Quality and verification", "Human evidence review"])
    with tabs[0]:
        st.metric("Collected records", len(rows))
        st.metric("Product observations (all records)", sum(is_product(r) for r in rows))
        st.caption(f"Showing {len(selected)} records. Exports use exactly this selection. Multiple lifecycle modules can describe one product.")
        st.dataframe(frame(db, **filters), use_container_width=True,
                     column_config={"source_url": st.column_config.LinkColumn("Licensed dataset URL"),
                                    "primary_source_url": st.column_config.LinkColumn("Original publisher reference (not independently checked)"),
                                    "license_url": st.column_config.LinkColumn("Reuse terms")})
        if selected:
            chosen = st.selectbox("Inspect selected record", [r['id'] for r in selected],
                                  format_func=lambda rid: next(f"{r['id']}: {r.get('manufacturer') or ''} — {r.get('product_name') or ''}" for r in selected if r['id']==rid))
            record = next(r for r in selected if r['id']==chosen)
            st.json({k:record.get(k) for k in ['manufacturer','product_name','original_value','original_unit',
                                             'declared_quantity','declared_unit','lifecycle_scope','geography','geography_basis',
                                             'publication_date','year','primary_source_url','source_url','license','attribution',
                                             'verification_status','hs6','hs_evidence','hs_edition','issues','evidence']})
        st.warning("Manufacturer-reported PCFs and mirrored EPD review claims are not independent verification by GCC-COS. Read source limitations; do not compare different scopes or methods.")
    with tabs[1]:
        st.dataframe(pd.DataFrame(load_registry("config/sources.json")).astype(str))
        st.subheader("Actual ingestion history")
        st.dataframe(pd.read_sql_query("SELECT * FROM runs ORDER BY id DESC", db))
    with tabs[2]:
        queue = [r for r in rows if r["review_status"] in {"needs_review", "rejected"}]
        st.dataframe(pd.DataFrame(queue).astype(str))
        if queue:
            with st.form("review"):
                record_id = st.selectbox("Record", [r["id"] for r in queue])
                reviewer = st.text_input("Reviewer")
                decision = st.selectbox("Decision", ["accepted", "rejected"])
                note = st.text_area("Evidence and reasoning (required)")
                if st.form_submit_button("Save review"):
                    try:
                        review(db, record_id, reviewer, decision, note)
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
        st.caption("HS assignment changes require a cited exact-name mapping and reingestion; acceptance alone never assigns an HS code.")
    with tabs[3]:
        st.dataframe(pd.read_sql_query("SELECT * FROM documents", db))
    with tabs[4]:
        st.download_button("Download selected CSV", frame(db, **filters).to_csv(index=False).encode("utf-8-sig"), "gcc-cos.csv", "text/csv")
        try:
            st.download_button("Download selected Excel", excel_bytes(db, **filters), "gcc-cos.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except ValueError as exc:
            st.warning(str(exc))
    with tabs[5]:
        report = build_audit(db)
        st.json(report['summary'])
        st.caption("Pinned archive and license checks establish traceability to a published dataset, not independent verification against the publisher. Repeated names are not automatically merged.")
        columns=['id','manufacturer','product_name','publication_year','audit_verification_class','archive_status','audit_warnings']
        st.dataframe(pd.DataFrame(report['observations']).reindex(columns=columns).astype(str))
        st.dataframe(pd.DataFrame(report['sources']).astype(str))
        st.dataframe(pd.DataFrame(report['duplicates']).astype(str))
        st.dataframe(pd.DataFrame(report['coverage']).astype(str))
    with tabs[6]:
        from gcc_cos import verification as human
        from gcc_cos import review_batch
        from pathlib import Path
        import tempfile
        human.schema(db)
        st.subheader("Authorized human evidence review")
        st.caption("Legacy review acceptance is triage only. Automatic comparisons always await human approval. Operator-provisioned local reviewer accounts are required for evidence uploads and decisions.")
        product_map={r['id']:r for r in rows if is_product(r)}
        if product_map:
            review_id=st.selectbox("Product observation for human review",list(product_map),
                                   format_func=lambda i:f"{i}: {product_map[i].get('manufacturer')} — {product_map[i].get('product_name')}")
            record=product_map[review_id]
            if st.button("Prepare this review packet"):
                review_batch.single(db,review_id)
                st.rerun()
            packet=human.latest_packet(db,review_id)
            if packet:
                st.caption('Current human review state: '+human.review_state(db,review_id))
                if packet['record_digest']!=human.digest(record):st.warning('This packet is stale: attach evidence against the current record before approval.')
                st.json(packet)
                st.dataframe(pd.DataFrame.from_dict(packet.get('comparison',{}),orient='index').astype(str))
                evidence=packet.get('publisher_evidence') or {}
                if evidence.get('local_file') and Path(evidence['local_file']).is_file() and evidence.get('reuse_permitted') is True:
                    st.download_button("Inspect archived publisher evidence",Path(evidence['local_file']).read_bytes(),Path(evidence['local_file']).name)
                st.caption("Blank publisher fields are missing evidence. Imported dataset licensing does not establish permission to extract or redistribute original manufacturer documents.")
                with st.form("attach_primary_evidence",clear_on_submit=True):
                    uploader=st.file_uploader("Permitted original publisher PDF or JSON",type=['pdf','json'])
                    specification=st.text_area("Evidence extraction specification (exact fields and PDF quotes/page numbers or JSON field paths)",
                                               value=json.dumps(review_batch.evidence_template(record),indent=2,ensure_ascii=False),height=200)
                    uploader_name=st.text_input("Authorized reviewer for upload")
                    uploader_password=st.text_input("Reviewer password for upload",type='password')
                    if st.form_submit_button("Attach evidence for comparison — do not approve"):
                        try:
                            human.authenticate(db,uploader_name,uploader_password)
                            if uploader is None:raise ValueError('Select a permitted publisher document')
                            spec=json.loads(specification)
                            with tempfile.TemporaryDirectory() as temporary:
                                staged=Path(temporary)/'source';staged.write_bytes(uploader.getvalue())
                                human.attach_evidence(db,review_id,staged,spec)
                            st.rerun()
                        except (ValueError,OSError) as exc:st.error(str(exc))
                with st.form("human_decision",clear_on_submit=True):
                    username=st.text_input("Authorized reviewer username")
                    password=st.text_input("Reviewer password",type='password')
                    decision=st.selectbox("Human evidence decision",['rejected','approved'])
                    explanation=st.text_area("Decision explanation (required)")
                    attested=st.checkbox("I personally inspected the complete original evidence, checked every compared field, licensing and expiry (including absence of expiry)")
                    if st.form_submit_button("Record authenticated human decision"):
                        try:
                            human.decide(db,review_id,username,password,decision,explanation,attested)
                            st.rerun()
                        except ValueError as exc:st.error(str(exc))
                st.dataframe(pd.read_sql_query('SELECT record_id,reviewer,decision,explanation,decided_at FROM human_decisions WHERE record_id=? ORDER BY id DESC',db,params=[review_id]))
        qualified=human.verified_rows(db)
        st.caption(f"{len(qualified)} records currently qualify for human-approved verified-only export. Expired, rejected, stale and unsupported evidence is excluded dynamically.")
        st.download_button("Download human-approved verified-only Excel",excel_bytes(db,verified_only=True,**filters),'verified-only.xlsx',
                           'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
finally:
    db.close()
