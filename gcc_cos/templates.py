"""Permission-gated templates support new categories without pretending records exist."""
CATEGORIES = ('cement','steel','aluminum','glass','vehicles','electronics','appliances','furniture','clothing')


def source_template(category):
    if category not in CATEGORIES:
        raise ValueError('Unsupported target category')
    return dict(id='configure-'+category, title=None, url=None, allowed_hosts=[],
                category=category, enabled=False, reuse_permitted=False,
                license=None, license_url=None, attribution=None, access_method='authorized_file_mapping',
                format='csv', adapter='mapped', connector_status='template_only_no_data_collected',
                columns={'manufacturer':'manufacturer', 'product_name':'model_or_variant',
                         'original_value':'footprint_value', 'original_unit':'footprint_unit',
                         'declared_quantity':'declared_quantity', 'declared_unit':'declared_unit',
                         'declared_unit_evidence':'declared_unit_evidence',
                         'lifecycle_scope':'lifecycle_boundary', 'geography':'country',
                         'publication_date':'publication_date', 'year':'reference_year',
                         'primary_source_url':'original_evidence_url', 'data_kind':'data_kind'},
                defaults={'category':category, 'entity_type':'product', 'methodology':None,
                          'verification_status':'not_independently_crosschecked',
                          'source_limitations':'Operator must establish reuse permission, product specificity and data kind; template is not source coverage'},
                notes='Choose published_product_footprint only for a genuine product report; generic emission factors must be labeled published_generic_factor. No values, sources, HS codes or permissions are supplied by this template.')
