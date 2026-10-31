"""Audit and Windows workflow regressions. Invented values below are SYNTHETIC TEST DATA."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import pandas as pd
import pytest
from gcc_cos.audit import build_audit, write_audit, independent_class
from gcc_cos.storage import connect, records
from gcc_cos.ingest import ingest, load_registry
from gcc_cos.download import download, DownloadBlocked

ROOT=Path(__file__).resolve().parents[1]
PHASE2=load_registry(ROOT/'examples/phase2/sources.json')
LOCAL2=json.loads((ROOT/'examples/phase2/local-files.json').read_text(encoding='utf-8'))
PHASE3=load_registry(ROOT/'examples/phase3/sources.json')
LOCAL3=json.loads((ROOT/'examples/phase3/local-files.json').read_text(encoding='utf-8'))

@pytest.fixture
def db(tmp_path):
    with closing(connect(tmp_path/'audit.sqlite')) as conn:
        yield conn


def populate(db,tmp_path,sources,files):
    for source in sources:
        result=ingest(db,source,tmp_path/'raw',ROOT/files[source['id']])
        assert result['status']=='completed',result


def test_full_phase2_audit_preserves_all_rows(db,tmp_path):
    populate(db,tmp_path,PHASE2,LOCAL2)
    before=records(db)
    report=build_audit(db)
    summary=report['summary']
    assert summary['product_observations']==1236
    assert summary['traceable_source_rows']==1236
    assert summary['distinct_manufacturer_product_names']==1228
    assert summary['source_datasets']==7
    assert summary['independently_verified']==0
    assert summary['verification_classes']=={'published_third_party_data':1236}
    assert summary['same_name_groups']==6
    assert summary['repeated_signature_groups']==4
    assert summary['repeated_signature_records']==8
    assert summary['automatically_merged_records']==0
    assert summary['exact_repeated_source_content_groups']==0
    assert sum(g['reason']=='different_lifecycle_modules' for g in report['duplicates'])==2
    assert records(db)==before


def test_archive_tampering_is_not_verified(db,tmp_path):
    populate(db,tmp_path,PHASE2[3:4],LOCAL2)
    filename=db.execute('SELECT local_path FROM documents').fetchone()[0]
    Path(filename).write_bytes(b'SYNTHETIC TEST CORRUPTION')
    report=build_audit(db)
    assert report['observations'][0]['archive_status']=='archive_checksum_mismatch'
    assert report['summary']['verification_classes']=={'unverified_record':1}


def test_evidence_row_tampering_is_detected(db,tmp_path):
    populate(db,tmp_path,PHASE2[3:4],LOCAL2)
    r=records(db)[0];r.pop('id');r['original_value']='999999' # SYNTHETIC TEST corruption
    with db: db.execute('UPDATE records SET payload=?',(json.dumps(r),))
    report=build_audit(db)
    assert report['summary']['traceable_source_rows']==0
    assert report['summary']['verification_classes']=={'unverified_record':1}


def test_status_label_cannot_promote_verification(db,tmp_path):
    populate(db,tmp_path,PHASE2[3:4],LOCAL2)
    r=records(db)[0];r.pop('id');r['verification_status']='independently_crosschecked'
    with db:db.execute('UPDATE records SET payload=?',(json.dumps(r),))
    report=build_audit(db)
    assert report['summary']['independently_verified']==0
    assert 'unsupported_independent_verification_claim' in report['observations'][0]['audit_warnings']
    assert independent_class(r,False)=='unverified_record'


def test_license_evidence_checksum_is_checked(db,tmp_path):
    populate(db,tmp_path,PHASE2[:1],LOCAL2)
    source=dict(PHASE2[0],license_evidence_sha256='0'*64)
    registry=tmp_path/'registry.json';registry.write_text(json.dumps([source]),encoding='utf-8')
    report=build_audit(db,registry)
    assert report['summary']['verification_classes']=={'unverified_record':1226}


def test_expansion_retains_expiry_and_publication_year(db,tmp_path,monkeypatch):
    from datetime import date
    class AuditDate(date):
        @classmethod
        def today(cls): return cls(2026,10,30)
    monkeypatch.setattr('gcc_cos.model.date', AuditDate)
    populate(db,tmp_path,PHASE3,LOCAL3)
    rows=records(db)
    assert len(rows)==5
    assert sum('declaration_expired' in r['issues'] for r in rows)==4
    report=build_audit(db)
    assert report['summary']['traceable_source_rows']==5
    assert report['summary']['independently_verified']==0
    assert all(r['publication_year'] and r['functional_unit'] for r in report['observations'])
    assert all(r['hs6'] is None for r in rows)


def test_audit_workbook_and_csv_are_readable(db,tmp_path):
    populate(db,tmp_path,PHASE2[3:4],LOCAL2)
    summary=write_audit(db,'config/sources.json',tmp_path/'reports',tmp_path/'audit.xlsx')
    assert summary['product_observations']==1
    sheets=pd.ExcelFile(tmp_path/'audit.xlsx').sheet_names
    assert {'Records','Product audit','Source verification','Coverage','Duplicate review','License notices'}<=set(sheets)
    assert len(pd.read_excel(tmp_path/'audit.xlsx',sheet_name='Product audit'))==1
    assert pd.read_csv(tmp_path/'reports/observations.csv').iloc[0]['audit_verification_class']=='published_third_party_data'


@pytest.mark.parametrize('status', [401,403,429])
def test_download_access_rejection_has_no_retry(monkeypatch,tmp_path,status):
    calls=[]
    class Response:
        status_code=status
        is_redirect=False
        headers={}
        text=''
        def __enter__(self):return self
        def __exit__(self,*args):pass
    class Robots:
        status_code=404
        text=''
    def get(self,url,**kwargs):
        calls.append(url)
        return Robots() if url.endswith('/robots.txt') else Response()
    import requests
    monkeypatch.setattr(requests.Session,'get',get)
    monkeypatch.setattr('gcc_cos.download.time.sleep',lambda _:None)
    source=dict(PHASE2[0],url='https://example.org/test.csv',allowed_hosts=['example.org'])
    with pytest.raises(DownloadBlocked) as exc:download(source,tmp_path)
    assert exc.value.http_status==status
    assert len(calls)==2
    assert 'no automatic retry' in exc.value.next_action


def test_structured_403_is_saved_and_batch_can_continue(db,tmp_path,monkeypatch):
    from gcc_cos.download import DownloadBlocked
    def denied(*args):
        raise DownloadBlocked('SYNTHETIC TEST HTTP 403','access_denied',403,'Obtain permitted access; do not bypass')
    monkeypatch.setattr('gcc_cos.ingest.download',denied)
    result=ingest(db,PHASE2[3],tmp_path/'raw')
    assert result['http_status']==403 and result['error_code']=='access_denied'
    assert db.execute('SELECT http_status,error_code FROM runs').fetchone()==(403,'access_denied')
    assert ingest(db,PHASE2[3],tmp_path/'raw',ROOT/LOCAL2[PHASE2[3]['id']])['inserted']==1


def test_old_runs_schema_migrates_without_losing_data(tmp_path):
    path=tmp_path/'legacy.sqlite'
    with closing(sqlite3.connect(path)) as legacy:
        legacy.execute('CREATE TABLE runs(id INTEGER PRIMARY KEY,source_id TEXT,started_at TEXT,status TEXT,inserted INTEGER,duplicates INTEGER,detail TEXT)')
        legacy.execute("INSERT INTO runs(source_id,detail) VALUES ('SYNTHETIC','Preserve test history')");legacy.commit()
    with closing(connect(path)) as conn:
        assert conn.execute('SELECT detail FROM runs').fetchone()[0]=='Preserve test history'
        assert {'http_status','error_code','next_action'} <= {r[1] for r in conn.execute('PRAGMA table_info(runs)')}


def test_warning_and_hs_filters_are_conservative():
    from gcc_cos.query import select
    rows=[dict(product_name='SYNTHETIC',issues=['test_warning'],hs6=None),dict(product_name='SYNTHETIC CLEAN',issues=[])]
    assert select(rows,warnings_only=True)==rows[:1]
    assert select(rows,warning='test_warning')==rows[:1]
    assert select(rows,hs6='000000')==[]


def test_windows_workflow_does_not_claim_an_unexecuted_run():
    workflow=(ROOT/'.github/workflows/tests.yml').read_text(encoding='utf-8')
    assert 'windows-latest' in workflow and 'ubuntu-latest' in workflow
    assert 'python scripts/smoke.py' in workflow
    for name in ('setup.ps1','test.ps1'):
        script=(ROOT/'scripts'/name).read_text(encoding='utf-8')
        assert '$LASTEXITCODE' in script and 'finally { Pop-Location }' in script
        assert 'ExecutionPolicy' not in script


@pytest.mark.parametrize('category', ['cement','steel','aluminum','glass','vehicles','electronics','appliances','furniture','clothing'])
def test_new_category_templates_never_claim_data_or_permission(category):
    from gcc_cos.templates import source_template
    template=source_template(category)
    assert not template['reuse_permitted'] and not template['enabled']
    assert template['url'] is None and template['license'] is None
    assert template['columns']['data_kind']=='data_kind'
    assert template['columns']['product_name']=='model_or_variant'


def test_model_geography_and_source_tampering_are_detected(db,tmp_path):
    populate(db,tmp_path,PHASE2[3:4],LOCAL2)
    r=records(db)[0];r.pop('id');r['geography']='SYNTHETIC TEST COUNTRY'
    with db:db.execute('UPDATE records SET payload=?',(json.dumps(r),))
    assert build_audit(db)['summary']['traceable_source_rows']==0


@pytest.mark.parametrize('category', ['cement','steel','aluminum','glass','vehicles','electronics','appliances','furniture','clothing'])
def test_authorized_template_ingestion_distinguishes_generic_data(db,tmp_path,category):
    import csv
    from gcc_cos.templates import source_template
    from gcc_cos.model import is_product
    source=source_template(category)
    path=tmp_path/'synthetic-generic.csv'
    row={column:'' for column in source['columns'].values()}
    row.update(manufacturer='SYNTHETIC TEST MAKER',model_or_variant='SYNTHETIC GENERIC TEST MATERIAL',
               footprint_value='100',footprint_unit='kg CO2e/kg',data_kind='published_generic_factor')
    with path.open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(row));writer.writeheader();writer.writerow(row)
    assert ingest(db,source,tmp_path/'raw',path)['status']=='failed'
    # Explicit TEST-ONLY permission metadata; never a source of production factors.
    source.update(reuse_permitted=True,license='SYNTHETIC TEST permission',license_url='https://example.org/test-license',
                  url='https://example.org/test.csv',title='SYNTHETIC TEST DATA',attribution='TEST ONLY')
    assert ingest(db,source,tmp_path/'raw',path)['inserted']==1
    assert not is_product(records(db)[0])


def test_audit_cannot_overwrite_active_database(db,tmp_path):
    path=db.execute('PRAGMA database_list').fetchone()[2]
    with pytest.raises(ValueError,match='active database'):
        write_audit(db,'config/sources.json',tmp_path/'report',path)
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
