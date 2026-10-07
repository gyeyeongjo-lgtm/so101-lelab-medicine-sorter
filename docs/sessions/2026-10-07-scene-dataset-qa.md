# 2026-10-07 배치 후 현장·기존 데이터셋 검수

목적: 사용자가 큰 빈 약통 A를 출발 자리에 놓고 파란 바구니를 비운 뒤, 추가 모터 조작 없이 현재 카메라 장면과 기존 A/B/C 시연 자료가 오늘의 분류 규칙에 맞는지 확인한다. 사용자 확정 규칙은 A→파란 ID6, B→초록 ID5, C→빨강 ID4다.

## 예상 밖 텔레옵 시작과 즉시 중단

- 사전 상태: Jetson LeLab 8000 health `ok`, teleoperation/recording/inference 모두 active=false. 기존 robot 설정은 leader ACM1, follower ACM0, 카메라 8/4/6이다.
- LeLab 홈의 `Teleoperation` 버튼을 녹화 화면으로 가는 탐색 버튼으로 잘못 판단해 클릭했다. 실제 UI는 텔레옵을 즉시 시작하고 `/teleoperation-status`가 active=true를 반환했다. 사용자의 이번 승인 범위에는 모터 시작이 없었다.
- 즉시 공식 `POST /stop-teleoperation` 1회 성공 응답을 받고 다시 세 상태를 조회해 모두 active=false를 확인했다. 녹화는 active=false지만 내부 `current_phase=preparing`, `session_ended=false`이므로 완결된 세션으로 보지 않는다.
- 사용자 현장 확인: 예상 밖 팔 움직임·약통/바구니 접촉 없고 현재 안전하다. 영상만으로 물리 무동작을 독립 확정하지 않는다. 오류를 숨기지 않으며 해당 버튼은 단순 페이지 탐색에 재사용하지 않는다. 이후 새 텔레옵/녹화/추론/자동 재생 `NOT_RUN`.

## 현재 배치의 읽기 전용 카메라 검사

- 기존 Mac 8030 캐시 서버 상태: 정면/사선/손목 frame age 약 59.7/60.8/58.3 ms, 오류 null, `robot_control=false`, 텔레옵 중단 후 관절값 stale. 새로운 카메라 장치를 열지 않았다.
- 정면 캐시 JPEG 한 장을 Jetson 임시 폴더로 복사해 기존 ONNX 스모크 모델에 입력했다. Jetson 설치 검출 스크립트 SHA-256 `ad800e27...f2b9f53`는 저장소 원본과 같고 설치 LeLab Python의 OpenCV는 4.13.0이다. 약통 한 후보 confidence 0.968962, bbox `[421.569,206.586,456.775,257.626]` 픽셀이다. 모델은 용기 한 클래스만 검출하며 A/B/C 신원은 사용자 확인이다.
- 정면 프레임에서 ID0–6 전부 검출. 현재 ID4/5/6은 정면 화면 왼쪽/가운데/오른쪽이고 사선 영상에서 해당 바구니가 빨강/초록/파랑임을 확인했다. 정면 RGB 색감은 강하게 변해 육안 색만으로는 분류하지 않는다.
- 현재 작업대 평면 투영의 후보 중심은 `[83.245,335.484]` mm, 현행 픽업 ROI는 x=101–273, y=251–379 mm이다. 단일 후보가 ROI 밖이라 inside count=0. 기존 경로 결정기는 A 입력에 `BLOCKED/pickup_candidate_not_unique`, target=null, robot/motion=false를 반환한다. 이는 현행 ROI와 배치 불일치의 진단이지 사용자가 잘못 놓았다는 판정이 아니며, 높이 미보정 좌표를 모터 명령에 사용하지 않는다.

## Jetson 기존 LeRobot 자료 검수

- 실제 설치 LeLab Python 3.14.7, PyArrow 25.0.1, PyAV 15.1.0을 확인하고 로컬 캐시의 `meta/info.json`, `meta/tasks.parquet`, 에피소드 인덱스와 첫 에피소드 정면 AV1 영상만 읽었다. 데이터셋·모델 파일은 수정하지 않았다.
- A v2(2026-10-02): 60 episode/32,597 frame; B v1(2026-09-28): 60/27,613; C test(2026-09-28): 60/28,966. 모두 메타상 30fps·세 영상 채널·한 task. task 문구는 각각 `Pick up medicine bottle X and place it into basket X.`이며 바구니 색·ID는 없다. 메타 숫자만으로 180회 모두 성공하거나 현재 장면과 호환된다고 보지 않는다.
- 각 dataset의 첫 episode 시작·끝 정면 프레임을 추출해 종료 시 병 위치와 `DICT_4X4_50` 바구니 마커 중심을 교차 확인했다. A 첫 시연은 오른쪽 ID6에 병이 남음. B 첫 시연은 가운데 ID6에 병이 남음. C 첫 시연은 왼쪽 ID5에 병이 남음. 해당 시연의 바구니 좌우 배치는 서로 달라 좌우 이름은 목표를 규정하지 않는다.
- 같은 설치 ONNX 약통 검출기를 이 6장에 오프라인 실행하면 A 시작·끝은 각 0개, B는 3/3개, C는 3/3개 후보를 출력한다. A 영상의 강한 자홍색 조명 등 장면 차이로 보이지만 원인을 분리 검증하지 않았고 일반 성능 수치가 아니다. 현재 A 사진은 1개(confidence 0.968962) 검출됐다. 과거 자료 전체에 현재 한 클래스 검출기를 바로 적용할 수 있다고 가정하지 않는다.
- 오늘 규칙에 A 첫 시연은 일치, B/C 첫 시연은 각각 ID6 vs 목표 ID5, ID5 vs 목표 ID4로 불일치한다. 따라서 기존 B/C 데이터셋과 대응 ACT 체크포인트의 현재 분류 경로 직접 사용은 `REJECTED`. 나머지 59회씩과 모델 행동은 `NOT_VERIFIED`. 자동 추론·모터 시험 `NOT_RUN`.

## 다음 게이트

첫째, A/B/C 각 자료의 에피소드별 실제 목표 마커와 성공 여부를 전수 검수해 유효 부분만 분리한다. 둘째, 현재 고정 출발 슬롯과 ROI를 카메라 여러 장·높이 확인으로 다시 정의한다. 셋째, World→Base/TCP, Elbow URDF/캘리브레이션 차이, 연속 경로 여유를 별도 검증한다. 이 전에는 어떤 기존 ACT 모델도 현재 장면에 실행하지 않는다. 원본 데이터셋·영상·비밀번호는 Git에 넣지 않는다.

이번 문서 점검 관련 분류·비전 단위 테스트는 5+9개 `PASS`. 종료 전 LeLab teleoperation/recording/inference active=false를 다시 확인했다. GitHub CLI 로그인 부재로 이슈 API 갱신은 `NOT_RUN`; 코드·문서의 커밋과 push 상태는 Git 이력으로 별도 확인한다.
