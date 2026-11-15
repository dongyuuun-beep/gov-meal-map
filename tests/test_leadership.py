import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from leadership import annotate, department_name
from data_store import pack_snapshot
from collect_leaders import posts,files
from resolve_leader_venues import choose

class LeadershipTests(unittest.TestCase):
 def row(self,**values):return dict(id='x',institution='용인시',department='정책과',merchant='식당',date='2026-10-01',amount_krw=80000,**values)
 def test_raw_user_and_department_are_not_attendance(self):
  r=annotate(self.row(executor='제1부시장'))
  self.assertEqual(r['leader_role'],'부시장');self.assertEqual(r['leader_basis'],'원문 사용자 기재')
  r=annotate(self.row(participant_text='시장 외 4명',purpose='구청장과 간담회'))
  self.assertNotIn('leader_role',r)
 def test_deputy_mayor_office_and_unrelated_general_affairs(self):
  r=self.row();r['department']='행정1부시장실';annotate(r)
  self.assertEqual(r['leader_role'],'부시장');self.assertIn('본인 참석 확인 아님',r['leader_basis'])
  r=self.row();r['department']='행정국 총무과';annotate(r)
  self.assertNotIn('leader_role',r)
 def test_source_scope_does_not_override_explicit_other_user(self):
  r=annotate(self.row(executor='비서실장',disclosure_role='시장'))
  self.assertNotIn('leader_role',r)
  r=annotate(self.row(disclosure_role='시장',disclosure_label='수원시장 공개내역'))
  self.assertEqual(r['leader_role'],'시장');self.assertIn('공개 단위',r['leader_basis'])
 def test_specific_district_and_mixed_sources(self):
  r=self.row(executor='구청장');r['department']='2026년 10월 업무추진비 집행내역(처인구청장, 대민협력관)';annotate(r)
  self.assertIn('처인구청장',r['leader_label'])
  r['executor']='대민협력관';annotate(r);self.assertNotIn('leader_role',r)
 def test_department_normalization_and_snapshot_preservation(self):
  r=self.row(executor='제2부시장');r['department']='2026년 10월 업무추진비(회계과)';annotate(r)
  self.assertEqual(r['department_name'],'회계과')
  packed=pack_snapshot({'records':[r]});source=packed['sources'][0]
  self.assertEqual(source['executor'],'제2부시장');self.assertEqual(source['leader_role'],'부시장')
 def test_discovery_only_expected_board_and_leadership_posts(self):
  html='<a href="/bbs/home/775/123/artclView.do">2026년 9월 장·차관 업무추진비 집행내역</a><a href="/bbs/home/775/124/artclView.do">정책과 업무추진비</a>'
  self.assertEqual(len(posts('농림축산식품부',html)),1)
  self.assertEqual(len(files('통일부','<a href="/web/unikorea/file/download/uu/abc">장관.pdf</a>')),1)
 def test_ambiguous_branches_never_get_a_pin(self):
  place=dict(name='예시식당 광화문점',lat='37.5',lon='127.0',new_address='서울 종로구 예시로 12',confirmid='123',cate_name_depth1='음식점')
  self.assertIsNotNone(choose({'place':[place],'place_totalcount':1},place['name']))
  self.assertIsNone(choose({'place':[place],'place_totalcount':2},place['name']))
  self.assertIsNone(choose({'place':[place],'place_totalcount':1},'다른식당'))

class LeaderRefreshPreservationTests(unittest.TestCase):
 def test_complete_outage_keeps_previous_expenses_and_reports_failures(self):
  import copy,tempfile
  from unittest.mock import patch
  import collect_leaders
  previous={'records':[{'id':'old','institution':'통일부','department':'장관 공개내역','merchant':'식당','amount_krw':80000,'source_url':'https://example.org/old','date':'2026-10-01','disclosure_role':'장관'}],'scope':'previous history','source_status':[]}
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'dist').mkdir()
   with patch.object(collect_leaders,'ROOT',root),patch.object(collect_leaders,'read_snapshot',return_value=copy.deepcopy(previous)),patch.object(collect_leaders,'collect_one',side_effect=OSError('offline')),patch.object(collect_leaders,'write_snapshot') as write:
    collect_leaders.refresh()
    output=write.call_args.args[1]
    self.assertEqual([r['id'] for r in output['records']],['old'])
    self.assertEqual(output['records'][0]['amount_krw'],80000)
    self.assertEqual(len(output['source_status']),4)
    self.assertTrue(all(st['status']=='failed' for st in output['source_status']))
