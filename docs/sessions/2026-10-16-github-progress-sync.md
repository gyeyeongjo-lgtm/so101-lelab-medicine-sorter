# 2026-10-16 GitHub 진행 상황 동기화

## 반영 범위

- 2026-10-14~15 SO-101 supervised teaching, contact release, atomic HOLD, single-session demo, LeLab UI safe entry 및 Torque writer 진단 코드와 요약 세션을 반영했다.
- 원본 로그, 비밀번호·키·토큰, 영상, 데이터셋, 모델 파일은 포함하지 않았다.
- 이번 복구 범위와 무관한 로컬 ArUco SVG 3개와 Charuco PDF 1개의 삭제는 커밋하지 않고 작업 폴더에 그대로 보존했다.

## 검증

- 관련 fake/unit test: `176/176 PASS`
- 변경 Python entrypoint compile: `PASS`
- staged whitespace 검사: `PASS`
- staged credential pattern 검사: 실제 credential 발견 없음. 고정 helper 하나만 허용하는 sudoers의 `NOPASSWD` 선언은 의도된 배포 파일이다.

## GitHub

- repository: `gyeyeongjo-lgtm/so101-lelab-medicine-sorter`
- branch: `fix/usb-recording`
- 진행 코드 커밋: `27c60b2 Add safe supervised demo recovery tooling`
- 원격 push: `PASS`

실제 모터 동작, serial open, Goal/Torque/config write 및 teaching 재실행은 이번 GitHub 동기화에서 `NOT_RUN`이다.

## 동기화 후 테스트 정합

- 작업 폴더를 다시 읽었을 때 위 두 커밋은 이미 원격에 있었고, 마커 SVG 3개와 Charuco PDF 1개 삭제만 별도 로컬 변경으로 남아 있었다. 기존 코드를 재커밋하지 않았다.
- 새 고정 포트 소유권 gate는 `/dev/ttyACM0`·`/dev/ttyACM1` 이외 조회를 거부한다. 두 구형 fuser fallback 테스트가 임시 디렉터리의 가짜 `ttyACM0`을 넘겨 오류가 났으므로, canonical 경로를 mock하고 helper 부재 상태를 명시해 원래 fuser fallback 의미를 그대로 검증하도록 테스트만 고쳤다.
- 프로젝트 가상환경의 관련 hardware-free 단위 시험 `194/194 PASS`, 로컬 캡처 서버 loopback 시험 `14/14 PASS`. 최초 전체 발견 실행 `615`개에는 로컬 Python의 `websocket` 누락, sandbox loopback bind 거부 및 위 구형 테스트 두 건이 섞인 오류 7건이 있었다. 이 전체 실행을 PASS로 보고하지 않는다.
- 실제 Jetson/serial/Goal/Torque/config write와 현장 동작 `NOT_RUN`. 원본 로그·비밀정보·데이터셋 추가 없음. 이슈 갱신 `NOT_RUN`.
