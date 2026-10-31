"""Local installation diagnostics. Never infers a Windows application-test result."""
import argparse
from contextlib import closing
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
PACKAGES=('pandas','openpyxl','pypdf','requests','streamlit','pytest')


def diagnose():
    result={'os':platform.system(),'python':platform.python_version(),'native_windows_diagnostic':os.name=='nt',
            'native_windows_application_tests':'not_inferred_from_diagnostics',
            'virtual_environment':sys.prefix!=sys.base_prefix,'checks':{},'packages':{},'network_requests_performed':False}
    checks=result['checks'];checks['python_supported']=sys.version_info>=(3,11)
    for name in PACKAGES:
        try:result['packages'][name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:result['packages'][name]='not_installed'
    checks['dependencies_present']=all(v!='not_installed' for v in result['packages'].values())
    checks['project_files_present']=all((ROOT/p).is_file() for p in ('requirements.txt','dashboard.py','gcc_cos/__main__.py'))
    try:
        (ROOT/'data').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='gcc-diagnostic-',dir=ROOT/'data') as temporary:
            path=Path(temporary);text='GCC-COS diagnostic — international text: é'
            (path/'utf8.txt').write_text(text,encoding='utf-8')
            checks['project_data_writable_utf8']=(path/'utf8.txt').read_text(encoding='utf-8')==text
            with closing(sqlite3.connect(path/'test.sqlite')) as db:
                db.execute('CREATE TABLE diagnostics(message TEXT)');db.execute('INSERT INTO diagnostics VALUES (?)',(text,));db.commit()
                checks['sqlite_write_integrity']=db.execute('SELECT message FROM diagnostics').fetchone()[0]==text and db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            if checks['dependencies_present']:
                import pandas as pd
                frame=pd.DataFrame({'diagnostic_text':[text]})
                frame.to_csv(path/'test.csv',index=False,encoding='utf-8-sig')
                frame.to_excel(path/'test.xlsx',index=False)
                checks['csv_excel_utf8_roundtrip']=pd.read_csv(path/'test.csv').iloc[0,0]==text and pd.read_excel(path/'test.xlsx').iloc[0,0]==text
    except Exception as exc:
        checks['filesystem_or_roundtrip']=False;result['local_error_type']=type(exc).__name__
    if checks['dependencies_present']:
        completed=subprocess.run([sys.executable,'-m','pip','check'],capture_output=True,text=True,cwd=ROOT)
        checks['pip_consistency']=completed.returncode==0
        completed=subprocess.run([sys.executable,'-m','gcc_cos','--help'],capture_output=True,text=True,cwd=ROOT)
        checks['cli_loads']=completed.returncode==0
    result['diagnostic_passed']=all(checks.values())
    result['next_action']='Run the full tests and scripts/smoke.py; diagnostics alone do not establish application readiness' if result['diagnostic_passed'] else 'Create the virtual environment and install requirements.txt; inspect failed local checks'
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='reports/phase4/diagnostics.json');args=parser.parse_args()
    output=Path(args.output)
    if output.suffix.lower()!='.json':parser.error('Choose a .json diagnostic report')
    result=diagnose();output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2));return 0 if result['diagnostic_passed'] else 1

if __name__=='__main__':raise SystemExit(main())
