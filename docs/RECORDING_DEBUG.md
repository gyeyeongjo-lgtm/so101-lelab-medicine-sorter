# 녹화 및 TX/RX 조사

확인 시각: 2026-09-05T21:18:17+09:00

## 원본 오류

현재 확보한 LeLab journal에는 실제 `POST /start-recording` 호출이 없다. 따라서 데이터셋 녹화 worker의 최초 오류는 아직 관측되지 않았다.

확인된 TX/RX 오류는 캘리브레이션의 “range recording” 단계에서 발생했다.

- 최초 시각: 2026-09-05 19:32:52+09:00
- 읽기: `sync_read("Present_Position")`, motor ids 1–6
- 오류: `Incorrect status packet`, `There is no status packet`
- 19:32:52–19:33:54 사이 총 14건
- 같은 시간대 커널 USB reset/disconnect: 없음

## 소스와 로그의 연결

오류 당시 원본 `calibrate.py`는 두 경로가 같은 `self.device.bus`를 읽었다.

1. 캘리브레이션 worker가 range를 수집하며 `Present_Position`을 반복 읽음.
2. 브라우저가 `/calibration-status`를 폴링할 때 request handler도 `Present_Position`을 읽음.

두 오류 메시지가 동일 초에 worker와 status handler 양쪽 라인에서 교차했고, 설치된 패치는 status handler의 버스 읽기를 제거해 worker가 최신 값을 게시하도록 바꿨다. worker 읽기에는 제한된 재시도 3회가 추가됐다.

서비스가 패치본으로 다시 시작된 19:35:21 이후:

- 19:37:58 리더 캘리브레이션 완료
- 19:43:41 팔로워 연결 성공
- 19:50:12 리더 캘리브레이션 완료
- 이후 동일 TX/RX 오류 0건

따라서 `OBSERVED`: 캘리브레이션 TX/RX 오류의 직접 원인은 동일 serial bus의 동시 읽기 경쟁과 일치하며, 적용된 직렬화 수정 뒤 journal 회귀는 통과했다. 이 결론을 데이터셋 녹화 오류 해결로 확대하지 않는다.

## 현재 녹화 경로의 소스 검증

- 요청의 `follower_port`는 `SO101FollowerConfig`(robot)에 전달된다.
- 요청의 `leader_port`는 `SO101LeaderConfig`(teleop)에 전달된다.
- 녹화 시작은 텔레옵/추론 active 상태를 검사한다.
- 실행 순서는 robot bus → teleop bus → calibration write → cameras → `configure()`다.
- follower/leader `configure()`는 토크 상태와 모터 레지스터를 변경한다. 단순 읽기 시험으로 사용할 수 없다.
- 두 SO 드라이버에는 `Present_Position` 재시도 2회가 선행 수정으로 들어가 있다.

## 현재 차단 조건

- 팔로워 serial `5AE6058306`이 현재 없음.
- 저장된 C920 2대가 현재 없음.
- 실제 녹화 요청/traceback이 journal에 없음.
- 녹화 시작은 토크·모터 설정·실제 움직임 가능성이 있어 현장 안전 확인 전 실행하지 않는다.

## 다음 최소 검증

1. 안전 확인 후 기존 정상 배선으로 팔로워와 카메라를 복원한다.
2. 장치를 열지 않는 `scripts/inspect_ports.py`로 두 serial과 카메라 노드만 확인한다.
3. LeLab의 robot record가 두 canonical 장치를 가리키도록 비교한다.
4. 현장 안전 범위가 승인된 뒤에만 기존 텔레옵 기준선 또는 작은 로컬 녹화를 실행해 실제 최초 오류를 확보한다.

## 자동 검사 결과

- Mac 단위 테스트: 3개 `PASS`
- Jetson 메타데이터 preflight: `ready=false`, exit 2
- `PASS`: 리더 serial, 리더 calibration, 팔로워 calibration
- `FAIL`: 팔로워 serial, `/dev/video0`, `/dev/video2`
- `BLOCKED`: 두 serial의 실제 canonical 장치 구분

preflight는 serial 및 camera 장치를 열지 않았다.
