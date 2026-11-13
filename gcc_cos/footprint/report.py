"""Downloadable reports of a calculation: CSV (one row per entry), JSON (everything) and HTML (printable)."""
import csv
import html
import io
import json

COLUMNS = ["line", "category", "label", "status", "message", "annual_quantity", "annual_unit", "kg_co2e", "factor_id", "factor_value", "factor_unit",
           "factor_geography", "factor_year", "boundary", "stand_in_other_country", "stand_in_other_year", "dataset_id", "source_title", "publisher",
           "license", "source_url", "publisher_report", "approval"]


def _row(line):
    f = line.get("factor") or {}
    return {"line": line["line"], "category": line.get("category"), "label": line.get("label"), "status": line["status"], "message": line["message"],
            "annual_quantity": line.get("annual_quantity"), "annual_unit": line.get("annual_unit"), "kg_co2e": line.get("kg_co2e"),
            "factor_id": f.get("factor_id"), "factor_value": f.get("value"), "factor_unit": f.get("unit"), "factor_geography": f.get("geography"),
            "factor_year": f.get("year"), "boundary": f.get("boundary"), "stand_in_other_country": line["proxy"]["geography"],
            "stand_in_other_year": line["proxy"]["year"], "dataset_id": f.get("dataset_id"), "source_title": f.get("source_title"),
            "publisher": f.get("publisher"), "license": f.get("license"), "source_url": f.get("source_url"),
            "publisher_report": f.get("publisher_report"), "approval": (f.get("approval") or {}).get("text")}


def _safe(value):
    # Keep spreadsheet programs from running text as a formula.
    return "'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")) else value


def to_csv(result):
    buffer = io.StringIO()
    buffer.write("# GCC household carbon footprint report. " + result["coverage"]["statement"] + "\n")
    buffer.write(f"# Country {result['household']['country']}, reporting year {result['household']['year']}. "
                 f"Covered total {result['totals']['covered_kg_co2e']} kg CO2e from {result['coverage']['calculated']} of {result['coverage']['entries']} entries.\n")
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for line in result["lines"]:
        writer.writerow({k: _safe(v) for k, v in _row(line).items()})
    return buffer.getvalue()


def to_json(result):
    return json.dumps(result, indent=2, ensure_ascii=False)


def to_html(result):
    e = html.escape
    t = result["totals"]
    def line_row(line):
        factor = line.get("factor") or {}
        kg = "" if line.get("kg_co2e") is None else f"{line['kg_co2e']:,.2f}"
        return (f"<tr><td>{line['line']}</td><td>{e(str(line.get('label') or line.get('activity')))}</td><td>{e(line['status'].replace('_', ' '))}</td>"
                f"<td class=n>{kg}</td><td>{e(str(factor.get('geography') or ''))} {e(str(factor.get('year') or ''))}</td>"
                f"<td>{e(str(factor.get('boundary') or ''))}</td><td>{e(line['message'])}</td></tr>")
    rows = "".join(line_row(line) for line in result["lines"])
    evidence = "".join(f"<li><b>{e(str(x['title']))}</b>, {e(str(x['publisher']))}. Licence: {e(str(x['license']))}. "
                       f"<a href='{e(str(x['url']))}'>{e(str(x['url']))}</a>. {e(str(x['approval'] or ''))}</li>" for x in result["evidence"])
    notices = "".join(f"<li>{e(n)}</li>" for n in result["notices"])
    tips = "".join(f"<li><b>{e(r['title'])}</b>: {e(r['detail'])} About {r['saving_kg_co2e']:,.0f} kg CO2e a year.</li>" for r in result["recommendations"])
    per_person = f"<p>Per person: {t['per_person_kg_co2e']:,.0f} kg CO2e</p>" if t["per_person_kg_co2e"] is not None else ""
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>GCC footprint report</title>
<style>body{{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#16261d}}h1{{color:#1f5135}}
table{{border-collapse:collapse;width:100%;font-size:.85rem}}td,th{{border-bottom:1px solid #d5dfd8;padding:.4rem;text-align:left;vertical-align:top}}
.n{{text-align:right;font-variant-numeric:tabular-nums}}.warn{{background:#fff6e0;border:1px solid #e3b341;padding:.8rem;border-radius:6px}}</style>
<h1>GCC household carbon footprint report</h1>
<p>Country {e(result['household']['country'])} · reporting year {e(str(result['household']['year']))} · household of {e(str(result['household']['people'] or 'not stated'))}</p>
<div class="warn"><b>Not a complete footprint.</b><ul>{notices}</ul></div>
<h2>Covered total: {t['covered_kg_co2e']:,.0f} kg CO2e ({t['covered_t_co2e']:,.2f} t CO2e) a year</h2>{per_person}
<h2>Entries</h2><table><tr><th>#</th><th>Entry</th><th>Status</th><th class=n>kg CO2e a year</th><th>Factor place and year</th><th>Boundary</th><th>Note</th></tr>{rows}</table>
<h2>Ways to cut, from the same data</h2><ul>{tips or '<li>None could be worked out from the entries.</li>'}</ul>
<h2>Sources and licences</h2><ul>{evidence or '<li>No source was used.</li>'}</ul>
</html>"""
