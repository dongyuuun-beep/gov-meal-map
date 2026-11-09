"""Public monthly Hwaseong council workbooks, kept separate from city hall."""
import re,subprocess
from concurrent.futures import ThreadPoolExecutor
from city_sources import parse_attachment,assign_post
BASE='https://council.hscity.go.kr'
LIST=BASE+'/cnts/bbs/boardList.php?bbsCd=cns&bbsSubCd=cns08'
def collect_council(fetch,record):
 listing=fetch(LIST);ids=list(dict.fromkeys(re.findall(r"goViewPage\('([0-9]+)'",listing)))[:10]
 if not ids:raise ValueError('Council expense list missing')
 def one(n):
  url=BASE+'/cnts/bbs/boardView.php?bbsCd=cns&bbsSubCd=cns08&bbsSn='+n+'&pageNo=1';out=[];errors=[];complete=[]
  try:
   page=fetch(url);files=list(dict.fromkeys(re.findall(r"fileDownLoad\('([0-9]+)'\s*,\s*'cns08'",page)))
   if not files:raise ValueError('Council attachments missing')
   month=re.search(r'20\d\d년\s*\d+월',page);title=(month[0] if month else '')+' 화성시의회 업무추진비 및 공통경비'
   for fi,f in enumerate(files):
    link=BASE+'/cms/utl/FileDownLoad.php?flSn='+f+'&flCd=cns08'
    try:
     body=subprocess.check_output(['curl','-4','-fsSL','--retry','1','--max-time','30',link])
     rows=parse_attachment(body,link,'화성',title,record);assign_post(rows,url,fi)
     for r in rows:
      r.update(institution='화성시의회',department=r.get('executor') or '의회사무국',source_dataset='화성시의회 공개 업무추진비·공통경비 중 식음료 후보')
     out.extend(rows);complete.append(url+'#file-'+str(fi))
    except Exception as e:errors.append(dict(url=link,error=str(e)))
   if not errors:complete.append(url)
  except Exception as e:errors.append(dict(url=url,error=str(e)))
  return out,errors,complete
 rows=[];errors=[];complete=[]
 with ThreadPoolExecutor(2) as pool:
  for a,b,c in pool.map(one,ids):rows.extend(a);errors.extend(b);complete.extend(c)
 if not rows and not complete:raise ValueError('No readable council files: '+str(errors[:2]))
 return rows,errors,complete
