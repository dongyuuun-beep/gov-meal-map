"""Link disclosed addresses and unambiguous city/name matches to public place records."""
import json,re,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter,deque
from urllib.parse import urlencode
from data_store import read_snapshot,write_snapshot
from resolve_city_addresses import address_parts as road_parts
from city_sources import spending_city,CITY_DISTRICTS
ROOT=Path(__file__).resolve().parents[1]
CITY=['화성','용인','수원']
def address_parts(address):
 if not address:return None
 city=spending_city(address)
 if not city:
  for c,ds in CITY_DISTRICTS.items():
   if any(address.strip().startswith(d) for d in ds):city=c;break
 if not city:return None
 compact=address
 for token in ['경기도',city+'특례시',city+'시',*CITY_DISTRICTS.get(city,())]:compact=compact.replace(token,' ')
 compact=re.sub(r'([가-힣]+(?:읍|면))',r'\1 ',compact)
 normalized=city+'시 '+' '.join(compact.split())
 road=road_parts(normalized)
 if road:return road
 lot=re.search(r'([가-힣0-9]+(?:동|리))\s*(산\s*)?(\d+(?:-\d+)?)',compact)
 if not lot:return None
 town=re.search(r'([가-힣]+(?:읍|면))',compact)
 return (city,'lot',town[1] if town else '',lot[1],'산' if lot[2] else '',lot[3])

def norm(s):
 s=re.sub(r'주식회사|유한회사|농업회사법인|㈜|\(주\)|\(유\)','',s or '')
 s=re.sub(r'[^가-힣a-z0-9]','',s.lower())
 for old,new in [('이디야커피','이디야'),('메가엠지씨커피','메가커피'),('메가mgc커피','메가커피'),('컴포즈커피','컴포즈'),('할리스커피','할리스')]:s=s.replace(old,new)
 return s
def multiple(s):return bool(re.search(r'외\s*\d|등\s*\d|[,/]| 및 ',s))
def compatible(original,matched):
 hints=re.findall(r'(?:^|\s)([가-힣]+(?:시|구|읍|면|동))(?=\s|$)',original or '')
 return all(h.replace('특례','') in (matched or '').replace('특례','') for h in hints)

def position(p):
 try:lat,lng=float(p['lat']),float(p['lon'])
 except (KeyError,TypeError,ValueError):return False
 return 36.8<lat<37.6 and 126.5<lng<127.6 and (lat!=int(lat) and lng!=int(lng))
def choose(response,city,merchant,address=None):
 parts=address_parts(address)
 if parts:
  found=[p for p in response.get('address',[]) if position(p) and address_parts(p.get('addr'))==parts and compatible(address,p.get('addr'))]
  if found:
   if max(float(p['lat']) for p in found)-min(float(p['lat']) for p in found)>.0015 or max(float(p['lon']) for p in found)-min(float(p['lon']) for p in found)>.0015:return None
   p=found[0];return dict(address=address,spending_city=city,spending_region='경기',address_match='source_address',location=dict(lat=float(p['lat']),lng=float(p['lon']),precision='address',match_method='source_address',evidence_url='https://map.kakao.com/?'+urlencode({'q':p['addr']})))
  return None
 if multiple(merchant) or len(norm(merchant))<3:return None
 places=response.get('place',[])
 # Generic names need a single search result; branch names must still match in full.
 if not merchant.strip().endswith('점') and (len(places)!=1 or int(response.get('place_totalcount') or len(places))!=1):return None
 found=[p for p in places if position(p) and city+'시' in (p.get('new_address') or p.get('address','')) and norm(p.get('name'))==norm(merchant) and p.get('openoff_status')!='N' and p.get('cate_name_depth1') in ['음식점','카페']]
 if len({p.get('confirmid') for p in found})!=1:return None
 p=found[0];addr=p.get('new_address') or p.get('address');return dict(address=addr,spending_city=city,spending_region='경기',address_match='name_city',matched_merchant=p['name'],location=dict(lat=float(p['lat']),lng=float(p['lon']),precision='place',match_method='name_city',evidence_url='https://place.map.kakao.com/'+str(p['confirmid'])))
def resolve(limit=150,per_city_limit=None):
 data=read_snapshot(ROOT/'dist')
 for r in data['records']:
  if r.get('location',{} ) and r['location'].get('match_method')=='name_city' and not compatible(r.get('source_address'),r.get('address')):
   r.update(location=None,address=r.get('source_address'),address_match=None,spending_city=None,spending_region=None)
 path=ROOT/'config/venue-locations.json';cache=json.loads(path.read_text()) if path.exists() else {};queries={};counts=Counter()
 # Explicit addresses include expenses of other institutions visiting these cities.
 for r in data['records']:
  p=address_parts(r.get('source_address',r.get('address')))
  if p and p[0] in CITY and (not r.get('location') or r.get('address_match')=='name_city') and not multiple(r['merchant']):
   k='address|'+'|'.join(p);queries[k]=(p[0],r['merchant'],r.get('address'))
 for city in CITY:
  names=Counter(r['merchant'] for r in data['records'] if r.get('source_city')==city and not r.get('location') and not multiple(r['merchant']))
  fresh=[(name,count) for name,count in names.most_common() if 'name|'+city+'|'+name not in cache]
  for merchant,_ in fresh[:per_city_limit if per_city_limit is not None else 80 if city=='화성' else 45]:
   if len(norm(merchant))>=3:queries['name|'+city+'|'+merchant]=(city,merchant,None)
 buckets={city:deque((k,v) for k,v in queries.items() if k not in cache and v[0]==city) for city in CITY};pending=[]
 while any(buckets.values()):
  for city in CITY:
   if buckets[city]:pending.append(buckets[city].popleft())
 failures=0
 for i,(k,(city,merchant,address)) in enumerate(pending[:limit]):
  if i:time.sleep(1.05)
  q=address if address else city+'시 '+' '.join(merchant.split())
  u='https://search.map.kakao.com/mapsearch/map.daum?'+urlencode(dict(q=q,msFlag='A',sort='0'))
  try:
   b=subprocess.check_output(['curl','-4','-fsSL','--connect-timeout','5','--max-time','15',u],stderr=subprocess.PIPE);result=json.loads(b)
   if not isinstance(result,dict) or 'place' not in result or 'address' not in result:raise ValueError('Unexpected map response')
   match=choose(result,city,merchant,address)
   cache[k]=match;failures=0
   if match:counts[city]+=1;print('Matched',city,merchant,match['address'],flush=True)
  except Exception as e:
   failures+=1;print('Lookup failed',type(e).__name__,flush=True)
   if isinstance(e,subprocess.CalledProcessError) and any(code in (e.stderr or b'') for code in [b'429',b'403']):break
   if failures>=3:break
  path.write_text(json.dumps(cache,ensure_ascii=False,indent=2)+'\n')
 changed=False
 for r in data['records']:
  if multiple(r['merchant']):continue
  original=r.get('source_address',r.get('address'));p=address_parts(original);match=None
  if p:match=cache.get('address|'+'|'.join(p))
  if not match and r.get('source_city') in CITY and not p:match=cache.get('name|'+r['source_city']+'|'+r['merchant'])
  if match and (not r.get('location') or (match.get('address_match')=='source_address' and r.get('address_match')=='name_city')):
   if not compatible(original,match['address']):continue
   r['source_address']=original;r.update(match);changed=True
 if changed:
  data['expense_updated_at']=data.get('expense_updated_at',data['updated_at']);data['updated_at']=datetime.now(timezone.utc).isoformat();data['address_updated_at']=data['updated_at'];write_snapshot(ROOT/'dist',data)
 print('New address/venue matches',dict(counts),flush=True)
if __name__=='__main__':resolve()
