import io,sys,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from city_sources import parse_attachment,date_value,spending_city,assign_post,posts,attachments
from collect import record

def workbook(rows):
 from xml.sax.saxutils import escape
 xml='<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
 for ri,row in enumerate(rows,1):
  xml+='<row r="%s">'%ri
  for col,value in row.items():xml+='<c r="%s%s" t="inlineStr"><is><t>%s</t></is></c>'%(col,ri,escape(str(value)))
  xml+='</row>'
 xml+='</sheetData></worksheet>'
 b=io.BytesIO()
 with zipfile.ZipFile(b,'w') as z:
  z.writestr('xl/workbook.xml','<workbook/>');z.writestr('xl/worksheets/sheet1.xml',xml)
 return b.getvalue()

class CitySourceTests(unittest.TestCase):
 def parse(self,rows,city='화성'):
  return parse_attachment(workbook(rows),'https://example.org/file',city,'2026년 10월 업무추진비 (정책과)',record)
 def test_hwaseong_amount_people_and_branch_preserved(self):
  r=self.parse([{'C':'사용일자(일시)','D':'사용장소(가맹점명)','E':'사용목적','F':'사용금액(원)','G':'대상인원'}, {'C':'2026-10-03','D':'예시식당(동탄호수공원점)','E':'정책 간담회','F':'120,000','G':'6'}])[0]
  self.assertEqual((r['amount_krw'],r['participants']),(120000,6))
  self.assertIsNone(r['spending_city']);self.assertIsNone(r['location'])
  self.assertEqual(r['merchant'],'예시식당(동탄호수공원점)')
  self.assertEqual(r['source_city'],'화성')
 def test_yongin_swapped_amount_people_and_address(self):
  r=self.parse([{'C':'일시','D':'사용처','E':'집행목적','F':'대상인원','G':'금액(천원)'},{'C':'26.10.20. (12:30)','D':'예시식당(용인시 처인구 예시로 1)','E':'직원 식사','F':'4','G':'80'}],'용인')[0]
  self.assertEqual((r['amount_krw'],r['participants'],r['date']),(80000,4,'2026-10-20'))
  self.assertEqual(r['spending_city'],'용인')
 def test_split_year_month_day_under_merged_header(self):
  r=self.parse([{'C':'사용일자','H':'사용 장소(가맹점명)','I':'사용목적','J':'사용금액(원)','K':'대상인원'},{'C':'2026','D':'10','E':'7','H':'예시식당','I':'간담회','J':'66000','K':'6'}],'평택')[0]
  self.assertEqual(r['date'],'2026-10-07')
 def test_date_formats_and_payer_location_distinction(self):
  self.assertEqual(date_value('26.10.21.\n(12:29)',2026),'2026-10-21')
  self.assertEqual(date_value('2026. 10. 22.',None),'2026-10-22')
  self.assertEqual(spending_city('경기도 화성특례시 병점구 세자로 469'),'화성')
  self.assertIsNone(spending_city('수원갈비'))
 def test_post_identity_survives_rotating_download_ids(self):
  a=record('https://example.org/a','sheet!3','2026-10-01','식사','예시','4명',80000,'수원시','정책과')
  b={**a,'source_url':'https://example.org/b'}
  assign_post([a],'https://example.org/post',0);assign_post([b],'https://example.org/post',0)
  self.assertEqual(a['id'],b['id']);self.assertEqual(a['source_post_url'],'https://example.org/post')
 def test_pdf_spaced_date_amount_people_and_unit(self):
  import types
  page=types.SimpleNamespace(extract_text=lambda **kw:'단위: 천원\n2026. 10. 22. 12:42 직원 격려 급식 제공 60 예시식당 6 카드')
  class PDF:
   pages=[page]
   def __enter__(self):return self
   def __exit__(self,*a):pass
  with patch.dict(sys.modules,{'pdfplumber':types.SimpleNamespace(open=lambda _:PDF())}):
   r=parse_attachment(b'%PDF','https://example.org/pdf','수원','정책과',record)[0]
  self.assertEqual((r['date'],r['amount_krw'],r['participants']),('2026-10-22',60000,6))

class CityAddressTests(unittest.TestCase):
 def feature(self,**overrides):
  return {**dict(lat='37.2322',lon='127.1747',osm_type='way',osm_id=1,address=dict(city='용인시',road='용인대학로',house_number='74',country_code='kr')),**overrides}
 def test_exact_city_road_number_required(self):
  from resolve_city_addresses import exact_match
  p=('용인','용인대학로','74')
  self.assertIsNotNone(exact_match([self.feature()],p))
  for field,value in [('city','수원시'),('road','용인로'),('house_number','75'),('country_code','jp')]:
   f=self.feature();f['address'][field]=value
   self.assertIsNone(exact_match([f],p))
  self.assertIsNone(exact_match([self.feature(),self.feature(lat='37.3')],p))
 def test_multiline_pdf_table_unit_and_explicit_won_override(self):
  import types
  class Table:
   bbox=(0,100,400,200)
   def extract(self):return [['사용일시','사용목적','사용액','사용장소','대상인원(명)'],['2026.10.7.\n(21:20)','간담회 식사비','260','예시식당','10']]
  class Page:
   width=400
   def extract_text(self,**kw):return '단위:천원'
   def find_tables(self):return [Table()]
   def crop(self,bbox):return self
  class PDF:
   pages=[Page()]
   def __enter__(self):return self
   def __exit__(self,*a):pass
  with patch.dict(sys.modules,{'pdfplumber':types.SimpleNamespace(open=lambda _:PDF())}):
   r=parse_attachment(b'%PDF','https://example.org/pdf','수원','정책과',record)[0]
  self.assertEqual((r['amount_krw'],r['participants']),(260000,10))
  from city_sources import parse_tables
  rows=[('0',[('A','일시'),('B','목적'),('C','금액(원)'),('D','장소')]),('1',[('A','2026-10-01'),('B','간담회'),('C','79,000'),('D','예시')])]
  rs,found=parse_tables([('sheet',rows)],'https://example.org','수원','정책과',record,1000)
  self.assertTrue(found);self.assertEqual(rs[0]['amount_krw'],79000)
 def test_readable_zero_expense_post_is_refreshed(self):
  from city_sources import collect_city
  listing="jsView('1179', '1234')";detail='<a href="/component/file/ND_fileDownload.do?file=1">파일</a>'
  body=workbook([{'A':'일시','B':'사용목적','C':'금액(원)','D':'장소'},{'A':'-','B':'-','C':'-','D':'-'}])
  with patch('city_sources.subprocess.check_output',return_value=body):
   rs,errors,complete=collect_city('수원',lambda url:listing if 'list.do' in url else detail,record)
  self.assertEqual(rs,[]);self.assertEqual(errors,[]);self.assertEqual(len(complete),2)

class ReversedPlaceTests(unittest.TestCase):
 def test_address_before_merchant_in_hwaseong_attachment(self):
  from city_sources import split_place
  self.assertEqual(split_place('동탄구 동탄대로 181(양산도)'),('양산도','화성시 동탄구 동탄대로 181'))
  self.assertEqual(split_place('동탄구 왕배산1길 5(쪼꼬미)'),('쪼꼬미','화성시 동탄구 왕배산1길 5'))
 def test_branch_names_never_become_addresses(self):
  from city_sources import split_place
  self.assertEqual(split_place('예시식당(동탄호수공원점)'),('예시식당(동탄호수공원점)',None))
  self.assertIsNone(spending_city('동탄구이식당'))
 def test_recognized_district_is_geography_without_payer_assumptions(self):
  self.assertEqual(spending_city('동탄구 동탄대로 181'),'화성')
  self.assertEqual(spending_city('용인시 처인구 금령로 1'),'용인')
  self.assertEqual(spending_city('수원시 영통구 예시로 1'),'수원')

class CombinedPaymentTests(unittest.TestCase):
 def test_separate_payment_lines_are_summed_instead_of_concatenated(self):
  from city_sources import amount_value
  self.assertEqual(amount_value('60,000\n121,470'),(181470,[60000,121470]))
  self.assertEqual(amount_value('4 5,000'),(45000,[45000]))
  self.assertEqual(amount_value('60,000 121,470'),(181470,[60000,121470]))
  with self.assertRaises(ValueError):amount_value('1\n44,000')
 def test_multi_merchant_cell_keeps_original_and_total(self):
  body=workbook([{'A':'일시','B':'장소','C':'사용목적','D':'금액(원)','E':'대상인원'},{'A':'2026-10-12 14:08\n2026/10/12 10:05','B':'빵이당 발안향남점\n쿠팡','C':'의료진 간식비 지급','D':'60,000\n121,470','E':'50'}])
  r=parse_attachment(body,'https://example.org/file','화성','2026년 10월 보건정책과',record)[0]
  self.assertEqual(r['amount_krw'],181470);self.assertEqual(r['amount_components'],[60000,121470]);self.assertEqual(r['merchant'],'빵이당 발안향남점 / 쿠팡');self.assertIsNone(r['location'])

class ExpandedHwaseongTests(unittest.TestCase):
 def test_higher_post_limit_keeps_default_for_other_cities(self):
  html=''.join("opDetail('%s')"%i for i in range(35))
  self.assertEqual(len(posts('화성',html)),10)
  self.assertEqual(len(posts('화성',html,30)),30)
 def test_council_approval_date_header(self):
  body=workbook([{'A':'사용자','B':'승인 일시','C':'사용장소(가맹점용)','D':'사용목적(내역)','E':'사용금액(원)','F':'대상 인원(명)'},{'A':'의장','B':'2026-10-01 12:00','C':'예시식당','D':'간담회 식비','E':'66000','F':'6'}])
  rs=parse_attachment(body,'https://example.org','화성','2026년 10월 의회',record)
  self.assertEqual(len(rs),1);self.assertEqual(rs[0]['amount_krw'],66000)

class CityPagingTests(unittest.TestCase):
 def test_paging_and_repeated_notice_are_not_double_counted(self):
  from city_sources import collect_city
  body=workbook([{'A':'일시','B':'장소','C':'사용목적','D':'금액(원)'},{'A':'2026-10-01','B':'예시식당','C':'간담회 식사','D':'50000'}])
  def fetch(url):
   if 'list.do' in url:return "jsView('1179', '1');jsView('1179', '"+('3' if 'q_currPage=2' in url else '2')+"')"
   return '<a href="/component/file/ND_fileDownload.do?file=1">첨부</a>'
  with patch.dict('city_sources.CITY_PAGES',{'수원':(2,2)}),patch('city_sources.subprocess.check_output',return_value=body):
   rows,errors,_=collect_city('수원',fetch,record)
  self.assertEqual(len(rows),3);self.assertEqual(len({r['id'] for r in rows}),3);self.assertEqual(errors,[])
 def test_ignored_page_parameter_fails_instead_of_claiming_history(self):
  from city_sources import collect_city
  with patch.dict('city_sources.CITY_PAGES',{'수원':(2,2)}):
   with self.assertRaisesRegex(ValueError,'repeated page'):collect_city('수원',lambda u:"jsView('1179', '1');jsView('1179', '2')",record)

class WrappedPlaceAddressTests(unittest.TestCase):
 def test_separate_address_line_is_used_in_either_order(self):
  from city_sources import split_place
  self.assertEqual(split_place('예시식당\n용인시 처인구 용인대학로 74'),('예시식당','용인시 처인구 용인대학로 74'))
  self.assertEqual(split_place('수원시 팔달구 예시로 12\n예시식당'),('예시식당','수원시 팔달구 예시로 12'))
  self.assertEqual(split_place('한스케익\n인계점'),('한스케익\n인계점',None))

class SourceUnitConflictTests(unittest.TestCase):
 def test_contradictory_detail_and_summary_units_are_quarantined(self):
  from city_sources import validate_pdf_totals
  text='집행내역 총괄\n(단위 : 건/천원)\n업무추진비 6/1,579\n세부집행내역\n(단위 : 천원)'
  with self.assertRaisesRegex(ValueError,'Conflicting source units'):
   validate_pdf_totals([{'amount_krw':n*1000} for n in [90000,758000,45000,210000,153000,323000]],text)
  validate_pdf_totals([{'amount_krw':n} for n in [90000,758000,45000,210000,153000,323000]],text)
  validate_pdf_totals([{'amount_krw':90000000}],text) # A food subset cannot validate a whole-document total.

class AttachmentVersionTests(unittest.TestCase):
 def row(self,i,url,name='same.pdf',amount=50000):
  r=record(url,str(i),'2026-10-01','직원 식사','예시식당','5명',amount,'수원시','정책과');r.update(source_post_url='https://example.org/post',source_file_name=name,source_date='2026-10-01 12:00',executor='과장');return r
 def test_same_named_attachment_superset_is_counted_once(self):
  from city_sources import dedupe_attachment_versions
  a=self.row(1,'https://example.org/a');b=self.row(1,'https://example.org/b');c=self.row(2,'https://example.org/b',amount=70000)
  out=dedupe_attachment_versions([a,b,c]);self.assertEqual(len(out),2);self.assertEqual(sum(r['amount_krw'] for r in out),120000)
  self.assertEqual(out[0]['overlapping_attachment_urls'],['https://example.org/a'])
 def test_distinct_budgets_and_repeated_rows_within_one_file_are_preserved(self):
  from city_sources import dedupe_attachment_versions
  a=self.row(1,'https://example.org/a','기관운영.pdf');b=self.row(1,'https://example.org/b','시책추진.pdf');self.assertEqual(len(dedupe_attachment_versions([a,b])),2)
  a=self.row(1,'https://example.org/a');b=self.row(2,'https://example.org/a');self.assertEqual(len(dedupe_attachment_versions([a,b])),2)
