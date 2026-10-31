"""Product adapters. Reported footprints are never promoted to independent verification."""
from datetime import datetime, timezone
from decimal import Decimal
import re

GWP_TOTAL = {'6a37f984-a4b3-458a-a20a-64418c145fa2', '77e416eb-a363-4258-a04e-171d843a6460'}
ILCD_OPEN_LICENSE = 'Free of charge for all users and uses'


def text(values):
    if isinstance(values, dict):
        values = [values]
    values = values or []
    return next((v['value'] for v in values if v.get('lang') == 'en' and v.get('value')),
                next((v['value'] for v in values if v.get('value')), None))


def year_of(value):
    years = set(re.findall(r'\b(?:19|20)\d{2}\b', value or ''))
    return next(iter(years)) if len(years) == 1 else None


def boavizta(row, source):
    required = {'manufacturer', 'name', 'gwp_total', 'sources', 'report_date', 'use_location'}
    if not required.issubset(row):
        raise ValueError('Boavizta schema changed: required columns missing')
    return dict(
        product_name=row['name'], manufacturer=row['manufacturer'], entity_type='product',
        category='electronics', subcategory=row.get('subcategory'),
        original_value=row['gwp_total'], original_unit='kgCO2eq',
        declared_quantity='1', declared_unit='item',
        declared_unit_evidence=source['schema_url'] + '#data-format',
        geography=row['use_location'] or None, geography_basis='use phase location, not necessarily manufacturing',
        year=year_of(row['report_date']), publication_date=row['report_date'] or None,
        primary_source_url=row['sources'] or None,
        lifecycle_scope='Manufacturing, transportation, use phase and recycling; total product lifecycle as defined by Boavizta schema',
        methodology='Manufacturer-reported PCF transcribed by Boavizta; individual methodology not independently established',
        data_kind='published_product_footprint', verification_status='manufacturer_reported_not_independently_crosschecked',
        source_limitations='Boavizta warns against accurate impact assessments or comparisons across manufacturers. Source models, use assumptions and transcription require review.',
        lifetime_years=row.get('lifetime') or None,
        product_mass_kg=row.get('weight') or None,
        conversion_evidence={'mass_column': 'weight (kg)', 'schema_url': source['schema_url']} if row.get('weight') else None,
        representativeness='Manufacturer model/configuration and stated use assumptions; see original report',
    )


def check_ilcd_permission(doc):
    ownership = doc.get('administrativeInformation', {}).get('publicationAndOwnership', {})
    restrictions = [v.get('value', '').strip().lower() for v in ownership.get('accessRestrictions', [])]
    if ownership.get('licenseType') != ILCD_OPEN_LICENSE or not restrictions or any(v != 'none' for v in restrictions):
        raise ValueError('ILCD document does not explicitly permit all uses with no access restrictions')
    return ownership


def ilcd_records(doc, source):
    ownership = check_ilcd_permission(doc)
    info = doc['processInformation']
    identity = info['dataSetInformation']
    flows = [f for f in doc['exchanges']['exchange'] if f.get('referenceFlow') is True]
    if len(flows) != 1:
        raise ValueError('Exactly one reference product flow is required')
    flow = flows[0]
    props = [p for p in flow.get('flowProperties', []) if p.get('referenceFlowProperty') is True]
    if len(props) != 1 or not props[0].get('referenceUnit'):
        raise ValueError('Unambiguous declared quantity and unit required')
    prop = props[0]
    impacts = [r for r in doc['LCIAResults']['LCIAResult']
               if r['referenceToLCIAMethodDataSet'].get('refObjectId') in GWP_TOTAL]
    if len(impacts) != 1:
        raise ValueError('Exactly one supported GWP-total/GWP method required; fossil/biogenic components are never substituted')
    impact = impacts[0]
    entries = impact.get('other', {}).get('anies', [])
    unit_entries = [e for e in entries if e.get('name') == 'referenceToUnitGroupDataSet']
    if len(unit_entries) != 1:
        raise ValueError('Impact numerator unit missing or ambiguous')
    unit = text(unit_entries[0]['value'].get('shortDescription'))
    if unit not in {'kg CO2 eqv.', 'kg CO_(2)-Äq.', 'kg CO_(2) eqv.', 'kg CO2-Äqv.'}:
        raise ValueError('Unsupported GWP numerator unit')
    allowed_modules = source.get('modules', ['A1-A3'])
    module_values = [e for e in entries if e.get('module') in allowed_modules]
    if not module_values or any(e.get('scenario') for e in module_values):
        raise ValueError('No supported unambiguous module values found')
    if len({e['module'] for e in module_values}) != len(module_values):
        raise ValueError('Duplicate lifecycle modules are ambiguous')
    reviews = doc.get('modellingAndValidation', {}).get('validation', {}).get('review', [])
    independent = [r for r in reviews if r.get('type') in {'Independent external review', 'Accredited third party review'}
                   and r.get('referenceToNameOfReviewerAndInstitution')]
    time = info.get('time', {})
    dates = [e['value'] for e in time.get('other', {}).get('anies', [])
             if e.get('name') == 'publicationDateOfEPD' and isinstance(e.get('value'), (int, float))]
    publication_date = datetime.fromtimestamp(dates[0] / 1000, timezone.utc).date().isoformat() if len(dates) == 1 else None
    materials = flow.get('materialProperties', [])
    conversion = {}
    # Require explicit physical units. The ambiguous "conversion factor to 1 kg" field is never used.
    for key, name, expected_unit in [('density_kg_m3', 'gross density', 'kg/m^3'), ('areal_mass_kg_m2', 'grammage', 'kg/m^2')]:
        matches = [p for p in materials if p.get('name') == name and p.get('unit') == expected_unit]
        if len(matches) == 1:
            conversion[key] = str(matches[0]['value'])
    for module in module_values:
        yield dict(
            product_name=text(identity['name'].get('baseName')), manufacturer=text(ownership.get('referenceToOwnershipOfDataSet', {}).get('shortDescription')),
            category='construction', subcategory=source.get('subcategory'), material=source.get('material'), entity_type='product',
            epd_id=ownership.get('registrationNumber'), publication_date=publication_date,
            year=str(time.get('referenceYear')) if time.get('referenceYear') else None,
            valid_until_year=time.get('dataSetValidUntil'),
            primary_source_url=doc.get('source') or source.get('primary_source_url'),
            original_value=module['value'], original_unit=unit,
            declared_quantity=str(prop.get('meanValue')), declared_unit=prop['referenceUnit'],
            declared_unit_evidence={'reference_flow_id': flow.get('dataSetInternalID'), 'property': prop},
            lifecycle_scope=module['module'], lifecycle_module=module['module'],
            geography=info.get('geography', {}).get('locationOfOperationSupplyOrProduction', {}).get('location'),
            geography_basis='EPD location of operation/supply/production',
            methodology=text(impact['referenceToLCIAMethodDataSet'].get('shortDescription')),
            impact_method_id=impact['referenceToLCIAMethodDataSet'].get('refObjectId'),
            data_kind='published_product_footprint',
            verification_status='source_declared_third_party_review' if independent else 'review_metadata_incomplete',
            verification_evidence=independent or None,
            source_limitations='Collected from a pinned public ILCD mirror. Original publisher document and current validity have not been independently crosschecked. Lifecycle modules are not full-lifecycle totals.',
            representativeness=doc.get('modellingAndValidation', {}).get('LCIMethodAndAllocation', {}).get('other'),
            conversion_evidence={'material_properties': materials, 'reference_flow_property': prop},
            **conversion,
            evidence={'json_pointer': '/LCIAResults/LCIAResult', 'method_id': impact['referenceToLCIAMethodDataSet'].get('refObjectId'),
                      'module': module, 'ownership_and_license': ownership, 'reference_flow': flow,
                      'dataset_uuid': identity.get('UUID'), 'reviews': reviews},
        )
