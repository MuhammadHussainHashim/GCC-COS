"""Real attributed examples are in examples/phase2. All invented rows below are labeled SYNTHETIC."""
from decimal import Decimal
import copy
import json
from pathlib import Path
import sqlite3
import pandas as pd
import pytest
from gcc_cos.products import boavizta, ilcd_records
from gcc_cos.ingest import ingest, load_registry
from gcc_cos.model import validate, is_product, PRODUCT_FIELDS
from gcc_cos.storage import connect, records, insert
from gcc_cos.export import export, frame
from gcc_cos.query import select

ROOT = Path(__file__).resolve().parents[1]
SOURCES = load_registry(ROOT/'examples/phase2/sources.json')
FILES = json.loads((ROOT/'examples/phase2/local-files.json').read_text())

@pytest.fixture
def db(tmp_path):
    conn=connect(tmp_path/'products.sqlite')
    yield conn
    conn.close()


def synthetic_product(**kwargs):
    return dict(product_name='SYNTHETIC TEST DEVICE',manufacturer='SYNTHETIC TEST MAKER',entity_type='product',
                data_kind='published_product_footprint',original_value='100',original_unit='kgCO2eq',
                declared_quantity='1',declared_unit='item',declared_unit_evidence='SYNTHETIC TEST SCHEMA',**kwargs)


def epd(index=3):
    source=SOURCES[index]
    return json.loads((ROOT/FILES[source['id']]).read_text()),source


def test_all_real_product_snapshots(db,tmp_path):
    results=[ingest(db,s,tmp_path/'raw',ROOT/FILES[s['id']]) for s in SOURCES]
    assert all(r['status']=='completed' for r in results)
    assert results[0]['inserted']==1226
    assert sum(r['inserted'] for r in results[1:])==10
    rows=records(db)
    assert len(rows)==1236 and all(is_product(r) for r in rows)
    assert all(r['data_kind']=='published_product_footprint' for r in rows)
    assert all(r['hs6'] is None for r in rows)
    assert all('primary_document_not_independently_crosschecked' in r['issues'] for r in rows)
    assert all(r['original_value'] and r['source_url'] and r['license'] and r['manufacturer'] for r in rows)
    assert ingest(db,SOURCES[0],tmp_path/'raw',ROOT/FILES[SOURCES[0]['id']])['duplicates']==1226


def test_boa_preserves_original_report_and_partial_date():
    row=dict(manufacturer='SYNTHETIC',name='SYNTHETIC DEVICE',gwp_total='100',sources='https://example.org/test-report',
             report_date='November 2020',use_location='EU',subcategory='Smartphone',weight='',lifetime='3')
    r=validate(boavizta(row,SOURCES[0]))
    assert r['publication_date']=='November 2020' and r['year']=='2020'
    assert r['normalized_value']=='100' and r['normalized_unit']=='kg CO2e/item'
    assert r['verification_status']=='manufacturer_reported_not_independently_crosschecked'
    assert r['data_kind']!='verified_product_footprint'
    assert r['primary_source_url']==row['sources']
    assert len(r['normalized_factors'])==1


def test_missing_metadata_is_not_invented():
    row=dict(manufacturer='SYNTHETIC',name='SYNTHETIC',gwp_total='100',sources='',report_date='',use_location='')
    r=validate(boavizta(row,SOURCES[0]))
    assert r['year'] is None and r['geography'] is None and r['publication_date'] is None
    assert 'missing_publication_date' in r['issues'] and 'missing_primary_source_url' in r['issues']


def test_boa_schema_drift_rejected():
    with pytest.raises(ValueError,match='schema changed'):
        boavizta({'name':'SYNTHETIC'},SOURCES[0])


def test_real_area_factor_and_grammage():
    doc,source=epd()
    r=validate(next(ilcd_records(doc,source)))
    assert r['original_value']=='21.8'
    assert r['original_unit']=='kg CO_(2)-Äq.'
    assert r['declared_unit']=='qm' and r['normalized_unit']=='kg CO2e/m2'
    assert r['normalized_value']=='21.8'
    factors=r['normalized_factors']
    # Real source declares density 2.4 kg/m3, thickness .08m, but grammage 179 kg/m2.
    # Preserve the published per-area result; do not derive per-kg from contradictory metadata.
    assert len(factors)==1
    assert 'inconsistent_density_areal_mass_thickness' in r['issues']
    assert r['verification_status']=='source_declared_third_party_review'
    assert r['data_kind']=='published_product_footprint'
    assert r['publication_date']=='2021-11-11'


def test_real_density_factor_uses_dimensioned_input():
    doc,source=epd(2)  # Holcim concrete, volume reference flow
    r=validate(next(ilcd_records(doc,source)))
    assert r['normalized_unit']=='kg CO2e/m3'
    assert r['density_kg_m3']=='2297.0'
    assert Decimal(r['normalized_factors'][1]['value'])==Decimal(r['original_value'])/Decimal('2297.0')


def test_modules_kept_separate_never_sum_d_or_fossil():
    doc,source=epd(1)
    rows=list(ilcd_records(doc,source))
    assert [r['lifecycle_module'] for r in rows]==['A1','A2','A3']
    assert [r['original_value'] for r in rows]==['158.777466419796','10.820329223073','9.539741034189']
    assert all('D'!=r['lifecycle_module'] for r in rows)
    assert all(r['declared_quantity']=='1000.0' and r['declared_unit']=='kg' for r in rows)

@pytest.mark.parametrize('mutation', ['license','restrictions','method','quantity','duplicate'])
def test_ilcd_fail_closed(mutation):
    doc,source=epd()
    own=doc['administrativeInformation']['publicationAndOwnership']
    if mutation=='license': own.pop('licenseType')
    if mutation=='restrictions': own['accessRestrictions']=[dict(value='Restricted')]
    if mutation=='method': doc['LCIAResults']['LCIAResult']=[]
    if mutation=='quantity': doc['exchanges']['exchange'][0]['flowProperties'][0].pop('referenceUnit')
    if mutation=='duplicate':
        impact=doc['LCIAResults']['LCIAResult'][0]
        impact['other']['anies'].append(dict(value='999999',module='A1-A3')) # SYNTHETIC TEST corruption
    with pytest.raises(ValueError): list(ilcd_records(doc,source))

@pytest.mark.parametrize('quantity,unit',[(None,'item'),('0','kg'),('-1','kg'),('NaN','kg'),('1','unknown')])
def test_missing_conversion_inputs(quantity,unit):
    r=synthetic_product()
    r.update(declared_quantity=quantity,declared_unit=unit)
    r=validate(r)
    assert r['normalized_value'] is None


def test_mass_conversion_requires_evidence():
    r=validate(synthetic_product(product_mass_kg='2'))
    assert len(r['normalized_factors'])==1
    r=validate(synthetic_product(product_mass_kg='2',conversion_evidence='SYNTHETIC TEST dimensioned mass'))
    assert r['normalized_factors'][1]['value']=='50'


def test_legacy_record_fingerprint_does_not_change(db):
    # Simulate a stored Phase 1 record with none of the new optional fields.
    r=validate(dict(product_name='SYNTHETIC LEGACY',original_value='1',original_unit='kg CO2',data_kind='published_inventory',entity_type='industrial_inventory'))
    legacy={k:v for k,v in r.items() if k not in PRODUCT_FIELDS}
    with db:
        assert insert(db,legacy)==1
        assert insert(db,r)==0


def test_csv_excel_sqlite_roundtrip_and_product_filters(db,tmp_path):
    source=SOURCES[3]
    assert ingest(db,source,tmp_path/'raw',ROOT/FILES[source['id']])['inserted']==1
    with db: insert(db,validate(dict(product_name='SYNTHETIC INVENTORY',entity_type='industrial_inventory',data_kind='published_inventory',original_value='1',original_unit='kg CO2')))
    for extension in ['csv','xlsx','sqlite']:
        dest=tmp_path/('exported-products.'+extension)
        assert export(db,dest,products_only=True)==1
        if extension=='csv':
            df=pd.read_csv(dest,dtype=str)
        elif extension=='xlsx':
            df=pd.read_excel(dest,dtype=str)
            assert 'License notices' in pd.ExcelFile(dest).sheet_names
        else:
            with sqlite3.connect(dest) as backup:
                assert len(records(backup))==1
                assert backup.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
                assert backup.execute('PRAGMA foreign_key_check').fetchall()==[]
                assert backup.execute('SELECT count(*) FROM documents').fetchone()[0]==1
            continue
        assert df.iloc[0]['original_value']=='21.8'
        assert 'Rinn' in df.iloc[0]['manufacturer']
        assert df.iloc[0]['license']=='Free of charge for all users and uses'
    assert len(records(db))==2
    with pytest.raises(ValueError,match='active database'):
        export(db,db.execute('PRAGMA database_list').fetchone()[2])


def test_queries_do_not_mislabel_generic_factors():
    r=synthetic_product()
    generic=dict(r,data_kind='published_generic_factor')
    assert len(select([r,generic],products_only=True))==1
    assert select([r],search='test maker')==[r]
    assert not select([r],search='does-not-exist')


def test_product_dashboard_search(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    import gcc_cos.storage
    original=gcc_cos.storage.connect
    path=tmp_path/'dashboard.sqlite'
    with original(path) as conn:
        ingest(conn,SOURCES[3],tmp_path/'raw',ROOT/FILES[SOURCES[3]['id']])
    monkeypatch.setattr(gcc_cos.storage,'connect',lambda _: original(path))
    app=AppTest.from_file(str(ROOT/'dashboard.py')).run(timeout=30)
    assert not app.exception
    app.checkbox[0].check().run()
    app.text_input[0].input('Rinn').run()
    assert not app.exception
    assert any('Showing 1 records' in c.value for c in app.caption)
    app.text_input[0].input('not-a-real-product').run()
    assert any('Showing 0 records' in c.value for c in app.caption)


def test_consistent_area_conversion():
    r=synthetic_product(areal_mass_kg_m2='20',density_kg_m3='100',conversion_evidence={'material_properties':[{'name':'layer thickness','unit':'m','value':'0.2'}]})
    r.update(declared_unit='qm')
    r=validate(r)
    assert r['normalized_unit']=='kg CO2e/m2'
    assert r['normalized_factors'][1]['value']=='5'
    assert 'inconsistent_density_areal_mass_thickness' not in r['issues']


def test_invalid_number_cannot_be_accepted_after_rejection(db):
    from gcc_cos.storage import review
    with db: insert(db,validate(dict(original_value='SYNTHETIC INVALID')))
    review(db,1,'Test reviewer','rejected','SYNTHETIC TEST review')
    with pytest.raises(ValueError,match='Invalid numeric'):
        review(db,1,'Test reviewer','accepted','SYNTHETIC TEST bypass attempt')


def test_revalidation_refreshes_derived_values_and_keeps_audit(db):
    from gcc_cos.storage import revalidate, review
    r=validate(synthetic_product())
    # Simulate an earlier validator's stale result, not a production carbon factor.
    r['normalized_value']='999'  # SYNTHETIC TEST corruption
    with db: insert(db,r)
    assert revalidate(db)=={'checked':1,'changed':1}
    assert records(db)[0]['normalized_value']=='100'
    assert db.execute('SELECT count(*) FROM validation_history').fetchone()[0]==1
    review(db,1,'Test reviewer','accepted','SYNTHETIC TEST evidence')
    assert revalidate(db)=={'checked':1,'changed':0}
    assert records(db)[0]['review_status']=='manually_accepted'


def test_offline_manifest_cli(tmp_path,capsys):
    from gcc_cos.cli import main
    source=SOURCES[3]
    registry=tmp_path/'registry.json';registry.write_text(json.dumps([source]))
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps({source['id']:str(ROOT/FILES[source['id']])}))
    database=tmp_path/'offline.sqlite'
    assert main(['--db',str(database),'--registry',str(registry),'ingest','--manifest',str(manifest)])==0
    result=json.loads(capsys.readouterr().out)
    assert result['inserted']==1 and result['status']=='completed'
    with connect(database) as conn:
        assert len(records(conn))==1
