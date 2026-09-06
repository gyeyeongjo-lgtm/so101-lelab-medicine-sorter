# SO-101 LeLab 문제사항 요약 — 참고용

작성일: 2026-09-05 (KST)
범위: 현재까지의 Jetson 조사, LeLab journal, 설치 소스, 장치 메타데이터, 사용자 확인 사항
성격: 참고용 분석 문서. 확정된 원인과 추정 원인을 구분하며, 이 문서 자체로 설정 변경이나 회귀 성공을 의미하지 않는다.

## 한 줄 요약

텔레오퍼레이션과 카메라 프리뷰는 동작했지만, 데이터셋 녹화는 follower 모터 버스의 TX/RX 응답 오류 때문에 episode를 저장하기 전에 실패했다. 이후 idle 읽기 전용 시험은 ID 1–6에서 전부 통과했으므로 상시 하드웨어 고장보다는 configure·torque 활성화·실제 제어·영상 부하가 결합된 조건부 오류가 현재 더 유력하다.

## 후속 읽기 전용 시험 결과 — 2026-09-06

- follower `/dev/ttyACM0`, serial `5AE6085272` identity 일치
- ID 1–6 ping 6/6 성공
- 개별 `Present_Position` 30/30 성공
- ID 1–6 group `sync_read` 5/5 성공
- ID 5도 전 항목 성공
- LeLab 텔레옵·녹화 모두 inactive
- register write, torque 변경, calibration, USB reconnect 없음

따라서 ID 5의 영구 고장, follower bus의 상시 단절, group sync-read의 구조적 실패는 현재 증거와 맞지 않는다. 짧은 시험이므로 간헐적인 물리·전기 문제까지 완전히 배제한 것은 아니다.

추가 20-round 시험에서도 개별 read 120/120과 group sync-read 20/20이 모두 성공했다. 반면 11:10 텔레옵 약 62초 동안 동일 follower 위치 read 오류는 255건 발생했고 정상 joint snapshot도 48건 섞였다. 설치된 텔레옵 loop가 follower에 1 ms sleep만 두고 `Goal_Position` sync-write를 반복하므로, 텔레옵 오류는 고빈도 write에 의한 bus 포화·응답 timing 문제로 현재 가장 잘 설명된다.

카메라·video·streaming encoding을 모두 제외한 최소 녹화도 `Devices ready` 직후 첫 observation에서 같은 오류로 실패했다. 반면 실패 직후 standalone read와 약 3초 torque-only 시험은 모두 통과했다. 따라서 녹화 오류는 카메라나 torque 자체보다 calibration/configure 연속 write 직후의 RX buffer·packet framing 문제로 더 좁혀졌다.

구체적 안전 승인 뒤 follower-only configure와 torque sequence에 host RX buffer clear+50ms settle을 넣은 시험은 position+voltage 40/40을 통과했다. 그러나 같은 수정을 실제 `record.py`에 배포한 무카메라 녹화는 첫 follower observation에서 다시 즉시 실패했다. 따라서 RX-clear-only 가설은 실제 경로에서 반증됐고 설치본은 원본으로 롤백했다.

추가 읽기 전용 시험에서 leader 단독도 ping 6/6, 개별 read 120/120, group read 20/20을 통과했다. 두 포트를 동시에 열고 30 Hz로 120 rounds씩 교차 group read한 시험도 양쪽 오류가 0건이었다. 단순 dual-open/read보다 dual-device 녹화 초기화의 register write·configure·torque 순서 직후 경계가 현재 핵심 조사 대상이다.

이후 승인된 dual-configure 계측에서는 follower configure 직후와 follower→leader 전체
configure 직후 최초 follower group-read가 각각 3/3 통과했다. configure 전 group-read와
계측 지연을 제거한 cold 전체 순서도 최초 follower read 3/3, leader read 1/1이 모두
SDK `comm=0`이었다. 설정 hash는 시험 전후 동일했고 Goal_Position write와 kernel USB
event는 없었다. 따라서 hardware 초기화 순서 자체의 결정적 결함은 약해졌으며, 실제
녹화의 background worker/dataset runtime 문맥 또는 간헐 packet·전기적 상태가 남는다.

## 사용자에게 확인된 정상 항목

- 기존 텔레오퍼레이션 동작을 사용자가 직접 확인했다.
- 두 로봇팔과 두 웹캠이 물리적으로 연결된 상태임을 사용자가 확인했다.
- 카메라 프리뷰가 정상적으로 표시되는 것을 사용자가 확인했다.
- 현장 안전 확인이 완료되었다.
- 기존 캘리브레이션·네트워크·LeLab 설정은 조사 중 변경하지 않았다.

## 실제로 관찰된 실패

### 녹화 실패 1 — 설정/토크 활성화 단계

- 시각: 2026-09-05 21:53:19 전후
- 실패 지점: follower `configure()` 후 motor ID 5에 `Torque_Enable=1`을 쓰는 단계
- 오류: `Incorrect status packet`
- 의미: 녹화 loop에 진입하기 전에도 follower bus 응답이 불안정했다.

### 녹화 실패 2 — 첫 observation 단계

- 시각: 2026-09-05 21:53:52 시작, 21:53:59 전후 실패
- 실패 지점: follower ID 1–6의 `Present_Position` group `sync_read`
- 오류: `Failed to sync read 'Present_Position' ... after 3 tries. [TxRxResult] Incorrect status packet!`
- 결과: `saved_episodes=0`, 세션 종료
- 카메라 0·2는 연결되었고 encoder도 시작된 뒤였다.

### 텔레오퍼레이션 중 선행 증거

- 21:45 전후에도 follower `Present_Position` 읽기에서 `There is no status packet`과 `Incorrect status packet`이 반복되었다.
- LeLab 코드는 이 예외를 잡아 joint position을 0으로 반환하므로, 팔이 일부 움직였다는 사실만으로 위치 read bus가 안정적이었다고 판단할 수 없다.

## 소스 코드로 확인한 경로

1. `record.py`가 follower·leader serial bus를 연결한다.
2. 캘리브레이션 레지스터를 쓰고 카메라를 연결한 뒤 `robot.configure()`를 호출한다.
3. follower `configure()`는 torque를 끄고 모터 설정을 쓴 다음 context 종료 시 torque를 다시 켠다.
4. record loop의 `get_observation()`이 follower의 `Present_Position`을 group sync-read한다.
5. Feetech bus는 실패 시 재시도하지만, malformed/timeout status packet의 원인을 복구하지는 않는다.
6. 녹화 시작 API는 텔레오퍼레이션이 active이면 시작을 거부한다. 따라서 이번 녹화 trace를 단순한 텔레옵 UI polling 경쟁으로 단정할 수 없다.

## 현재 판단

### 가장 유력한 원인

1. **실제 recording-worker/dataset runtime과 standalone 실행 문맥의 차이**
   - 실제 무카메라 녹화는 background `recording-worker` 안에서 첫 observation이 실패했다.
   - 동일 cold connect/calibration/configure/first-read는 standalone main thread에서 통과했다.
   - record 경로는 bus 연결 전에 `LeRobotDataset.create()`를 실행한다.
   - 이 차이는 아직 상관관계이며 원인으로 확정하지 않았다.

2. **간헐적인 packet·전원·connector/downstream chain 문제**
   - ID 5가 첫 실패 지점이었지만 읽기 전용 시험에서는 정상이었다.
   - 물리 문제라면 상시 단선보다 torque·움직임·진동·전원 부하에 따른 간헐 현상일 가능성이 높다.

3. **텔레옵의 별도 고빈도 write-loop 문제**
   - 설치된 loop는 1 ms sleep만 두고 follower Goal_Position sync-write를 반복한다.
   - 약 62초 동안 read 오류 255건과 정상 sample 48건이 섞인 현상을 가장 잘 설명한다.
   - 녹화 최초 read 실패와는 별도 결함일 가능성이 높다.

### 가능성은 있으나 현재 단독 원인으로 약한 것

- **텔레옵 joint polling과의 동시 접근**: 캘리브레이션 오류에는 소스·로그상 잘 맞지만, 녹화 시작 시 텔레옵은 차단되므로 이번 trace의 단독 원인으로는 약하다.
- **카메라/영상 encoder 부하**: 무카메라 회귀에서도 즉시 재현되어 최초 실패의 직접 원인에서는 제외됐다.
- **`/dev/ttyACM*` 이름 변동**: 재연결 시 번호가 바뀌지만 현재 live mapping과 preflight는 leader/follower를 서로 다른 장치로 확인했다. 직접적인 malformed packet 원인이라는 증거는 없다.

## 현재까지 약화되거나 배제된 원인

- 현재 조사 시점의 leader/follower serial 중복: by-id serial이 서로 다르고 preflight 7/7 통과
- leader의 상시 통신 불량: 단독 ping/read 및 dual-bus read가 모두 통과
- 두 serial 포트를 동시에 여는 행위 자체: dual-open 120-round 교차 read가 모두 통과
- 카메라 미인식: `/dev/video0`, `/dev/video2` 연결 성공
- 실패 순간의 kernel USB disconnect/reset: 해당 journal 구간에서 확인되지 않음
- Hugging Face 또는 네트워크 업로드: episode 저장 전에 serial read가 먼저 실패
- 단순 retry 부족: 재시도는 오류를 늦출 뿐 packet 손상·응답 누락을 해결하지 않음

## 포트·설정 관련 주의사항

- 현재 기록상 follower는 `/dev/ttyACM0`, serial `5AE6085272`이다.
- leader는 `/dev/ttyACM1`, serial `5AE6058306`이다.
- `/dev/ttyACM0`·`/dev/ttyACM1`은 USB 재열거 때 뒤바뀔 수 있다.
- 따라서 후속 회귀에서는 장치 serial 또는 `/dev/serial/by-id/`를 기준으로 역할을 확인해야 한다.
- 캘리브레이션 파일과 robot record는 snapshot으로 보존되어 있으며, 조사 중 새 calibration·baudrate·return-delay를 적용하지 않았다.

## 현재 미확인 사항

- follower bus를 LeLab 외 프로세스가 동시에 열고 있는지 여부
- 물리 케이블·커넥터·전원 측정 결과
- actual `recording-worker`에서 dataset 생성 이후 최초 low-level comm code
- background thread와 standalone main thread 차이가 재현에 영향을 주는지 여부
- 실패가 재현될 때 정확한 motor/register 경계와 전원/connector 상태
- `_sync_read` 재시도 사이 RX clear가 간헐 packet loss에서 복구 효과가 있는지 여부

## 다음 확인 순서 — 변경 없는 진단부터

1. LeLab 텔레옵·녹화를 중지하고 카메라 프리뷰를 닫는다.
2. follower 포트의 serial identity를 다시 확인한다.
3. 완료된 standalone 읽기 전용 결과를 기준선으로 보존한다.
4. 반복적인 calibration/configure 실행을 멈추고 source-only worker 계측안을 준비한다.
5. 다음 하드웨어 회귀는 새 승인 뒤 무카메라 실제 worker 1회로 제한한다.
6. worker 계측에서도 통과하면 register write를 반복하지 않고 read-only soak와 현장
   전원·connector 관찰로 간헐성을 확인한다.
7. 최초 실패 위치가 다시 확인된 뒤에만 SDK-level 복구 patch를 만든다.

## 보존 및 안전 상태

- Phase A 원본 백업과 recording incident snapshot을 Mac·Jetson에 보존했다.
- 읽기 전용 도구는 [scripts/diagnose_follower_bus.py](../scripts/diagnose_follower_bus.py)와
  [scripts/diagnose_dual_bus_readonly.py](../scripts/diagnose_dual_bus_readonly.py)이다.
- 승인 필수 lifecycle 도구는
  [scripts/diagnose_dual_configure_lifecycle.py](../scripts/diagnose_dual_configure_lifecycle.py)이며
  calibration/configure write와 torque toggle을 수행하므로 읽기 전용이 아니다.
- 이 문서와 최신 incident 문서는 로컬 작업 트리에 정리되어 있다.
- 승인된 분리 시험에서는 기존 calibration/configure와 torque toggle을 실행했지만 목표값,
  baudrate, return-delay, USB 연결은 바꾸지 않았다. 설치한 RX-clear patch는 실패 즉시 원본으로 롤백했다.
- 비밀번호·토큰·개인키를 파일·로그·GitHub에 기록하지 않았다.
- standalone follower bus 진단은 통과했지만, 실제 녹화 성공 판정은 짧은 회귀 녹화가 통과한 뒤에만 내린다.
