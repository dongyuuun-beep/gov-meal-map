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
