"""Refresh factual category/menu fields from public, already matched Kakao places.

No reviews, AI descriptions, photos, or inferred order details are republished.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import re
import subprocess
import time

from data_store import read_snapshot
from resolve_venues import norm

ROOT = Path(__file__).resolve().parents[1]
PLACE = re.compile(r'https://place\.map\.kakao\.com/(\d+)$')


def parse_profile(data, place_id, checked_at):
    summary = data.get('summary') or {}
    if str(summary.get('confirm_id')) != str(place_id):
        raise ValueError('Place ID mismatch')
    name = summary.get('name')
    address = summary.get('address') or {}
    point = summary.get('point') or {}
    if not name or not address.get('road', address.get('disp')):
        raise ValueError('Missing place identity')
    lat, lng = float(point['lat']), float(point['lon'])
    if not 33 < lat < 39 or not 124 < lng < 132:
        raise ValueError('Invalid place coordinate')
    category = summary.get('category') or {}
    menus = (data.get('menu') or {}).get('menus') or {}
    items = []
    for row in menus.get('items') or []:
        if not isinstance(row, dict) or not row.get('name'):
            continue
        price = row.get('price')
        items.append({
            'name': str(row['name']),
            'price_krw': price if isinstance(price, int) and not isinstance(price, bool) and price > 0 else None,
            'price_text': str(row.get('price_text') or '가격 미등록'),
            'recommended': row.get('is_recommend') is True,
            'source_updated_at': row.get('mod_at') or menus.get('items_updated_at'),
        })
    # Only an explicit source recommendation qualifies as a representative menu.
    items.sort(key=lambda m: not m['recommended'])
    return {
        'place_id': str(place_id), 'name': name,
        'address': address.get('road') or address['disp'],
        'location': {'lat': lat, 'lng': lng},
        'category': category.get('name'),
        'category_path': [category[k] for k in ['name1', 'name2', 'name3', 'name4'] if category.get(k)],
        'status': summary.get('status'),
        'menus': items, 'menu_updated_at': menus.get('items_updated_at'),
        'source_updated_at': (summary.get('meta') or {}).get('updated_at'),
        'source_url': 'https://place.map.kakao.com/' + str(place_id),
        'source_name': '카카오맵 등록 정보', 'checked_at': checked_at,
    }


def refresh(limit=40, days=30):
    path = ROOT / 'dist/restaurant-profiles.json'
    cache = json.loads(path.read_text()) if path.exists() else {'format': 'restaurant-profiles-v1', 'places': {}}
    data = read_snapshot(ROOT / 'dist')
    counts = Counter()
    names = {}
    for row in data['records']:
        match = PLACE.fullmatch((row.get('location') or {}).get('evidence_url', ''))
        if match:
            pid = match[1]
            counts[pid] += 1
            names.setdefault(pid, set()).add(norm(row.get('matched_merchant') or row['merchant']))
    now = datetime.now(timezone.utc)
    pending = []
    for pid, _ in counts.most_common():
        previous = cache['places'].get(pid)
        checked = datetime.fromisoformat(previous['checked_at']) if previous else None
        if not checked or now - checked >= timedelta(days=days):
            pending.append(pid)
    failures = 0
    for index, pid in enumerate(pending[:limit]):
        if index:
            time.sleep(1.1)
        try:
            body = subprocess.check_output(['curl', '-4', '-fsSL', '--connect-timeout', '5', '--max-time', '20',
                'https://place.map.kakao.com/places/panel3/' + pid], stderr=subprocess.PIPE)
            profile = parse_profile(json.loads(body), pid, now.isoformat())
            if norm(profile['name']) not in names[pid]:
                raise ValueError('Place name changed; retaining previous profile')
            cache['places'][pid] = profile
            failures = 0
            print(pid, profile['name'], len(profile['menus']), 'menus', flush=True)
            cache['updated_at'] = datetime.now(timezone.utc).isoformat()
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(cache, ensure_ascii=False, separators=(',', ':')) + '\n')
            temporary.replace(path)
        except Exception as exc:
            failures += 1
            print('Profile retained:', pid, type(exc).__name__, flush=True)
            if isinstance(exc, subprocess.CalledProcessError) and any(code in (exc.stderr or b'') for code in [b'403', b'429']):
                break
            if failures >= 3:
                break
    print('Profiles:', len(cache['places']), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=40)
    parser.add_argument('--days', type=int, default=30)
    args = parser.parse_args()
    refresh(args.limit, args.days)
