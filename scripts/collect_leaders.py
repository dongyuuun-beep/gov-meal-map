"""Incremental official minister/mayor disclosures; preserve failed attachments."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import html
import io
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urljoin

from collect import fetch, record
from city_sources import parse_attachment, parse_tables, attachments
from data_store import read_snapshot, write_snapshot
from leadership import annotate_all

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = {
    '통일부': ('https://www.unikorea.go.kr/web/unikorea/bbs/bbs_0000000000000125', 'unikorea'),
    '농림축산식품부': ('https://www.mafra.go.kr/home/5004/subview.do', 'mafra'),
    '수원시': ('https://www.suwon.go.kr/web/board/BD_board.list.do?bbsCd=1037', 'suwon'),
    '인천광역시': ('https://www.incheon.go.kr/open/OPEN010301', 'incheon'),
}


def links_in(text):
    return [(html.unescape(url), re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', ' ', body))).strip())
            for url, body in re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', text, re.I)]


def posts(institution, listing, limit=3):
    base, kind = PROVIDERS[institution]
    if kind == 'suwon':
        ids = list(dict.fromkeys(re.findall(r"jsView\('1037',\s*'([0-9]+)'", listing)))[:limit]
        return [('https://www.suwon.go.kr/web/board/BD_board.view.do?bbsCd=1037&seq=' + n, '') for n in ids]
    pattern = {'unikorea': r'/bbs_0000000000000125/\d+', 'mafra': r'/bbs/home/775/\d+/artclView.do', 'incheon': r'/open/OPEN010301/\d+'}[kind]
    result = {}
    for url, title in links_in(listing):
        if re.search(pattern, url) and '업무추진비' in title and (kind != 'mafra' or re.search('장.?차관', title)):
            result.setdefault(url.split('?')[0], title)
    return [(urljoin(base, u), title) for u, title in list(result.items())[:limit]]


def files(institution, text):
    base, kind = PROVIDERS[institution]
    patterns = {'unikorea': r'/file/download/uu/', 'mafra': r'/bbs/home/775/\d+/download.do', 'suwon': 'ND_fileDownload', 'incheon': '/comm/getFile'}
    result = {}
    for url, title in links_in(text):
        if re.search(patterns[kind], url):
            result.setdefault(urljoin(base, url), title)
    return list(result.items())


def parse_incheon(body, url, title):
    import pdfplumber
    tables = []
    with pdfplumber.open(io.BytesIO(body)) as pdf:
        for pi, page in enumerate(pdf.pages):
            for ti, table in enumerate(page.extract_tables()):
                header = [re.sub(r'\s+', '', c or '') for c in table[0]]
                if header[:8] != ['일자', '시간', '장소', '인원', '대상', '사용지역', '금액', '내역']:
                    continue
                table[0][7] = '사용목적'
                if len(table[0]) == 9:
                    table[0][8] = '사용방법'
                rows = [(str(ri), [(str(ci), cell or '') for ci, cell in enumerate(cells)]) for ri, cells in enumerate(table)]
                tables.append((str(pi) + '!table' + str(ti), rows))
    result, found = parse_tables(tables, url, '인천', title, record)
    if not found:
        raise ValueError('Incheon detail table not recognized')
    original = {sheet + '!' + rn: dict(cells) for sheet, rows in tables for rn, cells in rows}
    for row in result:
        cells = original[row['source_row']]
        row['participant_text'] = cells.get('4', '') + ' · 기재 ' + cells.get('3', '') + '명'
        row['spending_region'] = '인천' if cells.get('5') == '인천' else row.get('spending_region')
    return result


def collect_one(institution, limit=3):
    base, kind = PROVIDERS[institution]
    rows, completed, errors = [], set(), []
    for post, heading in posts(institution, fetch(base), limit):
        try:
            text = fetch(post)
            if kind == 'suwon':
                candidates = re.findall(r'20\d\d년\s*\d{1,2}월\s*수원시장\s*업무추진비[^<\n]{0,30}', text)
                if not candidates:
                    raise ValueError('Mayor disclosure title missing')
                heading = html.unescape(candidates[0])
            documents = files(institution, text)
            if not documents:
                raise ValueError('No public attachment')
            for url, filename in documents:
                try:
                    body = subprocess.check_output(['curl', '-4', '-fsSL', '--connect-timeout', '5', '--max-time', '25', url], stderr=subprocess.PIPE)
                    batch = parse_incheon(body, url, heading) if kind == 'incheon' else parse_attachment(body, url, institution.removesuffix('시'), heading, record)
                    role = '시장' if kind in ['suwon', 'incheon'] else '차관' if re.search(r'\(?차관\)?', filename) and '장관' not in filename else '장관' if '장관' in filename and '차관' not in filename else None
                    for row in batch:
                        row.update(institution=institution, source_post_url=post, source_dataset=institution + ' 고위직 공식 공개 첨부', source_city='수원' if kind == 'suwon' else None,
                                   source_license='공개 원문 사실 추출 · 원문 링크 제공', disclosure_role=role,
                                   disclosure_label=('수원시장' if kind == 'suwon' else '인천시장') + ' 공개내역' if kind in ['suwon', 'incheon'] else role,
                                   source_file_name=filename)
                    rows.extend(batch)
                    completed.add(url)
                except Exception as exc:
                    errors.append({'url': url, 'error': str(exc)[:250]})
        except Exception as exc:
            errors.append({'url': post, 'error': str(exc)[:250]})
    if not rows and not completed:
        raise ValueError('No readable leader records: ' + json.dumps(errors[:2], ensure_ascii=False))
    return rows, completed, errors


def refresh(limit=3):
    data = read_snapshot(ROOT / 'dist')
    old = {r['id']: r for r in data['records']}
    additions, completed, statuses = [], set(), []
    def run(institution):
        try:
            batch, done, errors = collect_one(institution, limit)
            return batch, done, {'source': institution + ' 고위직 공개', 'url': PROVIDERS[institution][0], 'status': 'partial' if errors else 'success', 'rows': len(batch), 'failed_files': errors}
        except Exception as exc:
            return [], set(), {'source': institution + ' 고위직 공개', 'url': PROVIDERS[institution][0], 'status': 'failed', 'error': str(exc)[:300]}
    with ThreadPoolExecutor(2) as pool:
        for batch, done, status in pool.map(run, PROVIDERS):
            additions.extend(batch); completed.update(done); statuses.append(status)
            print(status['source'], status['status'], status.get('rows'), flush=True)
    if not completed:
        print('All leader sources failed; retaining every existing record', flush=True)
    records = {r['id']: r for r in data['records'] if r['source_url'] not in completed}
    now = datetime.now(timezone.utc).isoformat()
    for row in additions:
        previous = old.get(row['id'], {})
        row['collected_at'] = previous.get('collected_at', now)
        if row['merchant'] == previous.get('merchant') and row.get('address') == previous.get('source_address', previous.get('address')):
            for key in ['address', 'source_address', 'location', 'address_match', 'matched_merchant', 'spending_city', 'spending_region']:
                if previous.get(key) and not row.get(key):
                    row[key] = previous[key]
        records[row['id']] = row
    annotate_all(records.values())
    data['records'] = sorted(records.values(), key=lambda r: (r.get('date') or '', r['id']), reverse=True)
    sources = {st['source'] for st in statuses}
    data['source_status'] = [st for st in data['source_status'] if st['source'] not in sources] + statuses
    data['scope'] += ' · 통일부·농식품부 장차관 및 수원·인천시장 최근 공개 첨부 일부.' if '통일부·농식품부' not in data['scope'] else ''
    data['updated_at'] = now
    write_snapshot(ROOT / 'dist', data)
    (ROOT / 'dist/leader-sources.json').write_text(json.dumps({'checked_at': now, 'sources': statuses}, ensure_ascii=False, indent=2) + '\n')
    print('Leader refresh:', len(additions), 'candidate expenses;', len(data['records']), 'total', flush=True)


if __name__ == '__main__':
    refresh()
