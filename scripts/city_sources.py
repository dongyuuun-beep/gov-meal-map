"""Official Hwaseong, Yongin, Suwon and Pyeongtaek attachment collectors."""
import io,re,json,html,zipfile,subprocess,hashlib
import xml.etree.ElementTree as ET
from datetime import datetime,timedelta
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor
from more_sources import xlsx_sheets,food,participants,region
SOURCES={
 '화성':('https://www.hscity.go.kr','https://www.hscity.go.kr/www/beffatPublict/BD_selectBeffatPublictBbsList.do?q_beffatPublictTy=1008&q_beffatPublictSj=657'),
 '용인':('https://www.yongin.go.kr','https://www.yongin.go.kr/user/bbs/BD_selectBbsList.do?q_bbsCode=1001&q_clCode=6'),
 '수원':('https://www.suwon.go.kr','https://www.suwon.go.kr/web/board/BD_board.list.do?bbsCd=1179'),
 '평택':('https://www.pyeongtaek.go.kr','https://www.pyeongtaek.go.kr/pyeongtaek/contents.do?mid=0110000000'),
}
CITY_DISTRICTS={'화성':('동탄구','병점구','만세구','효행구'),'용인':('처인구','기흥구','수지구'),'수원':('장안구','권선구','팔달구','영통구')}
def spending_city(address):
 for city in SOURCES:
  if re.search(city+r'(?:특례)?시',address or ''):return city
 for city,districts in CITY_DISTRICTS.items():
  if any(re.search(r'(?:^|\s)'+d+r'(?:\s|$)',address or '') for d in districts):return city
 return None

def split_place(value,address=None):
 # Both "상호(주소)" and "주소(상호)" occur in the official attachments.
 before=re.fullmatch(r'(.+?(?:대로|로|길)\s*\d+(?:-\d+)?[^()]*)\(([^()]+)\)\s*',value)
 if before and spending_city(before[1]):
  address=address or before[1].strip();value=before[2].strip()
 else:
  after=re.search(r'\(([^()]*(?:시|구|로|길|동)[^()]*)\)\s*$',value)
  if after and (re.search(r'(?:시|구)\s|(?:로|길)\s*\d|(?:동|읍|면)\s*\d',after[1]) or any(after[1].strip() in ds for ds in CITY_DISTRICTS.values())):
   address=address or after[1].strip();value=value[:after.start()].strip()
 city=spending_city(address)
 if city and not re.search(city+r'(?:특례)?시',address or ''):address=city+'시 '+address
 return value,address


def posts(city,text,limit=10):
 host=SOURCES[city][0]
 if city=='화성':
  ids=re.findall(r"opDetail\('([0-9]+)'",text);make=lambda n:host+'/www/beffatPublict/BD_selectBeffatPublictBbsType8Viewer.do?q_beffatPublictTy=1008&q_beffatPublictSj=657&bbscttSn='+n
 elif city=='용인':
  ids=re.findall(r'q_bbscttSn=([0-9]+)',text);make=lambda n:host+'/user/bbs/BD_selectBbs.do?q_bbsCode=1001&q_bbscttSn='+n
 elif city=='수원':
  ids=re.findall(r"jsView\('1179',\s*'([0-9]+)'",text);make=lambda n:host+'/web/board/BD_board.view.do?bbsCd=1179&seq='+n
 else:
  ids=re.findall(r"boardViewRenewal\('listForm',\s*'[^']*',\s*'Y',\s*'264',\s*'([0-9]+)'",text);make=lambda n:host+'/pyeongtaek/board/post/view.do?bcIdx=264&mid=0110000000&idx='+n
 return [make(n) for n in list(dict.fromkeys(ids))[:limit]]
def attachments(city,text):
 host=SOURCES[city][0]
 links=[urljoin(host,html.unescape(u)) for u in re.findall(r'href="([^"\s]*ND_fileDownload[^"\s]+)"',text)]
 for a,b in re.findall(r"yhLib\.file\.download\('([^']+)'\s*,\s*'([^']+)'",text):links.append(host+'/common/file/download.do?atchFileId='+a+'&fileSn='+b)
 return list(dict.fromkeys(links))
def title(text):
 plain=html.unescape(re.sub('<[^>]+>',' ',text));plain=' '.join(plain.split())
 matches=re.findall(r'20\d\d년\s*\d{1,2}월[^<>]{0,70}?업무추진비[^<>]{0,80}?\([^()]{1,35}\)',plain)
 result=matches[0] if matches else '공개 업무추진비'
 return re.split(r'작성자|등록자|첨부파일|조회|등록일시',result)[0].strip()
def date_value(value,year):
 value=str(value).strip()
 if re.fullmatch(r'\d{5}(?:\.\d+)?',value):return (datetime(1899,12,30)+timedelta(days=float(value))).date().isoformat()
 m=re.search(r'(20\d\d)[년./\-\s]+(\d{1,2})[월./\-\s]+(\d{1,2})',value)
 if m:
  return datetime(*map(int,m.groups())).date().isoformat()
 m=re.match(r"[’'‘]?(\d{2})[./\-]\s*(\d{1,2})[./\-]\s*(\d{1,2})",value)
 if m and year and int(m[1])==year%100:return datetime(year,int(m[2]),int(m[3])).date().isoformat()
 m=re.search(r'(\d{1,2})[월./\-\s]+(\d{1,2})',value)
 if m and year:return datetime(year,int(m[1]),int(m[2])).date().isoformat()
 return None

def amount_value(value,unit=1):
 raw=str(value)
 formatted=re.findall(r'(?<![\d,])\d{1,3}(?:,\d{3})+(?![\d,])',raw)
 if len(formatted)>1 and not re.sub(r'\d|,|\s|원','',raw):raw='\n'.join(formatted)
 lines=[re.sub(r'[,\s원]','',line) for line in raw.splitlines() if line.strip()]
 if not lines or not all(re.fullmatch(r'\d+(?:\.0+)?',line) for line in lines):return None,[]
 values=[int(float(v))*unit for v in lines]
 if len(values)>1 and any(v<1000 for v in values):raise ValueError('Ambiguous multiline amount: '+repr(value))
 return sum(values),values

def tabular(body):
 if body.startswith(b'PK'):
  z=zipfile.ZipFile(io.BytesIO(body))
  if 'xl/workbook.xml' in z.namelist():
   for sheet,rows in xlsx_sheets(body):yield sheet,[(n,list(c.items())) for n,c in rows]
  else:
   for name in sorted(z.namelist()):
    if not re.fullmatch(r'Contents/section\d+\.xml',name):continue
    tree=ET.fromstring(z.read(name))
    for ti,table in enumerate(tree.iter()):
     if table.tag.split('}')[-1]!='tbl':continue
     rows=[]
     for ri,tr in enumerate(table):
      if tr.tag.split('}')[-1]!='tr':continue
      cells=[]
      for ci,tc in enumerate(tr):
       if tc.tag.split('}')[-1]!='tc':continue
       text=' '.join(''.join(n.itertext()) for n in tc.iter() if n.tag.split('}')[-1]=='t')
       address=next((n for n in tc if n.tag.split('}')[-1]=='cellAddr'),None)
       col=int(address.get('colAddr')) if address is not None else ci
       cells.append((str(col),text))
      rows.append((str(ri),cells))
     yield name+'!'+str(ti),rows
 elif body.startswith(bytes.fromhex('D0CF11E0')):
  import xlrd
  book=xlrd.open_workbook(file_contents=body)
  for si,sheet in enumerate(book.sheets()):
   rows=[]
   for i in range(sheet.nrows):
    cells=[]
    for j in range(sheet.ncols):
     c=sheet.cell(i,j);v=str(c.value)
     if c.ctype==xlrd.XL_CELL_DATE:v=xlrd.xldate_as_datetime(c.value,book.datemode).isoformat()
     cells.append((str(j),v))
    rows.append((str(i),cells))
   yield 'xls!'+str(si),rows
 else:raise ValueError('Unsupported attachment format')

def parse_attachment(body,url,city,source_title,record):
 if body.startswith(b'%PDF'):return parse_pdf(body,url,city,source_title,record)
 out,found=parse_tables(tabular(body),url,city,source_title,record)
 if not found:raise ValueError('Expense table schema not recognized')
 return out

def parse_tables(tables,url,city,source_title,record,default_unit=1):
 out=[];year_match=re.search(r'20\d\d',source_title);year=int(year_match[0]) if year_match else None;found=False
 for sheet,rows in tables:
  mapping=None;unit=default_unit
  for rn,cells in rows:
   d={k:str(v).strip() for k,v in cells};h={k:re.sub(r'\s','',v) for k,v in d.items()}
   cols={}
   for k,v in h.items():
    if re.search('사용일|사용일자|집행일|사용일시|승인일시|^일시$|^일자$',v):cols['date']=k
    if re.search('사용처|사용장소|집행장소|가맹점명|^장소',v):cols['merchant']=k
    if re.search('집행목적|사용목적|집행내역|사용내역|^목적$',v):cols['purpose']=k
    if '금액' in v or v=='사용액':cols['amount']=k
    if re.search(r'인원|참석|대상\(명\)',v):cols['people']=k
    if re.search('사용방법|결제방법',v):cols['payment']=k
    if re.search('비목|^구분$|^비고$',v):cols['budget']=k
    if v=='사용자':cols['user']=k
    if v=='주소':cols['address']=k
   if all(k in cols for k in ['date','merchant','purpose','amount']):
    mapping=cols;unit=1000 if '천원' in h[cols['amount']] else 1 if '원' in h[cols['amount']] else default_unit;found=True;continue
   if mapping is None:continue
   get=lambda k:d.get(mapping.get(k,''),'')
   if not food(get('purpose')) or not get('merchant'):continue
   amount,components=amount_value(get('amount'),unit)
   if amount is None or amount<=0:continue
   date_text=get('date')
   if re.fullmatch(r'20\d{2}',date_text):
    # Some workbooks split one merged date header into year, month and day columns.
    keys=list(d);start=keys.index(mapping['date']);parts=[d[k] for k in keys[start:start+3]]
    if len(parts)==3 and all(re.fullmatch(r'\d{1,4}',v) for v in parts):date_text='-'.join(parts)
   date=date_value(date_text,year)
   if not date:raise ValueError('Unknown transaction date '+get('date'))
   raw_merchant=get('merchant');loc,address=split_place(raw_merchant,get('address') or None)
   if len(components)>1:
    loc=' / '.join(loc.splitlines())
    dates=[date_value(line,year) for line in get('date').splitlines() if line.strip()]
    if len(dates)>1 and (None in dates or len(set(dates))>1):date=None
   people=get('people');num=re.fullmatch(r'\d+(?:\.0+)?',people)
   r=record(url,sheet+'!'+rn,date,get('purpose'),loc,people,amount,city+'시',source_title,get('payment') or None)
   r.update(source_date=get('date'),amount_components=components if len(components)>1 else None,source_amount=get('amount'),source_merchant=raw_merchant,executor=get('user') or None,participants=int(float(people)) if num and float(people)>0 else participants(people),budget_category=get('budget') or None,address=address,spending_region='경기' if spending_city(address) else region(address or ''),spending_city=spending_city(address),source_city=city,source_dataset=city+'시 공식 공개 첨부파일')
   out.append(r)
 return out,found

def parse_pdf(body,url,city,source_title,record):
 import pdfplumber
 out=[];found=False
 with pdfplumber.open(io.BytesIO(body)) as pdf:
  for pi,page in enumerate(pdf.pages):
   text=page.extract_text(layout=True) or ''
   page_rows=[];table_found=False
   for ti,table in enumerate(page.find_tables() if hasattr(page,'find_tables') else []):
    above=page.crop((0,0,page.width,table.bbox[1])).extract_text() if table.bbox[1]>0 else ''
    units=re.findall(r'단위\s*[:：]\s*([^\n)]{1,25})',above or '')
    default_unit=1000 if units and '천원' in units[-1] else 1
    cells=[(str(ri),[(str(ci),v or '') for ci,v in enumerate(row)]) for ri,row in enumerate(table.extract())]
    batch,recognized=parse_tables([(str(pi)+'!table'+str(ti),cells)],url,city,source_title,record,default_unit)
    table_found=table_found or recognized;page_rows.extend(batch)
   if table_found:
    found=True;out.extend(page_rows);continue
   unit=1000 if re.search(r'(?:단위|금액)[\s:：(]*천원',text) else 1
   for ri,line in enumerate(text.splitlines()):
    m=re.match(r'^\s*(20\d\d[.\-]\s*\d{1,2}[.\-]\s*\d{1,2})\.?\s+(?:\d{1,2}:\d{2}(?::\d{2})?\s+)?(.+?)\s+([\d,]+)\s+(.+?)\s+(\d+)\s+(카드|신용카드|현금)\s*$',line)
    if not m:continue
    found=True;date,purpose,amount,merchant,people,payment=m.groups()
    if not food(purpose):continue
    r=record(url,str(pi)+'!'+str(ri),date_value(date,None),purpose,merchant,people+'명',int(amount.replace(',',''))*unit,city+'시',source_title,payment)
    r.update(spending_city=None,source_city=city,source_dataset=city+'시 공식 PDF 공개')
    out.append(r)
 if not found:raise ValueError('PDF expense rows not recognized')
 return out

def collect_city(city,fetch,record):
 if city=='화성':
  urls=[]
  for page in range(1,4):
   page_urls=posts(city,fetch(SOURCES[city][1]+'&q_rowPerPage=30&q_currPage='+str(page)),30)
   if page>1 and page_urls and set(page_urls)==set(urls[:30]):raise ValueError('Hwaseong pagination repeated first page')
   urls.extend(page_urls)
  urls=list(dict.fromkeys(urls))
 else:
  listing=fetch(SOURCES[city][1]);urls=posts(city,listing)
 if not urls:raise ValueError('City post list missing')
 def one(url):
  records=[];errors=[];completed=[]
  try:
   text=fetch(url);links=attachments(city,text)
   if not links:raise ValueError('No public attachments found')
   for fi,link in enumerate(links):
    try:
     body=subprocess.check_output(['curl','-4','-fsSL','--retry','1','--max-time','30',link])
     batch=parse_attachment(body,link,city,title(text),record)
     assign_post(batch,url,fi);records.extend(batch);completed.append(file_key(url,fi))
    except Exception as e:errors.append({'url':link,'error':str(e)})
  except Exception as e:errors.append({'url':url,'error':str(e)})
  if not errors:completed.append(url)
  return records,errors,completed
 rows=[];errors=[];complete=[]
 with ThreadPoolExecutor(2) as pool:
  for batch,failed,completed in pool.map(one,urls):
   rows.extend(batch);errors.extend(failed);complete.extend(completed)
 if not rows and not complete:raise ValueError('No readable city expense rows: '+json.dumps(errors[:3],ensure_ascii=False))
 return rows,errors,complete

def file_key(post_url,file_index):return post_url+'#file-'+str(file_index)

def assign_post(rows,post_url,file_index):
 for r in rows:
  r['source_post_url']=post_url
  r['source_file_key']=file_key(post_url,file_index)
  r['id']=hashlib.sha256((post_url+'#'+str(file_index)+'#'+str(r['source_row'])).encode()).hexdigest()[:20]
