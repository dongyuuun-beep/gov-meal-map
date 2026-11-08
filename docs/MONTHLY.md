# 월별 갱신 운영 지침

GitHub: https://github.com/dongyuuun-beep/gov-meal-map. 사용자 생성 저장소에 소스와 워크플로를 푸시했습니다. Sites와 GitHub의 두 원격을 최신 상태로 유지합니다.

Site ID는 `.openai/hosting.json`을 읽고 그대로 사용합니다. 새로운 Site를 만들지 않습니다. 같은 Site의 소스 저장소에서 이 지침을 읽을 수 있습니다.

## 운영 경로 (AI 불필요)

1. GitHub Actions `monthly.yml`이 매월 15일 09:20 Asia/Seoul에 실행됩니다.
2. 테스트 → `python scripts/collect.py` → 데이터 커밋 → 재사용 `deploy.yml` → GitHub Pages 배포.
3. 실패한 개별 출처는 기존 데이터를 유지하고 `source_status`에 오류를 기록합니다. 모든 출처가 실패하면 원래 데이터와 배포를 유지하고 워크플로를 실패 처리합니다.
4. GitHub Pages Settings의 Source는 GitHub Actions입니다. 개인 API 키·ChatGPT 구독·이 채팅 실행은 필요 없습니다.
5. 수동 갱신: Actions → Monthly data refresh → Run workflow.
6. 코드/화면 수정은 main에 push하면 Pages를 다시 배포합니다. 수집 워크플로 내부의 GITHUB_TOKEN 커밋은 push 이벤트를 새로 만들지 않으므로, 수집 완료 후 reusable deploy job을 명시적으로 호출합니다.
7. Sites의 ChatGPT 월별 작업은 중지했습니다. Sites는 초기 비공개 미리보기이며 GitHub Pages가 운영본입니다. Sites 재배포가 필요하면 현재 Sites 스킬 절차로 별도 수행합니다.

현재 수집 범위: 경기도 감사1과 고정 HTML 예시 재확인 + 울산시장 최신 목록의 상세 HTML. 전국 자동 전수 수집이 아닙니다. 최근 6개월 페이지 순회·추가 기관·PDF/HWP·위치 검수는 후속 작업입니다. 공식 사이트가 양식이나 주소를 바꾸면 수집기 유지보수가 필요합니다.
