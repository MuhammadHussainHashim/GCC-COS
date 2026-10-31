"""Representative review packets and access diagnostics; never approves observations."""
from collections import defaultdict
import json
from pathlib import Path
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
import requests
import pandas as pd
from .verification import FIELDS, schema, packets, latest_packet, save_packet, verified_rows, review_state, digest
from .storage import records, now
from .model import is_product
from .audit import safe_frame


def batch_schema(db):
    schema(db)
    db.execute('CREATE TABLE IF NOT EXISTS review_batch_members(batch TEXT,record_id INTEGER REFERENCES records(id),created_at TEXT,PRIMARY KEY(batch,record_id))')
    db.commit()


def prepare(db,batch='phase4',size=20):
    batch_schema(db)
    existing=[r[0] for r in db.execute('SELECT record_id FROM review_batch_members WHERE batch=? ORDER BY record_id',(batch,))]
    if existing:return existing
    if size<1:raise ValueError('Batch size must be positive')
    groups=defaultdict(list)
    for r in records(db):
        if is_product(r) and r.get('primary_source_url'):groups[r.get('manufacturer')].append(r)
    selected=[];seen_categories=set()
    while groups and len(selected)<size:
        for manufacturer in sorted(list(groups),key=str):
            pool=groups[manufacturer]
            pool.sort(key=lambda r:(r.get('subcategory') in seen_categories,'.pdf' not in r.get('primary_source_url','').lower(),
                                    'declaration_expired' in r.get('issues',[]),len(r.get('issues',[])),r['id']))
            r=pool.pop(0);selected.append(r);seen_categories.add(r.get('subcategory'))
            if not pool:del groups[manufacturer]
            if len(selected)>=size:break
    for r in selected:
        payload={'status':'awaiting_human_approval',
                 'selection_reason':'Manufacturer diversity, category diversity, original reference present; accessibility is not assumed',
                 'secondary_reference':{k:r.get(k) for k in FIELDS},
                 'publisher_evidence':None,'comparison':{k:{'stored':r.get(k),'publisher':None,'status':'missing_evidence'} for k in FIELDS},
                 'access':{'status':'not_checked','original_document_accessible':'not_established'},
                 'automatic_result':'Missing original publisher evidence; no approval or independent verification'}
        save_packet(db,r,payload)
        with db:db.execute('INSERT INTO review_batch_members VALUES (?,?,?)',(batch,r['id'],now()))
    return [r['id'] for r in selected]


def single(db, record_id):
    from .verification import get_record
    record=get_record(db, record_id)
    if not is_product(record):raise ValueError('Choose a product observation')
    current=latest_packet(db, record_id)
    if current:return current['id']
    return save_packet(db,record,{'status':'awaiting_human_approval','secondary_reference':{k:record.get(k) for k in FIELDS},
                                 'publisher_evidence':None,'comparison':{k:{'stored':record.get(k),'publisher':None,'status':'missing_evidence'} for k in FIELDS},
                                 'automatic_result':'Original publisher evidence missing; human review required'})


def members(db,batch):
    batch_schema(db)
    return [r[0] for r in db.execute('SELECT record_id FROM review_batch_members WHERE batch=? ORDER BY record_id',(batch,))]


def probe(db,batch):
    """Robots and HEAD metadata only. No original document body is downloaded without permission."""
    selected=set(members(db,batch));host_cache={};results=[]
    session=requests.Session();session.headers['User-Agent']='GCC-COS-human-review/0.4'
    for r in records(db):
        if r['id'] not in selected:continue
        packet=latest_packet(db,r['id']);url=r.get('primary_source_url') or '';parsed=urlsplit(url)
        access={'checked_at':now(),'url':url,'original_document_accessible':'not_established',
                'publisher_document_license':'not_established','document_body_downloaded':False}
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
            access['status']='unsupported_or_ambiguous_reference'
        else:
            host=parsed.netloc
            try:
                if host not in host_cache:
                    response=session.get('https://'+host+'/robots.txt',timeout=25,allow_redirects=False)
                    host_cache[host]=(response.status_code,response.text if response.status_code==200 else '')
                code,body=host_cache[host];access['robots_http_status']=code
                if code is None:
                    access['status']='network_error';access['error_type']=body;access['host_failure_cached']=True
                elif code not in (200,404,410):access['status']='robots_permission_unavailable'
                else:
                    policy=RobotFileParser();policy.parse(body.splitlines())
                    if code==200 and not policy.can_fetch('GCC-COS-human-review',url):access['status']='robots_disallows_reference'
                    else:
                        time.sleep(max(1,policy.crawl_delay('GCC-COS-human-review') or 0))
                        response=session.head(url,timeout=25,allow_redirects=False)
                        access['document_head_http_status']=response.status_code
                        access['status']='headers_accessible_permission_review_required' if response.status_code==200 else 'reference_access_not_established'
                        # A HEAD response is not content verification or reuse permission.
            except requests.RequestException as exc:
                access['status']='network_error';access['error_type']=type(exc).__name__
                if host not in host_cache:host_cache[host]=(None,type(exc).__name__)
        clean={k:v for k,v in packet.items() if k not in {'id','record_id','record_digest','created_at'}}
        clean['access']=access
        save_packet(db,r,clean);results.append({'record_id':r['id'],**access})
    session.close()
    return results


def evidence_template(record):
    return {'url':record.get('primary_source_url'),'format':'json' if record.get('epd_id') else 'pdf',
            'reuse_permitted':False,'license':None,'license_url':None,'document_title':None,'document_date':None,
            'valid_until':None,'expiry_statement':None,'fields':{k:None for k in FIELDS},
            'locators':{k:({'path':[]} if record.get('epd_id') else {'page':None,'quote':None})
                        for k in list(FIELDS)+['document_title','document_date','license','expiry_statement','valid_until']}}


def workbook(db,batch,path,templates_dir=None):
    selected=set(members(db,batch));rows=[];comparisons=[]
    for r in records(db):
        if r['id'] not in selected:continue
        p=latest_packet(db,r['id']);e=p.get('publisher_evidence') or {};access=p.get('access') or {};state=review_state(db,r['id'])
        row={'record_id':r['id'],'secondary_field_origin':'Licensed secondary dataset; not extracted or confirmed from the original publisher document','packet_current':p['record_digest']==digest(r),'manufacturer':r.get('manufacturer'),'product_name':r.get('product_name'),
             'original_value':r.get('original_value'),'original_unit':r.get('original_unit'),
             'declared_quantity':r.get('declared_quantity'),'declared_unit':r.get('declared_unit'),
             'lifecycle_boundary':r.get('lifecycle_scope'),'publication_date':r.get('publication_date'),
             'reference_year':r.get('year'),'original_publisher_url':r.get('primary_source_url'),
             'dataset_url':r.get('source_url'),'dataset_license':r.get('license'),'dataset_license_url':r.get('license_url'),
             'attribution':r.get('attribution'),'document_sha256':r.get('document_sha256'),
             'declaration_valid_until_year':r.get('valid_until_year'),'validation_warnings':r.get('issues'),
             'access_status':access.get('status','not_checked'),'original_document_accessible':access.get('original_document_accessible','not_established'),
             'publisher_license':e.get('license'),'publisher_license_url':e.get('license_url'),
             'publisher_document_title':e.get('document_title'),'publisher_document_date':e.get('document_date'),
             'publisher_declared_expiry':e.get('valid_until'),
             'workflow_status':state,'automatic_result':p['automatic_result'],
             'publisher_extraction':e.get('fields'),'publisher_locators':e.get('locators')}
        row.update({'publisher_'+field:e.get('fields',{}).get(field) for field in FIELDS})
        row['publisher_evidence_sha256']=e.get('sha256')
        rows.append(row)
        for k,v in p['comparison'].items():comparisons.append({'record_id':r['id'],'field':k,**v,'human_approval':state})
        if templates_dir:
            target=Path(templates_dir)/f"record-{r['id']}-evidence.json";target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():target.write_text(json.dumps(evidence_template(r),indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    target=Path(path);target.parent.mkdir(parents=True,exist_ok=True)
    origin=db.execute('PRAGMA database_list').fetchone()[2]
    if target.suffix.lower()!='.xlsx' or (origin and target.resolve()==Path(origin).resolve()):raise ValueError('Choose a separate .xlsx output')
    decisions=pd.read_sql_query('SELECT * FROM human_decisions',db)
    allqueue=[{'record_id':r['id'],'manufacturer':r.get('manufacturer'),'product_name':r.get('product_name'),
               'selected_in_batch':r['id'] in selected,'review_status':r.get('review_status'),
               'warnings':r.get('issues'),'source_url':r.get('primary_source_url')} for r in records(db) if is_product(r)]
    sheets={'Human review':rows,'Field comparisons':comparisons,'Full review queue':allqueue,
            'Human decisions':decisions.to_dict('records'),
            'Instructions':[{'instruction':'Workbook edits never grant approval. Use an operator-provisioned reviewer account in the dashboard or human-review CLI.'},
                            {'instruction':'Secondary-reference fields are not publisher extraction. Blank publisher fields mean missing evidence. Automatic results await human approval.'},
                            {'instruction':'Verified-only export requires supported current publisher evidence, current explicit human approval and no blocking discrepancies. Human evidence review is not third-party certification.'}]}
    with pd.ExcelWriter(target,engine='openpyxl') as writer:
        for name,items in sheets.items():
            frame=safe_frame(items)
            if any(isinstance(v,str) and len(v)>32767 for v in frame.to_numpy().flat):raise ValueError('Evidence exceeds Excel limits; inspect SQLite instead')
            frame.to_excel(writer,index=False,sheet_name=name)
    return {'batch':batch,'selected':len(rows),'publisher_documents_attached':sum(bool(r['publisher_extraction']) for r in rows),
            'automatic_approvals':0,'human_decisions':len(decisions),'verified_eligible':len(verified_rows(db))}
