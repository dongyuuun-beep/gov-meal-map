"""Durable history, compact browser payload, and a bounded compatibility sample."""
import gzip,json
from pathlib import Path
FULL_NAME='data.full.json.gz'
MAP_NAME='data.map.json.gz'
def read_snapshot(directory):
    full=Path(directory)/FULL_NAME
    if full.exists():return json.loads(gzip.decompress(full.read_bytes()))
    return json.loads((Path(directory)/'data.json').read_text())
def pack_snapshot(data):
    source_ids={};sources=[];place_ids={};places=[];strings=[];string_ids={};rows=[]
    def string(s):
        s=s or ''
        if s not in string_ids:string_ids[s]=len(strings);strings.append(s)
        return string_ids[s]
    for r in data['records']:
        source={k:r.get(k) for k in ('source_url','institution','department','source_license','source_city')}
        place={k:r.get(k) for k in ('merchant','address','spending_region','spending_city','location','address_match','source_address','matched_merchant')}
        sk=json.dumps(source,ensure_ascii=False,sort_keys=True);pk=json.dumps(place,ensure_ascii=False,sort_keys=True)
        if sk not in source_ids:source_ids[sk]=len(sources);sources.append(source)
        if pk not in place_ids:place_ids[pk]=len(places);places.append(place)
        rows.append([r['id'],source_ids[sk],place_ids[pk],r.get('date'),string(r.get('purpose')),string(r.get('participant_text')),r.get('participants'),r['amount_krw'],r.get('category'),r.get('budget_category'),r.get('payment_method')])
    return {**{k:v for k,v in data.items() if k!='records'},'format':'meal-map-v1','sources':sources,'places':places,'strings':strings,'rows':rows}
def atomic(path,body):
    tmp=path.with_suffix('.tmp');tmp.write_bytes(body);tmp.replace(path)
def write_snapshot(directory,data):
    directory=Path(directory)
    raw=json.dumps(data,ensure_ascii=False,separators=(',',':')).encode()
    atomic(directory/FULL_NAME,gzip.compress(raw,mtime=0))
    packed=json.dumps(pack_snapshot(data),ensure_ascii=False,separators=(',',':')).encode()
    atomic(directory/MAP_NAME,gzip.compress(packed,mtime=0))
    sample={**data,'records':data['records'][:1000],'full_data':MAP_NAME,'total_record_count':len(data['records'])}
    atomic(directory/'data.json',(json.dumps(sample,ensure_ascii=False,separators=(',',':'))+'\n').encode())
