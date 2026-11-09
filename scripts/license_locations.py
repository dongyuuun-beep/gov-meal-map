"""Match disclosed Seoul addresses to public restaurant-license coordinates.

Input coordinates: Seoul OA-16094, EPSG:5174. Output: EPSG:4326.
No fuzzy business-name matching or random point offsets.
"""
import re,unicodedata,math
from collections import defaultdict
from more_sources import SEOUL_BORO
SOURCE='https://data.seoul.go.kr/dataList/OA-16094/S/1/datasetView.do'
def norm_name(text):
    s=unicodedata.normalize('NFKC',text).lower()
    s=re.sub(r'주식회사|유한회사|\(주\)|㈜','',s)
    return re.sub(r'[^0-9a-z가-힣]','',s)
def address_keys(text):
    text=unicodedata.normalize('NFKC',text).replace('서울시','서울특별시')
    text=re.sub(r'([로길])\s+(\d+)\s*(가?길)',r'\1\2\3',text)
    district=next((b for b in SEOUL_BORO if b in text),'')
    keys=[]
    m=re.search(r'([가-힣0-9·]+(?:대로|로|길))\s*(\d+(?:-\d+)?)',text)
    if m:keys.append(('road',district,m[1],m[2]))
    m=re.search(r'([가-힣0-9]+(?:동\d?가|동|가))\s*(\d+(?:-\d+)?)',text)
    if m:keys.append(('lot',district,m[1],m[2]))
    return keys

def build_index(licenses,transform):
    by_address=defaultdict(list);by_name=defaultdict(list)
    for r in licenses:
        try:lng,lat=(r['lng'],r['lat']) if 'lat' in r else transform(float(r['X']),float(r['Y']))
        except (ValueError,KeyError,TypeError):continue
        if not(126.7<lng<127.3 and 37.4<lat<37.8):continue
        item=dict(lat=lat,lng=lng,name=r.get('BPLCNM',''),id=r['MGTNO'],address=r.get('RDNWHLADDR') or r.get('SITEWHLADDR'),district=next((b for b in SEOUL_BORO if b in r.get('SITEWHLADDR','')),''))
        for a in [r.get('RDNWHLADDR',''),r.get('SITEWHLADDR','')]:
            for key in address_keys(a):by_address[key].append(item)
        by_name[norm_name(item['name'])].append(item)
    return by_address,by_name

def match_location(row,index):
    if row.get('spending_region')!='서울' or re.search(r',| 및 ',row['merchant']):return None
    by_address,by_name=index;address=row.get('address') or '';name=norm_name(row['merchant'])
    district=next((b for b in SEOUL_BORO if b in address),'')
    candidates=[];method='official_address'
    for key in address_keys(address):
        candidates+=by_address.get(key,[])
        # Missing district is accepted only when all district-specific matches agree spatially.
        if not key[1]:
            for b in SEOUL_BORO:candidates+=by_address.get((key[0],b,key[2],key[3]),[])
    if not candidates:return None
    if not candidates:return None
    exact=[r for r in candidates if norm_name(r['name'])==name]
    if exact:candidates=exact
    candidates=list({r['id']:r for r in candidates}.values())
    # Do not choose one of distant branches or conflicting address coordinates.
    if max(r['lat'] for r in candidates)-min(r['lat'] for r in candidates)>.0012:return None
    if max(r['lng'] for r in candidates)-min(r['lng'] for r in candidates)>.0015:return None
    r=sorted(candidates,key=lambda r:r['id'])[0]
    return dict(lat=round(r['lat'],7),lng=round(r['lng'],7),precision='address' if not exact else 'licensed_place',evidence_url=SOURCE,matched_address=r['address'],license_id=r['id'],license_name=r['name'],match_method=method,source_crs='EPSG:5174')
