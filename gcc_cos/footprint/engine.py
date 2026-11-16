"""The household footprint calculation.

Rules (each one is tested):
- A line is calculated only when exactly one published factor matches its activity, unit,
  geography, reporting year and lifecycle boundary, and the factor's dataset is approved
  for this calculation (or the product passed human evidence review).
- Another country's or another year's factor is used only when the person explicitly allows
  it, and the line is then labelled as a stand-in (proxy).
- Two or more matching rows are reported as a duplicate and not used.
- Lines that cannot be calculated are listed with the reason; the result is never presented
  as a complete footprint.
"""
from decimal import Decimal, InvalidOperation

from . import catalog
from .repository import great_circle_km

STATUS_TEXT = {
    "calculated": "Calculated",
    "invalid_input": "The entry is not valid",
    "unit_mismatch": "No published factor in this unit",
    "missing_factor": "No published factor for this activity",
    "duplicate_factor": "More than one published factor matches, so none was used",
    "geography_mismatch": "The published factor is for another country",
    "year_mismatch": "The published factor is for another year",
    "boundary_mismatch": "The published factor covers a different lifecycle boundary",
    "not_approved": "The data has not been approved for this calculator yet",
}
NOT_COMPLETE = ("This covers only the activities entered. Other parts of a full footprint, such as clothing and other shopping, "
                "services, public spending and anything you skipped, are not included.")


def _d(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def _num(value, places=3):
    return float(round(value, places)) if value is not None else None


class Calculation:
    def __init__(self, repo, request):
        self.repo = repo
        self.request = request
        household = request["household"]
        self.country = str(household["country"]).upper()
        self.year = str(household["year"])
        self.people = household.get("people")
        proxies = request.get("proxies") or {}
        self.allow_geo = bool(proxies.get("other_geography"))
        self.allow_year = bool(proxies.get("other_year"))
        self.approvals = repo.approvals()
        self.verified = repo.verified_record_ids()
        self.datasets = repo.datasets()

    # ---- one line --------------------------------------------------------------------------------
    def line(self, item, number):
        out = {"line": number, "id": item.get("id") or f"line-{number}", "activity": item.get("activity"), "options": item.get("options") or {},
               "input": {k: item.get(k) for k in ("quantity", "unit", "period", "food_code", "record_id", "from_airport", "to_airport", "trips", "return_trip") if item.get(k) is not None},
               "status": None, "message": "", "kg_co2e": None, "flags": [], "factor": None, "proxy": {"geography": False, "year": False}}
        activity = catalog.ACTIVITIES.get(item.get("activity"))
        if activity is None:
            return self._fail(out, "invalid_input", f"Unknown activity {item.get('activity')!r}.")
        out["category"] = activity["category"]
        out["label"] = activity["label"]
        selector = activity["selector"]
        unit = item.get("unit")
        if unit not in selector["units"]:
            return self._fail(out, "unit_mismatch", f"{activity['label']} can be entered in: {', '.join(selector['units'])}. '{unit}' has no published factor here.")
        quantity = self._annual_quantity(item, out)
        if quantity is None:
            return out
        out["annual_quantity"] = _num(quantity, 4)
        out["annual_unit"] = unit
        factor = self._factor(item, activity, out)
        if factor is None:
            return out
        if not self._checks(factor, out):
            return out
        value = _d(factor["value"])
        kg = quantity * value
        out.update(status="calculated", message=STATUS_TEXT["calculated"], kg_co2e=_num(kg), factor=factor)
        if value == 0:
            out["flags"].append("zero_factor")
            if item.get("activity") == "car":
                out["message"] = "Calculated. The published direct (Scope 1) factor is 0 for a battery electric car; charging is counted under home electricity."
        return out

    def _fail(self, out, status, message, factor=None):
        out.update(status=status, message=message or STATUS_TEXT[status], kg_co2e=None)
        if factor is not None:
            out["factor"] = factor
        return out

    def _annual_quantity(self, item, out):
        if item.get("activity") == "flight" and (item.get("from_airport") or item.get("to_airport")):
            a, b = self.repo.airport(item.get("from_airport") or ""), self.repo.airport(item.get("to_airport") or "")
            if len(a) != 1 or len(b) != 1:
                self._fail(out, "invalid_input", "Both airports must be valid IATA codes from the airport list.")
                return None
            trips = _d(item.get("trips") or 1)
            if trips is None or trips <= 0:
                self._fail(out, "invalid_input", "The number of trips must be greater than zero.")
                return None
            distance = Decimal(str(round(great_circle_km(a[0], b[0]), 3)))
            legs = 2 if item.get("return_trip") else 1
            out["distance"] = {"from": a[0]["iata_code"], "to": b[0]["iata_code"], "great_circle_km": float(distance), "legs_per_trip": legs, "trips": float(trips),
                               "note": "Great-circle distance between the two airports; no allowance for indirect routing is added."}
            if item.get("unit") != "passenger-km":
                self._fail(out, "unit_mismatch", "Flights calculated from airports are in passenger-km.")
                return None
            return distance * legs * trips
        quantity = _d(item.get("quantity"))
        if quantity is None or quantity < 0:
            self._fail(out, "invalid_input", "Enter a number of zero or more.")
            return None
        period = item.get("period") or "year"
        if period not in catalog.PERIODS:
            self._fail(out, "invalid_input", f"The period must be one of: {', '.join(catalog.PERIODS)}.")
            return None
        out["period"] = period
        return quantity * catalog.PERIODS[period]

    def _dataset_info(self, dataset_id):
        d = self.datasets.get(dataset_id) or {}
        return {"dataset_id": dataset_id, "source_title": d.get("title"), "publisher": d.get("publisher"), "license": d.get("license"),
                "source_url": d.get("url"), "verification_status": d.get("verification_status")}

    def _factor(self, item, activity, out):
        selector = activity["selector"]
        source = selector["source"]
        unit = item.get("unit")
        if source == "activity_factors":
            options = item.get("options") or {}
            for key, allowed in activity["options"].items():
                if options.get(key) not in allowed:
                    self._fail(out, "invalid_input", f"Choose a {key}: {', '.join(allowed)}.")
                    return None
            name = selector["name"].format(**{k: options[k] for k in activity["options"]})
            row_unit, use_metric = selector["units"][unit], False
            if ">" in row_unit:
                row_unit, use_metric = row_unit.split(">")[0], True
            rows = self.repo.activity_factors(selector["dataset_id"], selector["area"], name, f"kg CO2e per {row_unit}", selector["scope"])
            if not rows:
                others = self.repo.activity_candidates(selector["area"], name)
                if any(r["note"] != selector["scope"] for r in others):
                    self._fail(out, "boundary_mismatch", f"A factor for '{name}' exists, but only for {', '.join(sorted({r['note'] for r in others}))}; this calculator needs {selector['scope']}.")
                elif others:
                    self._fail(out, "unit_mismatch", f"A factor for '{name}' exists, but only per {', '.join(sorted({r['unit_original'].replace('kg CO2e per ', '') for r in others}))}.")
                else:
                    self._fail(out, "missing_factor", f"The published data has no factor for '{name}'.")
                return None
            if len(rows) > 1:
                self._fail(out, "duplicate_factor", f"{len(rows)} published rows match '{name}' per {row_unit}: {', '.join(r['activity_id'] for r in rows)}. None was used.")
                return None
            row = rows[0]
            if use_metric and row["unit_metric"] != f"kg CO2e per {unit}":
                self._fail(out, "unit_mismatch", f"The published row is per {row_unit} and has no per-{unit} value.")
                return None
            return {**self._dataset_info(row["dataset_id"]), "factor_id": row["activity_id"], "name": name,
                    "value": row["value_metric"] if use_metric else row["value_original"],
                    "unit": row["unit_metric"] if use_metric else row["unit_original"],
                    "value_original": row["value_original"], "unit_original": row["unit_original"],
                    "geography": row["geography"], "iso3": catalog.GEOGRAPHY_ISO3.get(row["geography"]), "year": row["year"],
                    "boundary": selector["boundary"], "scope": row["note"], "page": row.get("source_page")}
        if source == "country_electricity":
            rows = self.repo.electricity(self.country)
            if not rows:
                self._fail(out, "missing_factor", f"No electricity figure is held for {self.country}.")
                return None
            if len(rows) > 1:
                self._fail(out, "duplicate_factor", f"{len(rows)} electricity figures are held for {self.country}. None was used.")
                return None
            row = rows[0]
            return {**self._dataset_info(row["dataset_id"]), "factor_id": f"{row['dataset_id']}:{row['iso3']}:electricity_carbon_intensity",
                    "name": f"Electricity generation, {row['country']}", "value": row["value_metric"], "unit": row["unit_metric"],
                    "value_original": row["value_original"], "unit_original": row["unit_original"], "geography": row["country"], "iso3": row["iso3"],
                    "year": row["year"], "boundary": selector["boundary"], "original_source": row.get("original_source")}
        if source == "product_averages":
            rows = self.repo.food(str(item.get("food_code") or ""))
            if not rows:
                self._fail(out, "missing_factor", "Choose a food from the list.")
                return None
            if len(rows) > 1:
                self._fail(out, "duplicate_factor", f"{len(rows)} food rows share this code. None was used.")
                return None
            row = rows[0]
            out["label"] = row["name_en"]
            return {**self._dataset_info(row["dataset_id"]), "factor_id": f"{row['dataset_id']}:{row['product_code']}", "name": row["name_en"],
                    "name_original": row["name_original"], "value": row["value_metric"], "unit": row["unit_metric"],
                    "value_original": row["value_original"], "unit_original": row["unit_original"], "geography": row["geography"],
                    "iso3": catalog.GEOGRAPHY_ISO3.get(row["geography"]), "year": row["year"], "boundary": selector["boundary"],
                    "data_quality_rating": row.get("data_quality_rating"), "subgroup": row.get("subgroup_original")}
        if source == "records":
            try:
                record_id = int(item.get("record_id"))
            except (TypeError, ValueError):
                self._fail(out, "invalid_input", "Choose the exact product from the list.")
                return None
            rows = self.repo.product(record_id)
            if len(rows) != 1:
                self._fail(out, "missing_factor", "No product record has this id.")
                return None
            r = rows[0]
            out["label"] = f"{r.get('manufacturer')} {r.get('product_name')}".strip()
            declared = str(r.get("declared_unit") or "")
            wanted = selector["units"][unit]
            if declared != wanted or _d(r.get("normalized_value")) is None:
                self._fail(out, "unit_mismatch", f"This product's published footprint is per {declared or 'an unstated unit'}, not per {wanted}.")
                return None
            module = r.get("lifecycle_module")
            if module:
                self._fail(out, "boundary_mismatch", f"This record covers only lifecycle module {module} (production stage), not the whole product lifecycle, so it is not combined with the other results.",
                           {"factor_id": f"record:{record_id}", "dataset_id": r.get("source_id")})
                return None
            return {**self._dataset_info(r.get("source_id")), "source_title": r.get("document_title"), "license": r.get("license"), "source_url": r.get("source_url"),
                    "factor_id": f"record:{record_id}", "record_id": record_id, "name": out["label"], "manufacturer": r.get("manufacturer"),
                    "model_and_variant": r.get("product_name"), "value": r.get("normalized_value"), "unit": r.get("normalized_unit"),
                    "value_original": r.get("original_value"), "unit_original": r.get("original_unit"),
                    "geography": r.get("geography"), "iso3": None, "year": r.get("year"), "boundary": r.get("lifecycle_scope"),
                    "publisher_report": r.get("primary_source_url"), "verification_status": r.get("verification_status"),
                    "source_limitations": r.get("source_limitations")}
        self._fail(out, "invalid_input", "This activity is not available.")
        return None

    def _checks(self, factor, out):
        product = factor["factor_id"].startswith("record:")
        if not product:
            if factor.get("iso3") != self.country:
                if not self.allow_geo:
                    self._fail(out, "geography_mismatch",
                               f"The only published factor is for {factor['geography']}, not your country ({self.country}). Allow other countries' factors to use it as a labelled stand-in.", factor)
                    return False
                out["proxy"]["geography"] = True
                out["flags"].append("other_country_factor")
            if str(factor.get("year")) != self.year:
                if not self.allow_year:
                    self._fail(out, "year_mismatch",
                               f"The published factor is for {factor['year']}, not your reporting year {self.year}. Allow other years' factors to use it as a labelled stand-in.", factor)
                    return False
                out["proxy"]["year"] = True
                out["flags"].append("other_year_factor")
        else:
            out["flags"].append("product_use_location_" + str(factor.get("geography") or "not_stated"))
        approval = self.approvals.get(factor.get("dataset_id"))
        if product and factor.get("record_id") in self.verified:
            factor["approval"] = {"level": "independently_reviewed", "text": "Passed GCC human evidence review against the publisher's document."}
        elif approval:
            factor["approval"] = {"level": approval["level"], "approver": approval["approver"], "approved_at": approval["approved_at"], "note": approval["note"],
                                  "text": f"Approved for estimation by {approval['approver']} on {approval['approved_at'][:10]}. Source-reported value, not independently verified."}
        else:
            self._fail(out, "not_approved", f"Dataset '{factor.get('dataset_id')}' has not been approved for this calculator. "
                                            f"An administrator can approve it with: python -m gcc_cos calculator-approve {factor.get('dataset_id')} --approver \"Name\" --note \"What was checked\"", factor)
            return False
        return True

    # ---- whole request ---------------------------------------------------------------------------
    def run(self):
        lines = [self.line(item, n) for n, item in enumerate(self.request.get("lines") or [], start=1)]
        done = [l for l in lines if l["status"] == "calculated"]
        skipped = set(self.request.get("skipped") or [])
        categories = []
        for key, label in catalog.CATEGORIES.items():
            own = [l for l in lines if l.get("category") == key]
            ok = [l for l in own if l["status"] == "calculated"]
            if not own:
                status = "skipped" if key in skipped else "not_answered"
            elif len(ok) == len(own):
                status = "calculated"
            else:
                status = "partial" if ok else "not_calculated"
            categories.append({"category": key, "label": label, "status": status, "lines": len(own), "calculated_lines": len(ok),
                               "kg_co2e": _num(sum((_d(l["kg_co2e"]) for l in ok), Decimal(0))) if ok else None})
        total = sum((_d(l["kg_co2e"]) for l in done), Decimal(0))
        groups = {}
        for l in done:
            g = groups.setdefault(l["factor"]["boundary"], Decimal(0))
            groups[l["factor"]["boundary"]] = g + _d(l["kg_co2e"])
        people = _d(self.people) if self.people else None
        problems = [l for l in lines if l["status"] != "calculated"]
        proxies = [l for l in done if l["proxy"]["geography"] or l["proxy"]["year"]]
        complete_entries = bool(lines) and not problems and all(c["status"] in ("calculated", "skipped") for c in categories)
        notices = [NOT_COMPLETE]
        if problems:
            notices.append(f"{len(problems)} of {len(lines)} entries could not be calculated and are not in the total. See the reason on each.")
        if any(c["status"] == "skipped" for c in categories):
            notices.append("Skipped sections are not in the total: " + ", ".join(c["label"] for c in categories if c["status"] == "skipped") + ".")
        if any(c["status"] == "not_answered" for c in categories):
            notices.append("Sections with no entries are not in the total: " + ", ".join(c["label"] for c in categories if c["status"] == "not_answered") + ".")
        if proxies:
            notices.append(f"{len(proxies)} entries use another country's or another year's published factor because you allowed it. They are labelled as stand-ins.")
        if len(groups) > 1:
            notices.append("The entries use factors with different lifecycle boundaries (listed under 'By boundary'). The total adds them up as an indication only.")
        result = {
            "calculator": "GCC household carbon footprint calculator", "api_version": "1",
            "household": {"country": self.country, "year": self.year, "people": self.people},
            "lines": lines, "categories": categories,
            "totals": {"covered_kg_co2e": _num(total), "covered_t_co2e": _num(total / 1000, 4),
                       "per_person_kg_co2e": _num(total / people) if people else None,
                       "per_person_t_co2e": _num(total / people / 1000, 4) if people else None,
                       "by_boundary": [{"boundary": b, "kg_co2e": _num(v)} for b, v in groups.items()]},
            "coverage": {"entries": len(lines), "calculated": len(done), "not_calculated": len(problems), "stand_ins": len(proxies),
                         "all_entries_calculated": complete_entries, "is_complete_footprint": False, "statement": NOT_COMPLETE},
            "notices": notices,
            "comparison": self._comparison(total, people),
            "recommendations": self._recommendations(done),
            "evidence": self._evidence(done),
        }
        return result

    def _comparison(self, total, people):
        row = self.repo.country_ghg(self.country)
        if not row or total <= 0:
            return None
        per_person = total / people if people else total
        return {"country": row["country"], "year": row["year"], "ghg_per_person_t": float(_d(row["value_original"])), "unit": row["unit_original"],
                "source": row["original_source"], "dataset_id": row["dataset_id"], "your_covered_t_per_person": _num(per_person / 1000, 4),
                "note": "All greenhouse gases from all sources in the country, divided by population. Your figure covers only the entries above."}

    def _evidence(self, done):
        seen = {}
        for l in done:
            f = l["factor"]
            key = f.get("dataset_id")
            entry = seen.setdefault(key, {"dataset_id": key, "title": f.get("source_title"), "publisher": f.get("publisher"), "license": f.get("license"),
                                          "url": f.get("source_url"), "verification_status": f.get("verification_status"),
                                          "approval": f.get("approval", {}).get("text"), "factors_used": set(), "publisher_reports": set()})
            entry["factors_used"].add(f["factor_id"])
            if f.get("publisher_report"):
                entry["publisher_reports"].add(f["publisher_report"])
        return [{**e, "factors_used": sorted(e["factors_used"]), "publisher_reports": sorted(e["publisher_reports"])} for e in seen.values()]

    def _recommendations(self, done):
        tips = []
        for l in done:
            f, qty, kg = l["factor"], _d(l.get("annual_quantity")), _d(l["kg_co2e"])
            activity = l["activity"]
            if activity == "car" and kg > 0:
                selector = catalog.ACTIVITIES["car"]["selector"]
                unit = selector["units"][l["input"]["unit"]]
                best = None
                for fuel in catalog.CAR_FUELS:
                    # Electric and plug-in cars are left out: their direct factor does not include charging electricity.
                    if fuel in (l["options"].get("fuel"), "Unknown", "Battery Electric Vehicle", "Plug-in Hybrid Electric Vehicle"):
                        continue
                    rows = self.repo.activity_factors(selector["dataset_id"], selector["area"], selector["name"].format(size=l["options"]["size"], fuel=fuel), f"kg CO2e per {unit}", selector["scope"])
                    if len(rows) == 1 and _d(rows[0]["value_original"]) and _d(rows[0]["value_original"]) * qty < kg and (best is None or _d(rows[0]["value_original"]) < _d(best["value_original"])):
                        best = rows[0]
                if best:
                    saving = kg - _d(best["value_original"]) * qty
                    tips.append({"category": "transport", "title": f"A {l['options']['size'].lower()} {best['name_en'].split(' · ')[-1].lower()} car would emit less",
                                 "detail": f"For the same {l['annual_quantity']:,.0f} {l['input']['unit']} a year, the published direct factor for a {l['options']['size'].lower()} car drops from {f['value']} to {best['value_original']} {f['unit']}. Both are direct (tailpipe) factors from the same table.",
                                 "saving_kg_co2e": _num(saving), "basis": [f["factor_id"], best["activity_id"]]})
            if activity == "flight" and l["options"].get("cabin") not in ("Economy class", "Average passenger") and kg > 0:
                selector = catalog.ACTIVITIES["flight"]["selector"]
                rows = self.repo.activity_factors(selector["dataset_id"], selector["area"], selector["name"].format(haul=l["options"]["haul"], cabin="Economy class", rf=l["options"]["rf"]),
                                                  "kg CO2e per passenger.km", selector["scope"])
                if len(rows) == 1:
                    saving = kg - _d(rows[0]["value_original"]) * qty
                    tips.append({"category": "transport", "title": "Fly economy instead of " + l["options"]["cabin"].lower(),
                                 "detail": f"The published factor for economy on this route type is {rows[0]['value_original']} instead of {f['value']} kg CO2e per passenger-km.",
                                 "saving_kg_co2e": _num(saving), "basis": [f["factor_id"], rows[0]["activity_id"]]})
            if activity == "food" and kg > 0 and f.get("subgroup"):
                options = [r for r in self.repo.foods_in_subgroup(f["subgroup"]) if _d(r["value_metric"]) is not None and _d(r["value_metric"]) < _d(f["value"])]
                if options:
                    low = min(options, key=lambda r: _d(r["value_metric"]))
                    saving = kg - _d(low["value_metric"]) * qty
                    if saving > 0:
                        tips.append({"category": "food", "title": f"Swap some {f['name']} for {low['name_en']}",
                                     "detail": f"In the same AGRIBALYSE food group ({f['subgroup']}), {low['name_en']} is {low['value_metric']} kg CO2e per kg against {f['value']}. Replacing all of it would save the amount shown; the foods are not nutritionally equal.",
                                     "saving_kg_co2e": _num(saving), "basis": [f["factor_id"], f"{f['dataset_id']}:{low['product_code']}"]})
            if activity == "electricity" and kg > 0:
                tips.append({"category": "home", "title": "Every 10% less electricity",
                             "detail": f"At {f['value']} kg CO2e per kWh in {f['geography']}, using 10% fewer kWh than you entered saves the amount shown.",
                             "saving_kg_co2e": _num(kg / 10), "basis": [f["factor_id"]]})
        return sorted(tips, key=lambda t: -(t["saving_kg_co2e"] or 0))


def calculate(repo, request):
    return Calculation(repo, request).run()
