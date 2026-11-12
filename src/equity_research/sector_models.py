"""Explicit provisional operating-sector research models for the 100-company pilot.

This registry is intentionally SIC-exact, not a guessed SIC-range authorization.
Its thresholds are unvalidated research hypotheses. An entry authorizes only
attempting a score with all original SEC, market, legal, and risk gates satisfied.
Neither sector membership nor score is participation-index certification.
Banks, insurers, brokers, financing entities and REITs have no models here.
"""
from types import MappingProxyType

# Each family gets a separate model identifier and operating-profit hypothesis.
# All six score components still require exact, verified inputs.
FAMILY_CODES = {
    "digital_services_v1": ("7370", "7320", "7389", "7841", "7990"),
    "pharmaceuticals_biotech_v1": ("2834", "2836"),
    "healthcare_devices_v1": ("3823", "3829", "3842"),
    "industrial_instruments_v1": ("3827",),
    "consumer_products_v1": ("2080", "2111", "2840"),
    "retail_and_distribution_v1": ("5211", "5331", "5651", "5961"),
    "restaurants_v1": ("5812",),
    "oil_gas_refining_v1": ("1311", "2911"),
    "industrial_manufacturing_v1": ("3523", "3531", "3559", "3590", "3600", "3711", "3721", "3724", "3760"),
    "hardware_networks_v1": ("3570", "3572", "3576", "3577", "3663", "3678"),
    "transport_v1": ("4011",),
    "telecommunications_v1": ("4812", "4813"),
    "regulated_utilities_v1": ("4911",),
    "materials_mining_v1": ("1000", "2810"),
    "electronic_computers_v1": ("3571",),
    "semiconductors_v1": ("3674",),
    "prepackaged_software_v1": ("7372",),
}

# Annual operating income / exact annual contract revenue. Thresholds are
# provisional and deliberately distinct; no claims of historical predictive
# validity are attached to these screening hypotheses.
PROFIT_BANDS = {
    "digital_services_v1": ((".25", 15), (".15", 10), (".08", 5), ("0", 2)),
    "pharmaceuticals_biotech_v1": ((".25", 15), (".15", 10), (".05", 5), ("0", 2)),
    "healthcare_devices_v1": ((".22", 15), (".14", 10), (".07", 5), ("0", 2)),
    "industrial_instruments_v1": ((".20", 15), (".12", 10), (".06", 5), ("0", 2)),
    "consumer_products_v1": ((".22", 15), (".14", 10), (".07", 5), ("0", 2)),
    "retail_and_distribution_v1": ((".08", 15), (".05", 10), (".02", 5), ("0", 2)),
    "restaurants_v1": ((".18", 15), (".12", 10), (".05", 5), ("0", 2)),
    "oil_gas_refining_v1": ((".20", 15), (".12", 10), (".05", 5), ("0", 2)),
    "industrial_manufacturing_v1": ((".20", 15), (".10", 10), (".05", 5), ("0", 2)),
    "hardware_networks_v1": ((".20", 15), (".10", 10), (".05", 5), ("0", 2)),
    "transport_v1": ((".20", 15), (".12", 10), (".05", 5), ("0", 2)),
    "telecommunications_v1": ((".22", 15), (".12", 10), (".05", 5), ("0", 2)),
    "regulated_utilities_v1": ((".25", 15), (".15", 10), (".08", 5), ("0", 2)),
    "materials_mining_v1": ((".20", 15), (".10", 10), (".05", 5), ("0", 2)),
    "electronic_computers_v1": ((".20", 15), (".10", 10), (".05", 5), ("0", 2)),
    "semiconductors_v1": ((".20", 15), (".10", 10), (".05", 5), ("0", 2)),
    "prepackaged_software_v1": ((".30", 15), (".20", 10), (".10", 5), ("0", 2)),
}

def _build_models():
    from .sector_policy import excluded_banking_or_insurance
    models = {}
    assert FAMILY_CODES.keys() == PROFIT_BANDS.keys()
    for family, codes in FAMILY_CODES.items():
        for sic in codes:
            if sic in models or excluded_banking_or_insurance(sic) or sic == "6798":
                raise ValueError("unsafe or duplicate sector model SIC")
            models[sic] = family
    return MappingProxyType(models)

MODELS = _build_models()
