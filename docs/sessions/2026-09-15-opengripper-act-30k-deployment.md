# 2026-09-15 — 오픈그리퍼 ACT 30k 배포·1회 추론

## 승인 범위

- 사용자 승인: `private model Supermassive111/act-so101-opengrip100-30k-v1 업로드·LeLab import·ACT 추론 1회 안전 승인, 현장 안전 확인`.
- 실제 추론은 1회, 최대 30초로 제한했다. 재시도, 토크·USB·캘리브레이션 변경, 서비스 재시작은 수행하지 않았다.

## 모델 배포

- 학습 checkpoint: `/Users/jogyeyeong/lerobot-training/act_opengrip100_20260914_30k_v4/checkpoints/030000/pretrained_model`.
- private Hub 모델: `Supermassive111/act-so101-opengrip100-30k-v1`.
- 원격 필수 모델·전/후처리·학습 설정 파일을 읽기 전용으로 확인했다.
- LeLab UI Import 완료: `ACT open gripper 100 episodes 30k v1`.

## 추론 사전 확인

- checkpoint image feature: `312`, `camera_2`, 각 640×480.
- LeLab 바인딩: `312`은 `#0 HD Pro Webcam C920`, `camera_2`는 `#2 USB Camera`로 일치했다.
- 추론 장치는 기존 Jetson GPU 호환성 제약에 따른 CPU fallback을 유지했다. 이 작업에서 runtime 설정을 변경하지 않았다.

## 1회 실제 추론 결과

- 정책 `Supermassive111/act-so101-opengrip100-30k-v1@root`로 시작했다.
- UI는 policy loading/하드웨어 연결 후 `RUNNING`, `00:06 / 00:30`을 표시했다.
- 이후 UI가 홈으로 복귀하면서 `Inference finished`, exit code `1`을 표시했다. 30초 만료 전 비정상 종료로 분류한다.
- 종료 log tail은 follower bus cleanup에서 id 1의 `Torque_Enable=0` write가 status packet을 받지 못해 6회 재시도 후 실패했음을 보였다.
- 사용자는 이 1회에서 follower가 아닌 leader arm이 움직였다고 보고했다. 이어서 읽기 전용으로 LeLab Calibration 화면을 확인했을 때 Leader port가 `/dev/ttyACM1`로 표시됐다. 이 값은 확정된 leader=`...5AE6085272`(`/dev/ttyACM0`), follower=`...5AE6058306`(`/dev/ttyACM1`) 역할과 반대다.
- 따라서 포트 역할 역전이 우선 수정 대상이다. 이 기록 작업에서는 설정 변경이나 추가 추론을 수행하지 않았다.
- 이후 사용자 승인으로 LeLab의 저장 포트만 leader=`/dev/ttyACM0`, follower=`/dev/ttyACM1`로 보정했다. API 재조회에서 두 값이 일치했고, 텔레오퍼레이션·녹화·추론은 보정 전후 모두 inactive였다. 캘리브레이션·모터 구동·추론 재시도는 하지 않았다.
- 그 뒤 1회 시험은 이 Calibration 화면용 값만 보정된 상태에서 이뤄졌다. UI는 `RUNNING 00:31 / 00:30` 뒤 exit code `1`로 종료했고, 모든 제어 작업은 inactive로 복귀했다.
- 이후의 실제 record 조회에서 Calibration 화면용 저장 port와 추론용 `so-101` robot record가 서로 다른 것을 확인했다. `so-101` record는 여전히 leader=`/dev/ttyACM1`, follower=`/dev/ttyACM0`여서 이 1회가 leader를 움직인 원인이었다.
- 같은 사용자 승인 범위에서 실제 `so-101` record의 port 두 값만 leader=`/dev/ttyACM0`, follower=`/dev/ttyACM1`로 보정하고 GET으로 재확인했다. camera binding, calibration config, 기타 robot fields는 보존했다.
- 읽기 전용 camera 확인: Jetson은 C920 index 0과 USB Camera index 2를 available로 반환했고, 두 remote preview stream 모두 HTTP 200 MJPEG frame stream을 반환했다. UI의 비녹화 상태 `No preview`는 서버 카메라 연결 실패를 뜻하지 않는다.
- 별도 현장 안전 승인 후, 보정된 실제 `so-101` record와 두 camera binding을 사용하여 ACT 30k를 최대 30초로 1회 실행했다. UI가 `RUNNING 00:01 / 00:30`에서 `00:28 / 00:30`까지 진행한 후 `Inference finished — Run completed`와 홈 `Ready`를 표시했다.
- 종료 후 API로 inference·teleoperation·recording inactive를 확인했다. `PASS (UI)`: 정상 시작·실행·시간 제한 종료 경로가 통과했다.
- 사용자 현장 관찰: follower arm은 실제로 움직였지만 물체를 잡지 못했다. 따라서 실행·포트 역할은 통과했지만 집기·분류 성능은 아직 실패다.
- 가설: 현재 2D ACT는 거리값을 직접 측정하지 않으며, 물체 시작 위치·자세·조명, 그리퍼 닫힘 타이밍/시연 품질, 데이터 범위가 실패에 기여할 수 있다.
- 별도 추가 현장 안전 승인으로 같은 보정 포트·모델·두 카메라 조건에서 최대 30초 ACT를 1회 더 실행했다. UI는 `RUNNING 00:24 / 00:30`에서 `00:32 / 00:30`까지 표시한 뒤 홈 `Ready`로 복귀했다. 이후 API는 inference·teleoperation·recording inactive를 반환했다. 실제 집기 결과는 현장 관찰 대기 상태다.
- `HISTORICAL FAIL (UI)`: 포트 역전이 남아 있던 첫 실행은 성공으로 판정하지 않는다. 위의 별도 승인·실제 record 보정 후 실행은 `Run completed`로 종료됐다.
- `NOT_VERIFIED`: 완료 뒤 상태 API가 오류 전문·log path를 유지하지 않았으므로, Jetson의 inference log를 읽기 전용으로 수집하기 전에는 최초 오류와 실제 물체 동작 결과를 확정하지 않는다.
- `NOT_PUSHED`: GitHub 작업 저장소의 커밋·push는 수행하지 않았다.

## 2026-09-17 추가 30k v1 추론

- 사용자 승인: `ACT 30k v1 팔로워 추론 1회 안전 승인, 현장 안전 확인`.
- 실행 직전 LeLab 홈은 `Ready`, local job 0개였으며, imported model `ACT open gripper 100 episodes 30k v1`의 정책 참조는 `Supermassive111/act-so101-opengrip100-30k-v1`로 확인됐다.
- 모달에서 checkpoint `latest`, camera binding `312`→`#0 HD Pro Webcam C920`, `camera_2`→`#2 USB Camera`(각 640×480)를 확인하고 최대 시간을 30초로 설정했다.
- `PASS (UI)`: Inference 화면에서 해당 정책으로 `RUNNING 00:21 / 00:30`, 이어 `RUNNING 00:25 / 00:30`까지 확인했다. 이후 UI가 자동으로 설정 화면으로 복귀했고 Stop control은 남아 있지 않았다.
- `NOT_VERIFIED`: UI 종료 경로는 확인했지만, 이번 run의 실제 집기 결과·Jetson의 종료 log/API 상태는 아직 별도 확인하지 않았다. 현장 관찰 결과를 받아야 성공률을 판정할 수 있다.

## 2026-09-17 50-episode v1 비교 추론

- 사용자 승인: `ACT open gripper 50 episodes v1 팔로워 추론 1회 안전 승인, 현장 안전 확인`.
- 첫 시작 시도는 이전 30k run이 LeLab 내부 상태에 잠시 active로 남아 있어 `Inference is already active`로 차단됐다. 이 시도는 50-episode 정책을 시작하지 않았고, 중복 제어를 피했다.
- 읽기 전용 Inference 화면 재조회에서 이전 run의 `Inference finished — Run completed`를 확인한 뒤 model 목록을 새로고침했다.
- `PASS (UI)`: `Supermassive111/act-so101-opengrip50-v1@root`를 checkpoint `latest`, `312`→C920 index 0, `camera_2`→USB Camera index 2, 최대 30초로 1회 실행했다. UI는 `RUNNING 00:21 / 00:30`, `RUNNING 00:26 / 00:30`까지 표시하고 자동으로 설정 화면으로 복귀했다.
- `NOT_VERIFIED`: 이번 50-episode run의 실제 집기·분류 결과 및 종료 log/API 상태는 현장 관찰·읽기 전용 log 확인 전까지 판정하지 않는다.
