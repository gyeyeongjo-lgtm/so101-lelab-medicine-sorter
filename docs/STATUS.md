# 현재 상태

업데이트: 2026-09-05T21:18:17+09:00

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
- `PASS`: 후속 작업 브랜치 `fix/usb-recording`을 만들고 이슈 #1–#4를 생성했다.
- `USER_REPORTED`: 기존 리더-팔로워 텔레오퍼레이션, 캘리브레이션, 웹캠, 네트워크 설정은 성공 상태였다.
- `PASS`: Jetson Phase A 환경 조사와 설정·캘리브레이션·소스·journal 백업을 완료했고 Jetson/Mac 양쪽 해시를 검증했다.
- `OBSERVED`: 현재 serial은 `5AE6085272` 한 대만 있고 저장된 팔로워 `5AE6058306`은 없다. `/dev/video*`도 없다.
- `OBSERVED`: 19:32 캘리브레이션 TX/RX 오류는 동시 bus 읽기와 일치하고, 19:35 직렬화 패치 이후 두 캘리브레이션에서 재발하지 않았다.
- `PASS`: 메타데이터 전용 포트 검사와 preflight 스크립트의 오프라인 단위 테스트 3개가 통과했다.
- `FAIL`: Jetson preflight는 팔로워 serial, `/dev/video0`, `/dev/video2` 누락을 검출해 `ready=false`로 종료했다.
- `NOT_RUN`: 실제 데이터셋 녹화, 텔레옵 회귀, 모터/토크 관련 시험.

## SSH 호스트 키 후보

2026-09-05에 `192.168.0.10`이 제시한 지문이다. 사용자가 ED25519 지문을 확인했고 프로젝트 전용 known-hosts 파일에 고정했다.

- RSA: `SHA256:E8sPqGMqQByy2SlJTg1RBxe3rWTp7yQfdDg7wKpJDyM`
- ECDSA: `SHA256:IBpxmbAkhxgYKSGgcTwLkb1yp6j4siHHUhWT3w6b8Lo`
- ED25519: `SHA256:dG9hPvs6yZcfIlZ0mPofx8lUPGYwDwW1M4UDzeSfx3o`

## 원본 지시서 무결성

- `CODEX_LELAB_SO101_RECOVERY.md`: `603ea8a57a21b28a019149b8f6ff25d407e1b5fe4e25dfe85e8c8d454362fb6f`
- `MAC_SSH_GITHUB_START.md`: `1827fc1b3484e9888ae81dbf398983b468c7b0583fb48614c6318a225f4e30cd`

## 다음 실행 한 단계

현장 안전 확인 후 기존 정상 배선의 팔로워와 카메라를 복원하고, 먼저 메타데이터 전용 포트 검사를 반복한다. 실제 장치 open, 모터 동작, 토크 변경 시험 범위는 별도로 확인한다.

## GitHub

- 저장소: <https://github.com/gyeyeongjo-lgtm/so101-lelab-medicine-sorter>
- 공개 범위: private (`PASS`)
- 기본 브랜치/초기 커밋: `main` / `8dd6761`
- 작업 브랜치: `fix/usb-recording`
- 이슈: #1 포트 식별, #2 녹화 TX/RX, #3 회귀·데이터 검증, #4 후속 로드맵
