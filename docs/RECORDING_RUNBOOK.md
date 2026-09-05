# LeLab 녹화 실행 기록표

상태: `BLOCKED` — 누락된 팔로워·카메라와 현장 안전 확인이 필요하다.

## 실행 전 게이트

1. 팔 주변을 비우고 두 팔을 안정적으로 지지하며 즉시 전원을 차단할 수 있는지 현장에서 확인한다.
2. 승인 뒤 기존 정상 배선의 누락 장치만 복원한다. 임의 포트 교환이나 hub 재배선은 하지 않는다.
3. 장치를 열지 않는 `inspect_ports.py`와 `preflight.py`로 두 serial의 canonical identity, 카메라 노드, calibration 파일을 확인한다.
4. preflight가 `ready=true`가 아니면 LeLab 연결·텔레옵·녹화를 시작하지 않는다.
5. 실제 모터/토크 범위는 별도로 승인받는다.

## 최소 진단 녹화

LeLab UI의 정확한 버튼·요청 payload와 설치 버전의 지원 옵션을 브라우저 개발자 도구 및 설치 소스로 다시 확인한 뒤 기록한다. 현재 journal에는 `POST /start-recording`이 없으므로 아래 항목은 모두 `NOT_RUN`이다.

- 시작 전 health, active teleop/recording, 선택 포트·카메라·task·repo_id
- 한 번의 짧은 로컬 진단 녹화
- 최초 실패 시각, HTTP 응답, worker traceback, 커널 USB 사건
- stop 완료 확인 후 다음 시작
- 저장 경로, episode/frame 수, 재로딩 결과

Hugging Face 업로드는 로컬 저장 성공과 별개이며 이번 범위에서 실행하지 않는다.
