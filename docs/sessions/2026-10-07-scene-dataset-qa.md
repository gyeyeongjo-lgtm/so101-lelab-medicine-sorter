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
- 사용자 확인 큰 A 장면의 정면 캐시 JPEG 한 장과 SHA·단일 프레임 한계를 Git 제외 `.local/medicine-class-scenes/20261007_A_source.*`에 복사했다. 이는 클래스 예시 1개일 뿐 분류기 학습/평가 자료로 충분하지 않다. 사용자에게 텔레옵이 꺼진 상태로 같은 자리에 중간 B, 이후 작은 C를 각각 바꿔 놓도록 요청해 현 장면 예시를 수집한다. 이 교체는 사람이 직접 수행하며 에이전트는 모터·USB·LeLab 설정을 건드리지 않는다.

## Jetson 기존 LeRobot 자료 검수

- 실제 설치 LeLab Python 3.14.7, PyArrow 25.0.1, PyAV 15.1.0을 확인하고 로컬 캐시의 `meta/info.json`, `meta/tasks.parquet`, 에피소드 인덱스와 첫 에피소드 정면 AV1 영상만 읽었다. 데이터셋·모델 파일은 수정하지 않았다.
- A v2(2026-10-02): 60 episode/32,597 frame; B v1(2026-09-28): 60/27,613; C test(2026-09-28): 60/28,966. 모두 메타상 30fps·세 영상 채널·한 task. task 문구는 각각 `Pick up medicine bottle X and place it into basket X.`이며 바구니 색·ID는 없다. 메타 숫자만으로 180회 모두 성공하거나 현재 장면과 호환된다고 보지 않는다.
- 각 dataset의 첫 episode 시작·끝 정면 프레임을 추출해 종료 시 병 위치와 `DICT_4X4_50` 바구니 마커 중심을 교차 확인했다. A 첫 시연은 오른쪽 ID6에 병이 남음. B 첫 시연은 가운데 ID6에 병이 남음. C 첫 시연은 왼쪽 ID5에 병이 남음. 해당 시연의 바구니 좌우 배치는 서로 달라 좌우 이름은 목표를 규정하지 않는다.
- 같은 설치 ONNX 약통 검출기를 이 6장에 오프라인 실행하면 A 시작·끝은 각 0개, B는 3/3개, C는 3/3개 후보를 출력한다. A 영상의 강한 자홍색 조명 등 장면 차이로 보이지만 원인을 분리 검증하지 않았고 일반 성능 수치가 아니다. 현재 A 사진은 1개(confidence 0.968962) 검출됐다. 과거 자료 전체에 현재 한 클래스 검출기를 바로 적용할 수 있다고 가정하지 않는다.
- 오늘 규칙에 A 첫 시연은 일치, B/C 첫 시연은 각각 ID6 vs 목표 ID5, ID5 vs 목표 ID4로 불일치한다. 따라서 기존 B/C 데이터셋과 대응 ACT 체크포인트의 현재 분류 경로 직접 사용은 `REJECTED`. 나머지 59회씩과 모델 행동은 `NOT_VERIFIED`. 자동 추론·모터 시험 `NOT_RUN`.

## 다음 게이트

### B 배치 보고 후 카메라 재확인

- 사용자에게서 `B 배치완료` 보고를 받았다. Jetson 8000의 teleoperation/recording/inference는 모두 active=false, Mac 8030의 세 카메라 오류 null·`robot_control=false`였다. 녹화 내부 `current_phase=preparing`, `session_ended=false`는 세션 종료 증거로 취급하지 않는다.
- 새 정면 캐시 JPEG에서 이전 A 출발 자리(화면 약 x=442,y=224)의 약통이 그대로 있고, 화면 약 x=375,y=231에 다른 약통이 추가됐다. 화면 왼쪽에도 약통이 보인다. B가 추가된 약통인지는 사용자 보고 외에 독립 확인이 없으며, A와 동일 자리의 단독 B 비교 자료가 아니다.
- 이 장면은 `.local/medicine-class-scenes/20261007_B_multibottle_unverified.jpg`에 원본 SHA-256 `85f62fe5a8600740b18fe64e98a5095a8354b6a4cdc7b8ed73407c095f99fc90` 및 제한 메타데이터와 함께 Git 제외로 보존했다. B 학습 샘플 승인·검출기 재학습·로봇 동작은 `NOT_RUN`. 사용자에게 텔레옵을 끈 채 B 하나만 기존 A 자리에 두는 재배치를 요청한다.

### B 단독 출발 자리 재배치 후 재촬영

- 사용자 `B 단독 배치 완료` 확인 후 Jetson 8000의 텔레옵·녹화·추론 active=false와 Mac 8030의 세 영상 수신 오류 null·`robot_control=false`를 읽기 전용으로 재확인했다. 녹화 내부의 `current_phase=preparing`, `session_ended=false`는 완료로 간주하지 않는다.
- 정면 캐시 한 장에서 이전 A 자리인 화면 약 x=440,y=228에 약통 하나만 보이고, 나머지 약통은 화면 왼쪽으로 치워져 있다. ID0–6은 육안으로 보이나 이번 장면의 자동 마커 재검출 및 용기 검출은 `NOT_RUN`. 한 개가 B라는 신원은 사용자 확인이고 영상만의 독립 분류 결과가 아니다.
- `.local/medicine-class-scenes/20261007_B_source.jpg` SHA-256 `571db2c17f78f3134fdfc2be1071957ae757ddb5ae3ff29d211a735d4f19b748` 및 제한 메타데이터를 Git 제외로 보존했다. A/B 각 한 장은 분류기 학습·성능 평가에 충분하지 않으며 픽업 ROI와 로봇 좌표/경로 문제도 해결하지 않는다. 로봇 동작·자동 추론·분류기 학습 `NOT_RUN`. 다음은 텔레옵을 끈 채 사용자에게 C 한 개를 같은 자리에 놓도록 요청한다.
- 후속 A/B 기존 ONNX 검출기 비교는 `NOT_RUN`: Mac 기본/번들 Python에 OpenCV가 없고, Jetson 키 기반 비대화형 SSH는 인증 거부됐다. 기존 로컬 askpass 경유 SSH도 이번 시도에서 응답을 완료하지 않아 작업자가 해당 시도를 중단했다. 비밀번호를 명령줄·출력·Git에 쓰지 않았고 원격 설정·파일·모터 작업은 수행하지 않았다. LeLab 8000과 Mac 8030 읽기 전용 상태 조회는 별도로 성공했다.

첫째, A/B/C 각 자료의 에피소드별 실제 목표 마커와 성공 여부를 전수 검수해 유효 부분만 분리한다. 둘째, 현재 고정 출발 슬롯과 ROI를 카메라 여러 장·높이 확인으로 다시 정의한다. 셋째, World→Base/TCP, Elbow URDF/캘리브레이션 차이, 연속 경로 여유를 별도 검증한다. 이 전에는 어떤 기존 ACT 모델도 현재 장면에 실행하지 않는다. 원본 데이터셋·영상·비밀번호는 Git에 넣지 않는다.

이번 문서 점검 관련 분류·비전 단위 테스트는 5+9개 `PASS`. 종료 전 LeLab teleoperation/recording/inference active=false를 다시 확인했다. GitHub CLI 로그인 부재로 이슈 API 갱신은 `NOT_RUN`; 코드·문서의 커밋과 push 상태는 Git 이력으로 별도 확인한다.
