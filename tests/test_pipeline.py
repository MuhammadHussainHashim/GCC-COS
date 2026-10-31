import json
from pathlib import Path
import pandas as pd
import pytest
from gcc_cos.model import validate, classify
from gcc_cos.ingest import ingest
from gcc_cos.storage import connect, records, review
from gcc_cos.export import export
from gcc_cos.download import download

FIXTURE = Path(__file__).parent / 'fixtures/synthetic.csv'

@pytest.fixture
def source():
    return dict(id='SYNTHETIC-TEST-ONLY', title='Synthetic fixture, not real factors',
                url='https://example.org/synthetic.csv',license='Synthetic test permission',
                license_url='https://example.org/test-license',attribution='TEST ONLY',
                reuse_permitted=True,enabled=True,format='csv',adapter='mapped',
                columns={'product_name':'name','original_value':'value','original_unit':'unit',
                         'geography':'country','year':'year'},
                defaults={'entity_type':'material','methodology':'SYNTHETIC',
                          'lifecycle_scope':'SYNTHETIC','data_kind':'unverified_estimate'})

@pytest.fixture
def db(tmp_path):
    connection=connect(tmp_path/'test.sqlite')
    yield connection
    connection.close()


def test_end_to_end_dedup_export_review(db, source, tmp_path):
    result=ingest(db,source,tmp_path/'raw',FIXTURE)
    assert result['inserted']==2 and result['status']=='completed'
    assert ingest(db,source,tmp_path/'raw',FIXTURE)['duplicates']==2
    first,invalid=records(db)
    assert first['normalized_value']=='1.000'
    assert first['evidence']['raw']['value']=='1000'
    assert invalid['review_status']=='rejected'
    assert 'invalid_numeric_value' in invalid['issues']
    assert 'missing_geography' in invalid['issues']
    assert first['hs6'] is None
    assert 'hs_manual_review' in first['issues']
    assert export(db,tmp_path/'out.csv')==2
    assert export(db,tmp_path/'out.xlsx')==2
    assert len(pd.read_excel(tmp_path/'out.xlsx'))==2
    review(db,first['id'],'Test reviewer','accepted','Synthetic review evidence')
    assert records(db)[0]['review_status']=='manually_accepted'
    assert db.execute('SELECT count(*) FROM reviews').fetchone()[0]==1
    with pytest.raises(ValueError):
        review(db,invalid['id'],'Test','accepted','Not allowed')

@pytest.mark.parametrize('unit,value,expected',[
 ('kg CO2e/t','500','0.500'),('t CO2e/t','2','2'),('Mt CO2','1','1000000000'),
 ('kg CO2e/USD2022','1',None),('kg CO2/kg','1',None)])
def test_scientific_units(unit,value,expected):
    r=validate(dict(original_unit=unit,original_value=value))
    assert r['normalized_value']==expected

@pytest.mark.parametrize('value',['NaN','Infinity','abc',None])
def test_invalid_numbers(value):
    assert validate({'original_value':value})['review_status']=='rejected'


def test_verified_claim_requires_evidence():
    r=validate(dict(original_value='1',data_kind='verified_product_footprint'))
    assert 'missing_independent_verification_evidence' in r['issues']


def test_hs_no_guessing():
    rule=dict(name='SYNTHETIC CEMENT',hs6='252329',evidence='TEST cited tariff entry',edition='TEST edition')
    assert classify('SYNTHETIC CEMENT',[rule])['hs6']=='252329'
    assert classify('cement',[rule])['hs6'] is None
    assert classify('SYNTHETIC CEMENT',[rule,rule])['hs6'] is None
    assert classify('SYNTHETIC CEMENT',[dict(rule,evidence='')])['hs6'] is None


def test_permission_and_failure_isolation(db,source,tmp_path):
    failed=ingest(db,dict(source,reuse_permitted=False),tmp_path,FIXTURE)
    assert failed['status']=='failed' and not records(db)
    assert ingest(db,source,tmp_path,FIXTURE)['inserted']==2
    assert db.execute('SELECT count(*) FROM runs').fetchone()[0]==2


def test_transaction_rolls_back(db,source,tmp_path):
    path=tmp_path/'invalid.json'
    path.write_text(json.dumps([{'name':'SYNTHETIC','value':'1','unit':'kg CO2','country':'Test','year':'2020'},{}]))
    result=ingest(db,dict(source,format='json'),tmp_path/'raw',path)
    assert result['status']=='failed' and result['inserted']==0
    assert not records(db)

@pytest.mark.parametrize('fmt',['json','xlsx'])
def test_formats(db,source,tmp_path,fmt):
    rows=[dict(name='SYNTHETIC',value='2',unit='kg CO2',country='Test',year='2020')]
    path=tmp_path/('test.'+fmt)
    if fmt=='json': path.write_text(json.dumps({'records':rows}))
    else: pd.DataFrame(rows).to_excel(path,index=False)
    result=ingest(db,dict(source,format=fmt,records_path=['records']),tmp_path/'raw',path)
    assert result['inserted']==1


def test_pdf_queue(db,source,tmp_path):
    from pypdf import PdfWriter
    path=tmp_path/'synthetic.pdf'
    writer=PdfWriter(); writer.add_blank_page(width=100,height=100)
    with path.open('wb') as f: writer.write(f)
    result=ingest(db,dict(source,format='pdf'),tmp_path/'raw',path)
    assert result['status']=='extracted_needs_review'
    assert not records(db)
    assert '[Page 1]' in db.execute('SELECT extracted_text FROM documents').fetchone()[0]


def test_checksum(db,source,tmp_path):
    result=ingest(db,dict(source,sha256='0'*64),tmp_path,FIXTURE)
    assert result['status']=='failed' and 'checksum' in result['detail']


def test_formula_escape(db,source,tmp_path):
    from gcc_cos.storage import insert
    with db: insert(db,validate(dict(product_name='=SYNTHETIC()',original_value='1',original_unit='kg CO2')))
    export(db,tmp_path/'out.xlsx')
    assert pd.read_excel(tmp_path/'out.xlsx')['product_name'][0]=="'=SYNTHETIC()"


def test_download_robots_denied(monkeypatch,source,tmp_path):
    import requests
    class Response:
        status_code=200
        text='User-agent: *\nDisallow: /'
    monkeypatch.setattr(requests.Session,'get',lambda *a,**kw: Response())
    with pytest.raises(ValueError,match='robots'):
        download(dict(source,allowed_hosts=['example.org']),tmp_path)


def test_download_unknown_host(source,tmp_path):
    with pytest.raises(ValueError,match='host'):
        download(dict(source,allowed_hosts=[]),tmp_path)


def test_disabled_sources_are_skipped(db,source,tmp_path):
    result=ingest(db,dict(source,enabled=False,reuse_permitted=False),tmp_path)
    assert result['status']=='disabled'


def test_discovery_does_not_grant_permission():
    from gcc_cos.discovery import candidates
    found=candidates('<a href="/factors.csv">data</a><a href="/factors.csv">duplicate</a><a href="http://example.org/a.pdf">insecure</a><a href="/page">page</a>', 'https://example.org/index')
    assert len(found)==1
    assert found[0]['url']=='https://example.org/factors.csv'
    assert not found[0]['reuse_permitted'] and not found[0]['enabled']


def test_real_demo_matches_bundled_source(db,tmp_path):
    # Real attributed data, distinct from synthetic fixtures; tests do not assert invented factors.
    from gcc_cos.ingest import load_registry
    registry=load_registry('examples/cement-registry.json')[0]
    assert ingest(db,registry,tmp_path/'raw','examples/cement-source.csv')['inserted']==3
    output=records(db)
    assert all(r['data_kind']=='published_inventory' and r['hs6'] is None for r in output)
    assert {r['geography'] for r in output}=={'Pakistan','United Kingdom','United States'}


@pytest.mark.parametrize("populated", [False, True])
def test_dashboard(tmp_path,monkeypatch,populated):
    # Use an isolated database; AppTest executes the actual Streamlit script.
    from streamlit.testing.v1 import AppTest
    import gcc_cos.storage
    original=gcc_cos.storage.connect
    monkeypatch.setattr(gcc_cos.storage,'connect',lambda _: original(tmp_path/'dashboard.sqlite'))
    if populated:
        from gcc_cos.ingest import load_registry
        with original(tmp_path/'dashboard.sqlite') as conn:
            ingest(conn,load_registry('examples/cement-registry.json')[0],tmp_path/'raw','examples/cement-source.csv')
    app=AppTest.from_file(str(Path('dashboard.py').resolve())).run(timeout=30)
    assert not app.exception
    assert app.metric[0].value==('3' if populated else '0')


def test_batch_continues_and_returns_failure(tmp_path, source, monkeypatch, capsys):
    from gcc_cos.cli import main
    monkeypatch.setattr('gcc_cos.ingest.download', lambda *_: FIXTURE)
    registry=tmp_path/'registry.json'
    registry.write_text(json.dumps([dict(source,id='blocked',reuse_permitted=False),source]))
    result=main(['--db',str(tmp_path/'batch.sqlite'),'--registry',str(registry),'ingest'])
    assert result==1
    output=[json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [r['status'] for r in output]==['failed','completed']
    assert output[1]['inserted']==2


def test_excel_audit_formula_escaped(db,tmp_path):
    with db:
        db.execute("INSERT INTO runs(source_id,detail) VALUES (?,?)", ('TEST','=SYNTHETIC()'))
    export(db,tmp_path/'audit.xlsx')
    assert pd.read_excel(tmp_path/'audit.xlsx',sheet_name='Ingestion runs')['detail'][0]=="'=SYNTHETIC()"
