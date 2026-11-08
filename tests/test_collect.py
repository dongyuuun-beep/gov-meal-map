import importlib.util
import unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('collect',Path(__file__).resolve().parents[1]/'scripts/collect.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

class ParserTests(unittest.TestCase):
    def test_ulsan_thousands_and_exclusion(self):
        html='<table><tr>'+''.join('<th>'+x+'</th>' for x in ['번호','결제내용','결제방법','인원(수량)','금액(천원)','참석대상','장소'])+'</tr><tr>'+''.join('<td>'+x+'</td>' for x in ['1','관계자 간담회','카드','9','360','관계자','예시식당'])+'</tr><tr>'+''.join('<td>'+x+'</td>' for x in ['2','경조금 지급','현금','1','50','직원','-'])+'</tr></table>'
        rows=c.parse_ulsan(html,'https://example.org','2026-08-04')
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['amount_krw'],360000);self.assertEqual(rows[0]['participants'],9)
    def test_missing_participants(self):
        r=c.record('https://example.org',1,None,'간담회','상호','관계자 등',10000,'기관','부서')
        self.assertIsNone(r['participants'])
    def test_schema_failure(self):
        with self.assertRaises(ValueError):c.parse_ulsan('<html>접근 차단</html>','https://example.org','2026-08-04')
    def test_no_speculative_company_dinner(self):
        self.assertEqual(c.category('업무협의 간담회'),'간담회')

if __name__=='__main__':unittest.main()
