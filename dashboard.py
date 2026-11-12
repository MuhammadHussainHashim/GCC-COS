"""Run from the repository root: python -m streamlit run dashboard.py"""
import json
import pandas as pd
import streamlit as st
from gcc_cos.storage import connect, records, review
from gcc_cos.ingest import load_registry
from gcc_cos.export import frame, excel_bytes
from gcc_cos.query import select
from gcc_cos.model import is_product, is_item
from gcc_cos.audit import build_audit
from gcc_cos import hs

st.set_page_config(page_title="GCC-COS", layout="wide")
st.title("Green Carbon Corridor — Carbon Data Collection")
st.caption("Quality checks do not verify a footprint. Annual inventories are not product factors.")
db = connect("data/carbon.sqlite")
try:
    hs_table, hs_source = hs.load_table()
    hs_mappings = hs.load_mappings(table=hs_table)
    rows = hs.annotate(records(db), hs_mappings, hs_table, hs_source)
    filters = {}
    filters['products_only'] = st.checkbox("Products only", value=False)
    filters['search'] = st.text_input("Search products, manufacturers, materials, EPD IDs or HS code")
    for label, key, field in [("Category", "category", "category"), ("Manufacturer", "manufacturer", "manufacturer"),
                              ("Geography", "geography", "geography"), ("Review status", "status", "review_status"),
                              ("Source-reported verification status", "verification_status", "verification_status")]:
        values = sorted({str(r[field]) for r in rows if r.get(field)})
        filters[key] = st.selectbox(label, [None] + values, format_func=lambda v: "All" if v is None else v)
    filters['warnings_only'] = st.checkbox("Only records with validation warnings", value=False)
    warnings = sorted({issue for row in rows for issue in row.get('issues', [])})
    filters['warning'] = st.selectbox("Validation warning", [None] + warnings, format_func=lambda v: 'All warnings' if v is None else v)
    selected = select(rows, **filters)
    tabs = st.tabs(["Records", "Sources", "Review queue", "Documents", "Exports", "Quality and verification", "Human evidence review", "HS codes", "Calculator", "Reference data"])
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
                                             'verification_status','hs_code','hs_description','hs_status','hs_basis','hs_reference_edition','issues','evidence']})
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
    with tabs[7]:
        st.subheader("HS codes (edition: " + hs_source["edition"] + ")")
        products = [r for r in rows if is_item(r)]
        summary = hs.coverage(products)
        unverified = summary["by_status"].get("proposed_not_verified", 0)
        if unverified:
            st.warning(f"NOT VERIFIED: {unverified} of {summary['records']} product records use a proposed HS mapping that no customs authority or reviewer has confirmed. Replace each one in config/hs_mappings.json once it is verified.")
        st.caption(f"{summary['by_status'].get('exact_rule', 0)} records carry an HS code given by their source. {summary['by_status'].get('unmapped', 0)} product records have no HS code. A 4-digit code means only the heading is known, not the 6-digit subheading.")
        table = pd.DataFrame(summary["codes"])
        if not table.empty:
            table["hs_status"] = table["hs_status"].map(hs.LABELS)
            st.dataframe(table, use_container_width=True, hide_index=True)
        st.subheader("Product-type mappings")
        st.dataframe(pd.DataFrame([{"category": m["match"].get("category"), "subcategory": m["match"].get("subcategory"),
                                    "product_name": m["match"].get("product_name"), "hs_code": m["hs_code"],
                                    "status": hs.LABELS[m["status"]], "basis": m["basis"]} for m in hs_mappings]).astype(str),
                     use_container_width=True, hide_index=True)
        st.subheader("Look up an HS code")
        query = st.text_input("Type a code (for example 8471) or words (for example smartphones)", key="hs_lookup")
        if query:
            found = hs.lookup(query, hs_table)
            st.dataframe(pd.DataFrame([{k: c[k] for k in ("code", "level", "description")} for c in found]), use_container_width=True, hide_index=True)
            if not found:
                st.info("No HS 2022 code matches.")
        st.caption("Source: " + hs_source["attribution"] + " License: " + hs_source["license"] + ". " + hs_source["limitations"])
    with tabs[8]:
        from gcc_cos import calculator
        import io
        st.subheader("Footprint calculator")
        st.warning("NOT VERIFIED: every footprint is the figure its publisher reported, and every HS code link is a proposed mapping. Use the results as estimates only. Transport of the goods is not included.")
        products = calculator.prepare(rows)
        basket = st.session_state.setdefault("calculator_basket", [])
        mode = st.radio("How do you want to enter products?", ["Pick products one by one", "Upload a CSV basket"], horizontal=True)
        if mode == "Pick products one by one":
            calculator_reference = calculator.reference_from(db)
            find_by = st.radio("What do you want to add?", ["Product type", "Specific product", "HS code", "Travel, heating or digital use", "Home electricity"], horizontal=True)
            with st.form("calculator_add", clear_on_submit=True):
                if find_by == "Product type":
                    kind, value = "type", st.selectbox("Product type", sorted({str(r["subcategory"]) for r in products if r.get("subcategory")}, key=str.casefold))
                elif find_by == "Specific product":
                    choices = {f"{r['id']}: {r.get('manufacturer') or ''} - {r.get('product_name') or ''}": str(r["id"]) for r in products}
                    kind, value = "record", choices.get(st.selectbox("Product (type to search)", list(choices)))
                elif find_by == "Travel, heating or digital use":
                    activities = {f"{a['geography']} | {a['area']}: {a['name_en']} (per {a['unit_metric'].split(' per ', 1)[-1]})": a["activity_id"] for a in calculator_reference["activity"].values()}
                    kind, value = "activity", activities.get(st.selectbox("Activity (the list starts with the country the factor is for; the quantity is in the unit shown)", sorted(activities))) if activities else None
                elif find_by == "Home electricity":
                    countries = {f"{c['country']} ({float(c['value_metric']):.3f} kg CO2e per kWh, {c['year']})": c["iso3"] for c in calculator_reference["electricity"].values()}
                    names = sorted(countries)
                    kind, value = "electricity", countries.get(st.selectbox("Country (the quantity is in kWh)", names, index=next((i for i, n in enumerate(names) if n.startswith("Pakistan")), 0))) if countries else None
                else:
                    kind, value = "hs", st.text_input("HS code, 4 or 6 digits (for example 847130)")
                quantity = st.number_input("Quantity", min_value=0.0, value=1.0, step=1.0)
                if st.form_submit_button("Add to basket"):
                    if value and quantity > 0:
                        basket.append({"kind": kind, "value": str(value), "quantity": str(quantity)})
                    else:
                        st.error("Choose a product and a quantity greater than zero.")
            if basket and st.button("Clear basket"):
                basket.clear()
                st.rerun()
            lines = list(basket)
        else:
            st.caption("The CSV needs a quantity column and one of record_id, hs_code or product_type in each row. See examples/calculator/company-basket.csv.")
            uploaded = st.file_uploader("Basket CSV", type=["csv"])
            lines = []
            if uploaded is not None:
                import tempfile
                from pathlib import Path
                with tempfile.TemporaryDirectory() as temporary:
                    staged = Path(temporary) / "basket.csv"
                    staged.write_bytes(uploaded.getvalue())
                    try:
                        lines = calculator.read_basket(staged)
                    except (ValueError, UnicodeDecodeError) as exc:
                        st.error(str(exc))
        people = st.number_input("People sharing this footprint (staff or household); leave 0 to skip", min_value=0, value=0, step=1)
        if lines:
            result = calculator.calculate(products, lines, hs_table, people=people or None, reference=calculator.reference_from(db))
            if len(result["totals"]) > 1:
                st.metric("All parts together (rough indication only)", f"{float(result['all_parts_together_kg_co2e']):,.1f} kg CO2e", help="The parts are measured in different ways, so this sum is only a rough guide.")
            for total in result["totals"]:
                st.metric(f"Total, {total['scope']}", f"{float(total['total_kg_co2e']):,.1f} kg CO2e",
                          help=f"Lowest {float(total['total_lowest']):,.1f} and highest {float(total['total_highest']):,.1f} kg CO2e, from the lowest and highest source record for each line.")
                st.caption(f"Range {float(total['total_lowest']):,.1f} to {float(total['total_highest']):,.1f} kg CO2e across {total['lines']} lines. NOT VERIFIED.")
                facts = [f"Biggest line: line {total['biggest_line']}, {total['biggest_line_share_percent']}% of this total."]
                if total["use_phase_kg_co2e"] is not None:
                    facts.append(f"Use phase {float(total['use_phase_kg_co2e']):,.1f} kg CO2e; making, transport and end of life {float(total['making_and_other_kg_co2e']):,.1f} kg CO2e.")
                if total["per_year_kg_co2e"] is not None:
                    facts.append(f"Per year of use: {float(total['per_year_kg_co2e']):,.1f} kg CO2e, using the lifetimes the sources assumed.")
                if total["per_person_kg_co2e"] is not None:
                    facts.append(f"Per person: {float(total['per_person_kg_co2e']):,.1f} kg CO2e.")
                st.write(" ".join(facts))
                chart = pd.DataFrame([{"line": f"{r['line']}: {r['label'] or r['query']}", "kg CO2e": float(r["total_kg_co2e"])} for r in result["lines"] if r["status"] == "ok" and r["scope"] == total["scope"]])
                st.bar_chart(chart, x="line", y="kg CO2e", horizontal=True)
            for warning in result["warnings"]:
                (st.error if warning.startswith("INCOMPLETE") else st.warning if warning.startswith("NOT VERIFIED") else st.info)(warning)
            table = pd.DataFrame(calculator.flat_lines(result), columns=calculator.LINE_COLUMNS)
            st.dataframe(table.astype(str).replace({"None": ""}), use_container_width=True, hide_index=True,
                         column_config={"report_url": st.column_config.LinkColumn("Publisher report (not checked)")})
            st.download_button("Download result CSV", table.to_csv(index=False).encode("utf-8-sig"), "gcc-footprint-result.csv", "text/csv")
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                table.to_excel(writer, index=False, sheet_name="Lines")
                pd.DataFrame(result["totals"]).to_excel(writer, index=False, sheet_name="Totals")
                pd.DataFrame({"Read this first": result["warnings"]}).to_excel(writer, index=False, sheet_name="Warnings")
            st.download_button("Download result Excel", buffer.getvalue(), "gcc-footprint-result.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("Add a product or upload a basket to see a total.")
    with tabs[9]:
        from gcc_cos import refdata
        st.subheader("Reference data")
        st.caption("These tables hold other kinds of numbers than product footprints: regulatory default values, activity factors, country averages and published assumptions. They are kept apart on purpose and are not added to product footprints.")
        reference_counts = refdata.counts(db)
        if not any(reference_counts.values()):
            st.info("No reference data is loaded yet. Run: python -m gcc_cos load-reference-data")
        else:
            st.dataframe(pd.DataFrame(refdata.rows(db, "reference_datasets")).astype(str), use_container_width=True, hide_index=True)
            chosen_table = st.selectbox("Table", [t for t, n in reference_counts.items() if n],
                                        format_func=lambda t: f"{refdata.TABLES[t][3]} ({reference_counts[t]:,} rows)")
            st.dataframe(pd.DataFrame(refdata.rows(db, chosen_table)), use_container_width=True, hide_index=True)
finally:
    db.close()
