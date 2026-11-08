import importlib.util
import unittest
import tempfile
import json
from unittest.mock import patch
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
    def test_total_outage_keeps_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'dist').mkdir()
            path=root/'dist/data.json';path.write_text('{"records":[]}')
            before=path.read_bytes()
            with patch.object(c,'ROOT',root),patch.object(c,'fetch',side_effect=TimeoutError('offline')):
                with self.assertRaises(ValueError):c.collect()
            self.assertEqual(path.read_bytes(),before)
    def test_partial_outage_preserves_failed_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'dist').mkdir();(root/'config').mkdir()
            old=c.record(c.GG_SEED,1,'2025-09-26','간담회','기존상호','6명',121000,'경기도','감사1과')
            (root/'dist/data.json').write_text(json.dumps({'records':[old]}));(root/'config/locations.json').write_text('{}')
            new=c.record(c.ULSAN+'&useDe=2026-08-04',1,'2026-08-04','간담회','신규상호','9명',360000,'울산광역시','시장')
            def fake_fetch(url):
                if url==c.GG_SEED:raise TimeoutError('offline')
                return '2026-08-04'
            with patch.object(c,'ROOT',root),patch.object(c,'fetch',side_effect=fake_fetch),patch.object(c,'parse_ulsan',return_value=[new]):c.collect()
            result=json.loads((root/'dist/data.json').read_text())
            self.assertEqual(len(result['records']),2)
            self.assertTrue(any(s['status']=='failed' for s in result['source_status']))

if __name__=='__main__':unittest.main()
