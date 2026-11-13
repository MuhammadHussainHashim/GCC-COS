"""Versioned, read-only web API and the calculator's web page.

Run:  python -m gcc_cos.web --db data/carbon.sqlite
The API only reads the database. Approving data for the calculator is done with the
`calculator-approve` command, never through the web.
"""
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from ..footprint import catalog
from ..footprint.engine import calculate
from ..footprint.report import to_csv, to_html, to_json
from ..footprint.repository import Repository, connect_read_only

STATIC = Path(__file__).resolve().parent / "static"
DEFAULT_DB = os.environ.get("GCC_DB", "data/carbon.sqlite")
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; "
       "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


class Household(BaseModel):
    model_config = ConfigDict(extra="forbid")
    country: str = Field(pattern=r"^[A-Z]{3}$", description="ISO 3166 alpha-3 code, for example PAK")
    year: int = Field(ge=1990, le=2100)
    people: Optional[int] = Field(default=None, ge=1, le=50)


class Proxies(BaseModel):
    model_config = ConfigDict(extra="forbid")
    other_geography: bool = False
    other_year: bool = False


class Line(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Optional[str] = Field(default=None, max_length=64)
    activity: str = Field(max_length=32)
    options: Dict[str, str] = Field(default_factory=dict, max_length=5)
    quantity: Optional[float] = Field(default=None, ge=0, le=1e9)
    unit: str = Field(max_length=32)
    period: Literal["year", "month", "week", "day"] = "year"
    food_code: Optional[str] = Field(default=None, max_length=32)
    record_id: Optional[int] = Field(default=None, ge=1)
    from_airport: Optional[str] = Field(default=None, pattern=r"^[A-Za-z]{3}$")
    to_airport: Optional[str] = Field(default=None, pattern=r"^[A-Za-z]{3}$")
    trips: Optional[float] = Field(default=None, gt=0, le=1000)
    return_trip: bool = False


class CalculationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    household: Household
    proxies: Proxies = Field(default_factory=Proxies)
    skipped: List[Literal["home", "transport", "food", "products"]] = Field(default_factory=list, max_length=4)
    lines: List[Line] = Field(default_factory=list, max_length=200)


def create_app(db_path=None):
    db_path = Path(db_path or DEFAULT_DB)
    app = FastAPI(title="GCC Carbon Footprint Calculator API", version="1.0.0", docs_url="/api/v1/docs", openapi_url="/api/v1/openapi.json", redoc_url=None)

    @contextmanager
    def repository():
        try:
            db = connect_read_only(db_path)
        except FileNotFoundError:
            raise HTTPException(503, f"The GCC database was not found at {db_path}. Load the data first (see docs/CALCULATOR_APP.md).")
        try:
            yield Repository(db)
        finally:
            db.close()

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError):
        problems = [{"field": ".".join(str(p) for p in e["loc"][1:]), "problem": e["msg"]} for e in exc.errors()]
        return JSONResponse({"error": "The request is not valid.", "problems": problems}, status_code=422)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        return JSONResponse({"error": "Something went wrong on the server. Nothing was changed."}, status_code=500)

    @app.get("/api/v1/health")
    def health():
        if not db_path.is_file():
            return {"status": "no_database", "database": str(db_path)}
        with repository() as repo:
            return {"status": "ok", "database_read_only": True, "approved_datasets": sorted(repo.approvals()),
                    "tables": sorted(t for t in repo.tables if t in {"records", "activity_factors", "country_data", "product_averages", "airports"})}

    @app.get("/api/v1/catalog")
    def get_catalog():
        return {"categories": catalog.CATEGORIES, "periods": list(catalog.PERIODS), "activities": catalog.public_catalog()}

    @app.get("/api/v1/countries")
    def countries():
        with repository() as repo:
            return {"countries": repo.countries()}

    @app.get("/api/v1/data-status")
    def data_status(country: str = Query(pattern=r"^[A-Z]{3}$"), year: int = Query(ge=1990, le=2100)):
        """For each data source the calculator uses: its place, year and approval, compared with the household's."""
        with repository() as repo:
            approved = repo.approvals()
            out = []
            for key, activity in catalog.ACTIVITIES.items():
                sel = activity["selector"]
                if sel["source"] == "country_electricity":
                    rows = repo.electricity(country)
                    place, when, dataset = (rows[0]["country"], rows[0]["year"], rows[0]["dataset_id"]) if len(rows) == 1 else (None, None, "owid-country-data")
                    local = bool(rows)
                elif sel["source"] == "records":
                    place, when, dataset, local = "per product", "per product", "product records", True
                else:
                    dataset = sel["dataset_id"]
                    places = repo.dataset_places(sel["source"], dataset)
                    place = ", ".join(sorted({p for p, _ in places})) or None
                    when = ", ".join(sorted({str(y) for _, y in places})) or None
                    local = any(catalog.GEOGRAPHY_ISO3.get(p) == country for p, _ in places)
                out.append({"activity": key, "label": activity["label"], "dataset_id": dataset, "factor_place": place, "factor_year": when,
                            "same_place": local, "same_year": None if when in (None, "per product") else str(when) == str(year),
                            "approved": dataset in approved if dataset != "product records" else None})
            return {"country": country, "year": year, "activities": out}

    @app.get("/api/v1/foods")
    def foods(q: str = Query(default="", max_length=60), limit: int = Query(default=30, ge=1, le=100)):
        with repository() as repo:
            return {"foods": repo.search_foods(q, limit)}

    @app.get("/api/v1/products")
    def products(q: str = Query(default="", max_length=80), limit: int = Query(default=30, ge=1, le=100)):
        with repository() as repo:
            approved, verified = repo.approvals(), repo.verified_record_ids()
            out = []
            for r in repo.search_products(q, limit):
                out.append({"id": r["id"], "manufacturer": r.get("manufacturer"), "model_and_variant": r.get("product_name"), "type": r.get("subcategory"),
                            "value": r.get("normalized_value"), "unit": r.get("normalized_unit"), "declared_unit": r.get("declared_unit"),
                            "year": r.get("year"), "use_location": r.get("geography"), "lifecycle": r.get("lifecycle_scope"),
                            "lifecycle_module": r.get("lifecycle_module"), "publisher_report": r.get("primary_source_url"),
                            "status": "independently reviewed" if r["id"] in verified else ("approved for estimation" if r.get("source_id") in approved else "not approved")})
            return {"products": out}

    @app.get("/api/v1/airports")
    def airports(q: str = Query(default="", min_length=2, max_length=40)):
        with repository() as repo:
            return {"airports": repo.search_airports(q)}

    @app.post("/api/v1/calculate")
    def post_calculate(body: CalculationRequest):
        with repository() as repo:
            return calculate(repo, body.model_dump())

    @app.post("/api/v1/reports/{fmt}")
    def report(fmt: Literal["csv", "json", "html"], body: CalculationRequest):
        with repository() as repo:
            result = calculate(repo, body.model_dump())
        content, media = {"csv": (to_csv, "text/csv"), "json": (to_json, "application/json"), "html": (to_html, "text/html")}[fmt]
        name = f"gcc-footprint-{result['household']['country']}-{result['household']['year']}.{fmt}"
        return Response(content(result), media_type=f"{media}; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{name}"'})

    if STATIC.is_dir():
        app.mount("/static", StaticFiles(directory=STATIC), name="static")

        @app.get("/", include_in_schema=False)
        def index():
            return FileResponse(STATIC / "index.html")

    return app
