"""Explicit human evidence review, separate from legacy triage or source review claims."""
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
from pypdf import PdfReader
from .storage import now, records
from .model import is_product, validate

FIELDS = ('product_name','manufacturer','original_value','original_unit','declared_quantity','declared_unit',
          'lifecycle_scope','publication_date','geography')
ITERATIONS = 600000


def schema(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS reviewers(username TEXT PRIMARY KEY,salt TEXT NOT NULL,password_hash TEXT NOT NULL,iterations INTEGER NOT NULL,enabled INTEGER NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS review_packets(id INTEGER PRIMARY KEY,record_id INTEGER REFERENCES records(id),record_digest TEXT NOT NULL,created_at TEXT NOT NULL,payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS human_decisions(id INTEGER PRIMARY KEY,record_id INTEGER REFERENCES records(id),packet_id INTEGER REFERENCES review_packets(id),record_digest TEXT NOT NULL,reviewer TEXT NOT NULL,decision TEXT NOT NULL,explanation TEXT NOT NULL,decided_at TEXT NOT NULL);
    ''')
    columns={row[1] for row in db.execute('PRAGMA table_info(human_decisions)')}
    if 'attested' not in columns:
        db.execute('ALTER TABLE human_decisions ADD COLUMN attested INTEGER NOT NULL DEFAULT 0')
        db.commit()


def digest(record):
    content={k:v for k,v in record.items() if k not in {'id','review_status','retrieved_at'}}
    return hashlib.sha256(json.dumps(content,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def get_record(db,record_id):
    row=db.execute('SELECT payload FROM records WHERE id=?',(record_id,)).fetchone()
    if row is None: raise ValueError('Record not found')
    return {'id':record_id,**json.loads(row[0])}


def add_reviewer(db,username,password):
    schema(db)
    if not username.strip() or len(password)<12: raise ValueError('Reviewer name and a password of at least 12 characters required')
    salt=secrets.token_hex(16)
    hashed=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),ITERATIONS).hex()
    with db:
        db.execute('INSERT INTO reviewers VALUES (?,?,?,?,?,?)',(username,salt,hashed,ITERATIONS,1,now()))


def authenticate(db,username,password):
    schema(db)
    row=db.execute('SELECT salt,password_hash,iterations,enabled FROM reviewers WHERE username=?',(username,)).fetchone()
    if not row or not row[3]: raise ValueError('Invalid or disabled reviewer credentials')
    calculated=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(row[0]),row[2]).hex()
    if not hmac.compare_digest(calculated,row[1]): raise ValueError('Invalid or disabled reviewer credentials')


def packets(db):
    schema(db)
    return [dict(id=i,record_id=rid,record_digest=d,created_at=t,**json.loads(payload))
            for i,rid,d,t,payload in db.execute('SELECT * FROM review_packets ORDER BY id')]


def latest_packet(db,record_id):
    found=[p for p in packets(db) if p['record_id']==record_id]
    return found[-1] if found else None


def save_packet(db,record,payload):
    schema(db)
    with db:
        cursor=db.execute('INSERT INTO review_packets(record_id,record_digest,created_at,payload) VALUES (?,?,?,?)',
                          (record['id'],digest(record),now(),json.dumps(payload,ensure_ascii=False)))
    return cursor.lastrowid


def _norm(value):
    return ' '.join(str(value or '').split()).casefold()


def compare(record,observed):
    comparison={}
    if not isinstance(observed,dict):observed={}
    for field in FIELDS:
        left,right=record.get(field),observed.get(field)
        if left is None or right is None or str(left).strip()=='' or str(right).strip()=='': status='missing_evidence'
        elif field in {'original_value','declared_quantity'}:
            try:
                a,b=Decimal(str(left)),Decimal(str(right))
                status='match' if a.is_finite() and b.is_finite() and a==b else 'discrepancy'
            except InvalidOperation:status='discrepancy'
        else:status='match' if _norm(left)==_norm(right) else 'discrepancy'
        comparison[field]={'stored':left,'publisher':right,'status':status}
    return comparison


def _proof(document,fmt,field,value,locator):
    if not isinstance(locator,dict):return False
    if fmt=='pdf':
        page=locator.get('page')
        quote=locator.get('quote','')
        if not isinstance(page,int) or not (1<=page<=len(document)) or not quote: return False
        # Quotes must actually occur on the specified page; values cannot be asserted without an excerpt.
        contained = _norm(quote) in _norm(document[page-1])
        if field in {'original_value','declared_quantity'}:
            return contained and bool(re.search(r'(?<![\w.])'+re.escape(str(value))+r'(?![\w.])',quote))
        return contained and _norm(value) in _norm(quote)
    obj=document
    try:
        for part in locator['path']:obj=obj[part]
    except (KeyError,IndexError,TypeError):return False
    if isinstance(obj,(dict,list)):return False
    if locator.get('transform'):
        if locator['transform']!='unix_ms_date' or field not in {'publication_date','document_date','valid_until'}:
            return False
        try:obj=datetime.fromtimestamp(float(obj)/1000,timezone.utc).date().isoformat()
        except (ValueError,TypeError,OverflowError,OSError):return False
    if locator.get('quote'):
        return _proof([str(obj)],'pdf',field,value,{'page':1,'quote':locator['quote']})
    if field in {'original_value','declared_quantity'}:
        try:
            a,b=Decimal(str(obj)),Decimal(str(value))
            return a.is_finite() and b.is_finite() and a==b
        except InvalidOperation:return False
    return _norm(obj)==_norm(value)


def evidence_checks(packet):
    evidence=packet.get('publisher_evidence') or {}
    if not isinstance(evidence,dict):return False,'Malformed publisher evidence'
    if not isinstance(evidence.get('local_file'),str):return False,'Publisher evidence file missing'
    if not isinstance(evidence.get('fields'),dict) or not isinstance(evidence.get('locators'),dict):return False,'Publisher field mappings are missing'
    if evidence.get('reuse_permitted') is not True or not evidence.get('license') or urlsplit(str(evidence.get('license_url') or '')).scheme != 'https':
        return False,'Publisher-document reuse permission is not established'
    path=Path(evidence.get('local_file',''))
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=evidence.get('sha256'):
        return False,'Publisher evidence is missing or its hash changed'
    try:
        if evidence['format']=='pdf':document=[p.extract_text() or '' for p in PdfReader(path).pages]
        elif evidence['format']=='json':document=json.loads(path.read_text(encoding='utf-8'))
        else:return False,'Publisher format requires manual extraction support'
        observed=evidence.get('fields',{})
        locators=evidence.get('locators',{})
        required=list(FIELDS)+['document_title','document_date','license']
        if evidence.get('valid_until'):required.append('expiry_statement')
        if evidence.get('valid_until'):required.append('valid_until')
        for field in required:
            value=observed.get(field) if field in FIELDS else evidence.get(field)
            if value is None or not _proof(document,evidence['format'],field,value,locators.get(field,{})):
                return False,'Missing or unsupported publisher evidence for '+field
    except (ValueError,OSError,KeyError,TypeError):
        return False,'Publisher evidence cannot be parsed'
    return True,''


def attach_evidence(db,record_id,document_path,spec,cache='data/publisher-evidence'):
    record=get_record(db,record_id)
    if not isinstance(spec,dict) or not isinstance(spec.get('fields'),dict) or not isinstance(spec.get('locators'),dict):
        raise ValueError('Evidence specification must contain fields and locators objects')
    url=spec.get('url','')
    if url!=record.get('primary_source_url') or urlsplit(url).scheme!='https':
        raise ValueError('Evidence URL must match the stored original publisher URL; cross-link provenance is not yet supported')
    if spec.get('reuse_permitted') is not True or not spec.get('license') or not spec.get('license_url'):
        raise ValueError('Documented publisher-document reuse permission is required; dataset licensing alone is insufficient')
    raw=Path(document_path).read_bytes()
    if len(raw)>30*1024*1024:raise ValueError('Publisher document exceeds 30 MiB')
    sha=hashlib.sha256(raw).hexdigest();fmt=spec.get('format')
    if fmt not in {'pdf','json'}:raise ValueError('Supported evidence formats: PDF with text, JSON with explicit field paths')
    target=Path(cache)/(sha+'.'+fmt);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    evidence={**spec,'local_file':str(target),'sha256':sha,'provenance':'Operator-supplied document; human must confirm publisher URL/file identity'}
    payload={'status':'awaiting_human_approval','publisher_evidence':evidence,
             'secondary_reference':{k:record.get(k) for k in FIELDS},
             'comparison':compare(record,spec.get('fields',{})),
             'automatic_result':'Not independently verified; automated comparisons require explicit human approval'}
    supported,reason=evidence_checks(payload)
    payload['evidence_supported']=supported;payload['evidence_issue']=reason
    return save_packet(db,record,payload)


def approval_blockers(record,packet):
    blockers=[]
    if not is_product(record):blockers.append('Not a product footprint observation')
    if record.get('review_status') in {'rejected','manually_rejected'}:blockers.append('Record is rejected')
    if not packet or packet['record_digest']!=digest(record):return blockers+['Missing or stale review packet']
    supported,reason=evidence_checks(packet)
    if not supported:blockers.append(reason)
    evidence=packet.get('publisher_evidence') or {}
    # Recompute, do not trust an editable saved "match" label.
    if any(v['status']!='match' for v in compare(record,evidence.get('fields',{})).values()):
        blockers.append('Publisher comparison has discrepancies or missing evidence')
    issues=validate(record)['issues']
    for issue in issues:
        if issue.startswith('missing_') or issue in {'invalid_numeric_value','negative_value_requires_methodology_review','unit_conversion_not_available','declared_unit_conversion_inputs_missing','declaration_expired','inconsistent_density_areal_mass_thickness','unknown_data_kind'}:
            blockers.append(issue)
    expiry=evidence.get('valid_until')
    try:
        if expiry and date.fromisoformat(expiry)<date.today():blockers.append('Publisher declaration expired')
        elif record.get('valid_until_year') and not expiry:blockers.append('Exact declaration expiry must be established')
        elif not expiry and evidence.get('expiry_statement')!='no_expiry_stated':blockers.append('Expiry status must be established')
    except (ValueError,TypeError):blockers.append('Invalid declaration expiry')
    if expiry and record.get('valid_until_year') and str(record['valid_until_year'])!=str(expiry)[:4]:
        blockers.append('Publisher expiry conflicts with stored validity year')
    return list(dict.fromkeys(blockers))


def decide(db,record_id,username,password,decision,explanation,attested=False):
    authenticate(db,username,password)
    if decision not in {'approved','rejected'} or not explanation.strip():raise ValueError('A decision and explanation are required')
    record=get_record(db,record_id);packet=latest_packet(db,record_id)
    if not packet:raise ValueError('Create a review packet first')
    if decision=='approved':
        if not attested:raise ValueError('Human must explicitly attest to inspecting the original publisher evidence')
        blockers=approval_blockers(record,packet)
        if blockers:raise ValueError('; '.join(blockers))
    with db:
        cursor=db.execute('INSERT INTO human_decisions(record_id,packet_id,record_digest,reviewer,decision,explanation,decided_at,attested) VALUES (?,?,?,?,?,?,?,?)',
                          (record_id,packet['id'],digest(record),username,decision,explanation,now(),int(attested)))
    return cursor.lastrowid


def verified_rows(db):
    schema(db)
    result=[]
    for record in records(db):
        row=db.execute('SELECT id,packet_id,record_digest,reviewer,decision,explanation,decided_at,attested FROM human_decisions WHERE record_id=? ORDER BY id DESC LIMIT 1',(record['id'],)).fetchone()
        if not row or row[4]!='approved' or row[7]!=1 or row[2]!=digest(record):continue
        active=db.execute('SELECT enabled FROM reviewers WHERE username=?',(row[3],)).fetchone()
        if not active or not active[0]:continue
        packet=next((p for p in packets(db) if p['id']==row[1]),None)
        if not packet or latest_packet(db,record['id'])['id']!=row[1] or approval_blockers(record,packet):continue
        result.append({**record,'human_approval_id':row[0],'human_reviewer':row[3],'human_verified_at':row[6],
                       'approval_explanation':row[5],'primary_evidence_sha256':packet['publisher_evidence']['sha256'],
                       'human_review_status':'approved_current_eligible',
                       'primary_evidence_url':packet['publisher_evidence']['url'],
                       'primary_document_license':packet['publisher_evidence']['license'],
                       'primary_document_license_url':packet['publisher_evidence']['license_url'],
                       'primary_document_title':packet['publisher_evidence']['document_title'],
                       'primary_document_date':packet['publisher_evidence']['document_date'],
                       'primary_declared_expiry':packet['publisher_evidence'].get('valid_until'),
                       'verification_scope':'Authorized human evidence/transcription review; not certification, scientific assurance or comparability'})
    return result


def review_state(db,record_id):
    record=get_record(db,record_id);packet=latest_packet(db,record_id)
    event=db.execute('SELECT packet_id,record_digest,decision FROM human_decisions WHERE record_id=? ORDER BY id DESC LIMIT 1',(record_id,)).fetchone()
    if not event or not packet or event[0]!=packet['id'] or event[1]!=digest(record):return 'awaiting_human_approval'
    if event[2]=='rejected':return 'rejected_by_authorized_human'
    return 'approved_current_eligible' if any(r['id']==record_id for r in verified_rows(db)) else 'approval_not_currently_eligible'
