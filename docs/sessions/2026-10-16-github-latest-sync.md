# 2026-10-16 GitHub 최신 동기화

## 반영 대상

현재 작업 트리에서 완료한 다음 결과를 한 리팩터링 커밋으로 묶었다.

- `python -m medicine_sorter` 단일 진입점과 mock workflow
- task별 readiness와 read-only SO-101 status adapter
- 고정 데모용 `supervised_teaching`/`fixed_demo` readiness
- Astra 새 작업대 좌표, intrinsic 적용, current-frame homography와 frozen-click UI
- P1–P4 독립 검증 원자료와 미해결 오차 기록
- ID0–6 70 mm 및 약통 ID7–9 30 mm ArUco PDF
- 대체된 실험 전용 실행기·전용 테스트 정리

첫 동기화 커밋은 `d0b00e0` (`Refactor sorter and validate Astra table`)이며
원격 `origin/fix/usb-recording`에 push했다. 삭제된 tracked 실행기의 사전 상태는
로컬 ref `refs/backup/pre-refactor-20261016`의 snapshot `8d37077d`에 보존했다.

## 제외

다음은 GitHub에 올리지 않았다.

- `.local/` 장비별 보정·실측 자산
- `models/`, `datasets/`, 원본 로그와 영상
- `tmp/` 생성 중간물과 렌더링 확인 이미지
- 비밀번호, key, token 등 credential
- `.venv/`, cache, Jetson 활성 파일의 로컬 backup

## 검증

`.venv` Python에서 다음을 실행했다.

- Astra/UI tests: `17/17 PASS`
- teach-capture tests: `14`개 중 `10 PASS`, `4 SKIPPED`
- sorter command/config/robot/vision tests: `30/30 PASS`
- Python compile: PASS
- staged `git diff --check`: PASS
- staged 파일 1 MiB 초과: 없음
- credential pattern 검사: 실제 credential 발견 없음

전체 legacy discovery는 시스템 Python에 `cv2`가 없어 8 error, 과거
600 mm marker reference를 기대하는 테스트 1 failure, 4 skip이므로 전체 PASS로
표현하지 않는다. 이는 제한 데모 readiness 문서에도 보존했다.

## 하드웨어 상태

Git 작업과 테스트만 수행했다. robot serial open, Goal/Torque/config write,
motor command, 서비스 재시작, USB 조작은 모두 `0/NOT_RUN`이다. 카메라 독립 검증
오차는 `UNRESOLVED`, live motion adapter는 `NOT_IMPLEMENTED`, 실제 제한 데모는
`BLOCKED/NOT_RUN` 상태를 유지한다.
