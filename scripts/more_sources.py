"""Public Seoul sheet and Sejong Council XLSX sources, no API key required."""
import io,json,re,zipfile,subprocess
import xml.etree.ElementTree as ET
from datetime import datetime,timedelta
from urllib.parse import urlencode,urljoin
from concurrent.futures import ThreadPoolExecutor
SEOUL='https://data.seoul.go.kr/dataList/dataView.do'
SJ='https://council.sejong.go.kr/mnu/cap/businessExpenseList.do'
SEOUL_BORO=['종로구','중구','용산구','성동구','광진구','동대문구','중랑구','성북구','강북구','도봉구','노원구','은평구','서대문구','마포구','양천구','강서구','구로구','금천구','영등포구','동작구','관악구','서초구','강남구','송파구','강동구']
def loose_json(text):
    # Transform syntax outside quoted strings only; never execute source JavaScript.
    parts=re.split(r'("(?:\\.|[^"\\])*")',text)
    for i in range(0,len(parts),2):
        parts[i]=re.sub(r'([{,]\s*)([A-Za-z_]\w*)\s*:',r'\1"\2":',parts[i])
        parts[i]=re.sub(r',\s*([}\]])',r'\1',parts[i])
    return json.loads(''.join(parts),strict=False)
def region(address):
    if re.search(r'제주|제주시|서귀포',address):return '제주'
    if re.search(r'세종특별|세종시|(?:^|\s)세종(?:\s|$)|보람동|소담동|호려울로|한누리대로|시청대로|나성로|조치원읍|연서면',address):return '세종'
    if '서울' in address:return '서울'
    if address=='중구' or address.startswith('중구 '):return '서울' # Seoul source calls this only for an unprefixed local district.
    for pattern,name in [('부산','부산'),('대전','대전'),('울산','울산'),('수원|화성|용인|평택|성남|고양|경기도','경기'),('인천','인천')]:
        if re.search(pattern,address):return name
    if any(address.startswith(b) for b in SEOUL_BORO):return '서울'
    return None

def participants(text):
    m=re.search(r'총\s*(\d+)\s*명',text)
    if m:return int(m[1])
    m=re.search(r'외\s*(\d+)\s*명',text)
    if m:return int(m[1])+1
    m=re.search(r'(\d+)\s*명',text)
    return int(m[1]) if m else None

def food(p):
    return not re.search(r'경조|부의|축의|격려금|명절|물품|선물|화환',p) and bool(re.search(r'간담|회의|식사|급식|중식|석식|오찬|만찬|회식|간식|다과|음료',p))

def seoul(fetch,record):
    def page(n):
        u=SEOUL+'?'+urlencode(dict(onepagerow=1000,infId='OA-22156',srvType='S',serviceKind=0,pageNo=n,ssUserId='SAMPLE_VIEW',strOrderby='EXEC_YR DESC, EXEC_MONTH DESC, EXEC_DT DESC'))
        x=loose_json(fetch(u))
        if x.get('result')!='ok' or not isinstance(x.get('list'),list):raise ValueError('Seoul sheet schema changed')
        return x['list']
    with ThreadPoolExecutor(max_workers=2) as pool:
        batches=list(pool.map(page,range(1,52,10)))
    return normalize_seoul(batches,record)

def normalize_seoul(batches,record):
    out=[];seen={};seen_source_rows=set()
    for batch in batches:
        for row in batch:
            source_row=tuple(row.get(k) for k in ('RONUM','NID','EXEC_DT','EXEC_LOC','EXEC_AMOUNT','EXEC_PURPOSE'))
            if source_row and source_row in seen_source_rows:continue
            if source_row:seen_source_rows.add(source_row)
            purpose=row.get('EXEC_PURPOSE','');loc=row.get('EXEC_LOC','')
            if not food(purpose) or not loc:continue
            amount=int(row['EXEC_AMOUNT'])
            if amount<=0:continue
            # Parentheses may also be part of a corporate merchant name: use the final address group.
            m=re.search(r'\(([^()]*(?:구|시|로|길|대로|동)[\s\S]*?)\)\s*$',loc)
            addr=m[1].strip() if m else ''
            merchant=loc[:m.start()].strip() if m else loc
            identity='|'.join(str(row.get(k,'')) for k in ['EXEC_DT','EXEC_LOC','EXEC_PURPOSE','BIMOK'])
            key=(row['NID'],identity);seen[key]=seen.get(key,0)+1
            r=record(row['URL'],identity+'|'+str(seen[key]),row['EXEC_DT'][:10],purpose,merchant,row.get('TARGET_NM',''),amount,'서울특별시',row.get('DEPT_NM_FULL') or row.get('DEPT_NM'),row.get('PAYMENT_METHOD'))
            r.update(participants=participants(row.get('TARGET_NM','')),address=addr or None,spending_region=region(addr),budget_category=row.get('BIMOK'),source_license='공공누리 제1유형 · 서울 열린데이터광장 OA-22156',source_dataset='서울시 본청 공개 지출 중 식음료 후보')
            out.append(r)
    if not out:raise ValueError('Seoul returned no food candidates')
    return out

def xlsx_sheets(body):
    z=zipfile.ZipFile(io.BytesIO(body));ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    strings=[''.join(n.itertext()) for n in ET.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
    for name in sorted(z.namelist()):
        if not re.fullmatch(r'xl/worksheets/sheet\d+.xml',name):continue
        rows=[]
        for node in ET.fromstring(z.read(name)).findall('.//m:row',ns):
            row={}
            for cell in node:
                v=cell.find('m:v',ns);value=v.text if v is not None else ''.join(cell.itertext())
                if cell.get('t')=='s' and value:value=strings[int(value)]
                row[re.sub(r'\d','',cell.get('r',''))]=value or ''
            rows.append((node.get('r'),row))
        yield name,rows

def parse_sejong(body,url,record):
    out=[]
    for sheet,rows in xlsx_sheets(body):
        dept='의회';headers=False
        for rownum,c in rows:
            if c.get('B','').startswith('사용자'):dept=c['B'].split(':',1)[-1].strip()
            if c.get('A')=='연번' and '금액' in c.get('F',''):headers=True;continue
            if not headers or not c.get('A','').isdigit() or not food(c.get('D','')):continue
            amount=c.get('F','').replace(',','').strip()
            if not re.fullmatch(r'\d+(?:\.0+)?',amount):raise ValueError('Unknown Sejong amount '+amount)
            if float(amount)<=0:continue
            rawdate=c.get('B','');m=re.search(r'20\d\d-\d\d-\d\d',rawdate)
            if m:date=m[0]
            elif re.fullmatch(r'\d{5}(?:\.\d+)?',rawdate):date=(datetime(1899,12,30)+timedelta(days=float(rawdate))).date().isoformat()
            else:raise ValueError('Unknown Sejong date '+rawdate)
            rawloc=c.get('C','');lines=rawloc.splitlines();merchant=lines[0].strip();addr=' '.join(lines[1:]).strip('() ')
            r=record(url,sheet+'!'+rownum,date,c['D'],merchant,c.get('E',''),int(float(amount)),'세종특별자치시의회',dept,c.get('G'))
            people=c.get('E','');r.update(participants=int(people) if people.isdigit() and int(people)>0 else None,participant_text='기재 인원 '+(people+'명' if people.isdigit() else '미공개'),address=addr or None,spending_region=region(addr),budget_category=c.get('H'),source_dataset='세종시의회 업무추진비 XLSX',source_license='공개 원문 사실 추출 · 원문 링크 제공')
            out.append(r)
    if not out:raise ValueError('No Sejong expense rows')
    return out

def sejong(fetch,record):
    listing=fetch(SJ);ids=list(dict.fromkeys(re.findall(r'businessExpenseView\.do\?bbsSn=(\d+)',listing)))[:6]
    if not ids:raise ValueError('Sejong list schema changed')
    out=[]
    for item in ids:
        url='https://council.sejong.go.kr/mnu/cap/businessExpenseView.do?bbsSn='+item
        html=fetch(url)
        if '의회운영업무추진비' not in html:continue
        files=[href for href,label in re.findall(r'href="([^"]*FileDownLoadProc.do\?flSn=\d+)"[^>]*>(.*?)</a>',html,re.S) if 'xlsx' in label and '업무추진비' in label]
        for file in files:
            source=urljoin(url,file)
            p=subprocess.run(['curl','-4','-fsSL','--retry','1','--max-time','30',source],capture_output=True,check=True)
            out.extend(parse_sejong(p.stdout,source,record))
    if not out:raise ValueError('Sejong XLSX missing')
    return out
