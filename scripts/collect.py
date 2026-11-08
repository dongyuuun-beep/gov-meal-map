"""Initial HTML collectors. Standard-library only; do not silently replace data on failure."""
import concurrent.futures
import hashlib
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GG_SEED = 'https://www.gg.go.kr/bbs/boardView.do?bIdx=196578000&bsIdx=530&menuId=1775'
ULSAN = 'https://www.ulsan.go.kr/u/rep/transfer/ecnmy/list.ulsan?mId=001003002007000000&se=1'

def fetch(url, data=None):
    req = urllib.request.Request(url, data=data, headers={'User-Agent': 'GovMealMap/0.1 (+https://github.com/dongyuuun-beep/gov-meal-map)'})
    with urllib.request.urlopen(req, timeout=35) as response:
        body = response.read()
        declared = response.headers.get_content_charset()
    for encoding in dict.fromkeys([declared or 'utf-8', 'utf-8', 'cp949']):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise ValueError('Unknown source encoding: '+url)

class Tables(HTMLParser):
    def __init__(self):
        super().__init__(); self.tables=[]; self.table=None; self.row=None; self.cell=None; self.skip=0; self.text=[]
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style'): self.skip+=1
        if tag=='table': self.table=[]
        if tag=='tr' and self.table is not None: self.row=[]
        if tag in ('td','th') and self.row is not None: self.cell=[]
    def handle_endtag(self, tag):
        if tag in ('script','style'): self.skip=max(0,self.skip-1)
        if tag in ('td','th') and self.cell is not None:
            self.row.append(' '.join(' '.join(self.cell).split())); self.cell=None
        if tag=='tr' and self.row is not None:
            if self.table is not None: self.table.append(self.row)
            self.row=None
        if tag=='table' and self.table is not None: self.tables.append(self.table); self.table=None
    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)
            if self.cell is not None: self.cell.append(data)

def integer(text):
    value = text.strip().replace(',','').removesuffix('원')
    if not re.fullmatch(r'\d+', value): raise ValueError('Invalid amount: '+text)
    return int(value)

def category(purpose):
    if '회식' in purpose: return '회식'
    if '간담회' in purpose: return '간담회'
    if any(w in purpose for w in ('식사','오찬','만찬','급식')): return '식사'
    if '회의' in purpose: return '회의'
    return '기타'

def record(url, row, date, purpose, merchant, participant_text, amount, institution, department, payment=None):
    m=re.search(r'(\d+)\s*명', participant_text)
    participants=int(m[1]) if m else None
    if amount<=0: raise ValueError('Non-positive amount requires refund handling')
    return dict(id=hashlib.sha256((url+'#'+str(row)).encode()).hexdigest()[:20],source_url=url,source_row=row,date=date,purpose=purpose,merchant=merchant,participant_text=participant_text,participants=participants,amount_krw=amount,institution=institution,department=department,payment_method=payment,budget_category=None,category=category(purpose),spending_region=None,address=None,location=None)

def parse_gg(html, url):
    p=Tables();p.feed(html);text=' '.join(p.text)
    date=re.search(r'(20\d\d-\d\d-\d\d)\s*일\s*업무추진비',text)
    if not date: raise ValueError('GG date missing')
    result=[]
    for table in p.tables:
        if table and table[0]==['집행내역','사용처','집행 대상자','금액']:
            for idx,c in enumerate(table[1:],1):
                if len(c)!=4: raise ValueError('GG table schema changed')
                result.append(record(url,idx,date[1],c[0],c[1],c[2],integer(c[3]),'경기도','감사1과'))
    if not result: raise ValueError('GG expense table missing')
    return result

def parse_ulsan(html,url,date):
    p=Tables();p.feed(html);result=[];found=False
    for table in p.tables:
        if table and table[0]==['번호','결제내용','결제방법','인원(수량)','금액(천원)','참석대상','장소']:
            found=True
            for c in table[1:]:
                if len(c)!=7: raise ValueError('Ulsan table schema changed')
                if c[6] in ('-', '') or category(c[1])=='기타': continue
                people=integer(c[3]); result.append(record(url,int(c[0]),date,c[1],c[6],c[5]+' '+str(people)+'명',integer(c[4])*1000,'울산광역시','시장',c[2]))
    if not found: raise ValueError('Ulsan expense table missing')
    return result

def collect():
    # GG's list JSON endpoint returned a security-policy block during research.
    # Refresh only the confirmed HTML seed; do not claim new GG rows are discovered.
    gg_urls={GG_SEED}
    records=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for batch in pool.map(lambda url:parse_gg(fetch(url),url),sorted(gg_urls)): records.extend(batch)
    ul_html=fetch(ULSAN)
    dates=sorted(set(re.findall(r'20\d\d-\d\d-\d\d',ul_html)),reverse=True)[:20]
    if not dates: raise ValueError('Ulsan list dates missing')
    # Include verified seed and discover latest listing dates. Full six-month pagination is follow-up.
    dates=sorted(set(dates+['2026-08-04']))
    for date in dates:
        url=ULSAN+'&useDe='+date
        records.extend(parse_ulsan(fetch(url),url,date))
    if not records: raise ValueError('No records; retaining previous dataset')
    target=ROOT/'dist/data.json'
    previous=json.loads(target.read_text())['records'] if target.exists() else []
    refreshed=set(gg_urls)|{ULSAN+'&useDe='+date for date in dates}
    old_by_id={r['id']:r for r in previous}
    combined={r['id']:r for r in previous if r['source_url'] not in refreshed}
    now=datetime.now(timezone.utc).isoformat()
    for r in records:
        old=old_by_id.get(r['id'])
        # Do not create churn by changing collection timestamps on unchanged rows.
        if old:
            comparable={k:v for k,v in old.items() if k not in ('collected_at','address','location','spending_region','address_evidence_url','source_license')}
            r['collected_at']=old.get('collected_at',now) if comparable==r else now
        else: r['collected_at']=now
        combined[r['id']]=r
    locations=json.loads((ROOT/'config/locations.json').read_text())
    for r in combined.values():
        r.update(locations.get(r['merchant'],{}))
        r['source_license']='공공누리 제3유형 표시 관측; 원문 전체 재배포 제외' if r['institution']=='경기도' else '출처별 이용조건 확인 필요'
    output={'updated_at':now,'scope':'경기도 감사1과 고정 예시 재확인 + 울산시장 최신 목록·확인 예시. 전국 전수 아님.','records':sorted(combined.values(),key=lambda r:(r['date'],r['id']),reverse=True)}
    temporary=target.with_suffix('.tmp');temporary.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n');temporary.replace(target)
    print('Collected',len(records),'rows; total',len(combined),'records')

if __name__=='__main__': collect()
