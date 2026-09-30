# 2026-09-30 Jetson 재연결과 6점 teach 전 장면 감사

## 범위

- Mac에서 기존 확인된 SSH host key로 `jetson3@192.168.50.20`에 접속했다.
- 로봇 모터·토크·USB·전원·캘리브레이션·시스템 서비스를 변경하지 않았다.
- LeLab API, 서비스/USB metadata, 기존 카메라 preview, 저장된 ONNX 모델로 읽기 전용 검사만 했다.

## Jetson·LeLab 상태

- `PASS`: Jetson SSH 22와 LeLab `/health`가 응답했다.
- `PASS`: `/teleoperation-status`, `/recording-status`, `/inference-status`는 모두 active=false였다.
- `NOT_VERIFIED`: Follower ID1–6 torque register는 직접 읽지 않았다. inactive 표시만으로 torque 0을 단정하지 않는다.
- `PASS`: canonical by-id는 Leader `5AE6085272`→ACM1, Follower `5AE6058306`→ACM0였고 저장된 `so-101.json`의 leader/follower port는 각각 ACM1/ACM0였다.
- `PASS`: 저장 camera record는 ceiling_vertical index 8, ceiling_oblique index 4, end_effector index 6으로 3대다.
- `OBSERVED`: Astra→V4L2 bridge는 active, 8020 YOLO preview는 inactive다. LeLab 8000의 `/camera-preview/8`과 `/camera-preview/4`는 실제 MJPEG 프레임을 반환했다. 이 소유권 상태는 변경하지 않았다.
- `OBSERVED`: recording status에 2026-09-28에 시작된 다른 3-camera session 이름이 남아 있었다. 실제 저장 데이터 무결성은 이 점검 범위에서 `NOT_VERIFIED`다.

## 현재 장면의 camera-only 검사

- Astra 정면 640×480 프레임에서 ArUco `DICT_4X4_50` ID0–6이 모두 검출됐다.
- 기존 `best.onnx`를 저장 프레임에만 실행해 약통 모형 3개의 bbox/confidence 0.873369, 0.722266, 0.540081을 얻었다.
- 기존 ID0–3 중심 homography로 bbox 중심을 작업대 평면에 투영한 값은 약 `(255.2,254.6)`, `(81.3,262.6)`, `(174.6,249.3)` mm다. 물체 높이와 카메라-로봇 변환이 미보정이므로 로봇 목표가 아니다.
- 바구니 마커의 영상 좌우 순서는 ID5·ID6·ID4였다. 사선 영상의 실제 색은 초록·파랑·빨강이어서 기존 ID↔색상 매핑과 일치했다. 정면 Astra의 보라색 tint만으로 색을 해석하지 않는다.
- 단일 프레임 검사는 300-frame 안정성이나 실제 약품 식별을 의미하지 않는다.

## teach 재개 판정

- `UNVERIFIED_TEACH_LAYOUT`: 약통 3개와 바구니 3개가 2026-09-28의 검은 X 6점을 가려 중심 위치 유지 여부를 확인할 수 없다. 그때의 P1–P6 world 좌표는 재검증 전 현재 로봇 calibration에 재사용하지 않는다.
- 이전 fixed-Jaw 4점 fit은 RMSE 5.780 mm, condition number 5887.5로 거부된 상태다. `T_B_W`와 TCP를 실제 이동에 사용하지 않는다.
- `NEXT`: 사용자가 작업대의 약통·바구니를 잠시 치우고 X 6개를 다시 노출하면 새 정면 프레임에서 marker ID0–3과 X 6개를 확인한 뒤 World 좌표를 재추출한다. 그 다음 현장 안전 확인 범위에서 닫힌 fingertip TCP의 P1–P6 teach를 진행한다.

## 실패·제한

- 첫 SSH key-only 시도는 password 인증이 필요해 실패했으며, 기존 대화에서 승인된 SSH 인증으로 접속했다.
- 첫 robot-record 구조 출력은 `leader_config`를 dict로 가정해 `AttributeError`를 냈다. 실제 설치 파일의 schema에 맞춰 `leader_port`/`follower_port`만 다시 읽어 확인했다. 설정 변경은 없었다.
- 사선 MJPEG의 첫 프레임은 녹색 초기화 화면이었다. 같은 수신 구간의 후속 프레임에서 실제 장면을 확인했다.
- browser automation은 LAN 프리뷰 URL을 `ERR_BLOCKED_BY_CLIENT`로 차단했다. 기존 HTTP 프레임을 읽어 offline으로 영상과 ID를 확인했다.

Git commit/push: `c83f537`을 `origin/fix/usb-recording`에 push 완료. 이 문장의 결과 기록은 후속 문서 커밋에 포함한다.
