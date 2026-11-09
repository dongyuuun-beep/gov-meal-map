import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from license_locations import address_keys,build_index,match_location
class LocationTests(unittest.TestCase):
 def index(self,rows):return build_index(rows,None)
 def license(self,**kw):return dict(MGTNO='example',BPLCNM='식당',RDNWHLADDR='서울특별시 중구 무교로 21',SITEWHLADDR='서울특별시 중구 다동 1',lat=37.566,lng=126.98,**kw)
 def test_road_number_is_not_lane_number(self):
  self.assertIn(('road','중구','을지로12길','22'),address_keys('서울 중구 을지로 12길 22'))
 def test_exact_address_has_evidence(self):
  r=dict(merchant='식당',address='중구 무교로 21',spending_region='서울')
  p=match_location(r,self.index([self.license()]))
  self.assertEqual(p['license_id'],'example');self.assertIn('OA-16094',p['evidence_url'])
 def test_same_name_without_address_not_mapped(self):
  self.assertIsNone(match_location(dict(merchant='식당',address='중구',spending_region='서울'),self.index([self.license()])))
 def test_distant_candidates_are_not_arbitrarily_chosen(self):
  a=self.license();b={**a,'MGTNO':'other','lat':37.58}
  self.assertIsNone(match_location(dict(merchant='식당',address='중구 무교로 21',spending_region='서울'),self.index([a,b])))
