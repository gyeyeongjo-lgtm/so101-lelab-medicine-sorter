# 2026-10-08 회전 바구니 ID5 마커 좌표 의미 점검

## 장면 비교

- 사용자가 초록 바구니를 긴 축이 정면 영상의 상하에서 좌우로 바뀌게 재배치했다. 재배치 전후 정면 JPEG 한 장씩을 로봇 제어 없이 검사했다. 동일한 작업대 ID0–3 기준과 8031의 설치 카메라 투영을 사용했다.
- ID5 **마커 중심의 테이블 평면 투영값**은 이전 `[192.966, 133.179]` mm, 회전 뒤 `[111.030, 230.299]` mm였다. 차이는 `[-81.936, +97.120]` mm, 평면 벡터 길이는 약 127.1 mm다. 바구니 몸체의 실제 중심 이동은 이 숫자로 계산할 수 없다. ID5는 바구니 신원 표식이며 바구니 입구 중심이나 목표 자세가 아니다. 더욱이 마커 높이는 테이블 평면과 다르므로 homography 투영은 높이 보정이 아니다.
- 별도 **탐색용 영상 분석**에서 중앙 ROI의 갈색 HSV 성분 최대 연결 요소를 잡으면 회전 전 몸체 bbox `(336,259,72,103)` px, 회전 후 `(322,260,103,75)` px로 긴 축 교체와 일치했다. 이 bbox 중심을 같은 테이블 평면에 투영한 값은 약 `[189.56,197.05]`→`[187.13,221.48]` mm로, ID5 이동 127.1 mm와 분명히 다르다. 하지만 ROI/HSV 임계값은 이 두 영상에서만 탐색했으며 조명·가림·다른 바구니에 대한 독립 검증이 없다. 몸체 표면의 높이·안쪽 입구 중심도 보정되지 않아 이 값을 로봇 목표로 쓰지 않는다.
- 첫 분석 호출은 `medicine_yolo_web`의 형제 모듈 import 경로가 없어 실패했고, `scripts`를 명시한 뒤 재실행했다. 두 번째 호출은 잘못된 `aruco_table.local.json` 구성 파일을 전달해 `markers` 키 오류가 났고, 실제 8031과 같은 `astra_rgbd.example.json`으로 재실행해 위 값을 얻었다. 실패 출력을 숫자 근거로 사용하지 않았다.

## 코드·런타임

- 8031 정면 상태의 각 `basket_markers[id]`에 `point_semantics=marker_center_projected_to_table_plane_not_basket_center`, `basket_center_table_xy_mm=null`, `basket_pose_verified=false`를 추가했다. 최상위 `basket_pose_authorized=false`와 높이 미보정 설명도 추가했다. 고정 슬롯 명령 미리보기 역시 `basket_pose_authorized=false`와 마커 ID가 바구니 중심이 아니라는 경고를 반환한다. 기존 목적지 색/ID·사진 저장·로봇 비활성 플래그는 유지한다.
- 합성 마커 투영 회귀 검사와 고정 슬롯 검사 20개를 통과했다. 새 검사 첫 실행은 합성 테스트에 영상 shape가 없어 실패했고 640×480 더미 영상을 제공해 수정했다. 프로젝트 가상환경과 시스템 환경에 의존성이 나뉘어 전체 회귀는 [캘리브레이션 기록](2026-10-08-calibration-trace-envelope-offline.md)에 적은 대로 각각 검증했다.
- LeLab `/teleoperation-status` inactive 확인 후 Mac의 기존 정확한 8031 PID와 명령·cwd·카메라 입력·수동 저장 옵션을 읽었다. 그 프로세스만 종료했다. 첫 `nohup` 백그라운드 재시작은 포트 listener가 생기지 않았고 로그도 비어 있어 실패로 기록한다. 동일 옵션을 유지한 전경 세션으로 재시작했고 `/health`에서 `ok=true`, 신선한 정면/사선, ID0–3/5, 새 의미 필드, `robot_enabled=false`, `manual_capture_enabled=true`를 확인했다. 8000·8030·Jetson 서비스·USB·모터·토크·캘리브레이션은 변경하지 않았다.
- 실제 바구니 중심·yaw·높이 보정·그리퍼 외접 여유는 `NOT_VERIFIED`; 자동 이동·재생 `NOT_RUN`. 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`.
