"""Normalize only explicitly declared amounts and dimensioned physical inputs."""
from decimal import Decimal, InvalidOperation, localcontext

NUMERATOR_UNITS = {'kgCO2eq', 'kg CO2 eqv.', 'kg CO_(2)-Äq.', 'kg CO2e', 'kg CO_(2) eqv.', 'kg CO2-Äqv.'}
DENOMINATORS = {'kg': 'kg', 'm3': 'm3', 'm2': 'm2', 'qm': 'm2', 'item': 'item'}


def positive(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result > 0 else None
    except (InvalidOperation, ValueError):
        return None


def normalize_product(r, value, issues):
    factors = []
    if r.get('original_unit') not in NUMERATOR_UNITS:
        issues.append('unit_conversion_not_available')
        return factors
    quantity = positive(r.get('declared_quantity'))
    denominator = DENOMINATORS.get(r.get('declared_unit'))
    if quantity is None or denominator is None or not r.get('declared_unit_evidence'):
        issues.append('declared_unit_conversion_inputs_missing')
        return factors
    with localcontext() as context:
        context.prec = 28
        factor = value / quantity
        r['normalized_value'] = str(factor)
        r['normalized_unit'] = 'kg CO2e/' + denominator
        factors.append(dict(value=str(factor), unit=r['normalized_unit'], formula='original_value / declared_quantity',
                            inputs={'original_value': str(value), 'declared_quantity': str(quantity), 'declared_unit': r['declared_unit']},
                            evidence=r['declared_unit_evidence']))
        extra = None
        if denominator == 'item':
            extra = positive(r.get('product_mass_kg'))
        elif denominator == 'm3':
            extra = positive(r.get('density_kg_m3'))
        elif denominator == 'm2':
            extra = positive(r.get('areal_mass_kg_m2'))
        conflict = False
        properties = (r.get('conversion_evidence') or {}).get('material_properties', []) if isinstance(r.get('conversion_evidence'), dict) else []
        thicknesses = [positive(p.get('value')) for p in properties if p.get('name') == 'layer thickness' and p.get('unit') == 'm']
        density, areal = positive(r.get('density_kg_m3')), positive(r.get('areal_mass_kg_m2'))
        if len(thicknesses) == 1 and thicknesses[0] and density and areal:
            predicted = density * thicknesses[0]
            if abs(predicted - areal) / areal > Decimal('0.01'):
                issues.append('inconsistent_density_areal_mass_thickness')
                conflict = True
        if denominator != 'kg' and extra is not None and r.get('conversion_evidence') and not conflict:
            factors.append(dict(value=str(factor / extra), unit='kg CO2e/kg',
                                formula='(original_value / declared_quantity) / mass_per_declared_unit',
                                inputs={'original_value': str(value), 'declared_quantity': str(quantity), 'mass_per_declared_unit_kg': str(extra)},
                                evidence=r['conversion_evidence']))
    return factors
