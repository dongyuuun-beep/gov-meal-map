"""Identify a disclosed user/office; never infer personal attendance from a purpose."""
import re

ROLES = ['장관', '차관', '시장', '부시장', '구청장', '부구청장', '도지사', '부지사', '군수', '부군수']


def role_from_user(value):
    text = re.sub(r'\s+', '', value or '')
    if any(word in text for word in ['비서', '직원', '수행', '담당', '과장', '국장', '실장', '위원']):
        return None
    for role in ['부구청장', '구청장', '부시장', '시장', '부지사', '도지사', '부군수', '군수', '차관', '장관']:
        if re.search(re.escape(role) + r'(?:직무대리)?(?:[가-힣]{2,4})?$', text):
            return role
    return None


def department_name(row):
    text = row.get('department') or '부서 미확인'
    if not re.search(r'20\d\d년', text):
        return text
    matches = re.findall(r'\(([^()]+)\)', text)
    if matches:
        return matches[-1].strip()
    match = re.search(r'(?:\d{1,2}월\s*)(.*?)\s*업무추진비', text)
    return match[1].strip() if match and match[1].strip() else text


def annotate(row):
    row['department_name'] = department_name(row)
    row['department_key'] = row['institution'] + ' · ' + row['department_name']
    user = row.get('executor') or ''
    role = role_from_user(user)
    label = user.strip()
    basis = '원문 사용자 기재' if role else None
    if not role and not user and row.get('disclosure_role') in ROLES:
        role = row['disclosure_role']
        label = row.get('disclosure_label') or role + ' 공개내역'
        basis = '직위별 공개 단위 · 본인 참석 확인 아님'
    if not role and not user:
        dept = row.get('department') or ''
        if re.fullmatch(r'(?:행정[12]|정무)?부시장실', dept):
            role, label, basis = '부시장', dept, '부시장실 집행부서 · 본인 참석 확인 아님'
        elif dept == '시장':
            role, label, basis = '시장', '시장 공개내역', '시장 전용 공개 단위 · 본인 참석 확인 아님'
    if role:
        if label == '구청장':
            districts = set(re.findall(r'[가-힣]+구청장', row.get('department') or ''))
            if len(districts) == 1:
                label = next(iter(districts))
        row.update(leader_role=role, leader_label=row['institution'] + ' · ' + label, leader_basis=basis)
    else:
        for key in ['leader_role', 'leader_label', 'leader_basis']:
            row.pop(key, None)
    return row


def annotate_all(rows):
    for row in rows:
        annotate(row)
