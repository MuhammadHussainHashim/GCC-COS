import argparse
import json
from pathlib import Path
from .ingest import ingest, load_registry
from .storage import connect, review, revalidate
from .export import export, selected_rows
from .discovery import discover


def add_filters(parser):
    parser.add_argument('--products-only', action='store_true')
    parser.add_argument('--verified-only', action='store_true')
    parser.add_argument('--search', default='')
    parser.add_argument('--warnings-only', action='store_true')
    parser.add_argument('--warning')
    parser.add_argument('--hs6', '--hs', dest='hs6', help='HS code or prefix (2, 4 or 6 digits)')
    for field in ('category', 'manufacturer', 'geography', 'status', 'verification-status'):
        parser.add_argument('--' + field)


def get_filters(args):
    return {key: getattr(args, key) for key in
            ('verified_only', 'products_only', 'search', 'category', 'manufacturer', 'geography', 'status', 'verification_status', 'warnings_only', 'warning', 'hs6')}


def main(argv=None):
    parser = argparse.ArgumentParser(description="GCC-COS carbon evidence pipeline")
    parser.add_argument("--db", default="data/carbon.sqlite")
    parser.add_argument("--registry", default="config/sources.json")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("sources")
    sub.add_parser("revalidate")
    p = sub.add_parser("reviewer-add")
    p.add_argument("username")
    p = sub.add_parser("reviewer-disable")
    p.add_argument("username")
    p = sub.add_parser("review-prepare")
    p.add_argument("--batch", default="phase4")
    p.add_argument("--size", type=int, default=20)
    p.add_argument("--record", type=int)
    p = sub.add_parser("review-probe")
    p.add_argument("--batch", default="phase4")
    p = sub.add_parser("review-workbook")
    p.add_argument("output")
    p.add_argument("--batch", default="phase4")
    p.add_argument("--templates-dir", default="reports/phase4/templates")
    p = sub.add_parser("review-attach")
    p.add_argument("id",type=int)
    p.add_argument("document")
    p.add_argument("spec")
    p = sub.add_parser("human-review")
    p.add_argument("id",type=int)
    p.add_argument("--reviewer",required=True)
    p.add_argument("--decision",choices=['approved','rejected'],required=True)
    p.add_argument("--explanation",required=True)
    p.add_argument("--attest",action='store_true',help="I personally inspected the complete publisher evidence, including expiry/absence of expiry")
    p = sub.add_parser("source-template")
    from .templates import CATEGORIES
    p.add_argument("category", choices=CATEGORIES)
    p.add_argument("output")
    p = sub.add_parser("research-prepare", help="Quarantine a legacy product workbook for manual evidence review")
    p.add_argument("workbook")
    p.add_argument("--output-dir", default="exports/research-review")
    p = sub.add_parser("hs-lookup", help="Search the bundled HS 2022 code list by number or words")
    p.add_argument("query")
    for command, table, text in (
            ("load-reference-values", "reference_values", "Load reference values by CN/HS code (bundled: UK CBAM default values)"),
            ("load-activity-factors", "activity_factors", "Load emission factors by activity (bundled: ADEME transport, heating, digital use)"),
            ("load-country-data", "country_data", "Load country data (bundled: Our World in Data emissions per person and electricity)"),
            ("load-hs-codes", "hs_codes", "Load the HS 2022 code list into the database"),
            ("load-hs-industry-links", "hs_industry_links", "Load the HS-to-industry link (bundled: HS 6-digit to NAICS, 2017)"),
            ("load-benchmarks", "benchmarks", "Load published benchmarks and assumptions (bundled: US EPA calculator)"),
            ("load-spend-factors", "spend_factors", "Load spend-based factors per US dollar by industry (bundled: US EPA supply chain factors)"),
            ("load-airports", "airports", "Load airports with coordinates (bundled: OurAirports)")):
        p = sub.add_parser(command, help=text)
        p.set_defaults(reference_table=table)
        if table != "hs_codes":
            p.add_argument("--dataset", help="Folder with data.csv and SOURCE.json; the bundled dataset is used when left out")
    sub.add_parser("load-reference-data", help="Load every bundled reference dataset")
    sub.add_parser("reference-tables", help="Show how many rows each reference table holds")
    p = sub.add_parser("calculate", help="Total footprint for a basket of products and quantities")
    p.add_argument("basket", nargs="?", help="CSV with quantity and one of record_id, hs_code, product_type per row")
    p.add_argument("--item", action="append", default=[], metavar="KIND=VALUE:QUANTITY",
                   help="One line without a file, for example hs=847130:10, type=Smartphone:2, record=15:1, activity=busthermique:120 (km) or electricity=PAK:300 (kWh). Repeat for more lines.")
    p.add_argument("--people", help="Number of people (staff or household) for a per-person figure")
    p.add_argument("--output", help="Save the full result as .json, .csv or .xlsx")
    sub.add_parser("hs-coverage", help="Show how many product records have an HS code, and how reliable it is")
    p = sub.add_parser("audit")
    p.add_argument("--output-dir", default="reports/phase3")
    p.add_argument("--workbook", default=None)
    p = sub.add_parser("discover")
    p.add_argument("--source", required=True)
    p.add_argument("--output", default="data/discovered-candidates.json")
    p = sub.add_parser("ingest")
    p.add_argument("--source", default="all")
    local = p.add_mutually_exclusive_group()
    local.add_argument("--file", help="Import an authorized local document using this source mapping")
    local.add_argument("--manifest", help="JSON mapping of source IDs to authorized local files; no network requests")
    p.add_argument("--hs-rules", default="config/hs_rules.json")
    p = sub.add_parser("records")
    p.add_argument("--review-only", action="store_true")
    add_filters(p)
    p = sub.add_parser("export")
    p.add_argument("output")
    add_filters(p)
    p = sub.add_parser("review")
    p.add_argument("id", type=int)
    p.add_argument("--reviewer", required=True)
    p.add_argument("--decision", choices=["accepted", "rejected"], required=True)
    p.add_argument("--note", required=True)
    args = parser.parse_args(argv)
    if args.command == "research-prepare":
        from .research import prepare_research
        try:
            print(json.dumps(prepare_research(args.workbook, args.output_dir), ensure_ascii=False))
        except (ValueError, FileNotFoundError) as exc:
            parser.error(str(exc))
        return 0
    if args.command == "hs-lookup":
        from .hs import load_table, lookup
        for code in lookup(args.query, load_table()[0]):
            print(json.dumps({k: code[k] for k in ("code", "level", "description")}, ensure_ascii=False))
        return 0
    db = connect(args.db)
    try:
        if args.command in {"load-reference-data", "reference-tables"} or getattr(args, "reference_table", None):
            from . import refdata
            try:
                if args.command == "reference-tables":
                    print(json.dumps(refdata.counts(db), indent=2))
                    return 0
                results = refdata.load_all(db) if args.command == "load-reference-data" else \
                    refdata.load_table_datasets(db, args.reference_table, getattr(args, "dataset", None))
            except (ValueError, OSError) as exc:
                parser.error(str(exc))
            for result in results:
                print(json.dumps(result))
            return 0
        if args.command == "calculate":
            from . import calculator
            from .storage import records
            try:
                lines = calculator.read_basket(args.basket) if args.basket else []
                for item in args.item:
                    kind, _, rest = item.partition("=")
                    value, _, quantity = rest.rpartition(":")
                    if kind not in calculator.KINDS or not value or not quantity:
                        raise ValueError(f"Cannot read --item {item!r}; write it like hs=847130:10")
                    lines.append({"kind": kind, "value": value, "quantity": quantity})
                if not lines:
                    raise ValueError("Give a basket CSV or at least one --item")
                result = calculator.calculate(records(db), lines, people=args.people, reference=calculator.reference_from(db))
                if args.output:
                    calculator.write_result(result, args.output)
            except (ValueError, OSError) as exc:
                parser.error(str(exc))
            for r in result["lines"]:
                if r["status"] == "ok":
                    print(f"{r['line']:>3}  {r['quantity']} {r['quantity_unit']} x {float(r['per_unit']):,.4g} {r['unit']} = {float(r['total_kg_co2e']):,.1f} kg CO2e"
                          f"  ({r['share_of_total_percent']}% of total)  [{r['kind']} {r['query']}: {r['label']}; {r['basis']}]")
                    if r["versus_same_maker_percent"] is not None:
                        print(f"       {float(r['versus_same_maker_percent']):+.1f}% against the median of {r['same_maker_records']} records of this type from the same manufacturer")
                else:
                    print(f"{r['line']:>3}  NO VALUE  [{r['kind']} {r['query']}] {r['message']}")
            for t in result["totals"]:
                print(f"TOTAL {t['scope']}: {float(t['total_kg_co2e']):,.1f} kg CO2e (lowest {float(t['total_lowest']):,.1f}, highest {float(t['total_highest']):,.1f}; {t['lines']} lines)")
                print(f"  Biggest line: {t['biggest_line']} ({t['biggest_line_share_percent']}% of this total)")
                if t["use_phase_kg_co2e"] is not None:
                    print(f"  Use phase {float(t['use_phase_kg_co2e']):,.1f} kg CO2e; making, transport and end of life {float(t['making_and_other_kg_co2e']):,.1f} kg CO2e")
                if t["per_year_kg_co2e"] is not None:
                    print(f"  Per year of use: {float(t['per_year_kg_co2e']):,.1f} kg CO2e (using the lifetimes the sources assumed)")
                if t["per_person_kg_co2e"] is not None:
                    print(f"  Per person: {float(t['per_person_kg_co2e']):,.1f} kg CO2e")
            if len(result["totals"]) > 1:
                print(f"ALL PARTS TOGETHER: {float(result['all_parts_together_kg_co2e']):,.1f} kg CO2e (rough indication only: the parts are measured in different ways)")
            for warning in result["warnings"]:
                print("! " + warning)
            return 0 if result["complete"] else 2
        if args.command == "hs-coverage":
            from .hs import annotate, coverage
            from .model import is_item
            from .storage import records
            print(json.dumps(coverage(annotate([r for r in records(db) if is_item(r)])), indent=2, ensure_ascii=False))
            return 0
        if args.command in {'reviewer-add','reviewer-disable','review-prepare','review-probe','review-workbook','review-attach','human-review'}:
            from . import verification as verification
            from . import review_batch
            import getpass
            if args.command == 'reviewer-add':
                password=getpass.getpass('New reviewer password (12+ characters): ')
                if password!=getpass.getpass('Confirm password: '):parser.error('Passwords differ')
                verification.add_reviewer(db,args.username,password)
                print('Reviewer provisioned by local operator; no records approved')
            elif args.command == 'reviewer-disable':
                with db: db.execute('UPDATE reviewers SET enabled=0 WHERE username=?',(args.username,))
                print('Reviewer disabled; their approvals no longer qualify for verified-only exports')
            elif args.command == 'review-prepare':
                print(json.dumps({'packet_id':review_batch.single(db,args.record),'automatic_approvals':0} if args.record else {'record_ids':review_batch.prepare(db,args.batch,args.size),'automatic_approvals':0}))
            elif args.command == 'review-probe':
                print(json.dumps(review_batch.probe(db,args.batch)))
            elif args.command == 'review-workbook':
                print(json.dumps(review_batch.workbook(db,args.batch,args.output,args.templates_dir)))
            elif args.command == 'review-attach':
                spec=json.loads(Path(args.spec).read_text(encoding='utf-8'))
                print(json.dumps({'packet_id':verification.attach_evidence(db,args.id,args.document,spec),'status':'awaiting_human_approval'}))
            elif args.command == 'human-review':
                print(json.dumps({'decision_id':verification.decide(db,args.id,args.reviewer,getpass.getpass('Reviewer password: '),args.decision,args.explanation,args.attest)}))
        elif args.command == "source-template":
            from .templates import source_template
            target = Path(args.output)
            if target.exists():
                parser.error("Refusing to overwrite an existing source configuration")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps([source_template(args.category)], indent=2)+"\n", encoding="utf-8")
            print("Disabled template saved; configure real source metadata and documented permissions before use")
        elif args.command == "audit":
            from .audit import write_audit
            print(json.dumps(write_audit(db, args.registry, args.output_dir, args.workbook)))
        elif args.command == "revalidate":
            print(json.dumps(revalidate(db)))
        elif args.command == "sources":
            sources = load_registry(args.registry)
            for s in sources:
                run = db.execute("SELECT status,started_at,detail FROM runs WHERE source_id=? ORDER BY id DESC LIMIT 1", (s["id"],)).fetchone()
                print(json.dumps({**s, "latest_run": run}, ensure_ascii=False))
        elif args.command == "discover":
            selected = [s for s in load_registry(args.registry) if s["id"] == args.source]
            if not selected:
                parser.error("Unknown source")
            try:
                found = discover(selected[0], Path(args.db).parent / "raw")
            except (ValueError, OSError) as exc:
                parser.error(str(exc))
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(json.dumps(found, indent=2), encoding="utf-8")
            print(f"Discovered {len(found)} candidates; permission and mapping review required")
        elif args.command == "ingest":
            selected = [s for s in load_registry(args.registry) if args.source == "all" or s["id"] == args.source]
            manifest = None
            if args.manifest:
                manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
                known = {s['id'] for s in load_registry(args.registry)}
                if not isinstance(manifest, dict) or not all(isinstance(v, str) for v in manifest.values()) or set(manifest) - known:
                    parser.error("Manifest must map known source IDs to file paths")
                selected = [s for s in selected if s['id'] in manifest]
            if not selected or (args.file and (len(selected) != 1 or args.source == "all")):
                parser.error("Select a known single source when importing a file")
            rules = json.loads(Path(args.hs_rules).read_text(encoding="utf-8"))
            results = [ingest(db, s, Path(args.db).parent / "raw", manifest[s["id"]] if manifest is not None else args.file, rules) for s in selected]
            for result in results:
                print(json.dumps(result))
            return int(any(r["status"] == "failed" for r in results))
        elif args.command == "records":
            for r in selected_rows(db, **get_filters(args)):
                if not args.review_only or r["review_status"] in {"needs_review", "rejected"}:
                    print(json.dumps(r, ensure_ascii=False))
        elif args.command == "review":
            review(db, args.id, args.reviewer, args.decision, args.note)
            print("Review saved; this does not certify the carbon value or change HS classification.")
        elif args.command == "export":
            print(f"Exported {export(db, args.output, **get_filters(args))} records to {args.output}")
    finally:
        db.close()
    return 0
