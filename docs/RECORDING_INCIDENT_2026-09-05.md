# 2026-09-05 데이터셋 녹화 오류 분석

확인 시각: 2026-09-05 21:53:19–21:54:03 KST

판정: 원인 확인 중. 오류가 발생하는 계층은 follower serial bus의 Present_Position 응답 경로로 좁혀졌다. 이번 기록에서는 Jetson·LeLab·모터 설정을 수정하지 않았다.

## 2026-09-06 읽기 전용 분리 시험

LeLab 텔레옵·녹화가 모두 inactive인 상태에서 follower `/dev/ttyACM0`을 읽기
전용으로 시험했다. 장치 serial은 저장된 follower와 같은 `5AE6085272`였다.

- motor ID 1–6 ping: 6/6 성공, 모두 model number 777
- 개별 `Present_Position`: 5 rounds × 6 motors = 30/30 성공
- 개별 read 최대 지연: 0.61 ms
- ID 1–6 group `sync_read`: 5/5 성공
- group read 최대 지연: 1.66 ms
- ID 5도 모든 ping·개별 read·group read에서 정상 응답
- 모터 register write, torque 변경, calibration, USB 재연결, camera access: 없음

이 결과는 follower 장치와 ID 5가 idle 상태에서 항상 고장 난 것은 아니라는 강한
반증이다. 다만 표본이 짧으므로 간헐 오류를 완전히 배제하지는 않는다. 현재 오류는
LeLab의 calibration/configure·torque enable sequence, 실제 제어 loop, 별도 port
owner, 또는 camera/encoder 부하가 결합될 때 나타나는 조건부 장애로 보는 편이 더
타당하다.

추가 20-round 시험도 같은 결과였다.

- 개별 `Present_Position`: 120/120 성공, 최대 0.40 ms
- group `sync_read`: 20/20 성공, 최대 1.66 ms
- 결과 보존: `backups/jetson/20260906T111440+0900_follower-readonly/`

## 2026-09-06 텔레옵 재현과 loop 빈도

사용자가 11:10:11–11:11:13 KST에 텔레옵을 실행한 최신 journal을 확인했다.

- 시작 직후 정상 joint sample이 있었지만 같은 초부터 `Present_Position` 오류 발생
- 약 62초 동안 `Error getting joint positions` 255건
- 같은 구간 정상 `[joint-debug]` snapshot 48건
- 오류는 `Incorrect status packet`과 `There is no status packet` 혼재
- 텔레옵 종료 뒤 standalone 읽기 전용 시험은 다시 전부 성공

설치된 `teleoperate.py`는 loop마다 leader action을 읽고 follower에
`Goal_Position` group sync-write를 보낸 뒤 1 ms만 sleep한다. follower 위치 read는
20 Hz로 끼워 넣는다. `SO101FollowerConfig.max_relative_target` 기본값은 `None`이라
`send_action()`은 추가 position read 없이 group sync-write를 실행한다. 따라서
follower bus에는 사실상 제한되지 않은 고빈도 write가 연속으로 들어가며, 그 사이의
20 Hz group read가 간헐적으로 깨지는 패턴과 정확히 맞는다.

이는 텔레옵 joint-read 오류의 가장 강한 소프트웨어 원인이다. 녹화 loop는 별도 FPS
제어를 사용하므로, 동일 원인이 녹화 실패까지 전부 설명한다고 아직 단정하지 않는다.
카메라 없는 최소 녹화 A/B로 configure/torque와 camera/encoder 부하를 분리해야 한다.

추가 환경 근거:

- follower USB adapter `/sys/.../power/control=on`: autosuspend 아님
- 조사 시 load average 0.20/0.15/0.07: 상시 CPU 포화 아님
- LeLab은 user unit `lelab.service`에서 2026-09-05 19:35부터 실행 중
- A/B 직전 백업: `/home/jetson3/so101-recovery-backups/20260906T111830+0900_pre-ab`
- 동일 백업을 Mac `backups/jetson/20260906T111830+0900_pre-ab/`에도 복사하고 9개 파일 hash를 검증함

## 2026-09-06 카메라 제외 녹화 A/B

현장 안전 확인 뒤 기존 leader/follower port와 calibration을 유지하고, 요청에서
`cameras={}`, `video=false`, `streaming_encoding=false`, `push_to_hub=false`만 적용한
최소 녹화를 실행했다.

- dataset id: `Supermassive111/codex_ab_nocam_20260906_112311`
- bus 연결, calibration write, follower/leader configure: 완료
- 카메라 객체 없음, encoder 없음
- `Devices ready` 직후 record loop의 첫 `robot.get_observation()`에서 동일 sync-read 오류
- leader action read 및 follower `Goal_Position` write 전에 실패
- session elapsed 0초, saved episode 0
- 같은 시간대 kernel USB reset/disconnect: 없음
- 실패 직후 standalone read: 개별 30/30, group 5/5 성공
- 시험 전후 robot record와 두 calibration 파일 SHA-256 동일
- 증거 백업: `backups/jetson/20260906T112311+0900_ab-nocam/`

따라서 카메라, 영상 encoder, Hub/network, record loop의 action write는 이번 최초
실패 원인에서 제외할 수 있다. 녹화 고장은 첫 observation 전에 실행된
calibration/configure/torque sequence와 강하게 결부된다.

## Torque-only 분리 시험

추가로 토크가 꺼진 상태에서 read-only로 현재 위치와 남은 목표 위치를 비교했다.
최대 차이는 12 raw unit이었고 전압은 전 모터 12.2V, 온도 37–40°C였다. 이후
목표 위치를 쓰지 않고 torque만 약 3초 켰다.

- torque enable: 성공
- 20 Hz position+voltage sample: 40/40 성공
- 전압: 전 sample 12.2V
- 최대 read 지연: 2.40 ms
- torque disable: 성공

토크 자체, stale goal로 인한 큰 점프, 정상 hold 상태의 전압강하는 직접 원인에서
약해졌다. 남은 최우선 가설은 calibration/configure의 연속 register write 이후 RX
buffer/packet framing이 깨지고, 현재 `_sync_read` retry가 buffer를 clear하지 않아
동일 상태로 3회 실패하는 것이다.

이 시점에는 이를 검증할 configure+RX-clear 임시 시험을 아직 실행하지 않았다. 기존 calibration
재기록, register configure, torque toggle을 포함하므로 별도의 구체적 사용자 승인을
기다린다.

## Configure+RX-clear 분리 시험

사용자가 register 재기록·torque toggle을 구체적으로 승인하고 현장 안전을 다시
확인한 뒤 시험했다. 녹화와 동일하게 follower calibration을 다시 쓰고
`robot.configure()`를 실행하되, 그 직후 host RX buffer를 clear하고 50 ms 기다린 다음
20 Hz로 position+voltage를 읽었다.

- configure: 성공
- RX buffer clear: follower port에 1회
- settle: 50 ms
- position+voltage read: 40/40 성공
- 전압: 11.6–12.2V
- 최대 read 지연: 3.19 ms
- torque disable: 성공
- 증거 백업: `backups/jetson/20260906T113454+0900_configure-clear/`

Baseline 카메라 제외 녹화는 같은 configure 직후 첫 sync-read가 즉시 실패했지만,
RX clear+50 ms를 추가한 follower-only sequence는 모두 통과했다. 이 결과만으로는
host RX 상태를 원인으로 확정할 수 없으며, 실제 dual-device 녹화 lifecycle에서 반드시
회귀해야 하는 후보 가설로 남겼다. 현재 `_sync_read` retry가 실패 사이에 port buffer를
clear하지 않는 점은 별도의 복구성 개선 후보다.

이를 최소 범위로 검증하기 위해 현재 `patches/lelab-20260906/record-rx-clear.failed.patch`로
보존한 변경을 준비했다.

- follower·leader configure 완료 후 각 serial RX buffer clear
- `port_handler.is_using=False` 복구
- record loop 시작 전 50 ms settle

로컬 patched file은 `py_compile`을 통과했고 원본 대비 위 변경만 포함했다.

## RX-clear patch 실제 무카메라 회귀와 롤백

사용자가 `record 패치 배포·서비스 재시작·무카메라 회귀`를 승인한 뒤 patch를 설치하고
service를 재시작했다. 요청은 baseline과 같이 `cameras={}`, `video=false`,
`streaming_encoding=false`, `push_to_hub=false`였다.

- dataset id: `Supermassive111/codex_ab_nocam_rxclear_20260906_114147`
- patch log: follower·leader RX clear와 50 ms settle 실행 확인
- 첫 status poll: recording active
- 약 0.25초 뒤 첫 follower observation: `There is no status packet`
- saved episode: 0, session elapsed: 0초
- kernel USB reset/disconnect: 없음
- 증거: `backups/jetson/20260906T114147+0900_rxclear-regression/`

따라서 **configure 후 RX clear+50 ms만으로는 실제 녹화 오류가 해결되지 않는다.**
follower-only configure-clear 통과는 조건 차이 또는 간헐성 때문에 생긴 부분 결과였고,
원인을 확정한 증거가 아니었다. 실패 직후 설치본은 pre-A/B 원본으로 롤백했다. 현재
live `record.py`와 보존 원본의 SHA-256은 `779fd897...`로 일치하며 service health가
정상이고 텔레옵·녹화는 inactive다.

## Leader 단독 및 dual-bus 읽기 전용 분리 시험

롤백 뒤 register·torque·USB 설정을 전혀 바꾸지 않고 추가 분리 시험을 수행했다.

- leader `/dev/ttyACM1`, serial `5AE6058306`: ping 6/6, 개별 position 120/120,
  group sync-read 20/20 성공
- follower와 leader를 동시에 열고 30 Hz, 120 rounds 동안 leader→follower 순으로
  group sync-read: leader 120/120, follower 120/120 성공
- 두 시험 모두 `disconnect(disable_torque=False)`로 종료
- 증거: `backups/jetson/20260906T114842+0900_dual-readonly/`

이 결과는 leader의 상시 고장, 두 USB adapter를 동시에 여는 행위, 두 버스에서 읽기
traffic을 번갈아 보내는 행위가 단독 재현 조건이라는 가설을 약화한다. 남은 차이는
실제 녹화 초기화의 calibration/register write, 두 device의 configure와 torque enable,
그리고 그 직후 첫 follower sync-read 경계다.

## Dual-configure lifecycle 계측

사용자가 register write·torque toggle을 포함한 단계별 계측과 현장 안전을 승인했다.
시험 전 현재 calibration, robot record, 설치 소스, service journal 10개 파일을
`20260906T120356+0900_pre-dual-configure`로 Jetson과 Mac에 보존하고 hash를 검증했다.

첫 실행은 설치본에 없는 내부 메서드명을 계측하려 해 **포트를 열기 전에** 종료됐다.
하드웨어 write·torque 변경은 없었고 service health를 복구한 뒤 설치된 API에 맞게
도구를 수정했다.

호출별 계측 시험 결과:

- trial A: 양쪽 calibration write 후 follower configure만 실행
- follower configure 직후 최초 `Present_Position` group-read: 3/3 `comm=0`
- follower torque state: ID 1–6 모두 enabled, voltage 12.2 V
- trial B: 녹화와 같은 follower configure→leader configure 전체 순서 실행
- 전체 configure 직후 최초 follower group-read: 3/3 `comm=0`
- leader group-read: 1/1 `comm=0`
- register/torque call error: 0건
- Goal_Position write: 0건
- 양쪽 torque disable 및 disconnect: 모두 성공
- 증거: `backups/jetson/20260906T121152+0900_dual-configure-result/`

위 시험에는 configure 전 상태 확인 group-read와 호출별 event 기록 비용이 포함됐다.
이 두 요소가 오류를 가렸을 가능성을 분리하기 위해, 사전 group-read와 호출별 래퍼를
모두 제거하고 전체 순서 1회만 반복했다.

- cold follower/leader connect: 각각 9.06 ms / 8.40 ms
- follower/leader calibration write: 각각 9.62 ms / 8.96 ms
- follower configure: 30.45 ms
- leader configure: 16.22 ms
- 그 직후 최초 follower group-read: 3/3 `comm=0`, 0.98–1.05 ms
- leader group-read: 1/1 `comm=0`
- Goal_Position write: 0건
- 양쪽 torque disable 및 disconnect: 모두 성공
- 증거: `backups/jetson/20260906T121642+0900_dual-configure-cold/`

두 결과 모두 시험 전후 저장된 follower/leader calibration과 robot record hash가 같고,
kernel USB event는 0건이었다. live `record.py`는 원본 hash `779fd897...`를 유지하며
LeLab service health도 정상이다.

따라서 dual-device calibration/configure/torque 순서와 cold first group-read는 현재
standalone에서 결정적으로 실패하지 않는다. 실제 무카메라 녹화와 남은 구조적 차이는
`threading.Thread(name="recording-worker")` 안에서 실행된다는 점과 bus 연결 전에
`LeRobotDataset.create()`가 실행되는 runtime context다. 다만 같은 실제 녹화 경로도
표본이 적으므로, 이 차이를 원인으로 확정하지 않고 간헐적인 packet/electrical 상태를
동일 우선순위로 유지한다.

## 화면과 실제 journal의 대응

첨부 화면의 토스트는 다음 오류를 표시한다.

Recording Failed
Failed to sync read Present_Position on ids=[1, 2, 3, 4, 5, 6] after 3 tries.
[TxRxResult] Incorrect status packet!

토스트 시각 전후 backend 근거:

- 21:53:52: POST /start-recording이 비동기 세션 시작 응답 200을 반환했다.
- 21:53:54: robot bus와 teleoperator bus 연결 성공.
- 21:53:55–21:53:56: /dev/video0, /dev/video2 카메라 연결 성공.
- 21:53:56: Devices ready, episode 1 시작, 두 영상 encoder 시작.
- 21:53:59: SOFollower.get_observation()의 sync_read(Present_Position, num_retry=2)가 3회 실패했다.
- 21:54:00: session error, saved_episodes=0, session ended.

따라서 화면의 200은 녹화 성공이 아니라 worker를 시작했다는 뜻이며, 실제 실패는 비동기 worker에서 발생한다.

## 같은 bus의 선행 증거

녹화 직전 텔레옵 구간도 같은 follower read 오류를 반복했다.

- 21:45:37: leader=/dev/ttyACM1, follower=/dev/ttyACM0으로 텔레옵 시작.
- 21:45:38 이후: leoperate.py:98이 Present_Position을 읽을 때 There is no status packet과 Incorrect status packet을 반복 기록했다.
- 21:46:09: 사용자가 텔레옵을 정지했고 follower/leader가 disconnect 됐다.

사용자가 관찰한 팔 움직임은 get_action과 send_action이 일부 성공했다는 뜻이지 follower 위치 읽기 bus가 안정적이라는 뜻은 아니다. 화면 프리뷰가 정상인 것도 serial 응답의 증거가 아니다.

## 두 녹화 시도의 차이

| 시각 | 실패 지점 | 의미 |
|---|---|---|
| 21:53:19 | SOFollower.configure가 context를 빠져나오며 motor id=5에 Torque_Enable=1을 쓸 때 Incorrect status packet | torque를 켜는 순간 특정 motor/버스 응답이 불안정하거나 전원·배선 부하에 민감할 가능성 |
| 21:53:52 | configure 통과 후 첫 episode의 get_observation에서 ids 1–6 sync_read 실패 | configure 한 줄이 아니라 실제 follower position-read 경로도 불안정 |

두 번째 실패는 카메라 연결과 encoder 시작 이후였지만 첫 번째 실패는 episode/read loop 이전에도 발생했다. 카메라가 직접 원인이라는 가설은 약해진다.

## 코드 호출 경로

Phase A에서 보존한 설치 소스 기준이다.

1. lelab/record.py:658–679가 SO follower와 SO leader를 만든다.
2. lelab/record.py:723–777이 bus 연결, calibration write, camera 연결, robot.configure를 실행한다.
3. lerobot/robots/so_follower/so_follower.py:159–173의 configure는 torque를 끄고 레지스터를 쓴 뒤 context 종료 시 torque를 다시 켠다.
4. lerobot/robots/so_follower/so_follower.py:182–190의 get_observation이 follower Present_Position을 sync_read(..., num_retry=2)로 읽는다.
5. lerobot/motors/motors_bus.py:1169–1193은 같은 sync reader로 재시도하고 3회 모두 실패하면 ConnectionError를 올린다.
6. lelab/record.py:785–813의 record_loop에서 observation이 실패하므로 episode 저장 전에 세션이 종료된다.

텔레옵도 lelab/teleoperate.py:203–225에서 action을 보낸 뒤 약 20 FPS로 follower observation을 읽는다. 소스에 bus 전체를 보호하는 공용 lock은 보이지 않으므로 joint-positions endpoint와 worker가 동시에 호출되는 경우 추가 경쟁 가능성이 남아 있다. 다만 이번 녹화 traceback 자체는 record worker의 follower read에서 직접 발생했다.

## 배제되었거나 약해진 가설

- 현재 USB 포트 중복: 최신 preflight 7/7 PASS. leader /dev/ttyACM1과 follower /dev/ttyACM0은 서로 다른 character device이며 by-id serial도 5AE6058306과 5AE6085272로 분리된다.
- 카메라 미인식: 두 카메라 연결과 /dev/video0, /dev/video2 preflight가 통과했다.
- 커널 USB 재열거: 21:53:19–21:54:10 실패 구간에 kernel USB disconnect/reset 이벤트가 없었다.
- Hugging Face 업로드/네트워크: episode 0개이고 follower read 실패가 먼저 발생했다. 화면 오류는 Hub 업로드 오류가 아니다.
- 단순 retry 부족: retry를 늘리면 보고 시점만 늦어질 뿐 malformed/timeout packet의 원인을 해결하지 않는다.

## 우선순위가 높은 원인 가설

1. LeLab recording-worker/dataset runtime과 standalone의 실행 문맥 차이 — 중간~높음

실제 무카메라 녹화는 두 번 첫 bus 경계에서 실패했지만 동일한 cold hardware 순서는
standalone main thread에서 통과했다. record 경로는 먼저 dataset을 만들고 background
thread 안에서 serial lifecycle을 실행한다. 아직 인과는 아니며 다음 계측 대상이다.

2. serial packet 소유권·초기화 순서·간헐 packet loss — 중간

텔레옵 소스에는 worker의 joint read와 `/joint-positions` 요청이 같은 bus 객체를 읽을 수 있는데 bus-level mutex가 없다. 다만 `handle_start_recording`은 텔레옵이 active이면 녹화를 거부하고, 이번 녹화 traceback은 recording worker의 자체 bus에서 발생했다. 따라서 이 가설은 캘리브레이션/텔레옵 오류에는 강하지만 이번 녹화 오류의 단독 원인으로는 약하며, stale 프로세스나 별도 serial opener가 있었는지 추가 확인할 때만 남긴다.

3. 간헐적인 packet 또는 전기적 상태 — 중간~높음

과거 실제 녹화에서는 id 5 torque enable과 전체 group-read가 각각 실패했지만 이번
계측은 같은 쓰기·torque 순서를 세 번 통과했다. 특정 설정값의 결정적 오류보다
간헐성이 강하며, 커널 USB event가 없다는 사실만으로 motor-side packet 손실이나
전원·커넥터 margin을 배제할 수 없다.

4. 역할·포트 경로의 불안정성 — 낮음~중간

현재 매핑은 물리 확인과 preflight가 통과했지만 /dev/ttyACM*는 재열거 시 바뀐다. 초기 백업 record의 leader/follower 문자열과 현재 record가 다르고 현재 calibration 두 파일도 백업 hash와 달라졌다. packet framing 오류의 직접 증거는 아니지만 재연성·역할 혼동 위험이다.

5. configure 후 RX buffer 잔류만의 문제 — 낮음

실제 RX-clear patch가 같은 첫 observation에서 실패했으므로 단독 원인으로는 반증됐다.
다만 SDK retry 중 framing 복구가 없다는 별도 약점은 남는다.

6. 카메라/encoder CPU 부하 — 낮음

첫 configure 실패가 episode/read loop 전에 발생했고 텔레옵에서도 serial read 오류가 있었으므로 주원인으로 보기 어렵다. 다만 Jetson에서 AV1/HEVC 두 encoder를 동시에 돌릴 때 timing margin을 줄일 수 있어 후속 A/B에서 분리한다.

## 다음 최소 검증 순서

실험 한 번에 한 변수만 바꾼다. 현장 안전 확인은 완료됐지만 아래는 별도 승인 범위에서만 실행한다.

1. 반복적인 calibration EEPROM write를 멈추고, source-only로 실제 recording-worker에
   최소 계측을 넣는 patch와 정확한 rollback diff를 준비한다.
2. 다음 승인 회귀에서는 dataset 생성 완료, worker thread 시작, 각 bus stage와 최초
   low-level comm code만 기록하고 무카메라 1회로 제한한다.
3. worker에서도 통과하면 여러 번의 register write를 반복하지 말고 read-only soak 또는
   물리 전원·커넥터 계측으로 간헐성을 확인한다.
4. 최초 실패 경계가 다시 잡힌 뒤에만 bus-level recovery를 별도 patch로 검증한다.
5. 무카메라 경로가 안정된 다음에 두 camera와 encoder를 한 대씩 추가한다.

### 읽기 전용 bus 시험 도구

위 1번 조건을 확인한 뒤 Jetson의 LeLab 런타임에서 다음 도구를 실행한다. 이 도구는
`handshake=False`로 포트를 열고 `ping`, 개별 `Present_Position` read, group
`sync_read`만 보낸다. `configure`, calibration, `write`, `sync_write`,
`enable_torque`, `disable_torque`를 호출하지 않으며 종료도 반드시
`disconnect(disable_torque=False)`로 한다.

```sh
PY=/home/jetson3/.local/share/uv/tools/lelab/bin/python
$PY /path/to/diagnose_follower_bus.py \
  --port /dev/ttyACM0 --expected-serial 5AE6085272 --rounds 5 \
  > /tmp/so101-follower-readonly-$(date +%Y%m%dT%H%M%S%z).json
```

실제 경로는 이 저장소를 Jetson에 둔 위치로 바꾼다. 출력 JSON에는 모터 값과 오류
문자열만 남기고 비밀번호·토큰은 포함하지 않는다. `individual_present_position`은
통과하고 `sync_present_position`만 실패하면 group packet 경로/타이밍을 우선
의심한다. ID 5 개별 read부터 실패하면 해당 모터·커넥터·downstream 전원/배선을
우선 점검한다. 이 시험 자체는 모터 목표값과 토크를 변경하지 않는다.

새 calibration, torque limit, baudrate, return-delay, USB 재배선은 이 분석 단계에서 변경하지 않는다. 각 시험의 최초 오류와 원래 설정은 별도 snapshot으로 보존한다.

## 보존 위치

- Phase A 원본: backups/jetson/20260905T210818+0900_phase-a/
- 이번 incident snapshot: backups/jetson/20260905T215359+0900_recording-incident/current/
- snapshot current calibration hash: leader d650e22f…, follower b2086017…
- snapshot current robot record hash: 3cf0b880…

두 디렉터리는 Git에서 제외된다. 비밀번호·토큰·인증 쿠키는 기록하지 않았다.
