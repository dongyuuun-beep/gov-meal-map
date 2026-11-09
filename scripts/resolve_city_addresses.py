"""Resolve explicit four-city addresses via exact OSM address matches (at most 40/month)."""
import json,re,subprocess,time
from pathlib import Path
from urllib.parse import urlencode
from city_sources import spending_city
from data_store import read_snapshot,write_snapshot
ROOT=Path(__file__).resolve().parents[1]

def address_parts(address):
 city=spending_city(address)
 m=re.search(r'([가-힣0-9·]+(?:대로|로|길))\s*(\d+(?:-\d+)?)',address or '')
 return (city,m[1],m[2]) if city and m else None

def key(parts):return '경기|'+'|'.join(parts)

def exact_match(features,parts):
 city,road,number=parts;matches=[]
 for f in features:
  a=f.get('address',{})
  area=' '.join(a.get(k,'') for k in ['city','county','municipality'])
  if a.get('country_code')!='kr' or city+'시' not in area.replace('특례',''):continue
  if a.get('road','').replace(' ','')!=road or a.get('house_number')!=number:continue
  lat,lng=float(f['lat']),float(f['lon'])
  if not 36.8<lat<37.5 or not 126.5<lng<127.6:continue
  matches.append(f)
 if not matches:return None
 if max(float(f['lat']) for f in matches)-min(float(f['lat']) for f in matches)>.0015 or max(float(f['lon']) for f in matches)-min(float(f['lon']) for f in matches)>.0015:return None
 f=matches[0]
 if f.get('osm_type') not in ['node','way','relation']:return None
 return dict(lat=float(f['lat']),lng=float(f['lon']),precision='address',spending_city=city,matched_address='경기도 '+city+'시 '+road+' '+number,evidence_url='https://www.openstreetmap.org/'+f['osm_type']+'/'+str(f['osm_id']))

def resolve(limit=40):
 data=read_snapshot(ROOT/'dist');path=ROOT/'config/address-locations.json';cache=json.loads(path.read_text());queries={}
 for r in data['records']:
  p=address_parts(r.get('address'))
  if not p:continue
  old=cache.get(key(p)) or cache.get('경기|'+'|'.join(p[1:]))
  if not old or old.get('spending_city')!=p[0]:queries[key(p)]=p
 matches=0;failures=0
 for i,(k,p) in enumerate(list(queries.items())[:limit]):
  if i:time.sleep(1.1) # Respect the public Nominatim service's maximum 1 request/second.
  url='https://nominatim.openstreetmap.org/search?'+urlencode(dict(q='경기도 '+p[0]+'시 '+p[1]+' '+p[2],format='jsonv2',addressdetails=1,limit=5,countrycodes='kr'))
  try:
   body=subprocess.check_output(['curl','-4','-fsSL','--connect-timeout','5','--max-time','12','-A','GovMealMap/0.1 (+https://github.com/dongyuuun-beep/gov-meal-map)',url],stderr=subprocess.PIPE)
   match=exact_match(json.loads(body),p)
   if match:cache[k]=match;matches+=1
   failures=0
  except Exception as e:
   failures+=1
   print('Address lookup unavailable:',type(e).__name__,flush=True)
   if failures>=3:break # Retain the expense update during a geocoder outage.
 changed=False
 for r in data['records']:
  p=address_parts(r.get('address'))
  if not p or re.search(r',| 및 |등\s*\d+\s*개소',r['merchant']):continue
  loc=cache.get(key(p)) or cache.get('경기|'+'|'.join(p[1:]))
  if loc and loc.get('spending_city')==p[0]:
   if r.get('location')!=loc or r.get('spending_city')!=p[0]:changed=True
   r.update(location=loc,spending_city=p[0],spending_region='경기')
 path.write_text(json.dumps(cache,ensure_ascii=False,indent=2)+'\n')
 if changed:write_snapshot(ROOT/'dist',data)
 print('New exact city address matches:',matches,'; pending unique addresses:',len(queries)-matches,flush=True)

if __name__=='__main__':resolve()
