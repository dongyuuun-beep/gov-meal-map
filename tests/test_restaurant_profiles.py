import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from refresh_restaurant_profiles import parse_profile


class RestaurantProfileTests(unittest.TestCase):
    def source(self):
        return {'summary': {'confirm_id': '123', 'name': '식당', 'address': {'road': '경기 수원시 효원로 12'},
                'point': {'lat': 37.26, 'lon': 127.03}, 'category': {'name': '한식', 'name1': '음식점'}, 'status': 'Y'},
                'menu': {'menus': {'items_updated_at': '2023-08-01', 'items': [
                    {'name': '코스', 'price': -1, 'price_text': '변동가격', 'is_ai_mate': True, 'ai_mate_desc': '복제하지 않을 설명'},
                    {'name': '정식', 'price': 15000, 'is_recommend': True, 'mod_at': '2026-11-12'},
                    {'name': '미등록 가격', 'price': 0}]}}}

    def test_registered_prices_and_explicit_recommendation(self):
        profile = parse_profile(self.source(), '123', '2026-11-14T00:00:00+00:00')
        self.assertEqual(profile['menus'][0]['name'], '정식')
        self.assertTrue(profile['menus'][0]['recommended'])
        self.assertEqual(profile['menus'][0]['price_krw'], 15000)
        self.assertEqual(profile['menus'][0]['source_updated_at'], '2026-11-12')
        self.assertIsNone(profile['menus'][1]['price_krw'])
        self.assertFalse(profile['menus'][1]['recommended'])
        self.assertEqual(profile['menus'][1]['price_text'], '변동가격')
        self.assertNotIn('ai_mate_desc', str(profile))
        self.assertIsNone(profile['menus'][2]['price_krw'])

    def test_wrong_place_or_bad_coordinate_rejected(self):
        with self.assertRaises(ValueError):
            parse_profile(self.source(), '456', '2026-11-14')
        data = self.source()
        data['summary']['point']['lat'] = 0
        with self.assertRaises(ValueError):
            parse_profile(data, '123', '2026-11-14')

    def test_missing_menu_is_preserved_as_unknown(self):
        data = self.source()
        data.pop('menu')
        self.assertEqual(parse_profile(data, '123', '2026-11-14')['menus'], [])


if __name__ == '__main__':
    unittest.main()
