# 2026-09-05 초기 접근 기록

- 날짜/시간 및 시간대: 2026-09-05T20:52:40+09:00
- 실행 위치: Mac
- 관련 이슈: GitHub #1–#4
- 상태: `PASS` (Phase A 조사·백업·private 저장소), `BLOCKED` (물리 안전), `NOT_RUN` (실제 녹화)

## 실행 및 관측

1. 복구 지시서 787줄과 Mac 시작 안내 170줄을 전체 확인했다.
2. Mac 운영체제, Git 작업 트리, SSH 계산 설정, GitHub CLI 설치 여부를 읽기 전용으로 조사했다.
3. Jetson의 SSH 22번과 LeLab 8000번 TCP 응답을 확인했다.
4. SSH 접속은 기존 호스트 키가 없어 검증 단계에서 중단했다. 호스트 키 검증을 끄거나 `known_hosts`를 변경하지 않았다.
5. GitHub CLI가 없어 인증 상태 확인과 비공개 저장소 생성은 실행하지 않았다.
6. 사용자가 Jetson ED25519 지문을 확인했다. 프로젝트 전용 known-hosts 파일에 해당 공개키를 고정하고 지문 일치를 재검증했다.
7. 공식 GitHub CLI v2.100.0 arm64 바이너리를 프로젝트 내부에 설치했고 공식 체크섬 검증을 통과했다.
8. `gh auth status` 결과 로그인된 GitHub 호스트가 없었다.
9. SSH 공개키 인증은 실패했다. 대화형 SSH 터미널을 열고 사용자의 직접 비밀번호 입력을 기다린다.
10. 실제 계정 `jetson3`으로 SSH 인증을 완료하고 프로젝트 전용 제어 소켓을 만들었다.
11. Jetson 환경, LeLab/LeRobot 버전·커밋, 실행 프로세스, USB/카메라 상태, 저장 설정을 조사했다.
12. Jetson과 Mac에 Phase A 백업을 만들고 전체 SHA-256 manifest를 양쪽에서 검증했다.
13. 메타데이터 전용 `inspect_ports.py`를 실행해 현재 하나의 serial과 세 alias, 사라진 팔로워 경로를 확인했다.
14. LeLab journal과 설치 소스·선행 patch를 비교해 캘리브레이션 TX/RX 경쟁 및 패치 후 비재발을 확인했다.
15. 실제 데이터셋 `/start-recording` 호출은 journal에 없어 녹화 오류는 별도 `NOT_RUN`으로 유지했다.
16. `inspect_ports.py`와 `preflight.py`의 하드웨어 없는 단위 테스트 3개가 통과했다.
17. Jetson preflight가 팔로워와 두 카메라 누락을 검출해 `ready=false`로 안전하게 차단했다.
18. GitHub CLI 인증을 macOS Keychain에서 확인하고 비공개 저장소를 생성했다.
19. 선별한 12개 파일만 초기 커밋 `8dd6761`로 만들고 `main`에 push했다. `prompt/`, `.local/`, `backups/`는 제외했다.
20. 포트 식별, 녹화 TX/RX, 회귀·데이터 검증, 후속 로드맵 이슈 #1–#4를 생성했다.
21. 작업 브랜치 `fix/usb-recording`의 증거 문서 커밋 `48d788b`을 push하고 GitHub API에서 동일 SHA를 확인했다.

## 보존 및 안전

- 기존 네트워크, LeLab, 캘리브레이션, USB, 카메라 설정을 변경하지 않았다.
- 원격 장치를 열거나 프로세스를 중지하지 않았다.
- 비밀번호, 토큰, 개인키, 환경 변수, 원본 로그를 수집하거나 기록하지 않았다.
- 원본 백업은 Jetson과 Mac 양쪽에 생성됐고 SHA-256 manifest 전체 검증을 통과했다. Mac 사본은 `backups/` 아래 Git 비추적으로 보존한다.

## 다음 실행 한 단계

현장 안전 확인 후 기존 정상 배선의 팔로워와 카메라를 복원하고 메타데이터 전용 검사를 반복한다. 이후 승인 범위에서만 하드웨어 시험을 수행한다.
