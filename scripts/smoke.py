"""Cross-platform offline smoke runner; all databases are isolated temporary files."""
from contextlib import closing
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import tempfile
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    subprocess.run([sys.executable, '-m', 'gcc_cos', *map(str,args)], cwd=ROOT, check=True)


def main():
    with tempfile.TemporaryDirectory(prefix='gcc-cos-smoke-') as temporary:
        work=Path(temporary); database=work/'offline.sqlite'
        for phase in ('phase2','phase3'):
            run('--db',database,'--registry',ROOT/f'examples/{phase}/sources.json','ingest',
                '--manifest',ROOT/f'examples/{phase}/local-files.json')
        run('--db',database,'revalidate')
        for suffix in ('csv','xlsx','sqlite'):
            run('--db',database,'export',work/('products.'+suffix),'--products-only')
        assert len(pd.read_csv(work/'products.csv'))==1241
        assert len(pd.read_excel(work/'products.xlsx'))==1241
        with closing(sqlite3.connect(work/'products.sqlite')) as db:
            assert db.execute('SELECT count(*) FROM records').fetchone()[0]==1241
            assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert db.execute('PRAGMA foreign_key_check').fetchall()==[]
        run('--db',database,'audit','--output-dir',work/'audit')
        summary=json.loads((work/'audit/summary.json').read_text())
        assert summary['product_observations']==1241
        assert summary['traceable_source_rows']==1241
        assert summary['independently_verified']==0
        run('--db',database,'review-prepare','--batch','smoke','--size','20')
        run('--db',database,'review-workbook',work/'human-review.xlsx','--batch','smoke','--templates-dir',work/'templates')
        run('--db',database,'export',work/'verified-only.xlsx','--verified-only')
        assert len(pd.read_excel(work/'human-review.xlsx',sheet_name='Human review'))==20
        assert len(pd.read_excel(work/'verified-only.xlsx'))==0
        result={'human_review_selected':20,'verified_only_records':0,'os':platform.system(),'python':platform.python_version(),'product_observations':1241,
                'csv_excel_sqlite_audit':'passed','native_windows_execution':os.name=='nt'}
        print(json.dumps(result))
        if output:=os.environ.get('GCC_SMOKE_REPORT'):
            target=Path(output)
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':
    main()
