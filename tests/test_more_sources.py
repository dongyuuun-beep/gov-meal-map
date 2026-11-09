import sys,unittest,io,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from more_sources import loose_json,participants,region,parse_sejong
from collect import record
class AdditionalSourceTests(unittest.TestCase):
 def test_json_strings_not_rewritten(self):
  self.assertEqual(loose_json('{result:"ok",list:[{x:"literal,{KEY: untouched",},]}')['list'][0]['x'],'literal,{KEY: untouched')
 def test_attendee_totals(self):
  self.assertEqual(participants('과장 외 10명(총 11명)'),11)
  self.assertEqual(participants('과장 외 3명'),4)
  self.assertIsNone(participants('업무관계자'))
 def test_sejong_daero_is_seoul(self):
  self.assertEqual(region('중구 세종대로 124'),'서울')
  self.assertEqual(region('세종 한누리대로 2144'),'세종')
  self.assertEqual(region('부산광역시 강서구 녹산산단로 123'),'부산')
 def test_xlsx_commas_serial_date_missing_people(self):
  xml='''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="5"><c r="A5" t="inlineStr"><is><t>연번</t></is></c><c r="F5" t="inlineStr"><is><t>금액(원)</t></is></c></row><row r="6"><c r="A6"><v>1</v></c><c r="B6"><v>46266.5</v></c><c r="C6" t="inlineStr"><is><t>예시식당</t></is></c><c r="D6" t="inlineStr"><is><t>중식 제공</t></is></c><c r="F6" t="inlineStr"><is><t>159,900</t></is></c></row></sheetData></worksheet>'''
  b=io.BytesIO()
  with zipfile.ZipFile(b,'w') as z:z.writestr('xl/worksheets/sheet1.xml',xml)
  rows=parse_sejong(b.getvalue(),'https://example.org',record)
  self.assertEqual(rows[0]['amount_krw'],159900);self.assertEqual(rows[0]['date'],'2026-09-01');self.assertIsNone(rows[0]['participants'])

class PaginationTests(unittest.TestCase):
 def test_overlap_removed_without_dropping_distinct_source_documents(self):
  from more_sources import normalize_seoul
  row=dict(RONUM='7',NID='doc-a',URL='https://example.org/a',EXEC_DT='2026-10-01 12:00',EXEC_LOC='예시식당(중구 무교로 21)',EXEC_AMOUNT='10000',EXEC_PURPOSE='정책 간담회',TARGET_NM='과장 외 2명',DEPT_NM='정책과')
  other={**row,'NID':'doc-b','URL':'https://example.org/b'}
  records=normalize_seoul([[row],[row,other]],record)
  self.assertEqual(len(records),2);self.assertEqual(sum(r['amount_krw'] for r in records),20000)
  self.assertEqual(records[0]['participants'],3)
