from __future__ import annotations
import argparse, hashlib, json, re, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / 'data' / 'input'
OUTPUT = ROOT / 'data' / 'output'
DB = OUTPUT / 'cos_carbon_data.sqlite'
OUTPUT.mkdir(parents=True, exist_ok=True)

SCHEMA = '''
CREATE TABLE IF NOT EXISTS source_files (
 file_hash TEXT PRIMARY KEY, file_name TEXT, source_path TEXT,
 imported_at TEXT, sheet_name TEXT, rows_seen INTEGER, notes TEXT
);
CREATE TABLE IF NOT EXISTS carbon_records (
 record_id TEXT PRIMARY KEY, product_name TEXT, factor_value REAL,
 original_unit TEXT, normalized_value REAL, normalized_unit TEXT,
 geography TEXT, reference_year TEXT, lifecycle_boundary TEXT,
 data_type TEXT, source_name TEXT, source_url TEXT, source_record_id TEXT,
 licence TEXT, verification_status TEXT NOT NULL DEFAULT 'Pending review',
 hs_code TEXT, hs_match_status TEXT DEFAULT 'Not matched',
 validation_flags TEXT, raw_record_json TEXT, collected_at TEXT,
 reviewer TEXT, review_decision TEXT, review_notes TEXT
);
CREATE TABLE IF NOT EXISTS collection_log (
 id INTEGER PRIMARY KEY AUTOINCREMENT, event_time TEXT, file_name TEXT,
 outcome TEXT, rows_seen INTEGER, details TEXT
);
'''

def now(): return datetime.now(timezone.utc).isoformat()
def db_connect():
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    return con

def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def clean_text(value):
    if pd.isna(value): return None
    value = str(value).strip()
    return value or None

def norm_col(value):
    return re.sub(r'[^a-z0-9]+', '_', str(value).lower()).strip('_')

def find_column(columns, candidates):
    normalized = {c: norm_col(c) for c in columns}
    for candidate in candidates:
        for original, normalized_name in normalized.items():
            if normalized_name == candidate or candidate in normalized_name:
                return original
    return None

def detect_columns(df):
    cols = list(df.columns)
    return {
      'product_name': find_column(cols, ['product_name','product','activity','material','description','name','generic_name']),
      'factor_value': find_column(cols, ['factor_value','emission_factor','carbon_footprint','co2e','kg_co2e','ghg_factor','value']),
      'original_unit': find_column(cols, ['original_unit','unit','units','denominator','functional_unit']),
      'geography': find_column(cols, ['geography','country','region','location']),
      'reference_year': find_column(cols, ['reference_year','year','publication_year']),
      'lifecycle_boundary': find_column(cols, ['lifecycle_boundary','boundary','scope','lifecycle_stage']),
      'hs_code': find_column(cols, ['hs_code','hs6','commodity_code','harmonized_system']),
      'source_url': find_column(cols, ['source_url','url','reference_url','link']),
      'licence': find_column(cols, ['licence','license','terms']),
      'data_type': find_column(cols, ['data_type','record_type','factor_type'])
    }

def flags_for(record):
    flags=[]
    v=record.get('factor_value')
    if v is None or pd.isna(v): flags.append('NO_NUMERIC_FACTOR')
    else:
        try:
            n=float(v)
            if n != n or n in (float('inf'), float('-inf')): flags.append('NON_FINITE_FACTOR')
            elif n < 0: flags.append('NEGATIVE_VALUE_REVIEW')
        except (ValueError,TypeError): flags.append('INVALID_FACTOR_VALUE')
    for field in ['product_name','original_unit','source_name','source_url','geography','reference_year','lifecycle_boundary','licence']:
        if not clean_text(record.get(field)): flags.append('MISSING_'+field.upper())
    if not clean_text(record.get('data_type')): flags.append('MISSING_DATA_TYPE')
    return sorted(set(flags))

def convert_mass_factor(value, unit):
    """Only safe mass-denominator conversions. Never infer a product footprint."""
    try: value=float(value)
    except (ValueError,TypeError): return None,None
    unit=(unit or '').strip().lower().replace('₂','2')
    mapping={
      'kg co2e/kg': (1.0,'kg CO2e/kg'),
      'kg co2e/tonne': (0.001,'kg CO2e/kg'),
      'kg co2e/tonne of product': (0.001,'kg CO2e/kg'),
      't co2e/tonne': (1.0,'kg CO2e/kg'),
      'tonne co2e/tonne': (1.0,'kg CO2e/kg'),
    }
    if unit not in mapping: return None,None
    multiplier,out_unit=mapping[unit]
    return value*multiplier,out_unit

def import_file(path: Path, sheet=None):
    if path.suffix.lower() not in ['.xlsx','.xls','.csv']:
        return 0, f'Skipped unsupported file type: {path.name}'
    digest=file_hash(path)
    with db_connect() as con:
        if con.execute('SELECT 1 FROM source_files WHERE file_hash=?',(digest,)).fetchone():
            return 0, f'Already imported (same content hash): {path.name}'
    try:
        if path.suffix.lower()=='.csv': sheets={'CSV':pd.read_csv(path)}
        else:
            book=pd.ExcelFile(path)
            if sheet and sheet not in book.sheet_names: raise ValueError(f'Sheet {sheet!r} not found. Sheets: {book.sheet_names}')
            sheets={s:pd.read_excel(path,sheet_name=s) for s in ([sheet] if sheet else book.sheet_names)}
    except Exception as e: return 0, f'Could not read {path.name}: {e}'
    total=0; details=[]
    with db_connect() as con:
        for sheet_name, df in sheets.items():
            if df.empty: details.append(f'{sheet_name}: empty'); continue
            mapping=detect_columns(df)
            if not mapping['factor_value'] or not mapping['original_unit']:
                details.append(f'{sheet_name}: stored in source file only; factor/unit columns not confidently detected')
                continue
            for _, row in df.iterrows():
                raw={str(k): (None if pd.isna(v) else (v.item() if hasattr(v,'item') else v)) for k,v in row.to_dict().items()}
                get=lambda key: row[mapping[key]] if mapping.get(key) else None
                try: value=float(get('factor_value')) if clean_text(get('factor_value')) else None
                except (ValueError,TypeError): value=None
                unit=clean_text(get('original_unit'))
                normalized,normalized_unit=convert_mass_factor(value,unit)
                record={
                  'product_name':clean_text(get('product_name')) or f'Unlabelled row {int(_)+1}',
                  'factor_value':value,'original_unit':unit,'normalized_value':normalized,'normalized_unit':normalized_unit,
                  'geography':clean_text(get('geography')),'reference_year':clean_text(get('reference_year')),
                  'lifecycle_boundary':clean_text(get('lifecycle_boundary')),
                  'data_type':clean_text(get('data_type')) or 'Unclassified source factor',
                  'source_name':path.stem,'source_url':clean_text(get('source_url')),
                  'source_record_id':None,'licence':clean_text(get('licence')),
                  'hs_code':clean_text(get('hs_code')),'raw':raw}
                record['validation_flags']=flags_for(record)
                identity='|'.join([digest,sheet_name,str(_),json.dumps(raw,sort_keys=True,default=str)])
                rid=hashlib.sha256(identity.encode()).hexdigest()[:24]
                con.execute('''INSERT OR IGNORE INTO carbon_records
                  (record_id,product_name,factor_value,original_unit,normalized_value,normalized_unit,geography,reference_year,lifecycle_boundary,data_type,source_name,source_url,source_record_id,licence,verification_status,hs_code,hs_match_status,validation_flags,raw_record_json,collected_at)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
                    rid,record['product_name'],value,unit,normalized,normalized_unit,record['geography'],record['reference_year'],record['lifecycle_boundary'],record['data_type'],record['source_name'],record['source_url'],None,record['licence'],'Pending review',record['hs_code'],'Pending human review' if record['hs_code'] else 'Not matched',json.dumps(record['validation_flags']),json.dumps(raw,default=str,ensure_ascii=False),now()))
                total+=1
            details.append(f'{sheet_name}: {len(df)} rows; detected columns={mapping}')
        con.execute('INSERT INTO source_files VALUES (?,?,?,?,?,?,?)',(digest,path.name,str(path),now(),','.join(sheets.keys()),total,' | '.join(details)))
        con.execute('INSERT INTO collection_log(event_time,file_name,outcome,rows_seen,details) VALUES (?,?,?,?,?)',(now(),path.name,'Imported' if total else 'Metadata only / review required',total,' | '.join(details)))
    return total, ' | '.join(details)

def import_all():
    files=[p for p in INPUT.iterdir() if p.is_file() and p.suffix.lower() in ['.xlsx','.xls','.csv']]
    if not files:
        print(f'No .xlsx, .xls or .csv files found. Copy files into: {INPUT}')
        return
    for path in files:
        n,msg=import_file(path)
        print(f'\n{path.name}: {n} rows imported/processed\n{msg}')

def export_all():
    with db_connect() as con:
        all_df=pd.read_sql_query('SELECT * FROM carbon_records',con)
        logs=pd.read_sql_query('SELECT * FROM collection_log',con)
        files=pd.read_sql_query('SELECT * FROM source_files',con)
    all_df.to_csv(OUTPUT/'all_carbon_records.csv',index=False)
    all_df[all_df['verification_status'].isin(['Published','Verified product footprint','Approved activity factor','Estimated'])].to_csv(OUTPUT/'approved_status_records.csv',index=False)
    logs.to_csv(OUTPUT/'collection_log.csv',index=False)
    files.to_csv(OUTPUT/'imported_source_files.csv',index=False)
    with pd.ExcelWriter(OUTPUT/'COS_Carbon_Data_Collection.xlsx',engine='openpyxl') as writer:
        all_df.to_excel(writer,sheet_name='All Records',index=False)
        all_df[all_df['verification_status'].isin(['Published','Verified product footprint','Approved activity factor','Estimated'])].to_excel(writer,sheet_name='Approved Status',index=False)
        logs.to_excel(writer,sheet_name='Collection Log',index=False)
        files.to_excel(writer,sheet_name='Source Files',index=False)
    flags=all_df['validation_flags'].fillna('[]').value_counts().rename_axis('flags').reset_index(name='records') if not all_df.empty else pd.DataFrame(columns=['flags','records'])
    report=[f'COS Carbon Data Tool report — {now()}',f'Total records: {len(all_df)}',f'Pending review: {(all_df.verification_status=="Pending review").sum() if not all_df.empty else 0}',f'Imported source files: {len(files)}','', 'Validation flag groups:',flags.to_string(index=False)]
    (OUTPUT/'run_report.txt').write_text('\n'.join(report),encoding='utf-8')
    print('Exports created in:',OUTPUT)
    print('\n'.join(report[:5]))

def status():
    with db_connect() as con:
        for table in ['source_files','carbon_records','collection_log']:
            count=con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            print(f'{table}: {count}')
        df=pd.read_sql_query('SELECT verification_status, COUNT(*) AS records FROM carbon_records GROUP BY verification_status',con)
    if not df.empty: print('\nStatuses:\n',df.to_string(index=False))

def main():
    parser=argparse.ArgumentParser(description='COS Carbon Data Collection Tool (local Windows CLI)')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('init',help='Create database tables')
    sub.add_parser('import',help='Import supported files from data/input')
    sub.add_parser('export',help='Export Excel/CSV/report files')
    sub.add_parser('run',help='Run import, status and export')
    sub.add_parser('status',help='Show database counts')
    args=parser.parse_args()
    db_connect().close()
    if args.command=='init': print('Database initialized at',DB)
    elif args.command=='import': import_all()
    elif args.command=='export': export_all()
    elif args.command=='status': status()
    elif args.command=='run': import_all(); status(); export_all()

if __name__=='__main__': main()
