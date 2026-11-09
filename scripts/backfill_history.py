"""One-time official history and license backfill; monthly refresh stays incremental.

Run with requirements-geodata.txt installed. Raw cache is not published.
"""
import argparse,gzip,json,time,math
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode
from datetime import datetime,timezone
from collect import fetch,record
from more_sources import loose_json,normalize_seoul
from license_locations import build_index,match_location
from data_store import read_snapshot,write_snapshot
ROOT=Path(__file__).resolve().parents[1]
def download(cache,kind,page):
    target=cache/f'{kind}-{page}.json.gz'
    if target.exists():return json.loads(gzip.decompress(target.read_bytes()))
    params=dict(infId='OA-22156' if kind=='expense' else 'OA-16094',srvType='S',serviceKind=0,ssUserId='SAMPLE_VIEW',onepagerow=1000,pageNo=page)
    if kind=='expense':params['strOrderby']='EXEC_YR DESC, EXEC_MONTH DESC, EXEC_DT DESC'
    else:params.update(filterCol='TRDSTATEGBN',txtFilter='01')
    for attempt in range(3):
        try:
            data=loose_json(fetch('https://data.seoul.go.kr/dataList/dataView.do?'+urlencode(params)))
            if data.get('result')!='ok' or not isinstance(data.get('list'),list):raise ValueError('Official source list missing')
            target.write_bytes(gzip.compress(json.dumps(data,ensure_ascii=False).encode(),mtime=0));return data
        except Exception:
            if attempt==2:raise
            time.sleep(2)
def dataset(cache,kind):
    first=download(cache,kind,1);total=first['page']['totalCount'];page_count=first['page']['pageCount']
    # Server advances 100 source rows per pageNo but returns 1,000 rows per request.
    # Advancing pageNo by 1 would silently repeat 900 rows. Use 10 + RONUM dedup.
    step=len(first['list'])//math.ceil(total/page_count)
    if step!=10:raise ValueError('Official pagination changed; inspect source RONUM before backfill')
    with ThreadPoolExecutor(3) as pool:pages=list(pool.map(lambda n:download(cache,kind,n),range(1,page_count+1,step)))
    rows={}
    for page in pages:
        for row in page['list']:
            key=tuple(row.get(k) for k in ('RONUM','NID','EXEC_DT','EXEC_LOC','EXEC_AMOUNT','EXEC_PURPOSE')) if kind=='expense' else row['MGTNO']
            rows[key]=row
    if len(rows)!=total:raise ValueError(f'Incomplete {kind} snapshot: {len(rows)} / {total}; refresh raw cache')
    return list(rows.values())
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cache-directory',default=str(ROOT/'data/raw/bulk'));args=parser.parse_args()
    cache=Path(args.cache_directory);cache.mkdir(parents=True,exist_ok=True)
    from pyproj import Transformer
    expenses=dataset(cache,'expense');licenses=dataset(cache,'food')
    transform=Transformer.from_crs(5174,4326,always_xy=True).transform
    compact=[]
    for r in licenses:
        try:lng,lat=transform(float(r['X']),float(r['Y']))
        except (ValueError,KeyError,TypeError):continue
        if not(126.7<lng<127.3 and 37.4<lat<37.8):continue
        item={k:r.get(k) for k in ['MGTNO','BPLCNM','RDNWHLADDR','SITEWHLADDR']};item.update(lat=lat,lng=lng);compact.append(item)
    now=datetime.now(timezone.utc).isoformat()
    idx={'rows':compact,'source':'https://data.seoul.go.kr/dataList/OA-16094/S/1/datasetView.do','source_crs':'EPSG:5174','updated_at':now}
    (ROOT/'config/restaurant-index.json.gz').write_bytes(gzip.compress(json.dumps(idx,ensure_ascii=False,separators=(',',':')).encode(),mtime=0))
    index=build_index(compact,None)
    records=normalize_seoul([expenses],record)
    for r in records:
        r['location']=match_location(r,index);r['collected_at']=now
        if r['date']=='1970-01-01':r['source_date']=r['date'];r['date']=None
    previous=read_snapshot(ROOT/'dist')
    # Replace earlier Seoul imports entirely, removing artificial page-overlap copies.
    combined={r['id']:r for r in previous['records'] if r['institution']!='서울특별시'}
    combined.update({r['id']:r for r in records})
    records=sorted(combined.values(),key=lambda r:(r['date'] or '',r['id']),reverse=True)
    snapshot={'updated_at':now,'scope':'서울시 본청 2023~2026년 공개 지출 이력 + 최신 자료 갱신 · 세종시의회 · 울산시장 · 경기도 예시. 전국 전수 아님.','source_status':[{'source':'서울시 본청 과거 지출','status':'success','official_rows':len(expenses),'food_rows':sum(r['institution']=='서울특별시' for r in records)},{'source':'서울시 일반음식점 인허가 좌표','status':'success','official_rows':len(licenses),'coordinate_rows':len(compact)}],'records':records}
    write_snapshot(ROOT/'dist',snapshot)
    points={(r['location']['lat'],r['location']['lng']) for r in records if r.get('location')}
    print('Published snapshot:',len(records),'records;',len(points),'unique coordinate points')
    if len(points)<2000:raise ValueError('Less than 2,000 verified coordinate points')
if __name__=='__main__':main()
