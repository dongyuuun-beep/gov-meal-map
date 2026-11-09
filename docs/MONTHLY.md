# 매일 갱신 운영 지침

운영 저장소: https://github.com/dongyuuun-beep/gov-meal-map. GitHub Pages가 운영본이며 GitHub Actions가 채팅 없이 수집·배포합니다.

## 운영 경로 (AI 불필요)

1. GitHub Actions `monthly.yml`이 매일 오전 10:00 Asia/Seoul에 실행됩니다.
2. 테스트 → `python scripts/collect.py` → 데이터 커밋 → 재사용 `deploy.yml` → GitHub Pages 배포.
3. 실패한 개별 출처는 기존 데이터를 유지하고 `source_status`에 오류를 기록합니다. 모든 출처가 실패하면 원래 데이터와 배포를 유지하고 워크플로를 실패 처리합니다.
4. GitHub Pages Settings의 Source는 GitHub Actions입니다. 개인 API 키·ChatGPT 구독·이 채팅 실행은 필요 없습니다.
5. 수동 갱신: Actions → Daily data refresh → Run workflow.
6. 코드/화면 수정은 main에 push하면 Pages를 다시 배포합니다. 수집 워크플로 내부의 GITHUB_TOKEN 커밋은 push 이벤트를 새로 만들지 않으므로, 수집 완료 후 reusable deploy job을 명시적으로 호출합니다.
7. Sites의 ChatGPT 매일 작업은 중지했습니다. Sites는 초기 비공개 미리보기이며 GitHub Pages가 운영본입니다. Sites 재배포가 필요하면 현재 Sites 스킬 절차로 별도 수행합니다.

현재 수집 범위: 서울시 본청 2023~2026년 이력을 보존하며 최신 6,000행 중 식음료 후보 갱신 + 세종시의회 최신 게시글 6개 중 업무추진비 XLSX + 경기도 감사1과 고정 HTML 예시 재확인 + 울산시장 최신 목록의 상세 HTML. 전국 자동 전수 수집이 아닙니다. 최근 6개월 페이지 순회·추가 기관·PDF/HWP·위치 검수는 후속 작업입니다. 공식 사이트가 양식이나 주소를 바꾸면 수집기 유지보수가 필요합니다.

좌표 인덱스는 OA-16094의 전체 기준 자료를 보존하고, 매일 최신 영업 자료 10,000행을 재확인합니다. pyproj는 공식 좌표계를 위경도로 변환하는 데 사용합니다. 인덱스 갱신 실패 시 기존 좌표 증거를 유지합니다. source row pagination은 pageNo 1,11,21,...이며 문서 ID·RONUM·거래 필드 복합 키 중복을 검사합니다.
