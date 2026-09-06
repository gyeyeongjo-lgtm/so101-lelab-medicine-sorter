# 녹화 및 TX/RX 조사

확인 시각: 2026-09-05T21:18:17+09:00

## 원본 오류

최신 incident의 실제 녹화 오류와 호출 경로는 `RECORDING_INCIDENT_2026-09-05.md`에 별도로 기록했다. 최신 로그에서는 21:53:59에 follower observation `sync_read`가 실패했고, 21:53:19의 선행 시도는 torque enable motor id 5에서 먼저 실패했다.

Phase A 백업 journal에는 실제 `POST /start-recording` 호출이 없었지만, 이번 incident에서 21:53:19와 21:53:52의 실제 녹화 worker 오류를 새로 확보했다. 최초 오류 단계와 traceback은 `RECORDING_INCIDENT_2026-09-05.md`를 기준으로 한다.

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

## 최신 상태

- 현재 follower는 `/dev/ttyACM0` serial `5AE6085272`, leader는 `/dev/ttyACM1`
  serial `5AE6058306`으로 확인됐다.
- 두 C920과 두 robot arm의 물리 연결 및 preflight 7/7 통과를 확인했다.
- 실제 녹화 traceback을 확보했고 무카메라 baseline 및 RX-clear patch 회귀가 모두 첫
  follower observation에서 실패했다.
- 실패 patch는 원본으로 롤백했고 LeLab service health는 정상이다.
- follower/leader standalone 및 dual-open 교차 read는 모두 통과했다.

## 다음 최소 검증

1. 변경 없이 port owner, serial identity, service inactive, journal 시작점을 확보한다.
2. 새 안전 승인 뒤 follower와 leader의 calibration/configure 경계를 단계별로 실행하며
   각 경계 직후 read와 low-level SDK 결과를 기록한다.
3. 정확한 최초 실패가 확인된 뒤에만 bus-level recovery patch를 별도로 검증한다.
4. 무카메라 회귀 통과 후에만 두 camera와 encoder를 다시 추가한다.

## 자동 검사 결과

- Mac 단위 테스트: 3개 `PASS`
- 최신 Jetson 메타데이터 preflight: 7/7 `PASS`
- follower standalone: 개별 120/120, group 20/20 `PASS`
- leader standalone: 개별 120/120, group 20/20 `PASS`
- dual-open 30 Hz 교차 group read: 양쪽 120/120 `PASS`
- 무카메라 baseline 및 RX-clear patch 회귀: 첫 observation `FAIL`

preflight는 serial 및 camera 장치를 열지 않았다.
