# 현재 시스템과 ArUco 진행 현황

최신 확인: 2026-10-05 Asia/Seoul

2026-10-05 업데이트: LeLab 8000을 복구해 텔레옵·녹화·추론 비활성을 확인했다. 기존 8000 정면·사선 MJPEG를 재사용하는 임시 읽기 전용 YOLO/ArUco 시험에서 약통 후보 3개와 ID0–3, 바구니 마커를 표시했다. 정면 밝기 균등화는 현 장면의 불안정한 ID4 인식을 개선했다. 기존 8020 서비스는 Astra 브리지와 충돌하므로 시작하지 않았고, 새 입력 코드는 저장소에만 있다. 자세한 최신 게이트는 [상태](STATUS.md)와 [당일 세션](sessions/2026-10-05-waypoint-capture-review.md)에 기록한다. 자동 투입은 World→Base 등록·Elbow 한계 정합·연속 적재 경로 검증 전까지 승인되지 않았다.

2026-09-30 재확인: Jetson은 다시 연결됐다. 현재 바구니는 정면 화면 왼쪽 ID5(초록), 가운데 ID6(파랑), 오른쪽 ID4(빨강)이며 ID↔색상 매핑은 유효하다. 약통·바구니가 teach용 X 6점을 가려 기존 World 점 좌표가 유지됐는지 `UNVERIFIED_TEACH_LAYOUT`이다. 자세한 결과는 `docs/sessions/2026-09-30-jetson-resume-scene-audit.md`에 있다.

이 문서는 실제 약품이 아닌 빈 약통/모형을 고정 작업대에서 검출·분류하는 연구용 프로토타입의 현재 구성을 요약한다. Jetson은 2026-09-29에 offline이었고 2026-09-30에 SSH·LeLab·카메라 연결을 재확인했다. 아래 보정 품질과 실험 결과는 각 날짜의 기록을 따른다.

## 전체 구성

```text
Orbbec Astra 천장 정면 RGB-D
  → ArUco ID0–3 작업대 좌표
  → YOLO 약통 검출
  → pixel 중심을 table XY로 dry-run 투영

RealSense D435 천장 사선 color
  → 작업 상황·가림 보조 확인

Generic USB 엔드이펙터 카메라
  → 손목 근접 시야·LeLab 녹화 입력

World table coordinate
  → T_B_W (아직 미검증)
  → grasp offset + workspace limit (아직 미검증)
  → 별도 안전 승인 후에만 실제 이동
```

## 카메라: 물리적으로 3대

| 카메라 | 물리 역할 | 실제 입력·사용 경로 | 현재 판정 |
|---|---|---|---|
| Orbbec Astra `2bc5:0401` | 천장 정면, 주 좌표계·YOLO·RGB-D | OpenNI2 `/opt/orbbec-openni2`, RGB888 640×480, DEPTH_1_MM | RGB intrinsic RMS 0.478 px, 2.5D 300-frame 안정성 통과 |
| Intel RealSense D435 `8086:0b07`, serial `236223023645` | 천장 사선 보조 시야 | V4L2 YUYV color 640×480, canonical by-id | 8020 보조 프리뷰; 주 작업대 좌표 소스는 아님 |
| Generic USB Camera `0bda:5844` | 팔로워 엔드이펙터/손목 | V4L2, 재열거 시 node는 변경 가능 | LeLab 3-camera 녹화·근접 확인용; 8020 표준 화면에서는 제외 |

`/dev/videoN`은 USB 재열거로 바뀌 수 있다. 재접속 후에는 by-id·USB serial·실제 frame을 다시 대조한다. RealSense의 color/IR/depth node는 서로 다른 물리 카메라로 세지 않는다.

## ArUco: 운영 마커 7개

Dictionary는 모두 `DICT_4X4_50`이다.

| ID | 개수 | 역할 | 크기·주의 |
|---|---:|---|---|
| 0–3 | 4 | 고정 작업대 기준점, homography와 table XY | ID0 검은면 75 mm, ID1–3은 70 mm로 실측. 중심 위치를 임의로 옮기지 않음 |
| 4 | 1 | 빨강 바구니 | 평평한 무광 흰 받침과 quiet zone 유지 |
| 5 | 1 | 초록 바구니 | 동일 |
| 6 | 1 | 파랑 바구니 | 동일 |

ChArUco 보드의 ID10–33은 카메라 intrinsic 보정용 임시 마커이다. 운영 작업대에 남겨 두지 않고 위 7개에 포함하지 않는다. Robot Base teach에 사용한 검은 X 6개도 ArUco가 아니라 접촉 기준점이다.

## ArUco로 진행한 과정

1. ID0–3을 인쇄·실측하고 작업대 모서리에 고정했다.
2. ChArUco 6×8, square 30 mm, marker 22 mm 보드로 Astra color intrinsic을 수집했다. 28개 view 정제 결과는 RMS 0.478 px이다.
3. ID0–3 중심 실측값으로 pixel→table homography를 만들고 정지 300-frame jitter를 검사했다.
4. ID4–6을 바구니 인식용으로 추가하고 `4=red`, `5=green`, `6=blue`로 고정했다.
5. Astra registered depth와 ID0–3 평면을 사용한 2.5D dry-run에서 기준점 높이는 약 ±1.51 mm, 바구니 XY 표준편차는 축별 최대 0.358 mm, 높이 표준편차는 최대 0.624 mm였다. 이는 카메라 안정성이지 로봇 절대 정확도가 아니다.
6. YOLO11n 스모크 모델을 ONNX로 export해 Astra live에서 약통 bbox와 table XY를 8020에 표시했다. `robot_enabled=false`, `robot_target_authorized=false`를 유지한다.
7. Robot Base 등록용 4점 teach는 RMSE 5.780 mm, max 6.694 mm, condition number 5887.5로 허용 기준을 넘어 거부했다. 이 transform은 실제 이동에 사용하지 않는다.
8. 새로운 닫힌 fingertip TCP와 신규 6점을 준비했지만 Jetson offline으로 teach 수집은 일시 중단됐다.

## 현재 로봇·USB 역할

| 역할 | stable serial path | 2026-09-28 최신 열거 node |
|---|---|---|
| Leader | `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6085272-if00` | `/dev/ttyACM1` |
| Follower | `/dev/serial/by-id/usb-1a86_USB_Single_Serial_5AE6058306-if00` | `/dev/ttyACM0` |

raw ACM 번호를 영구 식별자로 사용하지 않는다. teach 중 관절값은 LeLab이 이미 방송하는 `/ws/joint-data`만 읽고, 같은 bus를 다시 여는 `/joint-positions`는 사용하지 않는다.

## 2026-09-30 당시 teach 계획 (현재 적용하지 않음)

1. Jetson 복귀 후 8000/8020과 canonical USB를 읽기 전용으로 재확인한다.
2. 테레옵·녹화·추론이 모두 inactive인 상태에서 현장 안전을 확인한다.
3. 리더 명령으로만 그리퍼를 닫아 두 fingertip이 만나는 점을 단일 TCP로 고정한다. 손으로 억지로 닫지 않는다.
4. 현재 배치의 P1–P6 전체에서 `/ws/joint-data` 15개씩만 수집한다. 이전 4점 sample은 좌표가 변했으므로 재사용하지 않는다.
5. P6 후 테레옵을 종료하고 Follower ID1–6 torque 0을 확인한다.
6. 실제 URDF FK로 TCP+`T_B_W`를 fit한다. RMSE ≤5 mm, max ≤8 mm, condition number ≤1000을 모두 만족하지 못하면 계속 `robot_enabled=false`로 남긴다.
7. fit 통과 후에도 즉시 집기를 시작하지 않고, high-Z dry-run·workspace limit·STOP을 별도 검증한다.

VLM은 환부 판독의 보조 제안까지만 담당한다. 약품 확정과 로봇 구동은 사람 또는 검증된 규칙을 거친다.
