"""What the household calculator can ask for, and exactly which published factor answers each question.

Every activity names the dataset, the section, the row name, the unit, the scope and the
geography it needs. A factor is used only when all of these match one row exactly.
Nothing here is a number: values always come from the database.
"""

UK = "United Kingdom"
DESNZ = "uk-desnz-conversion-factors-2026"
PERIODS = {"year": 1, "month": 12, "week": 52, "day": 365}
CATEGORIES = {
    "home": "Home energy",
    "transport": "Transport",
    "food": "Food",
    "products": "Products",
}

# Activity factor geography names -> ISO 3166 alpha-3 codes used for the household location.
GEOGRAPHY_ISO3 = {"United Kingdom": "GBR", "France": "FRA", "United States": "USA"}

CAR_SIZES = ["Small", "Medium", "Large", "Average"]
CAR_FUELS = ["Petrol", "Diesel", "Hybrid", "Plug-in Hybrid Electric Vehicle", "Battery Electric Vehicle", "LPG", "CNG", "Unknown"]
MOTORBIKE_SIZES = ["Small", "Medium", "Large", "Average"]
BUS_TYPES = ["Average local bus", "Local bus (not London)", "Local London bus", "Coach"]
RAIL_TYPES = ["National rail", "International rail", "Light rail and tram", "London Underground"]
FLIGHT_HAULS = ["Domestic, to/from UK", "Short-haul, to/from UK", "Long-haul, to/from UK", "International, to/from non-UK"]
FLIGHT_CLASSES = ["Average passenger", "Economy class", "Premium economy class", "Business class", "First class"]
FLIGHT_RF = ["With RF", "Without RF"]


def _desnz(area, scope, units, name):
    """A UK DESNZ selector. units maps the unit a person enters to the unit in the factor row."""
    return {"source": "activity_factors", "dataset_id": DESNZ, "area": area, "scope": scope, "units": units, "name": name,
            "boundary": f"UK GHG conversion factors 2026, {scope} (direct emissions; well-to-tank not included)"}


ACTIVITIES = {
    "electricity": {
        "category": "home", "label": "Electricity used at home", "options": {},
        "selector": {"source": "country_electricity", "units": {"kWh": "kWh"},
                     "boundary": "Lifecycle emissions of electricity generation, country average (Our World in Data, Ember)"},
        "help": "Add up the kWh on your electricity bills. Losses in the grid and your supplier's own mix are not included.",
    },
    "natural_gas": {
        "category": "home", "label": "Natural gas", "options": {},
        "selector": _desnz("Fuels", "Scope 1", {"cubic metres": "cubic metres", "kWh (gross CV)": "kWh (Gross CV)", "kWh (net CV)": "kWh (Net CV)"},
                           "Gaseous fuels · Natural gas"),
        "help": "Gas bills usually show cubic metres or kWh. Use the unit printed on the bill.",
    },
    "lpg": {
        "category": "home", "label": "LPG (cylinders or tank)", "options": {},
        # "kg" uses the per-tonne row's metric value (kg CO2e per kg), which the dataset stores beside the original.
        "selector": _desnz("Fuels", "Scope 1", {"litres": "litres", "kg": "tonnes>kg", "kWh (gross CV)": "kWh (Gross CV)"}, "Gaseous fuels · LPG"),
        "help": "A standard Pakistani domestic cylinder holds 11.8 kg of LPG.",
    },
    "car": {
        "category": "transport", "label": "Private car", "options": {"size": CAR_SIZES, "fuel": CAR_FUELS},
        "selector": _desnz("Passenger vehicles", "Scope 1", {"km": "km", "miles": "miles"}, "Cars (by size) · {size} car · {fuel}"),
        "help": "Distance driven by the car (vehicle-km), not per passenger. Battery electric cars show 0 here because charging belongs under home electricity.",
    },
    "motorbike": {
        "category": "transport", "label": "Motorbike", "options": {"size": MOTORBIKE_SIZES},
        "selector": _desnz("Passenger vehicles", "Scope 1", {"km": "km", "miles": "miles"}, "Motorbike · {size}"),
        "help": "Distance ridden.",
    },
    "bus": {
        "category": "transport", "label": "Bus or coach", "options": {"type": BUS_TYPES},
        "selector": _desnz("Business travel- land", "Scope 3", {"passenger-km": "passenger.km"}, "Bus · {type}"),
        "help": "Distance you travelled as a passenger.",
    },
    "rail": {
        "category": "transport", "label": "Train, tram or metro", "options": {"type": RAIL_TYPES},
        "selector": _desnz("Business travel- land", "Scope 3", {"passenger-km": "passenger.km"}, "Rail · {type}"),
        "help": "Distance you travelled as a passenger.",
    },
    "flight": {
        "category": "transport", "label": "Flights", "options": {"haul": FLIGHT_HAULS, "cabin": FLIGHT_CLASSES, "rf": FLIGHT_RF},
        "selector": _desnz("Business travel- air", "Scope 3", {"passenger-km": "passenger.km"}, "Flights · {haul} · {cabin} · {rf}"),
        "help": "Distance flown per passenger. 'With RF' includes the extra warming effect of emissions at altitude (radiative forcing).",
    },
    "food": {
        "category": "food", "label": "Food", "options": {},
        "selector": {"source": "product_averages", "dataset_id": "agribalyse-3.2-synthesis", "units": {"kg": "kg"},
                     "boundary": "Food from field to plate, average for France (AGRIBALYSE v3.2)"},
        "help": "Weight of the food as bought.",
    },
    "product": {
        "category": "products", "label": "Products you bought", "options": {},
        "selector": {"source": "records", "units": {"items": "item", "kg": "kg", "m2": "m2", "m3": "m3"},
                     "boundary": "Product footprint as published by the manufacturer"},
        "help": "Pick the exact manufacturer, model and variant.",
    },
}


def public_catalog():
    """The catalog without internal selector details, for the API."""
    out = {}
    for key, activity in ACTIVITIES.items():
        out[key] = {"category": activity["category"], "category_label": CATEGORIES[activity["category"]], "label": activity["label"],
                    "options": activity["options"], "units": list(activity["selector"]["units"]), "help": activity["help"],
                    "boundary": activity["selector"]["boundary"]}
    return out
