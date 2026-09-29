# 2026-09-23 약통 bootstrap 반복성 확인

## 범위

- 전날 세 번째 자세가 유지된 상태에서 camera-only RGB-D 재촬영을 수행한다.
- robot serial, torque, teleoperation, recording, inference, motion command는 사용하지 않는다.
- 중복 표본을 무조건 늘리지 않고 좌표·높이 반복성을 먼저 판정한다.

## 결과

- 시작 전 LeLab health 정상, preview active, teleoperation·recording·inference inactive였다.
- 전날 pose 3과 오늘 첫 촬영 비교:
  - table XY `(169.861,250.251)` → `(173.242,269.322)` mm
  - XY 거리 19.368 mm, 높이 차이 1.280 mm
  - reference ID0–3 pixel 이동은 최대 1.275 px
- 날짜 사이 약통이 조금 이동한 것으로 보고, 현재 상태에서 즉시 한 번 더 촬영했다.
- 오늘 연속 두 촬영 비교:
  - table XY `(173.242,269.322)` → `(173.137,270.249)` mm
  - XY 차이 0.933 mm
  - pixel 중심 차이 0.154 px
  - 높이 `94.652` → `95.501` mm, 차이 0.849 mm
- 최종 30-frame run은 ID0–6, homography, depth pose 모두 30/30, reference plane RMS
  1.230 mm였다.

## 판정

- `PASS`: 정지한 현재 자세의 camera-only 2.5D 선택 반복성.
- `SKIPPED`: 두 반복 frame은 위치 다양성이 거의 없는 중복이므로 YOLO bootstrap images에는
  추가하지 않는다.
- `LIMIT`: 현재 검증 표본은 여전히 두 위치뿐이며 약품 종류 분류나 grasp pose 검증이 아니다.
- `NEXT (physical)`: 약통만 네 번째 비가림 위치로 옮겨 새로운 표본을 추가한다.

## 네 번째 자세 첫 시도

- capture와 foreground 추출은 성공했다.
- 실제 약통과 일치하는 C4는 bbox `(137,115,20,23)` px, table
  `(232.956,240.492)` mm, 높이 중앙값 94.707 mm였다.
- pickup ROI X=80–220 mm를 12.956 mm 벗어났고 화면상 ID6 바구니 marker에도 가까웠다.
- `PASS (fail-closed)`: `selected_candidate=null`로 유지되어 YOLO label/export가 생성되지 않았다.
- ROI를 관측값에 맞춰 임의 확장하지 않는다. 약통만 프리뷰 기준 오른쪽 약 3 cm, 위쪽 약
  3 cm 이동해 ROI 안쪽과 바구니에서 떨어뜨린 뒤 재시도한다.

## 네 번째 자세 재시도와 부분 조각 방어

- 조정 뒤 약통 전체 후보 C4는 bbox `(152,96,14,14)` px, table
  `(198.975,315.094)` mm, 높이 94.575 mm였다. ROI Y 최대 300 mm를 15.094 mm 벗어났다.
- ROI 안에 남은 작은 하단 조각 C5는 bbox `(157,113,6,7)` px, area 35 px, table
  `(194.054,267.188)` mm, 높이 43.765 mm였고 기존 largest-in-ROI 규칙이 이를 선택했다.
- `REJECTED`: RGB overlay에서 C5가 약통 전체가 아님을 확인해 image/label/metadata를 저장하지 않았다.
- bootstrap selector에 whole-object gate를 추가했다.
  - area 100–500 px
  - median height 70–120 mm
  - ROI와 위 조건을 모두 통과해야 선택
- 강화 필터를 같은 실패 snapshot에 적용하면 `selected_candidate=null`이고, 기존 정상 pose 2/3은
  각각 원래 table 좌표로 계속 선택됐다.
- 로컬 전체 camera-only 검사 21개가 통과했다. 최초 실행은 test assertion 배치 오류로 1건
  실패했고 테스트 코드를 바로잡은 뒤 21/21 통과했다.
- Jetson 설치 script/config SHA-256은 각각 `af39ecc4e7373153e6943dbf52e650b2e2f995e61d0c7f90d0a467d7c489e189`,
  `ce43a0d02263d6eae506c4037442560c63c37a2eb855b8744e5b525f1ce6d9e1`이다.
- `NEXT (physical)`: 약통만 프리뷰 기준 아래쪽으로 약 2 cm 옮겨 전체 중심을 ROI Y≤300 mm로
  넣은 뒤 다시 촬영한다.

## 네 번째 자세 최종 통과

- 강화된 whole-object gate가 선택한 C3:
  - bbox `(149,110,15,15)` px, area 175 px
  - centroid `(156.120,117.229)` px
  - table XY `(204.641,263.851)` mm
  - 높이 중앙값 95.672 mm, 최대 99.035 mm
- reference plane RMS는 0.704 mm였다.
- 기존 pose 002/003과의 XY 거리는 각각 124.760/37.344 mm로 중복 기준을 충분히 벗어났다.
- overlay에서 C3가 실제 흰색 약통 전체와 일치하는 것을 확인했다.
- `/home/jetson3/so101-medicine-bootstrap/`에 `pose_004` image, label, metadata를 저장했다.
  label은 `0 0.48906250 0.48958333 0.05937500 0.07916667`이다.
- 현재 검토 통과 positive 표본은 pose 002, 003, 004 세 건이다.
- `NEXT (physical)`: 약통만 작업대 밖으로 치운 뒤 empty ROI에서 selector가 null인지 확인하고
  negative image와 빈 label을 준비한다.

## Empty ROI negative

- 약통을 작업대 촬영 영역 밖으로 치운 뒤 30-frame RGB-D와 foreground 후보를 검사했다.
- `selected_candidate=null`, reference plane RMS 0.905 mm였다.
- ROI 경계의 C8 `(182.099,200.999)` mm는 area 18 px, 높이 56.401 mm라 whole-object gate가
  정상적으로 거부했다.
- 영상에서 실제 약통이 없음을 확인하고 `empty_001.png`, 빈 `empty_001.txt`, metadata JSON을
  비 Git bootstrap 경로에 저장했다.
- dataset pair audit 결과 images/labels/metadata stem이 모두 일치하고 normalized label 값이
  0–1 범위였다. 현재 4표본: positive 3, negative 1.
- `NEXT (physical)`: 같은 약통을 다시 세워 수직축 방향과 위치가 다른 positive 표본을 추가한다.

## 수집 목표와 다섯 번째 자세 첫 시도

- 수동 bootstrap 1단계 목표는 positive 8, negative 2다. 이후 자동 수집 흐름으로 서로 다른
  실제 frame 50–100개를 준비하며 수동 확인을 수십 번 반복하지 않는다.
- 다섯 번째 촬영에서 실제 약통 전체 C3은 bbox `(194,111,15,13)` px, area 163 px,
  table `(73.479,263.292)` mm, 높이 95.914 mm였다.
- whole-object filter는 통과하지만 pickup ROI X 최소 80 mm를 6.521 mm 벗어나
  `selected_candidate=null`이었다. overlay에서 ID3과도 가까운 것을 확인했다.
- `PASS (fail-closed)`: pose 005 image/label/metadata는 생성하지 않았다.
- `NEXT (physical)`: 약통만 프리뷰 기준 왼쪽으로 약 2 cm 옮겨 ROI 안쪽과 ID3에서
  여유를 만든 뒤 재수집한다.

## 다섯 번째 자세 재시도 통과

- 선택 C4는 bbox `(180,114,16,13)` px, area 168 px, table `(111.516,252.533)` mm,
  높이 중앙값 95.539 mm, 최대 98.630 mm였다.
- 기존 pose 002/003/004와의 XY 거리는 각각 45.037/58.390/93.810 mm였다.
- overlay에서 실제 약통 전체와 일치해 `pose_005` image, label, metadata를 저장했다.
- label: `0 0.58750000 0.50208333 0.06250000 0.07083333`
- pair audit 결과 총 5표본, positive 4, negative 1, 세 폴더 stem 일치다.
- `NEXT (physical)`: 약통을 치우고 pen 등 명확한 비대상 물체를 pickup ROI에 평평하게 두어
  두 번째 hard negative를 수집한다.

## Hard negative 002와 class 범위

- 약통 없이 비원통형 물체를 둔 30-frame capture에서 `selected_candidate=null`, ROI 안의
  15 mm 이상 foreground 후보도 0개였다. reference plane RMS는 1.327 mm였다.
- 시각 확인에서 흰 원통형 약통은 없고 비대상 물체만 있으므로 `hardneg_002` image, 빈 label,
  metadata를 저장했다.
- pair audit 결과 총 6표본, positive 4, negative 2, 세 폴더 stem 일치다.
- 현재 class 0은 `white_medicine_bottle_model`로 한정한다. 상자·펜은 negative이며 실제 약품
  신원이나 모든 형태의 약품 용기를 뜻하지 않는다.
- `configs/medicine_bootstrap.example.json`에 class, 목표 수, review 정책, training 미준비 상태를
  기록했다.
- `NEXT (physical)`: 비대상 물체를 치우고 같은 흰 원통형 약통의 다른 위치·수직축 방향 positive를
  네 건 더 수집한다.

## 여섯 번째 자세 첫 시도

- 실제 약통 전체 C3은 bbox `(135,98,14,25)` px, area 215 px, table
  `(242.674,296.894)` mm, 높이 93.204 mm였다.
- overlay에서 수직축 방향 변화로 측면 외형이 이전 표본과 달라 유효한 다양성임을 확인했다.
- whole-object gate는 통과하지만 ROI X 최대 220 mm를 22.674 mm 벗어나 선택/저장을 차단했다.
- `NEXT (physical)`: 방향은 그대로 유지하고 약통만 프리뷰 기준 오른쪽 약 2 cm, 아래쪽 약
  1 cm 이동해 ROI 안쪽 여유를 만든 뒤 재수집한다.

## 여섯 번째 자세 재시도 통과

- 선택 C3은 bbox `(146,104,16,14)` px, area 182 px, table `(209.179,284.667)` mm,
  높이 중앙값 95.930 mm, 최대 97.959 mm였다.
- 기존 pose 002–005와 최소 XY 거리는 pose 004 대비 21.305 mm였다. 방향 변화 표본이며
  overlay에서 실제 약통 전체와 일치했다.
- `pose_006` image, label, metadata를 저장했다. label은
  `0 0.48125000 0.46250000 0.06250000 0.07500000`이다.
- pair audit 결과 총 7표본, positive 5, negative 2다.
- `NEXT (physical)`: 현재 방향을 유지하고 프리뷰 기준 오른쪽의 검증된 빈 공간으로 이동해
  여섯 번째 positive를 수집한다.

## 일곱 번째 자세 첫 시도

- 실제 약통 전체 C3은 bbox `(200,107,16,27)` px, area 257 px, table
  `(59.110,259.918)` mm, 높이 94.439 mm였다.
- ROI X 최소 80 mm를 20.890 mm 벗어났고 overlay에서 bottle 오른쪽 경계와 ID3 quiet zone
  사이 여유도 거의 없었다.
- `PASS (fail-closed)`: pose 007은 저장하지 않았다.
- `NEXT (physical)`: 방향과 세로 위치는 유지하고 프리뷰 기준 왼쪽으로 약 3 cm 옮겨 ROI 및
  ID3 여유를 확보한 뒤 재수집한다.

### 일곱 번째 자세 재시도: 그리퍼와 병합

- 조정 후 약통이 프리뷰 중앙의 로봇 그리퍼 바로 아래로 들어갔다.
- foreground에서 약통이 robot component C0 bbox `(169,32,30,95)` px에 연결되어 독립적인
  whole-object 후보가 생성되지 않았다. `selected_candidate=null`로 저장을 차단했다.
- `NEXT (physical)`: 방향과 세로 위치를 유지하고 약통만 프리뷰 기준 오른쪽으로 약통 한 병
  너비(약 4–5 cm) 옮겨 그리퍼와 ID3 사이 여유 공간에 둔 뒤 재수집한다.

### 일곱 번째 자세 재시도 2: 수평 여유 부족

- 오른쪽 조정 뒤에도 약통 상단과 그리퍼 하단이 영상에서 맞닿아 robot C0 bbox가
  `(169,32,40,93)` px로 확장됐다. 독립 whole-object 후보가 없어 `selected=null`이었다.
- 약통 오른쪽에는 ID3이 있어 수평 방향만으로는 그리퍼와 marker 양쪽 여백을 동시에 확보하기
  어렵다.
- `NEXT (physical)`: 현재 방향은 유지하고 약통을 프리뷰 기준 대각선 아래·왼쪽으로 각각 약
  3 cm 옮겨, 그리퍼 아래와 바구니 위 사이에 흰 바탕 여백이 보이게 한 뒤 재수집한다.

### 일곱 번째 자세 최종 통과

- 독립 선택 C3은 bbox `(183,109,15,24)` px, area 227 px, table
  `(108.202,259.417)` mm, 높이 중앙값 95.572 mm, 최대 99.788 mm였다.
- pose 005와 XY 거리는 7.640 mm로 가깝지만 bbox가 pose 005의 `16×13`과 달리 `15×24`여서
  수직축 방향 변화가 영상에 반영된 것을 overlay로 확인했다.
- `pose_007` image, label, metadata를 저장했다. label은
  `0 0.59531250 0.50416667 0.05937500 0.11666667`이다.
- pair audit 결과 총 8표본, positive 6, negative 2다.
- `NEXT (physical)`: 현재 위치는 그대로 유지하고 약통만 수직축 기준 약 90° 회전해 다음 방향
  표본을 수집한다.

## 여덟 번째 자세: 같은 위치에서 회전

- C3 bbox `(183,108,16,14)` px, area 180 px, table `(105.678,272.885)` mm,
  높이 중앙값 96.537 mm, 최대 98.685 mm였다.
- pose 007 대비 XY 이동량 13.702 mm이며 bbox가 `15×24`에서 `16×14`로 바뀌었다.
  overlay에서 그리퍼와 분리된 흰 약통 전체가 선택된 것을 확인했다.
- `pose_008` image, label, metadata를 저장했다. label은
  `0 0.59687500 0.47916667 0.06250000 0.07500000`이다.
- 파일 stem 검사 결과 총 9표본, positive 7, negative 2다.
- `NEXT (physical)`: 방향은 유지하고 약통을 다른 비가림 위치로 옮겨 positive 목표 8건을 채운다.

## pose 008 이후 Astra 프리뷰 장애

- pose 008의 30-frame RGB-D 수집은 성공했고 ID0–6, homography, depth pose가 모두 30/30이었다.
- 종료 점검에서 프리뷰 `/health`가 503이었다. Astra는 `ok=false`, RealSense는 `ok=true`다.
- 서비스 로그의 최초 오류는 15:05:25 `OpenNI color stream start failed`였고, 이후
  `Failed to send a USB control request`가 반복됐다. `lsusb`에는 Astra `2bc5:0401`이
  bus 001 device 006으로 계속 보인다.
- 카메라 프리뷰 service를 종료하고 소유 프로세스가 없음을 확인한 뒤 단독 재시작했지만
  Astra 프레임은 0이며 같은 USB control request 오류가 반복됐다. RealSense stream은 정상이다.
- LeLab teleoperation·recording·inference는 inactive였다. USB 재연결·reset, 전원,
  로봇 serial·torque·motor command는 실행하지 않았다.
- `BLOCKED`: Astra RGB-D가 열리지 않아 pose 009 촬영은 `NOT_RUN`이다. 현장 안전 확인과
  사용자 명시 승인 후 Astra 카메라 USB만 재연결할지 결정한다.
- `NOT_PUSHED`: 이번 변경 사항은 commit·push하지 않았다. GitHub issue 갱신은 `NOT_RUN`이다.

## Astra USB 재연결 후 복구 확인

- 사용자가 현장에서 Astra USB를 재연결했다고 보고했다. Mac에서 Jetson의 기존 검증 호스트 키 별칭으로 SSH 접속했다.
- 15:35–15:36 KST 프리뷰 `/health`는 HTTP 200이며 Astra·RealSense 모두 `ok=true`, frame 수가 증가했다. LeLab `/health`도 HTTP 200이었다.
- Jetson의 `so101-camera-preview.service`는 active이고, LeLab teleoperation·recording·inference API는 모두 inactive였다. 별도 RGB-D diagnostic/helper 프로세스는 없었다.
- 기존 dataset에는 image 9건(positive 7, negative 2)만 있으며 `pose_009`는 없다. USB 재연결 후 RGB-D 30-frame 촬영은 아직 `NOT_RUN`이다.
- 마지막 positive에는 기존 pose 008과 다른 위치가 필요해 약통만 4–5 cm 옮겨 marker·그리퍼와 분리해 달라고 요청했다. 물리 배치 완료 전까지 촬영/저장은 하지 않는다.
- 로봇 serial·torque·motor command, 전원·USB 추가 조작은 실행하지 않았다. `NOT_PUSHED`: 문서·코드는 commit/push하지 않았다.

## pose 009 첫 배치: 촬영 통과, 표본 저장 보류

- 사용자가 약통 이동 완료를 알린 뒤 preflight에서 Astra·RealSense 프리뷰 HTTP 200, LeLab teleoperation·recording·inference inactive를 확인했다.
- 프리뷰 서비스를 단독으로 중지한 뒤 camera-only 30-frame RGB-D를 수집하고 즉시 서비스를 복구했다. 첫 시도는 설치된 M2 RGB-D helper가 `--low-bandwidth`를 지원하지 않아 frame 0에서 종료됐고, 미배포 상태였던 검증된 `/tmp/orbbec-rgbd-pipe-v5`를 명시해 재시도했다.
- 재시도는 30 frames, ID0–6/homography/depth pose 모두 30/30, 기준 plane RMS 중앙값 1.266 mm였다. ID38이 한 frame에서 추가 검출돼 exact-count 30/30으로 주장하지 않는다.
- 최초 후보 추출은 `selected=null`이었다. 디버깅에서 입력 depth pixel `(155,110)`의 원래 Z=788 mm가 밀집 XYZ 생성 식에서 33.409 mm로 바뀌어 높이가 실제 약 95.3 mm 대신 678.8 mm로 계산되는 것을 확인했다. 카메라 문제가 아니라 Python/NumPy 배열 계산 경로의 오류다.
- `scripts/depth_foreground_candidates.py`의 XYZ 구성을 독립 출력 배열에 명시적으로 계산하도록 수정하고, 입력 Z 보존 단위 테스트를 추가했다. Jetson에서 관련 8/8 tests와 동일 snapshot의 선택 C3 bbox `(147,105,15,13)`, table `(212.145,283.742)` mm, 높이 중앙값 95.307 mm를 통과했다.
- 깊이 구멍으로 C3가 약통 상단만 감싸고 하단 C6 `(152,122,6,8)`과 분리됐다. 검토 박스 override 기능을 추가하고 포함관계 테스트를 통과했지만, 디버깅용 label만 `/tmp`에 만들었고 dataset에는 저장하지 않았다.
- 현재 XY는 `pose_006` `(209.179,284.667)`과 3.107 mm 차이로 거의 중복이며, RGB 화면 왼쪽에 정체 미확인 흰 원통형 물체도 나타났다. 미라벨 대상 가능성을 배제할 수 없어 이번 frame은 보류했다.
- 설치 전 스크립트 SHA-256 `af39ecc4...`를 `/home/jetson3/so101-recovery-backups/20260923T155000_foreground-z-fix/`에 보존한 뒤 수정본 `382679e6...`만 `/opt/so101-rgbd/depth_foreground_candidates.py`에 배포했다. 설치본으로 동일 snapshot 재검사에서 C3 선택을 확인했다.
- 사용자에게 왼쪽 흰 물체를 화면 밖으로 치우고 중앙 약통만 제자리에서 수직축 기준 약 90° 회전해 달라고 요청했다. `pose_009`는 `NOT_SAVED`이며 dataset 수는 positive 7/negative 2 그대로다.
- 종료 점검에서 preview service active, Astra·RealSense `ok=true`, 세 LeLab 제어 inactive였다. 로봇 동작·전원·USB 추가 조작 없음. `NOT_PUSHED`: Git commit/push 및 GitHub issue 갱신은 실행하지 않았다.

## pose 009 회전 재촬영과 10표본 구조 검증

- 사용자가 왼쪽 흰 물체 제거와 중앙 약통 90° 회전을 완료한 뒤 preflight에서 두 preview `ok=true`, LeLab teleoperation·recording·inference inactive를 확인했다.
- preview를 잠시 중지하고 검증된 `/tmp/orbbec-rgbd-pipe-v5 --low-bandwidth`로 30 frames를 수집했다. ID0–6, homography, depth pose 모두 30/30, 추가 ID 없음, 기준 plane RMS 중앙값 1.740 mm였다. 수집 직후 preview를 다시 시작했다.
- 수정된 설치본이 C3 bbox `(146,105,16,13)`, table `(212.800,282.508)` mm, 높이 중앙값 95.160 mm를 선택했다. 약통 아래 C4 `(153,121,6,9)`는 깊이 구멍으로 분리됐으므로 RGB 검토로 전체 bbox `(146,105,16,25)`를 사용했다. 뚜껑 인쇄 방향은 pose 006과 다르고, 왼쪽 미라벨 흰 물체는 새 frame에서 사라졌다.
- `pose_009` image/label/metadata를 dataset에 저장했다. label은 `0 0.48125000 0.48958333 0.06250000 0.12083333`이다. pair audit는 총 10표본(positive 8, negative 2), 동일 stem, 이미지 320×240, label 0–1 범위를 통과했다.

## 전체 프레임 라벨 검토와 ROI 전용 파생본

- 8개 양성의 원본 이미지와 YOLO box 접촉시트를 시각 검토했다. pose 002·006·008은 병 아래 부분이 명확히 빠져 있었고 003·004·005도 하단 여유가 부족했다. pose 007과 새 pose 009는 전체 약통을 감쌌다.
- `scripts/review_bootstrap_labels.py`를 추가해 원본 선택 depth box 포함관계, label 변환, dry-run, 원본 backup, 원자적 쓰기를 구현했다. 로컬 단위 테스트 2/2와 Jetson dry-run 및 수정안 접촉시트 검토를 통과했다.
- 기존 6건의 label/metadata를 `/home/jetson3/so101-medicine-bootstrap/review-backups/20260923_whole_bottle_bbox_review_v1/`에 보존하고 전체 약통 박스로 갱신했다. metadata의 `label_review_history`에 기존 pseudo-label을 보존했다. 적용 후 image/label/metadata 10쌍, positive 8/negative 2, normalized label과 metadata 값 일치가 통과했다.
- 단, 원본 전체 프레임의 `empty_001`·`hardneg_002`에는 작업 ROI 밖에 대상 약통이 보인다. 따라서 빈 label인 두 이미지는 **전체 프레임 YOLO 음성으로 사용할 수 없다**.
- `scripts/build_medicine_roi_dataset.py`와 변환 단위 테스트 3/3을 추가했다. 원본을 변경하지 않고 Jetson 비 Git 경로 `/home/jetson3/so101-medicine-bootstrap/roi-v1/`에 고정 crop `[128,85,215,140]` px(87×55) 파생본 10쌍을 생성했다. 8 positive box는 모두 crop 내부, 2 negative crop에는 대상 약통이 없음을 접촉시트에서 확인했다.
- ROI 파생본은 `training_ready=false`다. 영상이 작고 양성 8/음성 2에 불과하며 유사한 위치가 반복된다. 실제 YOLO 성능이나 약품 신원 식별을 주장하지 않는다. 다음은 물리적으로 다양한 위치·회전·조명에서 50–100개의 실제 ROI frame을 수집하고 사람 검토용 분할을 만드는 단계다.
- 최종 점검에서 preview service active, Astra·RealSense `ok=true`, LeLab health 정상, teleoperation·recording·inference inactive, 진단 helper 잔류 없음이다. 로봇 동작·토크·전원·USB 조작 없음. `NOT_PUSHED`: 코드·문서 commit/push와 GitHub issue 갱신은 실행하지 않았다.
- GitHub issue #4 동기화 전 읽기 전용 조회를 시도했으나 Mac `gh` 인증이 없어 중단됐다. `BLOCKED_AUTH`: 이슈는 수정하지 않았고 사용자 토큰을 요청·저장하지 않았다. `NOT_PUSHED`: 로컬 dirty 작업물은 커밋·푸시하지 않았다.

## 종료 상태

- preview service active, Astra·RealSense `ok=true`.
- LeLab teleoperation·recording·inference inactive.
- camera diagnostic helper 잔류 없음.
- `NOT_PUSHED`: 변경 사항을 commit·push하지 않았다.

## 프리뷰 기반 ROI 검토 대기 수집기 (후속)

- `scripts/collect_medicine_roi_review.py`를 추가했다. 기존 Astra MJPEG 프리뷰를 읽기만 하며 카메라 직접 점유, depth, LeLab 제어 또는 로봇 serial에 접근하지 않는다. ID0–3 기준 마커, 기준점 pixel 이동, 연속 frame 안정성, ROI 변화량을 검사해 검토 대기 image/context/manifest만 저장한다. YOLO label은 생성하지 않고 `training_ready=false`, `robot_enabled=false`로 기록한다.
- Mac 오프라인 단위 테스트 4/4와 문법 검사를 통과했다. Jetson 사용자 홈에 스크립트를 복사해 20초 camera-only smoke를 실행했다.
- 첫 15초 시험에서 원본 해상도 검출만 사용하자 기준 마커 누락 29/29로 후보가 0장이었다. 프리뷰 JPEG 한 장에서는 640 px에서 ID1·3·4·5·6, 2배 확대에서 ID0, 3배 확대에서 ID2가 추가로 검출됐다. 1·2·3배 검출 결과를 원본 pixel 좌표로 합치도록 수정했다.
- 수정 후 20초 시험에서 검사 38회 중 기준 marker 누락 10회, 위치 이동 초과 0회, 정지 중복 11회였고 검토 대기 후보 **1장**만 `/home/jetson3/so101-medicine-bootstrap/review-queue-20260923-smoke-02/`에 저장했다. 이미지 87×55 ROI와 320×240 context의 구조를 확인했다. 화면상 흰 약통은 ROI에 있지만 이 후보는 새 위치/자세의 독립 표본으로 확인되지 않았으므로 8+2 학습 후보 수에 합산하지 않는다.
- ID2는 프리뷰 JPEG 3배 확대 검사에서도 30 frame 중 22 frame만 검출됐다. 수집기는 누락 frame을 fail-closed로 버리며, ID2 흰 여백/반사/시야를 물리적으로 개선하기 전에는 장시간 자동 수집 품질을 보장하지 않는다. 기준점 중심을 이동시키거나 카메라를 재장착하지 않는다.
- 마지막 점검: 프리뷰 service active, Astra·RealSense `ok=true`, LeLab teleoperation·recording·inference 모두 inactive. 로봇 동작·토크·전원·USB 조작 없음. GitHub 이슈 갱신 `NOT_RUN`, Git commit/push `NOT_PUSHED`.
- `NEXT (physical)`: ID2 검은 marker 중심은 움직이지 말고 주변 흰 여백과 가림/반사를 개선한다. 이후 약통만 pickup ROI 안에서 마커·그리퍼와 떨어진 새 위치/회전으로 **몇 번 묶어서** 바꾸며 수집기를 실행한다. 결과는 사람이 전체 약통 bbox와 중복을 확인한 후에만 별도 학습/평가 분할에 넣는다.

## 사용자 준비 후 2분 연속 ROI 후보 수집

- 사용자에게 약통만 ROI 안에서 다른 위치/방향으로 옮기고 각 자세에서 약 3초 멈추도록 안내했다. 기준 보드·ID0–3·바구니·카메라는 그대로 뒀다.
- 시작 전 Astra·RealSense 프리뷰 `ok=true`, LeLab teleoperation·recording·inference inactive를 확인했다. `/home/jetson3/so101-medicine-bootstrap/review-queue-20260923-live-01/`에 120초, 최대 20장 조건으로 camera-only collector를 실행했다.
- 결과: decoded 3606 frame, 검사 228회, 기준 marker 누락 70회, marker shift 초과 0회, 불안정 99회, 중복 47회, 저장 후보 4장(1.1/45.5/94.6/113.0초). 네 후보 모두 ROI에 흰 약통이 보이며 context/ROI를 시각 확인했다. 단, 프리뷰 JPEG 기반이며 whole-object bbox·기존 8개와 독립성은 확정하지 않았다. 이 4장을 학습/평가 데이터 또는 positive 목표 수에 합산하지 않는다.
- 종료 뒤 Astra·RealSense 프리뷰 `ok=true`, LeLab teleoperation·recording·inference inactive를 재확인했다. 로봇, 토크, 전원, USB 조작 없음. `NOT_PUSHED`: Git commit/push 및 GitHub issue 갱신 없음.
- `NEXT`: 수집된 4장을 기존 8개와 대조해 전체 병 bbox/가림/중복을 사람 검토하고, 더 많은 위치·방향/조명 variation을 묶어서 수집한다. ID2 간헐 누락으로 인한 fail-closed 폐기율을 계속 기록한다.

## 이어서 3분 연속 수집과 ROI 경계 검토

- 같은 사용자 준비 범위에서 프리뷰를 유지한 채 `/home/jetson3/so101-medicine-bootstrap/review-queue-20260923-live-02/`에 180초, 최대 30장으로 한 번 더 수집했다.
- decoded 5408 frame, 검사 342회, 기준 marker 누락 147회, marker shift 초과 0회, 불안정 168회, 중복 10회, 검토 대기 후보 10장이다. JPEG 프리뷰에서 ID2 누락 비율이 높아 전체 frame 수를 표본 수로 간주하지 않는다.
- context와 ROI 확대 접촉시트를 시각 검토했다. 최초 검토에서는 candidate_001 오른쪽·007 위쪽·008 오른쪽 경계 실패를 판정했다. 이어서 개별 ROI를 재확인하니 **candidate_005도 아래쪽에서 약통 몸통이 잘림**이 확인됐다. 따라서 적어도 001·005·007·008 네 장은 전체 약통 YOLO positive에 사용하지 않는다. 나머지 6장은 ROI 내 약통 외형이 보이는 예비 후보이나 정확한 bbox, 기존 8개/첫 run 4개와의 중복, 독립 평가 분할은 아직 검토 전이다.
- 두 run 합계는 원본 검토 대기 후보 14장이고, 그중 최소 4장은 ROI crop 실패다. **유효 학습 표본 10장으로 확정한 것이 아니다.** 자동 label 생성, 학습, 로봇 제어는 실행하지 않았다.
- 추가 수집 종료 뒤 LeLab teleoperation·recording·inference가 모두 inactive이고 Astra·RealSense 프리뷰가 모두 `ok=true`임을 재확인했다. GitHub issue `NOT_RUN`, Git commit/push `NOT_PUSHED`.

## 무인 후속 검토와 원본 해상도 보존

- 14개 후보의 개별 ROI와 기존 8개 label 위치를 대조했다. 추가 run 후보 001은 오른쪽, 005는 아래쪽, 007은 위쪽, 008은 오른쪽에서 대상 외곽이 ROI 경계에 닿거나 잘린다. 네 건은 검토 목록에서 제외하며 원본 파일은 그대로 보존한다. 나머지 후보도 기존 표본 또는 서로 비슷한 pixel 위치가 있어 위치 차이만으로 독립 표본이라 판정하지 않았다.
- 원본 8개와 처음 14개 후보는 87×55 ROI로 이미 저장돼 있어 새로운 고해상도 정보를 복구할 수 없다. 이후 후보 수집기의 기존 320×240 context/87×55 ROI 저장을 유지하면서 **640×480 context와 174×110 ROI를 함께 저장**하도록 확장했다. 자동 YOLO label과 robot target은 계속 생성하지 않는다.
- Mac 수집기 단위 테스트 4/4와 문법 검사를 통과했다. Jetson 사용자 홈의 기존 수집기는 보존하고 별도 `collect_medicine_roi_review_v2.py`를 배포해 12초 camera-only smoke를 실행했다. 정지 장면 후보 1장만 저장됐고 87×55, 320×240, 174×110, 640×480 이미지 네 종류의 쌍과 manifest를 확인했다. smoke 후보는 학습 표본에 추가하지 않는다.
- 마지막 점검: Astra·RealSense 프리뷰 `ok=true`, LeLab teleoperation·recording·inference inactive. 로봇·토크·전원·USB 조작 없음. GitHub issue 갱신 `NOT_RUN`, Git commit/push `NOT_PUSHED`.
- `NEXT (physical)`: 새 해상도의 실제 다양성은 사람이 약통 위치/방향·조명 조건을 바꿔야 생긴다. 바구니와 기준 마커를 건드리지 않은 상태에서 다음 연속 수집을 진행하되, ROI 경계에서 병 전체가 충분히 떨어지도록 안내한다. 데이터 50–100장 및 별도 평가 분할 전까지 `training_ready=false`다.

## 고해상도 5분 연속 수집과 비파괴 ROI 품질 검사

- 사용자 `다음촬영시작` 확인 후 Astra·RealSense preview `ok=true`, LeLab teleoperation·recording·inference inactive를 확인했다. 사용자는 약통만 위치·방향을 바꿨고, 기준 보드·바구니·카메라 이동은 요청하지 않았다.
- v2 수집기를 `/home/jetson3/so101-medicine-bootstrap/review-queue-20260923-live-03/`에 300초, 최대 50장으로 실행했다. decoded 9014 frame, 검사 573회, 기준 marker 누락 182회, marker shift 초과 0회, 불안정 296회, 중복 24회, 저장 후보 31장이다. 각 후보는 87×55/174×110 ROI와 320×240/640×480 context가 있다.
- 31장 고해상도 ROI 접촉시트를 시각 확인했다. 병이 ROI 밖에 있거나 아래·오른쪽에서 잘리는 장면이 섞여 있어 31장을 유효 표본으로 간주하지 않는다.
- `scripts/audit_medicine_roi_capture.py`를 추가했다. 현재 보라색/흰색 빈 약통 **한 모델에만 적용하는** HSV 몸통 검출과 8 px ROI 경계 검사이며, 명백한 crop 실패만 거르고 통과한 장면을 자동 승인하지 않는다. 로컬 단위 테스트 3/3과 Jetson 31장 구조 검사가 통과했다.
- Jetson 비 Git queue 안 `roi-edge-screen-v1.json` 결과는 `reject_body_at_roi_edge=13`, `hold_no_purple_body=3`, `needs_human_review=15`다. 명백한 실패 원본은 삭제하지 않았다. 15장은 whole-object bbox·그리퍼 접촉·기존 표본과 중복을 추가 검토해야 한다. 몸통 중심 거리 10 px 미만의 가까운 쌍은 001/019, 003/008, 004/012, 007/011, 008/026, 018/029다. 가까운 위치가 곧 동일 자세를 뜻하지 않으므로 자동 삭제하지 않았다.
- `training_ready=false`, 생성된 새 YOLO label 0개, 독립 평가 분할 `NOT_RUN`, 학습 `NOT_RUN`, 로봇 동작 `NOT_RUN`이다. 다음은 15장 bbox 수동 검토와 추가 물리적 위치·방향 다양성 확보이며, 현재 정지 장면을 더 복제하지 않는다.
- 종료 점검에서 Astra·RealSense 프리뷰는 모두 `ok=true`, LeLab teleoperation·recording·inference는 모두 inactive였다. robot serial, torque, motor, USB, 전원은 건드리지 않았다. GitHub issue 갱신 `NOT_RUN`, Git commit/push `NOT_PUSHED`.

## 15장 약통 박스 제안 생성

- `scripts/propose_medicine_roi_boxes.py`와 단위 테스트 2/2를 추가했다. 1차 감사 결과 `needs_human_review`인 15장만 대상으로 보라색 몸통 bbox를 뚜껑·몸통 전체 후보로 확장하고, 174×110 ROI 위에 빨간 박스를 그린다. 이 단계는 overlay/proposals JSON만 만들며 YOLO label은 만들지 않는다.
- Jetson의 비 Git queue 하위 `bbox-proposals-v1/`에 15개 overlay와 `proposals.json`을 생성했다. 접촉시트를 시각 확인한 결과 박스는 대체로 병 전체를 포함하지만 004·012는 그리퍼 끝이 뚜껑에 접하고, 서로 가까운 위치의 후보도 있어 정답 라벨로 확정하지 않았다.
- `NEEDS_USER_REVIEW`: 박스와 그리퍼 접촉 후보를 사용자가 확인하거나 제외 방침을 정해야 후속 label export가 가능하다. 원본 31장, 1차 감사 JSON, 박스 제안은 모두 별도 보존했고 기존 검증 데이터셋은 변경하지 않았다. `training_ready=false`, 학습/로봇 구동 `NOT_RUN`.

## 임시 라벨 export와 전체 화면 후보 복구

- 사용자 `다음단계진행해` 및 재개 지시에 따라 004·012 그리퍼 접촉 후보를 제외하고, 기존 174×110 ROI 박스 제안 13장을 `/home/jetson3/so101-medicine-bootstrap/provisional-roi-v2/`로 별도 export했다. 원본 queue와 기존 8+2 dataset은 변경하지 않았다.
- 13장 image/label/metadata stem, 174×110 shape, class 0 normalized 값, `review_required=true`, `training_ready=false`, `medicine_identity_verified=false`, `robot_target=false`, exact duplicate 0을 확인했다. 가까운 네 쌍은 위치는 비슷하지만 뚜껑 방향/조명 차이가 보여 자동 삭제하지 않고 중복 검토 대상으로 남겼다.
- 좁은 ROI에서 잘린 후보도 원본 640×480 context에는 약통 전체가 남아 있음을 확인했다. `scripts/propose_medicine_fullframe_boxes.py`와 단위 테스트 3/3을 추가했고, 작업대 중앙 검색창에서 보라색 몸통 후보가 31장 모두 정확히 하나씩 검출됐다. 004·012를 제외한 29장 full-frame 박스 overlay/JSON을 비 Git queue의 `fullframe-bbox-proposals-v1/`에 생성했다.
- 29장 전체 화면 접촉시트를 육안 검사했다. 박스는 약통을 감싸고, 일부 frame의 손·휴대폰은 약통을 가리지 않아 배경 변화로 보존했다. 이는 사람/휴대폰 탐지 데이터가 아니며 의료 신원 확인도 아니다.
- 첫 전체 화면 export `/home/jetson3/so101-medicine-bootstrap/provisional-fullframe-v1/`은 image/label 자체 검사는 통과했지만 `dataset.json.scope`가 잘못 `pickup_roi_only`로 기록됐다. **이 v1은 사용 금지**이며 원인 기록을 위해 삭제하지 않았다.
- export 도구에 `--scope`, `--image-folder`, `--bbox-key`를 추가하고 기존 단위 테스트 2/2를 다시 통과했다. 새 `/home/jetson3/so101-medicine-bootstrap/provisional-fullframe-v2/`를 `scope=full_frame`으로 생성했다. 29장 stem 일치, 640×480 shape, normalized label 범위, metadata의 full-frame source와 모든 safety flag를 검증했다.
- v2도 `provisional_color_based_proposal`, `review_required=true`, `training_ready=false`다. 양성 29장은 한 촬영 세션이며 독립 평가 표본과 진짜 full-frame negative가 없다. 최소 50개의 다양한 양성·별도 평가 분할 전에는 학습하지 않는다. robot motion/inference `NOT_RUN`.

## 첫 full-frame empty negative

- 사용자가 약통을 화면 밖으로 치웠다고 확인했다. 시작 전 Astra·RealSense preview `ok=true`, LeLab teleoperation·recording·inference inactive를 확인하고 v2 수집기로 정지 frame 1장을 별도 queue에 저장했다. 기준 marker shift 초과 0회였고 약통 몸통 후보는 0개였다.
- 640×480 전체 화면을 직접 검토해 약통이 없고 ID0–6, 세 바구니, 정지 로봇팔이 보이며 손은 작업 영역 밖인 것을 확인했다.
- `scripts/export_medicine_fullframe_negative.py`와 단위 테스트 2/2를 추가했다. 대상 크기/위치의 보라색 몸통 후보가 하나라도 있으면 export를 차단한다.
- `/home/jetson3/so101-medicine-bootstrap/fullframe-negatives-v1/`에 `empty_fullframe_001` 이미지, 빈 label, metadata를 생성했다. 640×480 shape, empty label, `automatic_body_candidates=0`, `visually_reviewed_empty_negative`, `training_ready=false`, `robot_target=false`를 검증했다.
- 동일 정지 장면을 반복 저장하지 않는다. 다음 유효 negative는 약통 없이 펜·작은 상자·휴대폰 등 실제 비대상 물체가 pickup 영역에 있는 서로 다른 hard-negative 장면이다. 양성 29장은 여전히 임시 제안이며 학습/평가 분할/로봇 구동 `NOT_RUN`.

## 첫 full-frame hard negative

- 사용자가 비대상 물체 배치를 완료했다고 알린 뒤 같은 camera-only preflight를 통과했다. v2 수집기로 정지 frame 1장을 별도 queue에 저장했고 기준 marker shift 초과 0회, 대상 크기/위치의 보라색 약통 몸통 후보 0개였다.
- 전체 화면을 직접 확인했다. 흰 작업 영역 중앙에 작은 흰색 직사각형 비대상 물체가 하나 있고 약통과 손은 없으며 ID0–6과 바구니는 보인다.
- 기존 검증된 negative exporter로 `/home/jetson3/so101-medicine-bootstrap/fullframe-hardnegatives-v1/`에 `hardneg_fullframe_001` 640×480 이미지, 빈 label, metadata를 생성했다. shape, empty label, body candidates 0, `training_ready=false`, `robot_target=false`를 검증했다.
- 현재 진짜 full-frame 음성은 empty 1장과 hard negative 1장이다. 다음은 이 물체를 치우고 형태가 다른 펜 또는 휴대폰 한 개를 같은 구역에 둔 두 번째 hard negative다. 동일 물체의 정지 frame 복제는 하지 않는다.

## 두 번째 hard negative와 통합 후보셋

- 사용자가 두 번째 비대상 물체 배치를 완료한 뒤 camera-only preflight를 통과했다. 정지 frame 1장을 별도 queue에 저장했고 기준 marker shift 초과 0회, 약통 몸통 후보 0개였다.
- 전체 화면에는 흰 작업 영역 중앙의 펜 한 개만 있고 약통과 손은 없었다. `/home/jetson3/so101-medicine-bootstrap/fullframe-hardnegative-002/`에 `hardneg_fullframe_002` 640×480 이미지, 빈 label, metadata를 저장해 shape/label/safety flag를 검증했다.
- `scripts/merge_medicine_fullframe_candidates.py`와 단위 테스트 2/2를 추가했다. 입력 source의 640×480 shape, positive 단일 class-0 label, negative empty label, `training_ready=false`, `robot_target=false`, stem 충돌을 검사하고 원본을 수정하지 않는다.
- 양성 후보 29장, empty negative 1장, 흰 직사각형 hard negative 1장, 펜 hard negative 1장을 `/home/jetson3/so101-medicine-bootstrap/provisional-fullframe-combined-v1/`로 병합했다. 총 32장(positive proposal 29, reviewed negative 3), stem/pair/shape/count와 `training_ready=false`, `robot_enabled=false`를 검증했다.
- 이 통합본은 편의용 검토 데이터셋이지 학습 승인본이 아니다. 양성은 같은 촬영 세션의 색상 기반 임시 박스이고, 음성은 3장뿐이며 독립 평가 세트가 없다. 다음은 휴대폰 등 어두운 직사각형 hard negative와 21개 이상의 추가 다양한 양성이다.

## 휴대폰 hard negative와 통합 후보셋 v2

- 사용자가 휴대폰 배치를 완료한 뒤 Astra·RealSense preview `ok=true`, LeLab teleoperation·recording·inference inactive를 확인했다.
- 수집기 파일을 직접 실행한 첫 시도는 실행 권한 부족으로 `Permission denied`가 발생했다. 원본 파일과 권한을 변경하지 않고 설치된 Python으로 같은 명령을 재실행해 20초 동안 후보 1장을 저장했다. 검사 33회 중 기준 marker 누락 17회, marker shift 초과 0회였다.
- 640×480 frame을 직접 검토했다. 흰 작업 영역 중앙에는 어두운 직사각형 휴대폰 한 개만 있고 약통과 손은 없으며 ID0–6과 세 바구니가 보였다.
- `/home/jetson3/so101-medicine-bootstrap/fullframe-hardnegative-003/`에 `hardneg_fullframe_003` image, 빈 label, metadata를 저장했다. 자동 보라색 몸통 후보 0개, 640×480 shape, `training_ready=false`, `robot_target=false`를 확인했다.
- 기존 원본을 수정하지 않고 `/home/jetson3/so101-medicine-bootstrap/provisional-fullframe-combined-v2/`를 새로 생성했다. 총 33장(임시 양성 29, 검토 음성 4), image/label/metadata stem 일치, 전 이미지 640×480, `training_ready=false`, `robot_enabled=false` 검사가 통과했다.
- 종료 점검에서 두 preview는 정상이고 LeLab 세 제어는 inactive였다. 로봇·토크·전원·USB 조작 없음. 학습·추론·로봇 구동 `NOT_RUN`, GitHub issue 갱신 `NOT_RUN`, commit/push `NOT_PUSHED`다.
- `NEXT (physical)`: 휴대폰을 치우고 흰 약통 모형 하나만 작업 영역의 기존과 다른 위치·방향에 배치한다. 기준 보드·마커·바구니·카메라·로봇은 고정한다. 이후 최소 21개의 다양한 양성과 별도 평가 표본을 확보한다.

## 추가 양성 자세 01 중복 검사

- 새 배치에서 camera-only 20초 수집으로 640×480 후보 1장을 저장했다. 검사 19회 중 기준 marker 누락 9회, marker shift 초과 0회였다.
- 육안상 약통 전체, ID0–6, 세 바구니가 보이고 손은 없었다. full-frame 색상 박스 제안은 `[374,234,31,41]`, 중심은 `(389.5,254.5)` px였다.
- 기존 임시 양성 29장과 비교하니 가장 가까운 `candidate_027`의 박스 `[373,238,32,40]`과 중심 거리가 3.54 px였다. 두 frame 모두 약통의 위치·방향이 사실상 같아 새 표본을 임시 양성으로 export하지 않았다. 기존 양성 29, 검토 음성 4를 유지한다.
- 기존 중심 분포에서 비교적 빈 안전 후보는 약 `(460,255)` px였다. 다음에는 현재 위치에서 프리뷰 기준 오른쪽으로 약통 폭 약 2개 옮기되 ID1과 접촉하지 않고, 뚜껑 방향도 약 90° 바꾼다.
- 종료 점검에서 두 preview 정상, LeLab teleoperation·recording·inference inactive였다. 학습·추론·로봇 구동 `NOT_RUN`, commit/push `NOT_PUSHED`다.
