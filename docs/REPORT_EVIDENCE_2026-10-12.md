# 중간보고서 정량 결과 자료

작성 기준일: 2026-10-12
범위: 기존 저장 로그, JSON/JSONL, `docs/STATUS.md`, 세션 기록의 재정리
신규 하드웨어 실험·모터 동작·토크 변경·서비스 재시작: `NOT_RUN`

> 이 문서는 보고서에 복사할 수 있는 결과와 내부 근거 추적 정보를 함께 담는다. `CANDIDATE`, `NOT_VERIFIED`, `NOT_RUN` 표시는 현재 검증 범위를 뜻하며 생략하지 않았다.

## 1. 비전 인식 결과

최신 완전 live frame에서 ArUco ID 0–3과 YOLO C 검출 1개가 확인되었다. C identity는 검출 중심과 사전 등록 슬롯의 최근접 대응으로 얻은 `PROVISIONAL_SLOT_MATCH`이며, 별도의 문자 인식 결과로 과장하지 않는다. [V1]

| 항목 | 값 | 내부 근거 |
|---|---:|---|
| YOLO confidence | `0.797704` | [V1] |
| YOLO center pixel | `(323.432, 241.028) px` | [V1] |
| table coordinate, raw | `(279.490, 363.628) mm` | [V1] |
| table coordinate, metric-scale corrected | `(249.914813, 325.149464) mm` | [V1] |
| table coordinate, corrected + X reflection | `(-249.914813, 325.149464) mm` | [V1] |
| robot coordinate | `(-62.635354, -295.315566) mm` | [V1] |
| detection source | `live frame` (`SHA-256 9c4eb1fd…f867e3`) | [V1], [V2] |

**보고서용 한 줄 결과**

```text
C detection: pixel (323.432, 241.028)
→ raw table (279.490, 363.628) mm
→ scale-corrected table (249.914813, 325.149464) mm
→ robot (-62.635354, -295.315566) mm
```

내부 근거: [V1], [V2]

## 2. Table → Robot 좌표 변환 결과

현재 사용 중인 값은 P1–P3 물리 거리의 **약 305 mm 1회 실측**으로 metric scale을 보정한 뒤 Table X reflection과 2차원 rigid fit을 적용한 후보이다. 수치 기준점 오차는 single-digit mm이지만 JSON 상태는 `CANDIDATE_SINGLE_DIGIT_WITH_APPROXIMATE_SCALE_MEASUREMENT`이며 자동 모션 승인과 동일하지 않다. [C1]

| 항목 | 최종 사용 후보값 | 내부 근거 |
|---|---:|---|
| table scale correction, `s` | `0.8941815920521514` | [C1] |
| reflection | Table X reflection: `Xt → -Xt` | [C1] |
| rotation angle | `+13.232332690279133°` | [C1] |
| translation vector | `(255.07098132667602, -554.6267149158423) mm` | [C1] |
| P1–P4 fit RMS error | `5.4292646071482835 mm` | [C1] |
| P1–P4 fit maximum error | `7.4345843591253775 mm` | [C1] |
| H1 validation error | `9.458087433707417 mm` | [C1] |
| Repeat P1 transform error | `4.693745988089348 mm` | [C1] |
| Repeat P3 transform error | `4.853131490505826 mm` | [C1] |

반사와 scale을 분리해 쓴 좌표변환식은 다음과 같다. [C1]

```text
[Xr]   [0.9734498867  -0.2289002359] [-s Xt]   [ 255.0709813]
[Yr] = [0.2289002359   0.9734498867] [ s Yt] + [-554.6267149]

s = 0.8941815921
```

이를 원래 raw table 좌표에 대한 하나의 식으로 합치면 다음과 같다. [C1]

```text
[Xr]   [-0.8704409695  -0.2046783773] [Xt]   [ 255.0709813]
[Yr] = [-0.2046783773   0.8704409695] [Yt] + [-554.6267149]
```

**보고서용 문장:** 보정 후 기준점 반복 측정의 transform 오차는 약 **4.7–4.9 mm** 수준으로 확인되었다. [C1]

## 3. TCP Pivot calibration 결과

| 항목 | 값 | 내부 근거 |
|---|---:|---|
| TCP offset X | `-51.748354423 mm` | [P1] |
| TCP offset Y | `-73.033741060 mm` | [P1] |
| TCP offset Z | `-54.531737248 mm` | [P1] |
| offset magnitude | `104.811878554 mm` | [P1] |
| RMS residual | `4.239858360 mm` | [P1] |
| max residual | `7.704718578 mm` | [P1] |
| condition number | `10.681414820` | [P1] |
| Pose 8 hold-out error | `2.552316 mm` | [P2] |

**물리적 의미:** 기존 pivot TCP = 5점 calibration 당시 사용한 금속 **PIN TIP**. [T1]

Pose 8 hold-out은 Pose 1–7 fit으로 계산했으며, Pose 8의 방향이 Pose 1과 `2.590°`밖에 다르지 않아 강한 독립 방향 hold-out은 아니라는 제한이 있다. [P2]

## 4. TCP frame mixing 발견 결과

아래의 `C/planner reference`는 기존 planner가 사용한 approach 기준점이다. 실제 C의 물리적 3차원 중심을 별도로 정밀 측정했다는 뜻은 아니다. [T1]

| 비교점 | base XYZ | C/planner reference와의 거리 | 내부 근거 |
|---|---:|---:|---|
| C/planner reference | `(-62.635354, -295.315566, 80.000000) mm` | `0 mm` | [T1] |
| PIN_TIP_TCP | `(-62.633534, -295.292436, 79.999429) mm` | `0.023209 mm` | [T1] |
| `gripper` link origin proxy | `(21.041429, -276.316864, 140.198749) mm` | `104.817194 mm` | [T1] |

수치상 PIN TIP은 planner reference에 `0.023209 mm`까지 일치하지만, `gripper` link origin proxy는 `104.817194 mm` 떨어져 있었다. [T1] 따라서 **기존 IK는 실제 gripper 중심이 아니라 calibration용 PIN TIP을 약통 목표점에 정렬하고 있었음이 수치적으로 확인되었다.** 실제 opening center는 URDF `gripper` origin과 동일하다고 가정하지 않으며, 다음 절의 별도 GRASP TCP 후보로 취급한다. [T1], [T2]

## 5. 새 GRASP TCP 후보

첨부 사진의 방향과 URDF/mesh 축을 교차 확인한 현재 coarse 후보는 다음과 같다. 이 값은 calibration을 다시 한 결과가 아니라, 기존 PIN TIP offset에 현장 실측 상대벡터를 합한 값이다. [T2]

| 항목 | 값 | 현장 측정과의 관계 | 내부 근거 |
|---|---:|---|---|
| PIN TIP → GRASP opening center | `(+47.000, +61.000, -70.000) mm` | 사진 평면 수직 `47 mm → local +X`; PIN 높이 `60–62 mm → local +Y`의 중간값 `61 mm`; jaw 방향 `70 mm → local -Z` | [T2] |
| PIN TIP → GRASP magnitude | `104.067285926 mm` | 위 3축 coarse 실측의 벡터 크기 | [T2] |
| 기존 PIN TCP | `(-51.748354, -73.033741, -54.531737) mm` | gripper origin → PIN TIP | [P1], [T2] |
| 새 GRASP TCP 후보 | `(-4.748354, -12.033741, -124.531737) mm` | `PIN TCP + PIN→GRASP`; `+Y=60–62 mm` 범위에서 후보 Y는 `-13.033741…-11.033741 mm` | [T2] |
| gripper origin → GRASP 후보 magnitude | `125.201882 mm` | 새 GRASP TCP 후보의 norm | [T2] |

보정 전·후의 position-only 수치 비교는 다음과 같다. [T2]

| endpoint 해석 | GRASP_TCP → C/planner reference 거리 | 검증 상태 | 내부 근거 |
|---|---:|---|---|
| 기존 PIN 기반 endpoint를 새 GRASP TCP로 해석 | `104.052692927 mm` | 기존 frame-mixing 오차의 크기 | [T2] |
| 새 GRASP TCP를 C reference에 맞춘 offline endpoint | `0.000274868 mm` | position-only FK residual | [T2] |

`orientation / collision / 최종 실측 정밀도 = NOT_VERIFIED`
`새 endpoint 채택 / Jetson 배포 / 실제 모터 동작 = NOT_RUN` [T2]

## 6. 실제 로봇 경로 개선 결과

아래 표는 시간순이다. `Load`는 해당 병목 관절의 `Present_Load` raw 값이며, Wrist가 병목인 시험은 Wrist load를 병기했다. 로그에 없는 값은 계산으로 보완하지 않고 `N/A`로 표시했다.

| 시험 | 전략 | 실패/성공 위치 | Elbow error | Wrist error | Load | C까지 남은 XY | 결과 | 내부 근거 |
|---|---|---|---:|---:|---:|---:|---|---|
| 최초 stop-and-wait | 최대 `2°` bounded waypoint 후 각 점 정착 | final endpoint timeout | `+2.830°` | `+0.404°` | `N/A` | `N/A` | `ABORT`, `PRE_APPROACH_PASS` 아님 | [R1] |
| stop-and-wait 54-waypoint | 동일 endpoint, 정착식 실행 | final endpoint timeout | `+1.733°` | `+0.226°` | `N/A` | `N/A` | tolerance `1.6°`를 Elbow가 `0.133°` 초과, `ABORT` | [R1] |
| continuous-following | max step `1°`, 중간 추종 envelope | waypoint `14/107` | `+4.047664°` | `N/A` | Elbow `200` | `N/A` | `Moving=0`, no-progress `1.009 s`, `ABORT` | [R2] |
| A_MINIMAL | Lift/Wrist 선행 staged unload | start gate | `N/A` | `N/A` | `N/A` | `N/A` | reference mismatch, motor send `0`, fail-closed | [R3] |
| A2_MINIMAL | fresh pose 기반 staged unload | waypoint `26/107` | `+4.386646°` | `+0.275207°` | Elbow `212` | feedback `240.322 mm` | no-progress `1.013 s`, `ABORT` | [R4] |
| LIFT_NEG50 | Lift `-50°`까지 선행 후 Elbow relief | waypoint `34/105`, Elbow target `60°` | `+4.483516°` | `-0.670330°` | Elbow `216` | feedback `249.271902 mm` | `PAUSE→ABORT`; 약 `65°`까지는 정상 추종 | [R5] |
| Shoulder–Elbow coupling | BALANCED_COUPLED, Lift 상승과 Elbow 감소 동시 진행 | waypoint `15/71` | `+3.315740°` | `+2.676333°` | Elbow/Wrist `164/136` | feedback `219.311026 mm` | Wrist envelope 초과, `PAUSE→ABORT` | [R6] |
| Wrist delayed coupling | delay `25/35/45%` 오프라인 비교 | dry-run 전체 path | `N/A` | `N/A` | `N/A` | planned final `0.010 mm` | `WRIST_DELAY_25` 선택; 실제 시험 전 단계 | [R7] |
| WRIST_DELAY_25 | Wrist 감소를 뒤로 지연한 coupled path | waypoint `71/71`, final stable verification | `+1.177475°` | `+1.264789°` | Elbow/Wrist `68/72` | `N/A` | **`PRE_APPROACH_PASS`**, 2026-10-11, 사용자 `APPROACH CONFIRMED` 뒤 출력 | [R8] |

`WRIST_DELAY_25`의 실제 성공은 기존 final arm tolerance `1.6°`를 전 관절이 통과한 **pre-approach 도달 결과**이다. grasp/lift는 실행되지 않았다. 이후 야간 종료 시 현장 `STOPPED` 확인은 `physical_stop=NOT_VERIFIED`였으므로, pre-approach 수치 PASS와 최종 현장 정지 확인 상태를 구분한다. [R8]

## 7. 보고서용 핵심 정량 결과 10개

1. YOLO C 중심 = `(323.432, 241.028) px`, confidence `0.797704`. [V1]
2. C table 좌표 = raw `(279.490, 363.628) mm`, scale-corrected `(249.914813, 325.149464) mm`. [V1]
3. Table–Robot calibration RMS = `5.429264607 mm`. [C1]
4. Pivot TCP norm = `104.811878554 mm`. [P1]
5. Pivot RMS = `4.239858360 mm`. [P1]
6. 기존 PIN TCP target error = `0.023209 mm`. [T1]
7. 기존 gripper-origin proxy target error = `104.817194 mm`. [T1]
8. PIN→GRASP offset magnitude = `104.067285926 mm`. [T2]
9. 새 GRASP TCP position-only target error = `0.000274868 mm`; orientation/collision은 `NOT_VERIFIED`. [T2]
10. PRE_APPROACH 결과 = `WRIST_DELAY_25`, `71/71` waypoint 완료, final Elbow/Wrist error `1.177475°/1.264789°`, **`PRE_APPROACH_PASS`**. [R8]

## 8. 보고서에 바로 넣을 결과 설명

천장 카메라의 live 영상에서 YOLO로 C 약통을 검출하고, 중심 영상 좌표 `(323.432, 241.028) px`를 작업대 좌표와 로봇 base 좌표로 순차 변환하였다. [V1] 작업대 좌표에는 `0.8941815921`의 metric scale과 Table X reflection을 적용하였으며, P1–P4 기준점 fit의 RMS 오차는 `5.429 mm`였다. [C1] 금속 PIN을 이용한 pivot calibration에서는 gripper frame 기준 TCP offset `(-51.748, -73.034, -54.532) mm`와 RMS residual `4.240 mm`를 얻었다. [P1] 이후 기존 IK endpoint를 재검산한 결과, PIN TIP은 C planner reference와 `0.023 mm` 이내로 일치했지만 gripper-origin proxy는 `104.817 mm` 떨어져 있어 calibration용 PIN TCP와 grasp TCP가 혼용되었음을 확인하였다. [T1] 현장 사진과 `47/60–62/70 mm` 실측을 URDF 축에 대응시켜 PIN→GRASP 후보 `(+47, +61, -70) mm`와 GRASP TCP 후보 `(-4.748, -12.034, -124.532) mm`를 산출하였다. [T2] 이 새 TCP를 사용한 position-only 오프라인 endpoint의 FK residual은 `0.000275 mm`였지만 orientation, collision 및 최종 실측 정밀도는 아직 `NOT_VERIFIED`이다. [T2] 실제 pre-approach 경로는 Shoulder–Elbow coupling과 Wrist 지연을 순차 적용해 개선했으며, `WRIST_DELAY_25` 시험에서 71개 waypoint를 완료하고 final Elbow/Wrist error `1.177°/1.265°`로 `PRE_APPROACH_PASS`를 얻었다. [R8] 다만 grasp, lift, 새 GRASP TCP 기반 실제 접근은 아직 `NOT_RUN`이므로 본 결과는 비전 좌표계, TCP frame 진단 및 기존 PIN 기반 pre-approach까지의 검증으로 한정한다. [T2], [R8]

## 9. 그림/표 캡션

- **그림 1. YOLO 기반 C 약통 검출 결과.** Live 천장 영상에서 검출한 C 약통 bounding box와 중심 영상 좌표.
- **그림 2. ArUco 기반 작업공간 좌표 추정.** ArUco ID 0–3으로 구성한 작업대 평면 homography와 C 중심의 table 좌표 변환.
- **그림 3. Table–Robot 좌표계 보정 결과.** Metric scale, Table X reflection 및 rigid transform을 적용한 기준점 대응 결과.
- **그림 4. PIN TIP 기반 TCP calibration.** 금속 PIN TIP을 고정점으로 사용한 8-pose pivot calibration과 pose별 residual.
- **그림 5. 기존 PIN TCP와 실제 GRASP TCP의 차이.** 동일 endpoint에서 PIN TIP, gripper-origin proxy 및 coarse GRASP opening center 후보의 위치 차이.
- **그림 6. 비전 기반 C pre-approach 실제 이동 결과.** Load-relief coupling과 Wrist delay 적용에 따른 경로 개선 및 `WRIST_DELAY_25` pre-approach 도달 결과.

- **표 1. Table–Robot calibration 오차.** P1–P4 fit 오차와 H1, Repeat P1, Repeat P3 검증 오차.
- **표 2. Pivot TCP calibration 결과.** PIN TIP offset, residual, condition number 및 제한된 Pose 8 hold-out 결과.
- **표 3. PIN TCP와 GRASP TCP 비교.** 기존 PIN endpoint의 frame-mixing 오차와 새 GRASP TCP position-only 후보 비교.
- **표 4. 로봇 경로 개선 실험 결과.** Stop-and-wait부터 staged coupling과 `WRIST_DELAY_25`까지의 실기·오프라인 결과.

## 10. 내부 근거 추적

| ID | source | 사용 내용 |
|---|---|---|
| V1 | `.local/c-red-pivot-tcp-table-20261011-s01/live_c_vision_ik_dry_run_current.json` | YOLO confidence/center, raw·corrected·reflected table XY, robot XY |
| V2 | `docs/sessions/2026-10-11-robot-fk-tcp-pivot-diagnostic.md`의 “HOLD 확인 뒤 live C vision/IK dry-run 복귀” | live frame SHA, ArUco ID 0–3, live source 상태 |
| C1 | `.local/c-red-pivot-tcp-table-20261011-s01/scale_corrected_reflected_table_robot_fit.json` | scale, reflection, rotation, translation, fit/H1/repeat 오차, transform matrix와 candidate 상태 |
| P1 | `.local/c-red-pivot-tcp-20261011/pivot_fit_08_poses.json` | 8-pose pivot offset/norm, RMS/max, rank, condition number |
| P2 | `docs/sessions/2026-10-11-robot-fk-tcp-pivot-diagnostic.md`의 “Pivot Pose 1–8 결과” | Pose 1–7 fit→Pose 8 hold-out와 방향 독립성 제한 |
| T1 | `docs/sessions/2026-10-12-c-approach-tcp-frame-diagnostic.md`의 1–4절 | physical point, current IK TCP 경로, approach endpoint FK와 거리 |
| T2 | `docs/sessions/2026-10-12-c-approach-tcp-frame-diagnostic.md`의 “첨부 사진 기반 axis mapping 정정과 coarse grasp TCP 후보” | 축 대응, PIN→GRASP/GRASP TCP 후보, 보정 전·후 거리, 검증 제한 |
| R1 | `docs/STATUS.md`의 “C pre-approach 중단 후 follower HOLD 상태 정정”; `docs/sessions/2026-10-11-robot-fk-tcp-pivot-diagnostic.md`의 stop-and-wait 기록 | 초기 `2.830°`, 54-waypoint `1.733°` final timeout |
| R2 | `docs/STATUS.md`의 “continuous-following 실기 1회”; 원격 원본 `/tmp/live-c-approach-20261011/results/live_c_pre_approach_continuous_attempt1.jsonl` | waypoint 14 Elbow stall |
| R3 | `docs/sessions/2026-10-11-robot-fk-tcp-pivot-diagnostic.md`의 “A_MINIMAL staged live 시도” | start gate fail-closed, send 0 |
| R4 | `.local/c-red-pivot-tcp-table-20261011-s01/live_c_pre_approach_staged_fresh2_attempt1.jsonl` | A2_MINIMAL waypoint 26 telemetry |
| R5 | `.local/c-red-pivot-tcp-table-20261011-s01/live_c_pre_approach_strong_unload_fresh3_attempt1.jsonl` | LIFT_NEG50 waypoint 34 telemetry |
| R6 | `.local/c-red-pivot-tcp-table-20261011-s01/live_c_pre_approach_coupled_final_fresh4_attempt1.jsonl` | BALANCED_COUPLED waypoint 15 telemetry |
| R7 | `docs/sessions/2026-10-11-robot-fk-tcp-pivot-diagnostic.md`의 “fresh5 delayed-Wrist coupled path dry-run” | Wrist delay 25/35/45% 비교와 WRIST_DELAY_25 선택 |
| R8 | `.local/c-red-pivot-tcp-table-20261011-s01/live_c_pre_approach_delayed_wrist_fresh5_attempt1.jsonl`; `docs/STATUS.md`의 “WRIST_DELAY_25 실기” | 71/71 telemetry, final errors/load, `PRE_APPROACH_PASS`와 현장 종료 제한 |

## 검증 상태 요약

- 이 문서 작성 중 신규 카메라 수신, SSH, serial bus 접근, motor command, Goal/Torque write, service restart는 수행하지 않았다.
- Table–Robot transform: `CANDIDATE_SINGLE_DIGIT_WITH_APPROXIMATE_SCALE_MEASUREMENT`; `robot_enabled=false`, `motion_authorized=false`. [C1]
- Pivot fit: `DIAGNOSTIC_ONLY`; physical meaning은 현장 절차에 따라 PIN TIP으로 식별. [P1], [T1]
- 새 GRASP TCP: coarse candidate; orientation/collision/최종 실측 정밀도 `NOT_VERIFIED`, 실제 적용 `NOT_RUN`. [T2]
- `PRE_APPROACH_PASS`는 기존 PIN 기반 pre-approach endpoint의 관절 tolerance 통과를 뜻하며, 실제 grasp/lift 성공을 뜻하지 않는다. [R8]
- 문서 변경 상태: `NOT_COMMITTED/NOT_PUSHED`.
