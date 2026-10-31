"""Every invented document/value/account in this module is SYNTHETIC TEST DATA, temporary only."""
from contextlib import closing
from datetime import date
import json
from pathlib import Path
import sqlite3
import pandas as pd
import pytest
from gcc_cos.storage import connect,insert,records,review
from gcc_cos.model import validate
from gcc_cos.verification import (add_reviewer,authenticate,attach_evidence,latest_packet,decide,verified_rows,
                                  save_packet,digest,compare,FIELDS,_proof)
from gcc_cos.export import export
from gcc_cos.review_batch import single,prepare,workbook

PASSWORD='SYNTHETIC-test-only-password'

@pytest.fixture
def ready(tmp_path):
    with closing(connect(tmp_path/'test.sqlite')) as db:
        raw=dict(product_name='SYNTHETIC TEST DEVICE',manufacturer='SYNTHETIC TEST MAKER',entity_type='product',
                 category='electronics',original_value='100',original_unit='kgCO2eq',declared_quantity='1',declared_unit='item',
                 declared_unit_evidence='SYNTHETIC test schema',geography='SYNTHETIC TEST COUNTRY',year='2026',
                 publication_date='2026-01-01',lifecycle_scope='SYNTHETIC cradle-to-grave',methodology='SYNTHETIC TEST METHOD',
                 data_kind='published_product_footprint',source_id='SYNTHETIC',source_url='https://example.org/dataset',
                 primary_source_url='https://example.org/publisher.json',document_title='SYNTHETIC source',
                 license='SYNTHETIC TEST permission',license_url='https://example.org/license',attribution='SYNTHETIC TEST ONLY')
        with db:insert(db,validate(raw))
        record=records(db)[0]
        document={k:record.get(k) for k in FIELDS}
        document.update(document_title='SYNTHETIC publisher report',document_date='2026-01-01',license='SYNTHETIC TEST permission',expiry_statement='no_expiry_stated')
        path=tmp_path/'synthetic-publisher.json';path.write_text(json.dumps(document),encoding='utf-8')
        spec=dict(url=record['primary_source_url'],format='json',reuse_permitted=True,license=document['license'],
                  license_url='https://example.org/license',document_title=document['document_title'],document_date=document['document_date'],
                  expiry_statement='no_expiry_stated',valid_until=None,fields={k:document[k] for k in FIELDS},
                  locators={k:{'path':[k]} for k in document})
        attach_evidence(db,record['id'],path,spec,tmp_path/'evidence')
        add_reviewer(db,'test-reviewer',PASSWORD)
        yield db,record,path,spec,tmp_path


def test_automatic_match_and_legacy_accept_never_approve(ready):
    db,r,*_=ready
    assert all(v['status']=='match' for v in latest_packet(db,r['id'])['comparison'].values())
    assert latest_packet(db,r['id'])['status']=='awaiting_human_approval'
    assert not verified_rows(db)
    review(db,r['id'],'Legacy reviewer','accepted','SYNTHETIC triage')
    assert not verified_rows(db)
    assert db.execute('SELECT count(*) FROM human_decisions').fetchone()[0]==0


def test_authenticated_attested_human_approval(ready):
    db,r,*_=ready
    with pytest.raises(ValueError,match='credentials'):decide(db,r['id'],'test-reviewer','wrong','approved','SYNTHETIC test',True)
    with pytest.raises(ValueError,match='attest'):decide(db,r['id'],'test-reviewer',PASSWORD,'approved','SYNTHETIC test')
    decide(db,r['id'],'test-reviewer',PASSWORD,'approved','SYNTHETIC TEST: personally checked source, rights and absence of expiry',True)
    selected=verified_rows(db)
    assert len(selected)==1 and selected[0]['human_reviewer']=='test-reviewer'
    assert selected[0]['human_verified_at'] and selected[0]['primary_evidence_sha256']
    assert records(db)[0]['data_kind']=='published_product_footprint'


def test_rejection_overrides_earlier_approval(ready):
    db,r,*_=ready
    decide(db,r['id'],'test-reviewer',PASSWORD,'approved','SYNTHETIC test evidence checked',True)
    decide(db,r['id'],'test-reviewer',PASSWORD,'rejected','SYNTHETIC test: later discrepancy')
    assert not verified_rows(db)
    assert db.execute('SELECT count(*) FROM human_decisions').fetchone()[0]==2


def test_record_and_evidence_changes_invalidate_approval(ready):
    db,r,path,spec,tmp=ready
    decide(db,r['id'],'test-reviewer',PASSWORD,'approved','SYNTHETIC test',True)
    packet=latest_packet(db,r['id']);Path(packet['publisher_evidence']['local_file']).write_text('SYNTHETIC corruption')
    assert not verified_rows(db)


def test_record_digest_and_reviewer_revocation(ready):
    db,r,*_=ready
    decide(db,r['id'],'test-reviewer',PASSWORD,'approved','SYNTHETIC test',True)
    with db:db.execute('UPDATE reviewers SET enabled=0')
    assert not verified_rows(db)
    with db:
        db.execute('UPDATE reviewers SET enabled=1')
        changed={k:v for k,v in r.items() if k!='id'};changed['original_value']='101'
        db.execute('UPDATE records SET payload=?',(json.dumps(changed),))
    assert not verified_rows(db)


def test_new_packet_requires_new_human_decision(ready):
    db,r,path,spec,tmp=ready
    decide(db,r['id'],'test-reviewer',PASSWORD,'approved','SYNTHETIC test',True)
    attach_evidence(db,r['id'],path,spec,tmp/'evidence')
    assert not verified_rows(db)


@pytest.mark.parametrize('change',['value','quote','license','url','expiry'])
def test_unsupported_or_expired_evidence_cannot_be_approved(ready,change):
    db,r,path,spec,tmp=ready
    if change=='value':spec['fields']['original_value']='999'
    if change=='quote':spec['locators']['manufacturer']={'path':['not_present']}
    if change=='license':spec['reuse_permitted']=False
    if change=='url':spec['url']='https://example.org/not-the-publisher.json'
    if change=='expiry':
        document=json.loads(path.read_text());document['valid_until']='2000-01-01';document['expiry_statement']='expired'
        path.write_text(json.dumps(document));spec.update(valid_until='2000-01-01',expiry_statement='expired');spec['locators']['valid_until']={'path':['valid_until']}
    if change in {'license','url'}:
        with pytest.raises(ValueError):attach_evidence(db,r['id'],path,spec,tmp/'evidence')
    else:
        attach_evidence(db,r['id'],path,spec,tmp/'evidence')
        with pytest.raises(ValueError):decide(db,r['id'],'test-reviewer',PASSWORD,'approved','SYNTHETIC test',True)
        assert not verified_rows(db)


def test_legacy_rejection_excludes_even_with_human_approval(ready):
    db,r,*_=ready
    decide(db,r['id'],'test-reviewer',PASSWORD,'approved','SYNTHETIC test',True)
    review(db,r['id'],'Legacy','rejected','SYNTHETIC rejection')
    assert not verified_rows(db)


def test_verified_exports_and_sqlite_credentials_scrubbed(ready):
    db,r,path,spec,tmp=ready
    for ext in ['csv','xlsx','sqlite']:
        assert export(db,tmp/('empty.'+ext),verified_only=True)==0
    assert len(pd.read_excel(tmp/'empty.xlsx'))==0
    assert len(pd.read_csv(tmp/'empty.csv'))==0
    with closing(sqlite3.connect(tmp/'empty.sqlite')) as copied:
        assert copied.execute('SELECT count(*) FROM records').fetchone()[0]==0
        assert copied.execute('SELECT count(*) FROM reviewers').fetchone()[0]==0
        assert copied.execute('SELECT count(*) FROM review_packets').fetchone()[0]==0
        assert copied.execute('PRAGMA foreign_key_check').fetchall()==[]
    decide(db,r['id'],'test-reviewer',PASSWORD,'approved','SYNTHETIC test',True)
    assert export(db,tmp/'approved.xlsx',verified_only=True)==1
    assert 'human_verified_at' in pd.read_excel(tmp/'approved.xlsx').columns
    hashed=db.execute('SELECT password_hash FROM reviewers').fetchone()[0]
    assert export(db,tmp/'approved.sqlite',verified_only=True)==1
    assert hashed.encode() not in (tmp/'approved.sqlite').read_bytes()
    with closing(sqlite3.connect(tmp/'approved.sqlite')) as copied:
        assert copied.execute('SELECT count(*) FROM reviewers').fetchone()[0]==0
        assert copied.execute('SELECT count(*) FROM human_decisions').fetchone()[0]==1
        assert copied.execute('PRAGMA foreign_key_check').fetchall()==[]
    authenticate(db,'test-reviewer',PASSWORD)


def test_synthetic_pdf_numeric_quote_cannot_match_substring():
    assert not _proof(['SYNTHETIC footprint 1000 kg'],'pdf','original_value','100',{'page':1,'quote':'1000 kg'})
    assert _proof(['SYNTHETIC footprint 100 kg'],'pdf','original_value','100',{'page':1,'quote':'100 kg'})


def test_pending_packet_workbook_keeps_publisher_values_blank(tmp_path):
    with closing(connect(tmp_path/'batch.sqlite')) as db:
        with db:
            for i in range(3):insert(db,validate(dict(product_name=f'SYNTHETIC {i}',manufacturer=f'TEST {i}',entity_type='product',data_kind='published_product_footprint',original_value='100',original_unit='kgCO2eq',primary_source_url='https://example.org/test.pdf')))
        ids=prepare(db,'test',3)
        assert len(ids)==3 and prepare(db,'test',3)==ids
        summary=workbook(db,'test',tmp_path/'review.xlsx')
        assert summary['selected']==3 and summary['human_decisions']==0
        frame=pd.read_excel(tmp_path/'review.xlsx')
        assert frame['publisher_extraction'].isna().all()
        assert set(frame['workflow_status'])=={'awaiting_human_approval'}


def test_review_rejection_requires_account_and_explanation(ready):
    db,r,*_=ready
    with pytest.raises(ValueError):decide(db,r['id'],'anonymous','none','rejected','SYNTHETIC')
    with pytest.raises(ValueError):decide(db,r['id'],'test-reviewer',PASSWORD,'rejected','')


def test_explicit_json_timestamp_and_quote_locators():
    assert _proof({'published':0},'json','publication_date','1970-01-01',{'path':['published'],'transform':'unix_ms_date'})
    assert not _proof({'published':0},'json','original_value','1970-01-01',{'path':['published'],'transform':'unix_ms_date'})
    assert _proof({'validity':'2024-03-16 to 2029-03-16'},'json','valid_until','2029-03-16',{'path':['validity'],'quote':'2024-03-16 to 2029-03-16'})
    assert not _proof({'year':2029},'json','valid_until','2029-12-31',{'path':['year']})


def test_expiry_and_attestation_are_rechecked_at_export(ready):
    db,r,*_=ready
    decide(db,r['id'],'test-reviewer',PASSWORD,'approved','SYNTHETIC test',True)
    with db:db.execute('UPDATE human_decisions SET attested=0')
    assert not verified_rows(db)


def test_human_state_records_actual_decision(ready):
    from gcc_cos.verification import review_state
    db,r,*_=ready
    assert review_state(db,r['id'])=='awaiting_human_approval'
    decide(db,r['id'],'test-reviewer',PASSWORD,'approved','SYNTHETIC test',True)
    assert review_state(db,r['id'])=='approved_current_eligible'
    decide(db,r['id'],'test-reviewer',PASSWORD,'rejected','SYNTHETIC later rejection')
    assert review_state(db,r['id'])=='rejected_by_authorized_human'


def test_authorized_human_interface_on_synthetic_fixture(ready,monkeypatch):
    # This exercises a SYNTHETIC fixture in a temporary DB, never the real collection.
    from streamlit.testing.v1 import AppTest
    import gcc_cos.storage
    root=Path(__file__).resolve().parents[1]
    db,r,*_=ready
    location=db.execute('PRAGMA database_list').fetchone()[2]
    original=gcc_cos.storage.connect
    monkeypatch.setattr(gcc_cos.storage,'connect',lambda _:original(location))
    app=AppTest.from_file(str(root/'dashboard.py')).run(timeout=30)
    assert not app.exception
    next(w for w in app.text_input if w.label=='Authorized reviewer username').input('test-reviewer')
    next(w for w in app.text_input if w.label=='Reviewer password').input(PASSWORD)
    next(w for w in app.selectbox if w.label=='Human evidence decision').select('approved')
    next(w for w in app.text_area if w.label=='Decision explanation (required)').input('SYNTHETIC TEST: personally inspected evidence, license and expiry')
    next(w for w in app.checkbox if w.label.startswith('I personally inspected')).check()
    next(w for w in app.button if w.label=='Record authenticated human decision').click().run(timeout=30)
    assert not app.exception
    assert db.execute('SELECT count(*) FROM human_decisions').fetchone()[0]==1
    assert len(verified_rows(db))==1


def test_publisher_probe_caches_same_host_failures_without_downloads(tmp_path,monkeypatch):
    import requests
    from gcc_cos.review_batch import probe
    calls=[]
    def fail(self,url,**kwargs):
        calls.append(url);raise requests.exceptions.ProxyError('SYNTHETIC TEST proxy denial')
    monkeypatch.setattr(requests.Session,'get',fail)
    with closing(connect(tmp_path/'probe.sqlite')) as db:
        with db:
            for i in range(2):insert(db,validate(dict(product_name=f'SYNTHETIC {i}',manufacturer=f'TEST {i}',entity_type='product',data_kind='published_product_footprint',original_value='100',original_unit='kgCO2eq',primary_source_url=f'https://example.org/test-{i}.pdf')))
        prepare(db,'test',2)
        results=probe(db,'test')
        assert len(calls)==1 and calls[0].endswith('/robots.txt')
        assert all(r['document_body_downloaded'] is False for r in results)
        assert results[1]['host_failure_cached'] is True


@pytest.mark.parametrize('malformed', [None, []])
def test_malformed_field_mappings_do_not_create_supported_evidence(ready,malformed):
    db,r,path,spec,tmp=ready
    spec['fields']=malformed
    with pytest.raises(ValueError,match='fields and locators'):
        attach_evidence(db,r['id'],path,spec,tmp/'evidence')
    assert not verified_rows(db)
