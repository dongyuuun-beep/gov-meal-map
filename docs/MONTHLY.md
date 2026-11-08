# 월별 갱신 운영 지침

GitHub: https://github.com/dongyuuun-beep/gov-meal-map. 사용자 생성 저장소에 소스와 워크플로를 푸시했습니다. Sites와 GitHub의 두 원격을 최신 상태로 유지합니다.

Site ID는 `.openai/hosting.json`을 읽고 그대로 사용합니다. 새로운 Site를 만들지 않습니다. 같은 Site의 소스 저장소에서 이 지침을 읽을 수 있습니다.

1. GitHub 저장소 또는 Sites 소스 저장소 최신 소스를 정상 인증된 GitHub/Sites 접근으로 열기. 소스 접근 권한을 먼저 확인합니다.
2. `python scripts/collect.py` 실행. 경기도 감사1과는 고정 HTML 예시만 재확인, 울산시장 최신 목록의 날짜별 상세를 탐색합니다. 다른 기관이 수집되었다고 주장하지 않습니다.
3. `python -m unittest discover -s tests`, `node tests/core.test.cjs`, `node --check dist/app.js` 실행.
4. 실패 시 기존 정상 배포를 유지합니다. 원인과 영향 기관을 사용자에게 보고합니다. 오류 페이지나 빈 응답으로 기존 파일을 덮어쓰지 않습니다.
5. 새 `dist/data.json`의 집행 건수·금액·인원 단위·위치 확인 건수를 확인합니다. 위치는 `config/locations.json`에서 검증된 대응만 허용합니다. 이름 유사성만으로 임의 좌표를 추가하지 않습니다.
6. GitHub 저장소가 실제로 연결되어 있는 경우 인증된 접근으로 변경 데이터를 커밋·푸시합니다. 미연결이면 이 단계를 건너뛰고 Sites 갱신을 계속합니다. 원격 HEAD가 바뀌면 먼저 최신 변경을 보존해 통합합니다.
7. 같은 Site의 소스 저장소에 동기화하고, 현재 Sites 스킬의 검증·패키징·비공개 배포 절차로 정적 웹앱을 갱신합니다. `.openai/hosting.json`의 ID와 기존 접근 범위를 유지합니다.
8. 배포 성공을 읽어 확인한 뒤 건수·수집범위·누락·정정 반영 사항을 짧게 보고합니다.

GitHub cron: 매월 15일 09:20 Asia/Seoul. Sites 연결 작업: 매월 15일 10:00 Asia/Seoul. Actions는 데이터 이력을 독립 보관하며, Sites 작업도 같은 수집기를 재실행해 Actions 지연에 의존하지 않습니다. 두 저장소 데이터는 동일 행 ID로 갱신하므로 중복 합산하지 않습니다.

현재 알려진 제한: 경기도 신규 게시글 탐색 차단, 울산 목록 첫 페이지 범위, 첨부파일 기관 미연결, 식당 지점·좌표 다수 미확인. 최근 6개월 페이지 순회와 모든 중앙부처/광역 본청 연결은 추가 개발 과제입니다.
