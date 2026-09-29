# 2026-09-29 GitHub 진행 기록 재개

## 요청·기준

- 사용자가 그동안의 LeLab, USB/TX-RX, ArUco, 카메라, YOLO, Robot Base 등록 진행 사항을 비공개 GitHub에 즉시 반영하라고 요청했다.
- `prompt/LELAB_SO101_CODEX_PACKAGE/CODEX_LELAB_SO101_RECOVERY.md` 787행과 `MAC_SSH_GITHUB_START.md` 170행을 전체 읽었다.
- 원본 prompt, 비밀번호, 키, 토큰, 원본 로그, 데이터셋, 모델, 현장 `*.local.json`은 커밋하지 않는다.

## 접속·인증

- `BLOCKED_NETWORK`: Jetson은 사용자 확인상 offline이다. `192.168.50.20:22`, `:8000`, `:8020`은 모두 timeout이다.
- `NOT_RUN`: 오늘의 Jetson live USB·LeLab·torque 재확인과 신규 Jetson 백업은 실행하지 못했다.
- `PASS`: remote `gyeyeongjo-lgtm/so101-lelab-medicine-sorter` 의 `main`과 `fix/usb-recording` branch를 `git ls-remote` 로 읽었다.
- `OBSERVED`: 프로젝트 로컬 GitHub CLI 2.100.0은 현재 로그아웃 상태다. Git HTTPS credential로 remote 읽기는 성공했다.

## 문서화

- `docs/CURRENT_SYSTEM_AND_ARUCO.md`를 추가했다.
- 현재 카메라는 물리 3대로 분리했다: Orbbec Astra 천장 정면 RGB-D, RealSense D435 천장 사선, Generic USB 엔드이펙터.
- 운영 ArUco는 `DICT_4X4_50` ID0–6 총 7개다. ID0–3은 작업대, ID4=red·ID5=green·ID6=blue는 바구니다.
- ChArUco ID10–33은 intrinsic 보정용 임시 보드이며, Robot Base teach의 X 6점은 ArUco가 아님을 명시했다.
- 4점 TCP+`T_B_W` fit이 기준 미달로 거부된 결과와 닫힌 fingertip TCP 6점 재수집 순서를 기록했다.

## 안전·커밋 범위

- 로봇 제어, 토크 변경, USB 재연결, 전원 조작, 캘리브레이션은 실행하지 않았다.
- 미완료된 로봇 transform은 `robot_enabled=false`, `motion_authorized=false`를 유지한다.
- 커밋 전 secret pattern, 대용량, 미디어/모델, staged diff를 재검토한다.

## 결과

- `PASS`: 프로젝트 `.venv`의 OpenCV 5.0.0 환경에서 하드웨어 없는 `unittest discover` 93/93이 통과했다.
- `PASS`: `python3 -m compileall -q scripts tests`가 통과했다.
- `FAIL (environment only)`: 시스템 Python 3.13의 첫 전체 테스트는 `cv2` 미설치로 91개 중 import error 1개가 발생했다. 코드 실패로 숨기지 않고, 실제 프로젝트 환경에서 재실행해 통과했다.
- `PASS`: 진행 기록·코드·테스트·ArUco 인쇄 자산 116개 파일을 `a68b39f` (`feat: preserve ArUco vision and medicine sorting progress`)로 커밋했다.
- `PASS`: `origin/fix/usb-recording` push가 `80e8047..a68b39f`로 성공했다. GitHub CLI 세션은 로그아웃이지만 기존 Git HTTPS credential의 쓰기 권한은 실제 push로 검증됐다.
- 상태: `PUSHED`.
