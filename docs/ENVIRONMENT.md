# 실행 환경

최초 확인: 2026-09-05T21:18:17+09:00

네트워크 주소 재확인: 2026-09-17

## 2026-09-29 기록 상태

- Jetson `192.168.50.20` 전원/네트워크가 사용자에 의해 offline인 상태라 SSH 22, LeLab 8000, preview 8020 모두 응답하지 않았다.
- 따라서 오늘의 USB·서비스·토크 상태와 신규 Jetson 백업은 `BLOCKED_NETWORK / NOT_RUN`이다.
- 아래 Jetson 항목은 이전 접속에서 실제 확인한 최신 누적 기록이며 2026-09-29 live 재확인으로 간주하지 않는다.

## Mac

- 작업 위치: `/Users/jogyeyeong/Documents/ChatGPT/자율설계`
- 운영체제: macOS 26.6.2, arm64
- Git: 2.50.1
- GitHub CLI: 프로젝트 로컬 `.local/bin/gh`, v2.100.0, 공식 배포 체크섬 검증 완료
- GitHub CLI: 2026-09-29 `gh auth status` 세션은 로그아웃 상태
- Git HTTPS remote: `git ls-remote origin` 성공. 기존 credential의 private remote 읽기는 `PASS`
- GitHub 저장소: `gyeyeongjo-lgtm/so101-lelab-medicine-sorter`; private 판정은 기존 검증 기록을 유지하며 최종 push로 쓰기 권한을 재검증한다.

## Jetson

- 최신 LAN SSH: `jetson3@192.168.50.20:22`
- 이전 주소: `192.168.0.10`, `192.168.0.30`
- `192.168.50.20`의 ED25519 지문은 이전 주소에서 확인한 동일 Jetson 지문과 일치
- hostname: `ubuntu`
- 모델: NVIDIA Jetson Orin Nano Engineering Reference Developer Kit Super
- 운영체제: Ubuntu 22.04.5 LTS
- L4T: R36.5.2
- 커널: `5.15.199-tegra`, aarch64
- 메모리: 7.4 GiB, 조사 시 available 4.2 GiB
- 루트 저장소: 116 GiB 중 82 GiB 여유
- 사용자 그룹: `dialout`, `video` 포함

## LeLab 실행 환경

- 서비스: user systemd `lelab.service`, active/running
- 바인딩: `0.0.0.0:8000`
- 실행 명령: `/usr/bin/sg dialout -c "exec .../bin/python -m uvicorn lelab.server:app --host 0.0.0.0 --port 8000 --log-level info"`
- Python: `/home/jetson3/.local/share/uv/tools/lelab/bin/python`, Python 3.14 venv
- LeLab: 0.1.0, 원본 commit `39fcfee669f0b98e7a1fc4dde23025ea8cc7e5ce`
- LeRobot: 0.6.0, commit `30da8e687a6dfc617fcd94afc367ac7071c376ce`
- pySerial: 3.5
- NumPy: 2.2.6
- PyTorch: 2.11.0+cu128
- Feetech Servo SDK: 1.0.0

현재 설치본은 LeLab 원본과 동일하지 않다. `calibrate.py`, `server.py`, SO follower/leader 드라이버와 프런트엔드에 2026-09-05 선행 수정이 적용돼 있다. 원본, 현재본, 기존 백업, diff는 Phase A 백업에 보존했다.

## 백업

- Jetson: `/home/jetson3/so101-recovery-backups/20260905T210818+0900_phase-a`
- Mac: `/Users/jogyeyeong/Documents/ChatGPT/자율설계/backups/jetson/20260905T210818+0900_phase-a`
- 파일: 시스템·USB·커널 이력·LeLab journal·설정·캘리브레이션·실행 소스·원본 소스·기존 패치 diff
- 무결성: Jetson과 Mac에서 `MANIFEST.sha256` 전체 `PASS`
- Git 상태: `backups/`는 제외되어 원본 journal·캘리브레이션이 커밋되지 않는다.
