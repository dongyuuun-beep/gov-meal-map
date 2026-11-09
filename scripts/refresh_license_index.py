"""Refresh latest 10,000 active license rows; keep earlier observed address evidence."""
import gzip,json
from pathlib import Path
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from collect import fetch
from more_sources import loose_json
ROOT=Path(__file__).resolve().parents[1]
def refresh():
    from pyproj import Transformer
    transform=Transformer.from_crs(5174,4326,always_xy=True).transform
    target=ROOT/'config/restaurant-index.json.gz'
    data=json.loads(gzip.decompress(target.read_bytes())) if target.exists() else {'rows':[]}
    combined={r['MGTNO']:r for r in data['rows']}
    def page(n):
        url='https://data.seoul.go.kr/dataList/dataView.do?'+urlencode(dict(infId='OA-16094',srvType='S',serviceKind=0,ssUserId='SAMPLE_VIEW',onepagerow=1000,pageNo=n,filterCol='TRDSTATEGBN',txtFilter='01'))
        return loose_json(fetch(url))['list']
    with ThreadPoolExecutor(2) as pool:
        batches=list(pool.map(page,range(1,92,10)))
    for batch in batches:
        for r in batch:
            try:lng,lat=transform(float(r['X']),float(r['Y']))
            except (ValueError,KeyError,TypeError):continue
            if not(126.7<lng<127.3 and 37.4<lat<37.8):continue
            item={k:r.get(k) for k in ['MGTNO','BPLCNM','RDNWHLADDR','SITEWHLADDR']};item.update(lat=lat,lng=lng);combined[r['MGTNO']]=item
    data.update(rows=list(combined.values()),updated_at=datetime.now(timezone.utc).isoformat(),source='https://data.seoul.go.kr/dataList/OA-16094/S/1/datasetView.do',source_crs='EPSG:5174')
    temp=target.with_suffix('.tmp');temp.write_bytes(gzip.compress(json.dumps(data,ensure_ascii=False,separators=(',',':')).encode(),mtime=0));temp.replace(target)
    print('License address index',len(data['rows']))
if __name__=='__main__':refresh()
