# 2026-09-20 — 세 카메라 매핑과 ArUco live 확인

## 범위와 안전 상태

- 사용자 보고: ArUco marker 인쇄·배치 완료, 카메라 3대 Jetson 연결 완료.
- 시작 전 LeLab `/health` 정상, teleoperation·recording·inference 모두 inactive 확인.
- 실제 모터 동작, torque, robot serial, USB 재연결, SO-101 calibration은 수행하지 않았다.
- `v4l2-ctl`은 Jetson에 설치되어 있지 않아 sysfs, `/dev/v4l/by-id`, `udevadm`으로 canonical 장치를 확인했다.

## 확정 카메라 매핑

| 사용자 확정 역할 | 현재 node | stable identity |
|---|---:|---|
| 천장 사선 | `/dev/video0` | C920 `27292FAF`, `046d:082d` |
| 로봇팔·손목 | `/dev/video2` | Generic USB `200901010001`, `0bda:5844` |
| 천장 수직·ArUco 기준 | `/dev/video4` | C920 `07FE1FAF`, `046d:082d` |

- 각 물리 카메라는 index0/index1 node 쌍을 만들었다. `/dev/video1`, `3`, `5`는 추가 물리 카메라가 아니다.
- Safari의 `/camera-preview/0`, `/camera-preview/2`, `/camera-preview/4` 별도 탭에서 세 640×480 stream을 확인했다.

## camera-only ArUco 검사

LeLab 작업이 모두 inactive인 상태에서 카메라 한 대씩 순차적으로 90 frames를 읽었다.

### `/dev/video0` — 천장 사선

- captured: 90/90
- ID 0: 0
- ID 1: 0
- ID 2: 88
- ID 3: 0
- 판정: `FAIL` for four-marker workspace view. 카메라 frame read 자체는 `PASS`.

### `/dev/video4` — 천장 수직

- captured: 90/90
- ID 0: 90
- ID 1: 89
- ID 2: 88
- ID 3: 22
- 판정: `PARTIAL`. 네 ID를 모두 검출했지만 ID 3 안정성이 부족하다.

## 화면 관찰

- `/dev/video2`에는 로봇 그리퍼가 근접 표시돼 손목 카메라 역할과 일치했다.
- `/dev/video4`에는 팔로워와 네 marker가 모두 보였다.
- 작업대 중앙에 강한 조명 반사가 보였다. 현재 marker와 직접 겹치지는 않지만 이후 노출·검출 안정성에 영향을 줄 수 있어 조명 고정과 반사 억제가 필요하다.

## 현재 점유와 다음 한 단계

- `ACTIVE_RESOURCE`: 사용자 요청에 따라 Safari에 세 preview tab을 열어 둔 상태다. 다음 OpenCV detector, camera calibration, LeLab recording을 시작하기 전에 세 탭을 닫아야 한다.
- ID 3을 평평하게 펴고 가림·반사·프레임 가장자리를 피하도록 조금 안쪽으로 조정한다.
- preview를 닫은 뒤 천장 수직 `/dev/video4`로 300-frame ID 안정성 검사를 다시 실행한다.
- `NOT_VERIFIED`: intrinsic calibration, homography/jitter, marker pose, wrist hand-eye calibration.
- `NOT_PUSHED`: Git commit·push를 수행하지 않았다.

## Marker center 실측과 현장 config

사용자가 marker 중심 사이 거리를 다음과 같이 실측했다.

- ID 0–1: 343 mm
- ID 1–2: 274 mm
- ID 2–3: 340 mm
- ID 3–0: 277 mm
- ID 0–2: 440 mm
- ID 1–3: 436 mm

ID 0=(0,0), ID 1=(343,0)으로 좌표계를 고정하고 여섯 거리를 최소제곱으로 맞춘 결과:

- ID 2=(345.082, 273.708) mm
- ID 3=(5.446, 276.666) mm
- 전체 거리 잔차 RMS: 약 0.34 mm

`configs/aruco_table.local.json`에 위 좌표와 천장 수직 `/dev/video4`, 640×480@30을
저장했고 parser 검증을 통과했다. 현장 local config는 Git 제외 상태다.

- `/camera-preview/4` Safari 탭을 닫았지만 LeLab 내부 preview 1개가 즉시 release되지 않았다.
- 공식 `POST /camera-preview-stop`은 `stopping=1`을 반환했지만 direct V4L2 open은 계속 실패했다.
- teleoperation·recording·inference가 모두 inactive인 상태를 확인한 뒤 `lelab.service`만 재시작했다. 재시작 뒤 `/health` 정상 및 세 작업 inactive를 재확인했다.

## 300-frame homography 및 ID 안정성 검사

- 카메라: 천장 수직 `/dev/video4`, 640×480@30, camera-only
- 실제 marker center 좌표를 적용한 homography run은 300 frames를 완료했다.
- sampled frame 대부분에서 ID 0·1·3만 검출됐다. ID 2가 보인 일부 frame에서만 homography가 성립해, 지속적인 좌표 jitter는 계산할 수 없었다.
- 별도 300-frame 집계: ID 0=300, ID 1=300, ID 2=0, ID 3=299, captured=300/300.
- 판정: `FAIL` for stable four-marker homography. 카메라 frame read는 `PASS`.
- 마지막 annotated frame에서 ID 2는 오른쪽 아래 작업면 가장자리에 붙어 있으며 오른쪽·아래쪽 흰 여백이 사실상 없었다. 다음 물리 조정은 ID 2만 안쪽으로 20–30 mm 이동해 네 방향에 최소 10–20 mm 흰 여백을 확보하는 것이다.
- `NOT_VERIFIED`: 네 marker 지속 검출 조건의 homography jitter, intrinsic calibration, marker pose.
- `SAFETY`: 이 검사와 service recovery에서 robot serial, torque, teleoperation, recording, inference를 실행하지 않았다.
- `NOT_PUSHED`: Git commit·push를 수행하지 않았다.

## ID 2 조정 후 재검사

- 사용자 보고: 오른쪽 아래 ID 2의 위치와 여백 조정 완료.
- 시작 전 `/health` 정상, teleoperation·recording·inference 모두 inactive, preview `stopping=0`을 확인했다.
- 300-frame ID 집계: captured=300/300, ID 0=300, ID 1=300, ID 2=300, ID 3=300. 판정 `PASS`.
- 이어진 300-frame homography run의 30-frame 주기 표본 모두에서 네 ID와 homography가 준비됐다.
- 최근 30-frame 화면 중심 jitter 표본은 약 0.20–0.22 mm RMS였다. 카메라·검출 안정성은 `PASS`.
- `CAUTION`: 위 jitter는 이동 전 marker center 좌표를 scale로 사용했으므로 절대 위치 정확도를 뜻하지 않는다. ID 2를 옮겨 기존 ID 2 좌표가 stale해졌다.
- `NEXT`: 새 ID 1–2, ID 2–3, ID 0–2 중심 거리를 다시 실측하고 ID 2 좌표를 재계산한다. 재계산 전 config는 로봇 목표 좌표에 사용하지 않는다.
- `SAFETY`: camera-only 검사이며 robot serial, torque, teleoperation, recording, inference를 실행하지 않았다.
- `NOT_PUSHED`: Git commit·push를 수행하지 않았다.

## 조정 후 거리 재측정과 최종 좌표 검증

- 새 중심 거리: ID 1–2=260 mm, ID 2–3=325 mm, ID 0–2=424 mm.
- 움직이지 않은 점은 ID 0=(0,0), ID 1=(343,0), ID 3=(6.242,276.930) mm로 고정했다.
- ID 2의 최소제곱 좌표는 (332.181,260.854) mm다. 세 새 거리의 적합값은 422.361, 261.079, 326.335 mm이고 잔차 RMS는 약 1.37 mm다.
- `configs/aruco_table.local.json`을 새 좌표로 갱신했고 parser 검증을 통과했다.
- 시작 전 `/health` 정상, teleoperation·recording·inference inactive, preview `stopping=0`을 확인했다.
- 새 좌표로 `/dev/video4` 300-frame homography run을 완료했다. 30-frame 주기 표본마다 네 ID와 homography가 준비됐고 종료 코드는 0이었다.
- 초기 표본 jitter 0.513 mm 이후 안정화됐으며, 후반 표본은 약 0.04–0.11 mm RMS, 마지막은 0.087 mm였다.
- 화면 중심의 최종 표본 작업대 좌표는 약 (134.348,166.723) mm였다.
- `PASS`: ArUco 네 ID 가시성, 평면 homography 생성, 정지 카메라 단기 안정성.
- `NOT_VERIFIED`: camera intrinsic calibration, lens distortion correction, robot-base 좌표 등록, 실제 로봇 도달 정확도.
- `SAFETY`: camera-only 검사이며 robot serial, torque, teleoperation, recording, inference를 실행하지 않았다.
- `NOT_PUSHED`: Git commit·push를 수행하지 않았다.
