import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from resolve_venues import choose
class VenueTests(unittest.TestCase):
 def place(self,**kw):return dict(name='예시식당 수원점',new_address='경기 수원시 팔달구 예시로 12',lat=37.26,lon=127.03,confirmid='1',cate_name_depth1='음식점',openoff_status='Y',**kw)
 def test_branch_exact_name_and_city(self):
  self.assertIsNotNone(choose({'place':[self.place()]},'수원','예시식당 수원점'))
  self.assertIsNone(choose({'place':[self.place()]},'용인','예시식당 수원점'))
  self.assertIsNone(choose({'place':[self.place()]},'수원','예시식당 용인점'))
 def test_ambiguous_places_and_generic_chains_rejected(self):
  p=self.place();p2={**p,'confirmid':'2'}
  self.assertIsNone(choose({'place':[p,p2]},'수원','예시식당 수원점'))
  self.assertIsNone(choose({'place':[p]},'수원','스타벅스'))
 def test_source_address_exact_road_and_number(self):
  p=dict(addr='경기 용인시 처인구 용인대학로 74',lat=37.2322,lon=127.1747)
  self.assertIsNotNone(choose({'address':[p]},'용인','식당','용인시 용인대학로 74'))
  self.assertIsNone(choose({'address':[p]},'용인','식당','용인시 용인대학로 75'))
 def test_imprecise_coordinates_rejected(self):
  p={**self.place(),'lat':37,'lon':127}
  self.assertIsNone(choose({'place':[p]},'수원','예시식당 수원점'))
 def test_wrapped_single_merchant_name_can_match_but_multiple_merchants_cannot(self):
  from resolve_venues import multiple
  p={**self.place(),'name':'한스케익 인계점'}
  self.assertIsNotNone(choose({'place':[p],'place_totalcount':1},'수원','한스케익\n인계점'))
  self.assertTrue(multiple('한스케익, 다른카페'))
  self.assertIsNone(choose({'place':[p],'place_totalcount':1},'수원','한스케익 외 2개소'))
 def test_known_chain_brand_alias_still_requires_identical_branch(self):
  p={**self.place(),'name':'이디야커피 수원인계점'}
  self.assertIsNotNone(choose({'place':[p],'place_totalcount':1},'수원','이디야 수원인계점'))
  self.assertIsNone(choose({'place':[p],'place_totalcount':1},'수원','이디야 수원역점'))
  self.assertIsNone(choose({'place':[p],'place_totalcount':1},'수원','이디야'))
 def test_lot_address_and_compact_road_address_keep_municipal_context(self):
  from resolve_venues import address_parts
  self.assertEqual(address_parts('용인시수지구풍덕천동123-4'),('용인','lot','','풍덕천동','','123-4'))
  self.assertNotEqual(address_parts('화성시 팔탄면 구장리 12'),address_parts('화성시 다른면 구장리 12'))
  self.assertEqual(address_parts('용인시처인구용인대학로74'),('용인','용인대학로','74'))
  p=dict(addr='경기 용인시 수지구 풍덕천동 123-4',lat=37.32,lon=127.09)
  self.assertIsNotNone(choose({'address':[p]},'용인','식당','용인시 수지구 풍덕천동 123-4'))
  self.assertIsNone(choose({'address':[p]},'용인','식당','용인시 수지구 풍덕천동 123-5'))
