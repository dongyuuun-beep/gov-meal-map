"""Backfill official city history once; daily collection keeps the archive."""
import sys,json,collections
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from collect import fetch,record
from city_sources import collect_city,CITY_HISTORY_PAGES as CITY_PAGES
from data_store import read_snapshot,write_snapshot
ROOT=Path(__file__).resolve().parents[1];s=read_snapshot(ROOT/'dist');old={r['id']:r for r in s['records']};results=[];done=set();status=[]
with ThreadPoolExecutor(2) as pool:
 jobs={pool.submit(collect_city,city,fetch,record,True):city for city in ['화성','용인','수원']}
 for job in as_completed(jobs):
  city=jobs[job]
  try:
   rows,errors,complete=job.result();results+=rows;done.update(complete);status.append(dict(source=city+'시 최신 '+str(CITY_PAGES[city][0]*CITY_PAGES[city][1])+'게시글',status='partial' if errors else 'success',rows=len(rows),failed_files=errors));print(city,len(rows),'rows',len(errors),'failed files',flush=True)
  except Exception as e:
   status.append(dict(source=city+'시 과거 수집',status='failed',error=str(e)));print(city,'FAILED',str(e),flush=True)
if not results and not done:raise RuntimeError('All city history sources failed; previous snapshot retained')
rows={r['id']:r for r in s['records'] if r.get('source_post_url') not in done and r.get('source_file_key') not in done};now=datetime.now(timezone.utc).isoformat()
for r in results:
 prev=old.get(r['id'],{});r.update(collected_at=prev.get('collected_at',now),source_license=prev.get('source_license','공개 원문 사실 추출 · 원문 링크 제공'))
 # Reuse a location only for an unchanged counterparty and original address.
 if r.get('source_merchant',r['merchant'])==prev.get('source_merchant',prev.get('merchant')) and r.get('address')==prev.get('source_address',prev.get('address')):
  for k in ['address','source_address','address_match','matched_merchant','location','spending_city','spending_region']:
   if not r.get(k) and prev.get(k):r[k]=prev[k]
 rows[r['id']]=r
s.update(records=sorted(rows.values(),key=lambda r:(r.get('date') or '',r['id']),reverse=True),updated_at=now);s['source_status']=[st for st in s['source_status'] if not any(st['source'].startswith(c+'시 ') for c in ['화성','용인','수원'])]+status
s['scope']='서울 본청 공개 이력 · 화성 300게시글·화성시의회 10개월 · 용인·수원 200게시글씩 · 세종·평택·울산·경기도 일부. 전국 전수 아님.'
write_snapshot(ROOT/'dist',s);print('TOTAL',len(rows),'unique expense records',flush=True)
