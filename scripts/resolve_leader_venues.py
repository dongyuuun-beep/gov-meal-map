"""Map only globally unambiguous full restaurant names in new leader disclosures."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlencode
from data_store import read_snapshot, write_snapshot
from resolve_venues import norm, multiple
from city_sources import spending_city
ROOT=Path(__file__).resolve().parents[1]


def choose(data, merchant):
    places=data.get('place') or []
    if len(places)!=1 or int(data.get('place_totalcount') or len(places))!=1 or multiple(merchant):return None
    p=places[0]
    if norm(p.get('name'))!=norm(merchant) or p.get('openoff_status')=='N' or p.get('cate_name_depth1') not in ['음식점','카페']:return None
    try:lat,lng=float(p['lat']),float(p['lon'])
    except (KeyError,ValueError,TypeError):return None
    if not 33<lat<39 or not 124<lng<132:return None
    address=p.get('new_address') or p.get('address')
    if not address or not p.get('confirmid'):return None
    first=address.split()[0]
    region=next((x for x in ['서울','부산','대구','인천','광주','대전','울산','세종','경기','강원','충북','충남','전북','전남','경북','경남','제주'] if first.startswith(x)),None)
    if not region:return None
    return {'address':address,'address_match':'name_city','matched_merchant':p['name'],'spending_region':region,'spending_city':spending_city(address),'location':{'lat':lat,'lng':lng,'precision':'place','match_method':'name_city','evidence_url':'https://place.map.kakao.com/'+str(p['confirmid'])}}


def resolve(limit=40):
    data=read_snapshot(ROOT/'dist');path=ROOT/'config/leader-venue-locations.json'
    cache=json.loads(path.read_text()) if path.exists() else {}
    candidates=Counter(r['merchant'] for r in data['records'] if r.get('leader_role') and '고위직 공식 공개' in r.get('source_dataset','') and not r.get('location') and not multiple(r['merchant']) and len(norm(r['merchant']))>=3)
    pending=[name for name,_ in candidates.most_common() if name not in cache][:limit]
    failures=0
    for i,name in enumerate(pending):
        if i:time.sleep(1.1)
        url='https://search.map.kakao.com/mapsearch/map.daum?'+urlencode({'q':' '.join(name.split()),'msFlag':'A','sort':'0'})
        try:
            body=subprocess.check_output(['curl','-4','-fsSL','--connect-timeout','5','--max-time','15',url],stderr=subprocess.PIPE)
            result=json.loads(body)
            if 'place' not in result:raise ValueError('Map schema changed')
            cache[name]=choose(result,name);failures=0
            path.write_text(json.dumps(cache,ensure_ascii=False,indent=2)+'\n')
            if cache[name]:print('Matched',name,cache[name]['address'],flush=True)
        except Exception as exc:
            failures+=1
            if isinstance(exc,subprocess.CalledProcessError) and any(code in (exc.stderr or b'') for code in [b'403',b'429']):break
            if failures>=3:break
    changed=0
    for row in data['records']:
        match=cache.get(row['merchant'])
        if match and not row.get('location') and row.get('leader_role') and '고위직 공식 공개' in row.get('source_dataset','') and not row.get('address'):
            row['source_address']=None;row.update(match);changed+=1
    if changed:
        data['address_updated_at']=datetime.now(timezone.utc).isoformat();write_snapshot(ROOT/'dist',data)
    print('Leader venue locations added:',changed,flush=True)

if __name__=='__main__':resolve()
