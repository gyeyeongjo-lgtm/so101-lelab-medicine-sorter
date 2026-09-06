# 현재 상태

업데이트: 2026-09-06T11:49:00+09:00

## 상태 요약

- `OBSERVED`: Codex는 Mac 로컬 `/Users/jogyeyeong/Documents/ChatGPT/자율설계`에서 실행 중이다.
- `OBSERVED`: 작업 루트는 커밋이 아직 없는 기존 Git 저장소이며 remote가 없다.
- `OBSERVED`: 사용자 원본인 `prompt/`는 미추적 상태로 보존되어 있다.
- `OBSERVED`: `192.168.0.10:22`와 `192.168.0.10:8000`은 TCP 연결에 응답한다.
- `OBSERVED`: 실제 SSH 대상은 `jetson3@192.168.0.10:22`이다.
- `PASS`: 사용자가 ED25519 호스트 키를 확인했고, 프로젝트 전용 known-hosts 파일의 지문도 일치했다.
- `PASS`: 실제 SSH 계정 `jetson3`으로 인증했고 프로젝트 전용 소켓을 재사용 중이다.
- `PASS`: 공식 GitHub CLI v2.100.0 arm64 바이너리를 프로젝트 로컬 `.local/bin/gh`에 설치하고 배포 체크섬을 검증했다.
- `PASS`: 프로젝트 로컬 GitHub CLI가 macOS Keychain의 `gyeyeongjo-lgtm` 계정으로 인증됐고 API 호출도 통과했다.
- `PASS`: 비공개 GitHub 저장소 `gyeyeongjo-lgtm/so101-lelab-medicine-sorter`를 만들고 초기 `main` 커밋 `8dd6761`을 push했다.
- `PASS`: 후속 작업 브랜치 `fix/usb-recording`의 증거 문서 커밋 `48d788b`을 push하고 원격 SHA를 확인했다.
- `PASS`: 이슈 #1–#4를 생성하고 API에서 open 상태를 확인했다.
- `USER_REPORTED`: 기존 리더-팔로워 텔레오퍼레이션, 캘리브레이션, 웹캠, 네트워크 설정은 성공 상태였다.
- `PASS`: Jetson Phase A 환경 조사와 설정·캘리브레이션·소스·journal 백업을 완료했고 Jetson/Mac 양쪽 해시를 검증했다.
- `HISTORICAL`: Phase A 직후에는 serial `5AE6085272` 한 대만 보였고 저장된 팔로워 `5AE6058306` 및 `/dev/video*`가 일시적으로 누락됐다. 이후 물리 재연결 뒤 아래 최신 preflight를 다시 확인했다.
- `OBSERVED`: 19:32 캘리브레이션 TX/RX 오류는 동시 bus 읽기와 일치하고, 19:35 직렬화 패치 이후 두 캘리브레이션에서 재발하지 않았다.
- `PASS`: 메타데이터 전용 포트 검사와 preflight 스크립트의 오프라인 단위 테스트 3개가 통과했다.
- `FAIL`: Jetson preflight는 팔로워 serial, `/dev/video0`, `/dev/video2` 누락을 검출해 `ready=false`로 종료했다.
- `HISTORICAL`: 이 단계에서는 실제 데이터셋 녹화, 텔레옵 회귀, 모터/토크 관련 시험을 실행하지 않았다. 이후 아래 승인 시험으로 상태가 갱신됐다.
- `OBSERVED`: 21:53:19와 21:53:52 녹화 시도는 각각 torque enable id 5, follower `Present_Position` sync-read에서 실패했고 저장 episode는 0개였다.
- `PASS`: 최신 장치 preflight 7/7; 두 serial과 두 카메라가 존재하고 서로 다른 장치다.
- `PASS`: Mac에서 읽기 전용 follower 진단 도구 `scripts/diagnose_follower_bus.py`의 문법 검사와 기존 오프라인 단위 테스트 3개를 통과했다.
- `PASS`: 2026-09-06 Jetson standalone 읽기 전용 follower 시험에서 올바른 serial identity, ping 6/6, 개별 position read 30/30, group sync-read 5/5를 확인했다. ID 5도 정상이며 torque·register·USB 설정을 변경하지 않았다.
- `PASS`: 추가 20-round 읽기 전용 시험도 개별 120/120, group 20/20 성공했고 Mac backup에 hash 검증해 보존했다.
- `OBSERVED`: 11:10 텔레옵 약 62초 동안 follower 위치 read 오류 255건과 정상 joint snapshot 48건이 섞였다. 설치된 loop는 1 ms sleep으로 follower sync-write를 반복해 bus 포화 가능성이 높다.
- `PASS`: A/B 직전 캘리브레이션·robot record·설치 소스·journal 9개 파일을 Jetson과 Mac에 백업하고 SHA-256 전체 검증을 통과했다.
- `FAIL`: 카메라·video·streaming encoding을 제외한 최소 녹화도 `Devices ready` 직후 첫 follower observation에서 같은 sync-read 오류로 실패했다. saved episode 0, kernel USB event 없음.
- `PASS`: 실패 직후 standalone read 30/30·group 5/5가 다시 성공했고 시험 전후 설정 파일 hash가 동일했다.
- `PASS`: stale goal 차이는 최대 12 raw unit이었으며 torque-only 약 3초 시험에서 enable/disable, position+voltage 40/40, 12.2V 유지가 모두 통과했다.
- `PASS`: 구체적 안전 승인 뒤 configure+RX-clear+50ms 시험을 실행해 position+voltage 40/40, torque disable 성공을 확인했다.
- `FAIL`: 승인된 RX-clear patch를 Jetson에 배포하고 service를 재시작한 뒤 카메라 없는 실제 녹화를 회귀했다. patch log와 50 ms settle은 확인됐지만 첫 follower observation이 `There is no status packet`으로 즉시 실패했고 episode는 0개였다.
- `PASS`: 실패한 patch를 pre-A/B 원본으로 롤백했다. 현재 설치본과 보존 원본의 SHA-256은 모두 `779fd897...`로 같고 `lelab.service`, `/health`, 텔레옵·녹화 inactive 상태를 다시 확인했다.
- `PASS`: leader `/dev/ttyACM1` standalone 읽기 전용 시험도 serial `5AE6058306`, ping 6/6, 개별 position 120/120, group 20/20으로 통과했다.
- `PASS`: leader와 follower 포트를 동시에 열고 30 Hz로 120 rounds 교차 group read한 시험은 양쪽 모두 120/120, 오류 0건이었다. 단순 dual-open 및 양방향 read traffic은 재현 조건에서 약해졌다.
- `PASS`: patch 실패와 dual-read 결과를 Jetson/Mac 양쪽 backup에 보존하고 체크섬을 검증했다.
- `INFO`: 현재까지의 확정 사실·가설·배제 사항은 `docs/PROBLEM_SUMMARY_REFERENCE_2026-09-05.md`에 참고용으로 정리했다.
- `BLOCKED`: 녹화 초기화 직후 follower read 실패가 남아 있어 데이터셋 녹화를 회귀 통과로 판정할 수 없다.

## SSH 호스트 키 후보

2026-09-05에 `192.168.0.10`이 제시한 지문이다. 사용자가 ED25519 지문을 확인했고 프로젝트 전용 known-hosts 파일에 고정했다.

- RSA: `SHA256:E8sPqGMqQByy2SlJTg1RBxe3rWTp7yQfdDg7wKpJDyM`
- ECDSA: `SHA256:IBpxmbAkhxgYKSGgcTwLkb1yp6j4siHHUhWT3w6b8Lo`
- ED25519: `SHA256:dG9hPvs6yZcfIlZ0mPofx8lUPGYwDwW1M4UDzeSfx3o`

## 원본 지시서 무결성

- `CODEX_LELAB_SO101_RECOVERY.md`: `603ea8a57a21b28a019149b8f6ff25d407e1b5fe4e25dfe85e8c8d454362fb6f`
- `MAC_SSH_GITHUB_START.md`: `1827fc1b3484e9888ae81dbf398983b468c7b0583fb48614c6318a225f4e30cd`

## 다음 실행 한 단계

RX-clear-only 수정은 실제 녹화에서 반증됐고 원본으로 복구했다. 다음 변경 전에는 dual bus lifecycle을 계측해 follower configure, leader configure, torque enable, 첫 observation 사이의 최초 실패와 SDK 통신 결과 코드를 정확히 분리한다. register write·torque 변경을 포함하는 새 시험이나 SDK patch 배포는 다시 구체적으로 승인받는다.

## GitHub

- 저장소: <https://github.com/gyeyeongjo-lgtm/so101-lelab-medicine-sorter>
- 공개 범위: private (`PASS`)
- 기본 브랜치/초기 커밋: `main` / `8dd6761`
- 작업 브랜치/검증된 원격 커밋: `fix/usb-recording` / `4903c1a`
- 이슈: #1 포트 식별, #2 녹화 TX/RX, #3 회귀·데이터 검증, #4 후속 로드맵
