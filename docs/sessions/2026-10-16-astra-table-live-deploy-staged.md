# 2026-10-16 Astra 작업대 좌표 활성 배포 및 live 확인

## 범위

- 기존 `medicine-yolo-preview.service`와 8020 UI만 확장한다.
- 로봇 serial, LeLab, Goal/Torque/config write, 모터 동작은 사용하지 않는다.
- 카메라 작업에 로봇 관절 보정·전체 분류 readiness를 적용하지 않는다.

## 확인된 실제 실행 경로

- 서비스: `/etc/systemd/system/medicine-yolo-preview.service`
- 사용자/그룹: `jetson3:video`
- Python: `/usr/bin/python3` (`3.10.12`)
- 실행 코드:
  `/home/jetson3/so101-medicine-bootstrap/models/yolo11n-medicine-smoke-v1/medicine_yolo_web.py`
- 활성 설정: `/opt/so101-rgbd/astra_rgbd.example.json`
- Astra RGB: `/opt/orbbec-openni2/bin/orbbec-rgb-pipe`, RGB888 `640×480`
- dictionary: `DICT_4X4_50`
- 좌표 정의: ID0 검은 사각형 중심이 원점, ID0→ID1이 +X, 작업대 안쪽이
  +Y, 작업대 위쪽이 +Z, 단위 mm

기존 활성 설정 SHA-256은
`4084552908c877c90585eb76b5b5ebf23b49d8abfc1bd858608d7ebcc355ffd0`이고,
오래된 reference centers를 포함한다. 또한 설정이 참조하는
`/opt/so101-rgbd/astra_color_intrinsics.local.json`은 활성 경로에서 누락돼
있었다. 기존 서비스 코드는 왜곡 보정 없이 원본 640×480에 homography를
계산했다.

## 준비한 변경

- 새 reference centers:
  - ID0 `[0.000, 0.000] mm`
  - ID1 `[527.324, 0.000] mm`
  - ID2 `[524.108, 318.309] mm`
  - ID3 `[10.865, 321.156] mm`
- ID0–6 70 mm, ID7–9 30 mm 인쇄 규격을 구분한다. 실제 출력물 자 실측은
  여전히 `NOT_RUN`이다.
- intrinsic 파일 SHA-256
  `2be8287af33b15bccec80b71b41b47de85be510323e50f7033cbb517658bde73`,
  640×480, reprojection RMS `0.477959973 px`를 실제로 로드한다.
- 왜곡 보정된 전체 640×480 프레임 하나에서 검출, overlay, frozen-frame
  클릭 XY를 모두 수행한다. resize/crop은 없다.
- ID0–3 중심, ID0 원점, +X/+Y 축, current-frame validity, 최신 시각을 표시한다.
- ID0–3 중 하나라도 빠지면 `INVALID_CURRENT_FRAME`이며 이전 homography를
  현재 결과로 재사용하지 않는다.
- `/api/table-point`는 정확히 고정한 프레임의 작업대 평면 `z=0` 점만
  변환한다. 약통 상단 등 높이가 있는 점에는 같은 정확도를 주장하지 않는다.
- 새 좌표의 6거리 적합 RMS `2.600 mm`는 배치 적합 residual로만 표시하며
  카메라 위치/로봇 집기 정확도로 승격하지 않는다.

## 검증

- 로컬 카메라 단위/회귀: `17/17 PASS`
- Python compile, JSON parse, `git diff --check`: `PASS`
- Jetson `/usr/bin/python3`, OpenCV `4.8.0`, NumPy `1.21.5` 격리 smoke:
  - import/compile: `PASS`
  - config/intrinsic load: `PASS`
  - 합성 ID0–3 검출: `PASS`
  - `VALID_CURRENT_FRAME`: `PASS`
  - 새 좌표와 70/30 mm marker size load: `PASS`
- 로봇 serial open 및 motor/Goal/Torque/config write: `0`

## 백업과 배포 상태

변경 전 파일을 다음 위치에 읽기 가능한 복사본으로 보관했다.

`/home/jetson3/so101-camera-backups/20261016T2045-table-coordinates/`

검증된 배포 번들과 적용 스크립트는 다음에 있다.

`/home/jetson3/so101-camera-deploy-stage-20261016/`

사용자가 sudo 사용을 승인했고, 비밀번호는 파일·명령·문서에 기록하지 않고
대화형 sudo 프롬프트에만 입력했다. 검증된 배포 스크립트가 파일 hash를 다시
검사한 뒤 활성 설정·intrinsic·웹 코드·읽기 전용 보조 모듈을 설치하고
`medicine-yolo-preview.service` 하나만 재시작했다. 서비스는
`active/running`, main PID `10656`, `ExecMainStatus=0`이다.

실제 활성 hash는 다음과 같다.

- web code: `74548aee952875c46b910d7cb32290834244bd3fb50f36a46210a4b8f7f931fc`
- workspace config: `717a31fe897592751e4be18fad1604c8130dc2544a35fdeb47e2d17801a79df2`
- intrinsic: `2be8287af33b15bccec80b71b41b47de85be510323e50f7033cbb517658bde73`

`/health` 5회 연속에서 Astra와 RealSense 모두 healthy, frame age
`0.044–0.260 s`, ID0–3 모두 검출, `VALID_CURRENT_FRAME`, 새 reference centers,
왜곡 보정 적용과 `undistorted_full_frame`/`resize_crop=none`을 확인했다. ID9는
이 5회 중 일부 프레임에서 누락됐지만 ID9는 작업대 변환 reference가 아니며,
약통 마커 검출 안정성은 별도 후속 항목이다.

실제 frozen frame sequence `201`의 ID0 중심 pixel `[227.124,128.831]`을
`/api/table-point`에 전달한 결과 `[-0.001,0.000] mm`였다. 이는 같은
보정점 self-check이지 독립 정확도 검증은 아니다. 서로 다른 실제 프레임 20개는
모두 유효했고 누락 0이었다. reference marker 중심의 짧은 pixel 흔들림은 다음과
같다.

- ID0: x/y 표준편차 `0.0347/0.0302 px`, span `0.124/0.123 px`
- ID1: x/y 표준편차 `0.0759/0.0404 px`, span `0.293/0.152 px`
- ID2: x/y 표준편차 `0.0154/0.0265 px`, span `0.069/0.126 px`
- ID3: x/y 표준편차 `0.0198/0.0249 px`, span `0.079/0.108 px`

브라우저에서도 Astra 영상 위 ID0–3 중심, ID0 원점, +X/+Y 100 mm 축,
`TABLE XY VALID`와 새 작업대 평면 frozen-click UI를 확인했다. 따라서 현재
상태는 다음과 같다.

독립 검증 수집 준비에서 기존 frozen-click 응답에 같은 프레임의
`observed_at_utc`와 `transform_validity`를 추가했다. 로컬 회귀는 계속
`17/17 PASS`; Jetson 활성 코드 SHA-256은
`6ce3199501689649faf5401ff3673db59ccecfa516d925380c2efe6900cd1939`다.
실제 sequence `75` 응답에서 관측 시각
`2026-10-16T11:58:29.303458+00:00`, `VALID_CURRENT_FRAME`, ID0 self-check
`[-0.001,-0.001] mm`, robot/motion authorization false를 확인했다.

```ini
JETSON_STAGE = PASS
JETSON_ACTIVE_CONFIG = PASS
ASTRA_LIVE_NEW_COORDINATES = PASS
INDEPENDENT_VALIDATION_POINTS = NOT_RUN
ROBOT_IO = 0
```

## 독립 검증점 측정 절차

ID0 중심을 `(0,0)`으로 하고 ID0→ID1을 +X로 삼는다. 작업대 평면에 얇은
십자 표시를 중앙, 약통 예정 영역, 가장자리의 3곳 이상 두고, 직각자/줄자를
이 두 축에 평행하게 사용해 각 십자 중심의 실제 X/Y를 독립 측정한다.
각 점마다 새 frozen frame을 최소 10회 만들고 같은 십자 중심을 클릭해
camera X/Y를 기록한다. `dx`, `dy`, `sqrt(dx²+dy²)`, 반복 표준편차/최대범위,
유효 관측 수와 marker 누락 수를 구분한다. 마커 네 점의 self-fit reprojection,
독립 위치 오차, 반복 흔들림은 서로 다른 지표로 보고한다. 실측값이 없으므로
현재 독립 검증 결과는 임의 생성하지 않고 `NOT_RUN`이다.

## 독립 검증점 기준값 입력 — Method B

사용자는 1 mm 눈금 자로 검은 사각형 중심부터 작업대 평면의 얇은 테이프
십자까지 거리를 측정했다. 마지막 문장의 "세 점"은 별도 정정이 없는 한
P1–P4 모두 ID2·ID3 쪽 작업대 안이라는 뜻으로 임시 해석하며 `Y>0`을 사용한다.
기준선은 ID0→ID1이고 `L=527.324 mm`; ID0→ID3을 Y축으로 사용하지 않는다.

```text
P1 d0=109 mm, d1=453 mm -> reference=(80.352, 73.652) mm
P2 d0=446 mm, d1=110 mm -> reference=(440.798, 67.921) mm
P3 d0=264 mm, d1=510 mm -> reference=(83.124, 250.572) mm
P4 d0=507 mm, d1=285 mm -> reference=(430.375, 268.004) mm
```

네 점 모두 `|d0-d1| <= L <= d0+d1`을 만족하고 square-root radicand가
양수다. 거리 두 개를 각각 독립적으로 `±1 mm` 변화시킨 단순 민감도
cross-check에서 최대 XY 이동은 P1 `2.315`, P2 `2.553`, P3 `1.574`,
P4 `1.590 mm`였다. 이는 자의 확정 불확도나 통계 신뢰구간이 아니라 1 mm
입력 변화에 대한 계산 민감도다. P1/P2는 기준선에 더 가까워 Y가 상대적으로
민감하다.

이 네 점은 현재 변환 평가에만 사용하며 보정 입력으로 사용하지 않는다.
이 시점에는 UI click 표본이 없었으며, 아래 후속 섹션에서 수집을 시작했다.

## Frozen-frame UI 문법 오류 수정

사용자가 `현재 작업대 프레임 고정`을 눌러도 이미지가 나타나지 않고
상태가 `상태 읽는 중…`에 머무는 현상을 재현했다. Python triple-quoted
`INDEX_HTML`의 `freezeTable()` 문자열에 있던 `\n`이 HTML 생성 시 literal
newline으로 바뀌어 JavaScript single-quoted string을 끊은 것이 원인이었다.
해당 한 곳을 `\\n`으로 수정하고 생성된 HTML에 escaped newline이 남고 literal
newline이 없는지 확인하는 회귀 검사를 추가했다.

- 로컬 관련 테스트: `17/17 PASS`
- Python compile, `git diff --check`: `PASS`
- 수정 코드 SHA-256:
  `20a45f3be0e334fd11fa04e676664f5efc578347ba56b51b4f5cc1b37efba08c`
- 변경 전 활성 코드 백업:
  `/home/jetson3/so101-camera-backups/20261016T2125-freeze-ui-fix/medicine_yolo_web.py.before`
- Jetson compile·생성 HTML escape 검사: `PASS`
- `medicine-yolo-preview.service`: `active`, `ExecMainStatus=0`
- 브라우저 실제 검증: 상태 poll 정상, frozen sequence `435`, JPEG data URL
  로드, `undistorted_full_frame` 표시 `PASS`
- 마커 좌표·intrinsic·보정값 변경: `0`
- 로봇 serial/Goal/Torque/config/motor I/O: `0`
- P1–P4 새 프레임 독립 검증 클릭 수집: `COMPLETE (12/12)`
- P3 동일 프레임 5회 클릭: `COMPLETE (5/5)`

## 독립 검증 수집 시작

P1의 첫 번째 새 frozen-frame 클릭 `P1-F1`을 UI 응답에서 직접 수집했다.

- frame sequence: `868`
- observed: `2026-10-16T12:32:04.644525+00:00`
- validity: `VALID_CURRENT_FRAME`
- clicked pixel: `[259.806, 164.973]`
- coordinate space: `undistorted_full_frame`
- camera table XY: `[78.151, 88.560] mm`
- P1 reference: `[80.352, 73.652] mm`
- `ΔX = -2.201 mm`, `ΔY = +14.908 mm`
- planar error: `15.070 mm`

이 한 표본으로 판정 기준을 만들거나 보정값을 변경하지 않았다. 수집은
`docs/sessions/2026-10-16-astra-independent-validation.json`에 구조화해 보존했다.

P1의 두 번째 새 frozen-frame 클릭 `P1-F2`도 직접 수집했다.

- frame sequence: `1306`
- observed: `2026-10-16T12:34:14.164935+00:00`
- validity: `VALID_CURRENT_FRAME`
- clicked pixel: `[258.915, 166.973]`
- camera table XY: `[77.205, 93.218] mm`
- `ΔX = -3.147 mm`, `ΔY = +19.566 mm`
- planar error: `19.817 mm`
- P1-F1→F2 좌표 차이: `[-0.946,+4.658] mm`, 평면 거리 `4.753 mm`

서로 다른 frozen frame의 결과라 마지막 차이는 frame 변화와 click
선택 편차가 함께 포함된다. 순수 카메라 흔들림으로 해석하지 않는다.

P1의 세 번째 새 frozen-frame 클릭 `P1-F3`을 수집했다.

- frame sequence: `1551`
- observed: `2026-10-16T12:35:27.013340+00:00`
- clicked pixel: `[258.470, 164.528]`
- camera table XY: `[75.348, 87.414] mm`
- `ΔX = -5.004 mm`, `ΔY = +13.762 mm`
- planar error: `14.644 mm`

P1 새 프레임의 평균은 `[76.901,89.731] mm`, 평균 좌표의 기준점 오차는
`[-3.451,+16.079] mm`, 평면 거리 `16.445 mm`다. 새 표본의 X/Y sample
standard deviation은 `1.426/3.074 mm`, range는 `2.803/5.804 mm`다. 이는 새
프레임 변화와 클릭 편차가 섞인 값이다.

P2의 첫 번째 새 frozen-frame 클릭 `P2-F1`을 수집했다.

- frame sequence: `1822`
- observed: `2026-10-16T12:36:47.630073+00:00`
- validity: `VALID_CURRENT_FRAME`
- clicked pixel: `[466.536, 160.861]`
- camera table XY: `[448.176, 78.401] mm`
- P2 reference: `[440.798, 67.921] mm`
- `ΔX = +7.378 mm`, `ΔY = +10.480 mm`
- planar error: `12.817 mm`

P2의 두 번째 새 frozen-frame 클릭 `P2-F2`도 수집했다.

- frame sequence: `2042`
- observed: `2026-10-16T12:37:53.061652+00:00`
- validity: `VALID_CURRENT_FRAME`
- clicked pixel: `[466.536, 159.638]`
- camera table XY: `[448.304, 75.793] mm`
- `ΔX = +7.506 mm`, `ΔY = +7.872 mm`
- planar error: `10.877 mm`
- P2-F1→F2 좌표 차이: `[+0.128,-2.608] mm`, 평면 거리 `2.611 mm`

P2의 세 번째 새 frozen-frame 클릭 `P2-F3`을 수집했다.

- frame sequence: `2354`
- observed: `2026-10-16T12:39:25.832008+00:00`
- clicked pixel: `[465.312, 160.861]`
- camera table XY: `[446.182, 78.336] mm`
- `ΔX = +5.384 mm`, `ΔY = +10.415 mm`
- planar error: `11.724 mm`

P2 새 프레임의 평균은 `[447.554,77.510] mm`, 평균 좌표의 기준점 오차는
`[+6.756,+9.589] mm`, 평면 거리 `11.730 mm`다. X/Y sample standard
deviation은 `1.190/1.487 mm`, range는 `2.122/2.608 mm`다. 이도 새 프레임
변화와 클릭 편차가 섞인 값이다.

P3의 첫 번째 새 frozen-frame 클릭 `P3-F1`을 수집했다.

- frame sequence: `2756`
- observed: `2026-10-16T12:41:24.628258+00:00`
- validity: `VALID_CURRENT_FRAME`
- clicked pixel: `[248.679, 240.324]`
- camera table XY: `[82.943, 248.612] mm`
- P3 reference: `[83.124, 250.572] mm`
- `ΔX = -0.181 mm`, `ΔY = -1.960 mm`
- planar error: `1.968 mm`

P3의 두 번째 새 frozen-frame 클릭 `P3-F2`도 수집했다.

- frame sequence: `3060`
- observed: `2026-10-16T12:42:54.634351+00:00`
- validity: `VALID_CURRENT_FRAME`
- clicked pixel: `[247.455, 240.324]`
- camera table XY: `[80.934, 248.557] mm`
- `ΔX = -2.190 mm`, `ΔY = -2.015 mm`
- planar error: `2.976 mm`
- P3-F1→F2 좌표 차이: `[-2.009,-0.055] mm`, 평면 거리 `2.010 mm`

P3의 세 번째 새 frozen-frame 클릭 `P3-F3`을 수집했다.

- frame sequence: `3350`
- observed: `2026-10-16T12:44:21.295275+00:00`
- clicked pixel: `[247.455, 240.324]`
- camera table XY: `[81.029, 248.663] mm`
- `ΔX = -2.095 mm`, `ΔY = -1.909 mm`
- planar error: `2.834 mm`

P3 새 프레임의 평균은 `[81.635,248.611] mm`, 평균 좌표의 기준점 오차는
`[-1.489,-1.961] mm`, 평면 거리 `2.462 mm`다. X/Y sample standard
deviation은 `1.133/0.053 mm`, range는 `2.009/0.106 mm`다. 이도 새 프레임
변화와 클릭 편차가 섞인 값이다.

P4의 첫 번째 새 frozen-frame 클릭 `P4-F1`을 수집했다.

- frame sequence: `3717`
- observed: `2026-10-16T12:46:09.829704+00:00`
- validity: `VALID_CURRENT_FRAME`
- clicked pixel: `[464.088, 253.771]`
- camera table XY: `[435.566, 267.755] mm`
- P4 reference: `[430.375, 268.004] mm`
- `ΔX = +5.191 mm`, `ΔY = -0.249 mm`
- planar error: `5.197 mm`

P4의 두 번째 새 frozen-frame 클릭 `P4-F2`도 수집했다.

- frame sequence: `4033`
- observed: `2026-10-16T12:47:42.938117+00:00`
- validity: `VALID_CURRENT_FRAME`
- clicked pixel: `[464.088, 252.549]`
- camera table XY: `[435.545, 265.611] mm`
- `ΔX = +5.170 mm`, `ΔY = -2.393 mm`
- planar error: `5.697 mm`
- P4-F1→F2 좌표 차이: `[-0.021,-2.144] mm`, 평면 거리 `2.144 mm`

P4의 세 번째 새 frozen-frame 클릭 `P4-F3`을 수집했다.

- frame sequence: `4391`
- observed: `2026-10-16T12:49:28.017442+00:00`
- clicked pixel: `[462.864, 254.994]`
- camera table XY: `[433.569, 270.145] mm`
- `ΔX = +3.194 mm`, `ΔY = +2.141 mm`
- planar error: `3.845 mm`

P4 새 프레임의 평균은 `[434.893,267.837] mm`, 평균 좌표의 기준점 오차는
`[+4.518,-0.167] mm`, 평면 거리 `4.521 mm`다. X/Y sample standard
deviation은 `1.147/2.268 mm`, range는 `1.997/4.534 mm`다.

12개 새 프레임 표본의 평면 오차 RMS는 `10.604 mm`, 최대는 P1-F2의
`19.817 mm`다. 전체 signed delta 평균은 `[+1.584,+5.885] mm`이다. 위치별
평균 오차 방향은 P1 `(-X,+Y)`, P2 `(+X,+Y)`, P3 `(-X,-Y)`, P4
`(+X,-Y)`로, 단일 전역 offset보다 위치 의존 경향이 보인다. 아직 P3
동일 프레임 5회 click 편차를 수집하지 않았고 보정값은 변경하지 않았다.

동일 프레임 5회 click을 한 번에 회수하기 위해 기존 `chooseTable()` 결과
표시에 현재 frozen sequence의 `click_history` 배열만 추가했다. 새
프레임을 고정할 때마다 기록은 초기화되며, API·좌표 수학·보정값은
변경하지 않았다. 로컬 회귀 `17/17 PASS`; 활성 코드 SHA는
`b278d36cfc520d7b959c2f3a1b2360e911a8bebf9b10cb7b6301883f4c9f9523`이다. 변경 전
코드는 `/home/jetson3/so101-camera-backups/20261016T2151-click-history/`에
보관했다. 서비스 `active`, `ExecMainStatus=0`, ID0–3
`VALID_CURRENT_FRAME`, 브라우저 reload/status poll PASS다. P3 다섯 클릭 실측은
아직 `NOT_RUN`.

P3 동일 프레임 5회로 제출된 첫 시도는 frame sequence `403`,
`VALID_CURRENT_FRAME`, 다섯 응답 모두 pixel `[463.866,252.882]`, table XY
`[435.281,266.225] mm`였다. 이 위치는 P3 기준점에서 `352.505 mm`, P4
기준점에서 `5.219 mm`로 P4 십자를 누른 것으로 판정했다. 따라서
`REJECTED_WRONG_POINT`로 별도 기록하고 P3 click variation에는 포함하지
않았다. P3 동일 프레임 5회는 여전히 `NOT_RUN`.

재측정에서는 frame sequence `691`, observed
`2026-10-16T13:05:31.218888+00:00`, `VALID_CURRENT_FRAME`에서 P3를
다섯 번 클릭했다. 모든 클릭의 pixel은 `[247.233,240.657]`, table XY는
`[80.780,249.293] mm`로 같았다. P3 기준점 대비 `ΔX=-2.344 mm`,
`ΔY=-1.279 mm`, 평면 오차 `2.670 mm`다. 동일 프레임 5회의 pixel과
table XY sample standard deviation/range는 모두 `0.000`이다. 이는 이번 UI
클릭 좌표 정밀도에서 선택 편차가 관측되지 않았다는 뜻이며, 일반적으로
클릭 오차가 영임을 증명하는 것은 아니다.

수집은 새 프레임 `12/12`, P3 동일 프레임 `5/5`로 완료했다.
사전 PASS 기준은 없으며, 검증점 기준값의 자 측정·기준 길이 오차가 포함된다.
이 결과로 마커 좌표·intrinsic·homography 산식을 수정하지 않았고, 로봇
연결·이동도 하지 않았다.
