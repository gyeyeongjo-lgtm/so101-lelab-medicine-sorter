# 2026-10-09 C→빨강 전체 텔레옵 시연

## 2026-10-10 후속: 모델 한계와 서보 캘리브레이션 분리

- LeLab OFF 읽기 전용 fresh follower `(Pan −7.604, Lift −100.000, Elbow +96.308, Flex +50.066, Roll −20.000)°`를 재측정했다. Elbow는 URDF 밖이지만 설치 follower calibration SHA `2f74c130...e29c2e`의 raw 880–3087(약 ±97.011°) 안이다. 리더 Pan/Flex/Roll 불일치 `+7.736/−7.516/+13.143°`; viewer 종료, 모터·토크 명령 0회. 파일상의 서보 범위는 물리 안전 증명이 아니다.
- 읽기 전용 5점 캡처는 URDF 밖 feedback도 FK 계산하고 모델 불일치 경고만 저장한다. fixed safe_start IK seed를 제거하고 관측 시작 5축을 요구한다. 별도 자율 planning limit의 2° reserve 수치 후보는 `PENDING_PHYSICAL_VALIDATION`이라 자동 IK에서 거부한다. 관련 로컬 시험 33/33 PASS.
- Jetson 기존 Elbow guard SHA `2e5ffa30...0118362`를 백업한 뒤 실제 servo calibration 동적 범위 guard SHA `1ca311d0...7204b09`를 설치했다. 설치 Python fake test PASS, LeLab health ok/teleop inactive/포트 해제. 그러나 `LELAB_TEMP_WRIST_ALIGN=1` 환경이 없어 새 guard는 실행 경로에서 **비활성**. 해당 지속 설정 요청은 auto-review가 거부해 우회하지 않고 정확한 사용자 승인 대기. 텔레옵·5점 이동 `NOT_RUN`.
- 8034 천장 수신기가 LeLab 재시작 뒤 stale였으나 8000 MJPEG는 살아 있었다. 읽기 전용 수신기만 재시작하고 기존 P1–P4/H1 등록 파일을 보존·재등록했다. fresh camera age 1.6 ms, 등록 5/5, 캡처 0/5, rigid TCP 미설정. 원본 로그·비밀정보 Git 제외, 이슈 API `NOT_RUN`, `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-10 후속: 5점 현장 캡처 안전 게이트

- live 천장 영상 수신기에서 X 표시 P1–P4/H1을 등록했으나 실제 캡처는 `0/5`. 로봇 제어 기능은 없다. 사용자가 C와 바구니를 작업대 밖으로 치웠고, 손목 롤 축 중심을 볼 수 있을 것 같다고 답했다. 물리 TCP 위치·offset과 빨강 입구 독립 측정은 아직 미검증이다.
- LeLab OFF·읽기 전용 Jetson 관절 화면에서 follower Elbow `+90.330°`가 다시 확인됐다(URDF 상한 `+90°`). 이 값은 이번 fresh 읽기이며, 리더도 follower와 크게 다르다. 안전 복구 없이 LeLab/teleop·5점 포즈 이동·실제 approach를 진행하지 않는다. 읽기 viewer 종료 메시지 `ports_released=True` 확인. 모터/토크 명령 `NOT_RUN`; fit/hold-out/실측 IK `NOT_RUN`, 변경 `NOT_COMMITTED/NOT_PUSHED`.
- 사용자의 텔레옵 복구 요청 후 현장 정지·비접촉 답변을 받았다. 8000 health 정상, 제어 작업 세 종류 inactive. 로컬 guard 가짜 시험 10/10 PASS; 현재 `feedback_outside_urdf`는 기존 의도된 hard failure여서 동일 상태의 UI 시작으로 해소되지 않는다. 서비스/가드/URDF를 변경하거나 시작을 재시도하지 않았으며, 현장 복귀 범위가 정해지기 전 모터·토크 조작 `NOT_RUN`.
- 새 manual-recovery 요청에 따라 정상 guard 불변·상한 밖 +1° 이내에서 내부 +89° 부근 한 번만 송신하는 로컬 후보와 설치본 대상 패치를 만들었다. 다른 다섯 축 fresh 위치 고정, 기존 follower torque/config toggle 회피, 2° 시작 정렬, 정상 시 20 ms loop. 로컬 가짜 시험 13/13·원본 SHA 대상 `patch --dry-run --fuzz=0`·문법 PASS. 설치/서비스 반영과 live `NOT_RUN`.
- 원격 LeLab OFF·포트 무점유에서 쓰기/토크 API 차단 읽기 전용 진단을 두 번 했다. 두 번째 raw `(2015,817,3079,2650,1637,774)`와 degree `(−7.604,−100.000,+96.308,+50.066,−20.000°, gripper 22.093%)`가 첫 읽기와 일치했다. 여섯 축 torque register는 모두 1. `Goal_Position` 읽기는 전 축 0에 해당하는 값으로 나타나 현재 목표 확인 근거로 쓰지 않았고 로컬 후보 패치의 그 비교는 안정된 fresh feedback 두 번 검사로 교체했다. 사용자가 앞선 +90.330° 이후 팔로워를 직접 움직였다고 확인했다. 현재 +96.308°에서는 내부 +90°까지 6.308°라 2° step으로는 첫 유효 목표를 만들 수 없다. 현장 정지·비접촉 보고 유지, 추가 구동/설치 패치/5점 캡처 `NOT_RUN/BLOCKED`.

## 2026-10-10 후속: live 카메라와 좌표 blocker 재점검

- 카메라 USB `2bc5:0401`/`/dev/astra`와 V4L2 `/dev/video8`는 존재했다. 8000·8002 정면 MJPEG는 6초간 0 byte였고 8000 서버 로그의 V4L2 `select() timeout`, 8002 장치 open 및 실행 중인 OpenNI→GStreamer 브리지를 확인했다. 두 LeLab의 세 제어 작업이 모두 inactive임을 확인한 뒤 브리지 한 서비스만 재시작해 정면 MJPEG를 양쪽에서 6초당 약 8.4–8.5 MB 수신했다. 최초 프레임 정지 시각과 OpenNI 내부 원인은 미확인이다. LeLab 서비스·로봇 포트·토크·모터·카메라 설정은 불변이다.
- 복구된 live 정면 프레임 두 장에서 ArUco ID0–6과 table homography가 준비됐지만 YOLO bbox는 0개였다. C가 작업대에 없으므로 C pixel/table XY는 `BLOCKED`; 다른 저장 프레임의 C 좌표를 live 결과로 쓰지 않는다. 세 번째 신규 MJPEG 연결은 첫 frame 전에 종료돼 연결 안정성도 추가 확인이 필요하다.
- 기존 외부 파라미터/베이스 마커/hand-eye/teach 자료에는 승인된 table→robot/TCP 변환이 없고, 성공 place 기록은 같은 시각의 ID4·입구 table XY를 담지 않는다. 기존 거부 변환과 빨강 입구 후보 offset은 여전히 `DIAGNOSTIC_ONLY`. 독립 4 fit점+1 hold-out점, 검증 TCP 및 빨강 입구 중심 한 점 전에는 실측 robot XY·IK/URDF dry-run을 출력하지 않는다. 실제 접근 `NOT_RUN/BLOCKED`, 코드·trajectory·calibration·URDF·replay 변경 없음, `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-10 후속: vision-guided 4개 blocker만 점검

1. **A/B/C 신원:** YOLO 한 클래스의 bbox 중심을 기존 ArUco ID0–3 작업대 homography로 투영하고 81개 보존된 검수 프레임의 A/B/C 슬롯 중심 median에 최근접 배정한다. 좌표는 각각 `(76.557,351.317)/(179.722,336.457)/(289.600,327.939) mm`; 거리 ≤45 mm와 2순위 격차 ≥25 mm를 요구한다. 저장 C 프레임 `(318.757,239.599) px→(289.666,331.112) mm→C`, 거리 3.174 mm. 81/81 재판정은 같은 프레임으로 중심을 만들었으므로 in-sample이다. Runtime은 사람 라벨을 읽지 않는다.
2. **작업대→로봇:** 기존 P1–P6 teach의 TCP 미검증 및 hold-out 오차 9.932 mm를 재확인했다. 성공 텔레옵 107,422주기에는 동시 카메라/마커 좌표가 없어 2D 대응점이 아니다. 옛 거부 `T_B_W` 사용을 코드에서 제거했다. 새 2D fit은 검증 TCP offset과 네 모서리처럼 분산된 4개 접촉점, 별도 중앙 hold-out 1개, 각 접촉/영상-관절 동기를 요구한다. fit RMS 5 mm·max 8 mm·hold-out max 8 mm 이내가 아니면 robot XY/IK는 비운다. 현재 5개 유효점과 TCP offset은 `NOT_AVAILABLE`.
3. **빨강 입구:** 저장된 빈 정면 프레임의 육안 입구 중심 `(313,290) px`와 ID4 중심 `(307.5,346) px`의 homography 차이는 `(-2.269,+98.737) mm`. 이는 높이가 다른 두 표면의 2D 투영 및 시각 추정이라 `DIAGNOSTIC_OFFSET_ONLY`; 성공 place 관절만으로 바구니 입구의 table XY를 검증할 수 없다. ID4→입구 중심 독립 1회 측정이 남는다.
4. **IK/카메라:** 새 읽기 전용 경로는 검증 XY가 제공되면 C approach/grasp/lift, 빨강 hover/place의 위치 IK·FK 잔차·URDF 여유를 순서대로 계산한다. 가짜 XY와 실제 설치 URDF SHA 모델의 5단계 수치 시험은 통과했지만 이는 물체/경로 검증이 아니다. 저장 프레임은 신원·작업대 좌표까지만 PASS, robot XY/실측 5단계 IK/URDF는 `NOT_RUN`. LeLab 8000·8002의 천장 `/camera-preview/8`은 HTTP 200 MJPEG 응답 뒤 8초간 프레임 0바이트, 새 live CLI는 timeout. 서비스 재시작/카메라 설정 변경 없음. 관련 36/36 시험 통과, 모터·토크·USB·replay 변경 `NOT_RUN`; 마지막 follower Elbow +90.330° URDF 밖이라 live 접근 금지. `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-10 방향 전환: 비전→IK 진단 경로

사용자의 새 최종 목표는 고정 trajectory가 아닌 YOLO→ArUco→C 작업대 좌표→IK→C→빨강이다. 기존 replay는 참고/fallback으로만 남기고 수정하지 않았다. 기존 `medicine_yolo_web.TableMapper`가 이미 ID0–3 중심으로 픽셀→작업대 평면 homography를 계산한다. ID4는 빨강 바구니 마커이며 입구 중심이 아니다. YOLO 출력 클래스는 `white_medicine_bottle_model` 하나라 C 신원은 저장 프레임의 사람 라벨과 임시 고정 슬롯으로만 추정한다.

새 `scripts/c_red_vision_ik_dry_run.py`는 저장된 C 이미지 SHA/라벨, 마커 완전성, URDF SHA를 확인한 뒤 읽기 전용 위치 IK만 계산한다. 설치 URDF와 같은 SHA `443d38d7...f67236`의 FK를 사용한다. 사람 확인 저장 프레임 한 장의 C 검출은 confidence `0.836797`, 중심 `(318.757,239.599) px`, 작업대 `(289.666,331.112) mm`, ID0–6 검출이었다. 기존 pickup ROI에는 들지 않는다. Mac 8030은 연결되지 않아 실시간 카메라 시험은 `NOT_RUN`.

거부된 World→Base/TCP 변환과 임시 높이 `Z_SAFE/APPROACH/GRASP/LIFT/PLACE=(100/80/50/100/80) mm`를 명시한 **진단 모드**의 위치 IK에서 approach/grasp/lift 잔차 `0.233/0.947/0.097 mm`, 최소 예약 URDF 여유 `45.318°`; `numeric_dry_run=APPROACH_GRASP_LIFT_PASS`와 별개로 `motion_authorized=false`다. 그 진단 옵션이 없는 기본 실행은 joint target 없이 exit 2로 차단한다. 위치만 풀었고 방향, swept path, 충돌, 잡힘, 바구니 입구/놓기 pose는 풀지 않았다. 거부된 변환은 실기 목표로 사용하지 않는다. C 라벨-SHA 불일치·마커 누락·투영 누락·IK 실패 테스트를 포함해 관련 32/32 PASS, 문법 및 `git diff --check` PASS.

실기 안전 차단: 마지막 fresh follower Elbow `+90.330°`는 URDF 상한 `+90°` 초과, World→Base/TCP fit 거부, Z/그리퍼 방향 미검증, 빨강 입구 중심/경로 미검증. 따라서 현장 재확인/승인 이전에도 자동 approach는 불가하며 이번에는 Jetson·USB·모터·토크를 건드리지 않았다. `NOT_COMMITTED/NOT_PUSHED`; 저장 프레임과 원본 로그는 Git 제외.

## 현장 부재 야간 오프라인 준비 — physical run 금지

사용자가 퇴근해 현장에 없음을 명시했다. 이 절의 변경과 시험은 Mac의 로컬 파일·가짜 버스·기존 기록만 사용했다. LeLab start, USB serial open, 토크/Goal_Position, 실제 팔 움직임, 자동 live 송신은 모두 `NOT_RUN/BLOCKED_FOR_PHYSICAL_RUN`이다. 마지막 follower `(+19.297, −42.769, +86.989, −31.165, +3.824)°`는 이전 읽기 결과이며 내일 fresh 상태가 아니다.

### 한시 Elbow 방향 보호

- 설치 대상 `teleoperate.py`의 기존 `elbow_start_deg + 0.5` 고정 차단을 추적했다. 설치 SHA로 마지막 확인된 값은 `a5ac255d15cbba05d0c095ec927106c303ef50790291566fb29f383cb8102576`이다. 로컬 [패치](../../patches/lelab-20261009/teleoperate-directional-elbow-guard.patch)와 [순수 보호 모듈](../../scripts/temporary_elbow_direction_guard.py)은 상한 +90°/하한 −100° 방향 차단, 한계 쪽 +0.5° 제한, 한계 안쪽 2° reserve, 연속 목표 간 최대 2°를 적용한다. 클리핑하지 않으며 URDF 밖 현재값/목표를 차단한다. 차단 전에 관절명, current, requested target, delta, lower/upper margin, toward/away 방향, reason을 남긴다.
- 가짜 버스와 순수 판정 9/9 PASS. `+86.99→+87.8` 차단, `+86.99→+86.0` 허용, 1° 안팎 연속 감소로 +32.44까지 허용, 바로 +80으로 6.99° 점프는 차단, +90 초과와 하한 대칭 차단, 비-Elbow action 불변이다. 패치 hunk 형식 오류를 고쳤고 로컬 parser가 4개 hunk를 읽었다. 단, Jetson 실제 `patch --dry-run`은 원격 인증 부재로 **NOT_RUN**. 설치 소스·서비스는 그대로다.
- 기존 설치 보정은 매 텔레옵 시작 시 `elbow_offset = follower_start_elbow - first_leader_elbow`, `wrist_offset = follower_start_flex - first_leader_flex`로 새로 계산한다. Elbow 절댓값 3.5°와 Wrist 15°는 cap이며 고정 가산값이 아니다. 과거 +2.945°/+2.417°는 한 정렬 순간의 값일 뿐 내일 보정값 확정 근거가 아니다.

### 내일 safe_start 목표표

| 관절 | follower safe_start | 텔레옵 보정 | leader-side 목표 | 예상 follower 명령 |
|---|---:|---:|---:|---:|
| Pan | +11.736° | 없음 | +11.736° | +11.736° |
| Lift | −22.330° | 없음 | −22.330° | −22.330° |
| Elbow | +32.440° | 시작시 측정 `E` (절댓값 ≤3.5°) | `+32.440° − E` | +32.440° |
| Wrist Flex | +5.538° | 시작시 측정 `W` (절댓값 ≤15°) | `+5.538° − W` | +5.538° |
| Wrist Roll | −20.396° | 없음 | −20.396° | −20.396° |
| Gripper | 3.446% | 없음 | 3.446% | 3.446% |

과거 값 `E=+2.945°`, `W=+2.417°`가 **다시 실측된 경우에만** Elbow leader 목표 +29.495°, Flex +3.121°다. `+3.5°` 자체를 목표 보정으로 사용하면 안 된다. 내일 fresh E/W 없이는 “정확한 단일 리더 수치”가 존재하지 않는다. 첫 명령은 follower 현재값에 맞도록 계산되며 실제 도착 판정은 leader 숫자가 아니라 fresh follower 방송/종료 후 read-only 실측으로 한다.
fresh 정렬값 네 개를 얻으면 [오프라인 계산기](../../scripts/safe_start_leader_targets.py)의 `--leader-elbow`, `--follower-elbow`, `--leader-flex`, `--follower-flex`에 입력해 그 세션의 리더 목표를 출력할 수 있다. 프로그램은 보정 cap을 확인하지만 USB·LeLab에 접속하거나 모션을 승인하지 않는다(2/2 시험 PASS).

### approach 회귀·진단 로그

- 기존 4배 `safe_start→approach` 후보 640 targets/nominal 269.000초, URDF 최소 팔 여유 7.582°를 로컬 dry-run으로 재확인. settle·scheduler rebase·exclusive bus 포함 관련 23+10개 테스트 PASS. 안전 판정·scheduler·trajectory·calibration·time-scale·URDF는 변경하지 않았다.
- [replay 파일](../../scripts/replay_c_red_approach.py)에 target index/seq, nominal interval, rebased deadline, send 호출/반환, feedback 읽기 시작/끝, settle 횟수·시간, absolute command-feedback error, 최소 URDF margin, guard state를 성공 표본 timing JSON에 보강했다. 모든 첫/settle feedback은 **차단 판정 전에** 별도 `sample_timing`을 기록하므로 abort 표본에도 같은 시각·오차·여유가 남는다(`PENDING_CHECK` 뒤 ABORT 이유). 87ms fake bus 640/640에 JSON callback을 넣은 6건 시험은 0.16초 wall-clock 내 통과했고 가상 완료 시간은 기존 324.680초와 동일했다. 이는 실제 Jetson 로깅 지연 보장이 아니다. 새 로깅본 Jetson 설치/dry-run은 원격 인증 부재로 `NOT_RUN`.

### 나머지 phase / 명령 / 포트

- 원본 SHA 고정 `follower_command` waypoint를 경계 seq `28363→45133→60669→72140→92158→94174`에서만 분할했다. 새 trajectory·IK·clipping 없음. 각 phase 독립 URDF·최대 인접 step·gripper 변화·가짜 87ms 버스 재생 PASS. approach 640, grasp 459, transport 141, place 199, retreat 72 목표, 총 1511. 최소 margin은 각각 7.582/12.857/30.000/57.582/58.780°. Grasp gripper 명령은 61.409%→4.671%로 닫힘을 보존하고 place는 4.671%→33.691%로 열림을 보존한다. 원본 command-feedback 최대 Elbow 오차는 grasp 8.132°/transport 8.659°이고, 기존 approach settle 진입선 밖의 기록 waypoint는 grasp 173/460·transport 97/142·place 160/200·retreat 56/73이다. 따라서 후속 구간에 approach용 tracking guard를 그대로 live 적용할 준비가 되었다고 주장할 수 없다. [오프라인 실행기](../../scripts/prepare_c_red_phases.py)에는 실제 송신 경로가 없고 phase가 실패하면 다음 fake phase를 실행하지 않는다. 이상적 feedback이 명령과 같다는 모형일 뿐 물리 추종·잡힘·충돌·테두리 여유 검증이 아니다. 각 phase 상태 `DRY_RUN_ONLY`; 특히 후속 phase를 approach 성공 직후 무승인 자동 이어서 실행할 수 없다.
- `C를 빨강 바구니에 옮겨` 파서는 `C:red`로 분해되고 오프라인 5 phase dry-run에만 연결된다. A/B route live는 만들지 않았다. 역할별 [순수 preflight](../../scripts/so101_port_roles.py)는 canonical ACM0 follower/ACM1 leader에서 follower read/replay는 ACM0만, leader read는 ACM1만, LeLab/정렬 화면은 둘 다 필요함을 검사한다. permission denied와 port busy를 구별하는 가짜 시험 3/3 PASS. 실제 장치 무점유는 내일 새로 확인해야 한다.
- 관련 목표 시험은 C red/settle/scheduler 23개, 방향 보호 9개, 독점 버스 10개, 역할별 포트 3개, 명령 파서 9개, 리더 목표 2개로 **56/56 PASS**. 전체 suite `257 tests`는 5개 오류로 FAIL: `test_observe_teleop_trace` import 때 로컬 `websocket` 패키지 없음 1개, `test_teach_capture_web`의 localhost bind가 sandbox에서 `PermissionError` 4개. 하드웨어 기능 회귀의 증거로 해석하지 않고 별도 환경 문제로 남긴다. 문법 검사·`git diff --check` PASS, Jetson 설치 문법/dry-run `NOT_RUN`.

### 내일의 현장 최소 절차와 명령 (오늘 미실행)

1. 사용자가 현장에 있을 때 C 제거·빈 그리퍼·사람/장애물 없음·정지·현장 중단 준비를 확인한다. LeLab OFF, canonical 두 포트 ID와 점유를 확인한다. **아래 배포 전에** 설치 SHA가 위 값과 같은지 재확인하고 백업한다. 다르면 중단한다. 원격 인증은 터미널에만 입력하고 채팅/로그에 남기지 않는다.
2. 방향 보호 패치와 로깅본을 Jetson으로 옮긴 뒤 설치 Python 문법과 dry-run을 확인한다. 수동 복귀 시에는 읽기 전용 화면으로 leader를 follower에 정렬하되 E/W는 시작시 차이로 산정한다. 화면을 종료해 두 포트를 비운 후 LeLab 시작, leader 3초 고정·fresh 8032 방송·점프 없음 확인, 작은 전체 팔 이동으로 follower safe_start 표의 팔 5축 각 ±3°에 맞춘다. Elbow의 **실제 연속 명령 목표**는 2° 이하씩 변해야 하며 차단 시 무리하게 반복하지 않는다. 리더를 유지한 채 LeLab 종료, 실제 정지·비접촉을 확인하고 follower를 별도 fresh read-only로 읽어 ±3°/URDF를 확인한다.
3. follower-only ACM0 독점, LeLab inactive, C 제거/경로 여유를 다시 확인한 뒤 **별도 현장 live 승인 범위에서만** 4배 approach 한 구간을 실행한다. 중단 시 다음 목표/phase로 넘어가지 않는다. 640/640과 실제 정지·비접촉을 확인하기 전 grasp는 실행하지 않는다. 후속 4개 phase는 아직 live adapter/현장 clearance 검증이 없어 `DRY_RUN_ONLY`다.

Mac에서 옮길 파일(실행 전 source/백업 검증 필수):

```bash
cd '/Users/jogyeyeong/Documents/ChatGPT/자율설계'
ssh jetson3@192.168.50.20 'set -e; test "$(sha256sum /home/jetson3/so101-approach-trial/replay_c_red_approach.py | awk "{print \$1}")" = 782a6cd3e5a7142163cf3ae1c5caac48f7bc2945c803d229e6c1c9e798a43540; test ! -e /home/jetson3/so101-approach-trial/replay_c_red_approach.py.before-overnight-logging-20261009; cp -p /home/jetson3/so101-approach-trial/replay_c_red_approach.py /home/jetson3/so101-approach-trial/replay_c_red_approach.py.before-overnight-logging-20261009'
scp scripts/temporary_elbow_direction_guard.py patches/lelab-20261009/teleoperate-directional-elbow-guard.patch scripts/replay_c_red_approach.py jetson3@192.168.50.20:/home/jetson3/so101-approach-trial/
```

Jetson 터미널에서 설치 전 검증·백업·패치·dry-run(현재 **NOT_RUN**, 내일 현장 안전 확인 뒤 실행):

```bash
set -e
lelab_site=/home/jetson3/.local/share/uv/tools/lelab/lib/python3.14/site-packages/lelab
trial_dir=/home/jetson3/so101-approach-trial
test "$(sha256sum "$lelab_site/teleoperate.py" | awk '{print $1}')" = a5ac255d15cbba05d0c095ec927106c303ef50790291566fb29f383cb8102576
test ! -e "$lelab_site/temporary_elbow_direction_guard.py"
test ! -e "$lelab_site/teleoperate.py.before-directional-guard-20261009"
cp -p "$lelab_site/teleoperate.py" "$lelab_site/teleoperate.py.before-directional-guard-20261009"
patch --dry-run -d "$lelab_site" -p0 -i "$trial_dir/teleoperate-directional-elbow-guard.patch"
patch -d "$lelab_site" -p0 -i "$trial_dir/teleoperate-directional-elbow-guard.patch"
install -m 0644 "$trial_dir/temporary_elbow_direction_guard.py" "$lelab_site/temporary_elbow_direction_guard.py"
/home/jetson3/.local/share/uv/tools/lelab/bin/python -m py_compile "$lelab_site/teleoperate.py" "$lelab_site/temporary_elbow_direction_guard.py"
systemctl --user restart lelab.service
cd "$trial_dir"
/home/jetson3/.local/share/uv/tools/lelab/bin/python replay_c_red_approach.py --candidate trajectory_candidate.json --time-scale 4
```

주의: 첫 SSH 백업이 성공한 뒤에만 `scp`를 실행한다. 설치 파일 SHA mismatch·LeLab active·포트 점유가 나타나면 배포/실기를 중단한다.

접근 live 명령 자체는 이전 승인 범위와 동일하며 **오늘 NOT_RUN**:

```bash
cd /home/jetson3/so101-approach-trial
set -o pipefail
/home/jetson3/.local/share/uv/tools/lelab/bin/python replay_c_red_approach.py --candidate trajectory_candidate.json --time-scale 4 --live --confirm-scope safe_start_to_approach 2>&1 | tee approach-live-next.log
```

이 live 명령은 설치/현장 게이트 통과 후 사람 감독하 별도 사용해야 한다. `RUN APPROACH` 확인을 요구하고, 성공해도 grasp 자동 연결은 없다. 오늘 원본 실기 로그·데이터셋·비밀정보 Git 제외, 로컬 변경 `NOT_COMMITTED/NOT_PUSHED`, 이슈 API `NOT_RUN`.

## 후속 LeLab 시작 복구 및 safe_start 수동 복귀 중단

- 두 canonical USB 포트 권한 `root:dialout 660`/사용자 `dialout`/`rw`, 사용자 인증 `sudo fuser` PID 없음·exit 1을 확인했다. 첫 UI 시작 성공 직후 worker가 `Temporary alignment blocked by shoulder_lift mismatch`(21:11:45 KST)로 종료된 실제 로그를 찾았다. LeLab OFF의 읽기 전용 리더/팔로워 정렬만 다시 수행했으며 포트 검사 구조·서비스·설치 코드는 바꾸지 않았다.
- 정렬 뒤 기존 UI 재시작은 `teleoperation_active=true`, 8032 방송 새 수신·오류 없음으로 검증됐고 사용자 현장 3초 정지·급격한 움직임 없음 확인. 정상 시작은 복구됐다. 다만 safe_start 수동 이동 두 번은 기존 한시 `Elbow 시작값보다 +0.5° 초과` 보호장치가 새 목표를 보내기 전 차단해 각각 21:26:03, 21:34:04 KST에 중단됐다. 사용자 현장 정지·안전 확인. 해당 순간의 실제 차단 목표값은 로그에 없어 추정하지 않는다.
- 마지막 read-only follower `(Pan +19.297,Lift −42.769,Elbow +86.989,Flex −31.165,Roll +3.824°)`; Elbow URDF +90°까지 3.011°다. leader는 종료 뒤 별도 이동되어 현 follower와 불일치. LeLab OFF, 8031 뷰어 종료·포트 해제. `+0.5°` 한시 guard 해제/완화, safe_start 도착, 자동 approach/live/grasp 모두 `NOT_RUN`. 원본 로그·비밀정보는 커밋하지 않았고 이슈 API `NOT_RUN`, 변경 `NOT_COMMITTED/NOT_PUSHED`.

## 후속 4배 접근 재시험 준비 — 텔레옵 시작 상태 불일치

- scheduler 수정본의 live 재시험을 위해 리더/팔로워 읽기 전용 정렬을 끝내고 뷰어를 닫았다. 사용자 요청의 리더 관절 화면 그리퍼 표시 추가는 이후 작업으로 보류; 이번 시험 코드는 변경하지 않았다.
- 사용자가 C 제거·주변 여유를 확인한 뒤 LeLab 시작을 두 차례 시도하고 팔 정지를 보고했다. 두 번 모두 canonical 8000 `/teleoperation-status`는 `teleoperation_active=false`였고, 8032 관절 방송은 2026-10-09 11:06:46 UTC 수신값에서 갱신되지 않았으며 `WebSocketTimeoutException`이었다. 화면의 녹색 `Live Robot Data`와 시작 성공 알림은 실제 작업 활성과 불일치한다. 두 USB 포트를 대상으로 한 `lsof`에는 PID가 표시되지 않았다(무관한 mount 경고 존재).
- 리더/팔로워 이동 및 새 자동 송신 0회. safe_start 수동 복귀와 접근 640개 재시험은 `NOT_RUN/BLOCKED`, 원인 `NOT_VERIFIED`. 사용자에게 추가 시작·리더 이동을 중단하도록 안내했다. 새 로그 원본·비밀정보 커밋 없음, 이슈 API `NOT_RUN`, 변경 `NOT_COMMITTED/NOT_PUSHED`.

- 범위: 고정 배치 C 한 병을 사람 감독 LeLab 텔레옵으로 집어 빨강 바구니에 놓고 퇴피. 프로그램 `send_action`/trajectory replay는 실행하지 않았다.
- 시작: Jetson 설치 기록 패치를 다음 한 세션에만 활성화했다. teleop OFF·canonical follower ACM0/leader ACM1 무점유에서 읽기 전용 8031 화면으로 5축을 정렬했다. 최초 수치 불일치 때문에 시작을 보류했고 최종 리더−팔로워 차이는 `(Pan +0.176, Lift +0.484, Elbow +0.484, Flex −1.538, Roll −1.714)°`였다. 화면을 종료해 포트를 해제한 뒤 사용자가 LeLab을 직접 시작했다. 첫 3초 740주기에서 최대 시작 대비 command 1.714°·feedback 1.495°, 오류 0건, 사용자 확인상 급격한 이동 없음.
- 사람 확인: 공중 여유 자세에서 정지 → C 접근 비접촉 정지 → C 실제 집기/소폭 들기 성공 → 빨강 바구니 중앙 상공 비접촉 정지 → C가 빨강 안에 남도록 놓음 → 열린 그리퍼 비접촉 퇴피. 단계별 확인 후 Jetson 같은 시계로 `approach`, `grasp`, `transport`, `place`, `retreat` 마커를 각각 기록했다. 최초 종료 보고 때 서버는 아직 active이고 두 포트가 점유돼 있어 완료 처리하지 않았다. 사용자가 종료를 다시 실행한 뒤 서버 inactive·포트 무점유를 확인했다.
- 원본: Jetson `/home/jetson3/lelab-teleop-cycle-traces/1791523577320343828/`; Git 제외 복사본 `.local/teleop-cycle-traces/2026-10-09-c-red/`. 107,422주기/430.853초, 이벤트 5개, 오류 0개, 순서/범위 검사 `data_complete=true`. `cycles.jsonl` SHA-256 `01a8b48183ed90d1acc34d70ce855520e9fa75f75fa6d1ffaae822005bf18978`는 Jetson·Mac 일치. 매 주기 leader position/follower command/fresh follower feedback 6축을 별도 필드로 보존했다. manifest의 `physical_task_success_verified=false`를 현장 성공의 자동 검증으로 바꾸지 않았다.
- URDF 감사의 새 사실: Elbow 초과는 `retreat`에서만 command 12,573주기(최대 상한 +7.494°), feedback 12,554주기(최대 +6.571°). 다른 팔 관절 및 앞 구간에서 수치상 초과는 없었다. 최종 follower feedback Elbow +96.571°로 URDF +90° 상한 밖이다. 따라서 이 수동 시연은 자동 경로 승인 근거가 아니며, 특히 퇴피·종료 자세를 재생하지 않는다. 실제 환경/자체 충돌·물체 여유도 별도 검증이 필요하다.
- 정리: 기록 티켓 소모 뒤 기록 환경을 해제하고 LeLab 서비스만 재시작했다. teleop inactive, 두 포트 무점유, 추가 모터 명령 `NOT_RUN`. 기존 calibration/URDF/토크 설정 미변경. 기록 모듈 단위 시험 5/5, 읽기 전용 8031 실측, 설치 Python 문법 확인. 이슈 갱신 `NOT_RUN`, 로컬 변경 `NOT_COMMITTED/NOT_PUSHED`; 원본 로그·비밀정보는 Git에 넣지 않는다.

## 같은 원본의 오프라인 자동화 후보 추출

- `scripts/extract_c_red_cycle_candidate.py`는 manifest SHA를 대조한 뒤 원본을 읽기만 한다. 설치 URDF 제한 스냅샷 SHA `443d38d7...f67236`을 사용하며 그리퍼 0–100%를 Jaw rad에 억지로 대입하지 않는다. 원본의 첫 Elbow 초과 command는 `seq 94849`/2026-10-09 14:32:37.894 KST에서 직전 +89.670°→+90.022°(다음 +90.462°), feedback은 `seq 94868`/14:32:37.971에서 직전 +89.978°→+90.242°(다음 +90.505°)다. 명령 초과가 피드백 초과보다 먼저이므로 이 이전의 안정점에서 후보를 끝냈다.
- `safe_start`: `seq 28363`, 14:28:11.268 KST, 명령 `(Pan +11.736, Lift −22.330, Elbow +32.440, Flex +5.538, Roll −20.396°, gripper 3.446%)`; 피드백 `(11.824, −20.615, 34.593, 6.989, −20.440°, 3.488%)`. 접근 마커 직전 약 1초/249표본에서 세 스트림 변화 0°, 명령·피드백 최소 한계 여유 55.407°. C 비접촉은 단계별 현장 보고이나 동기화된 영상 없음.
- `safe_retreat/end` 수치 후보: `seq 94174`, 14:32:35.196 KST, 명령 `(5.846, −21.890, 20.484, −5.890, −11.516°, gripper 33.691%)`; 피드백 `(5.846, −19.209, 21.407, −5.846, −11.560°, 33.354%)`. retreat 마커 뒤 약 1초/251표본에서 피드백 변화 0°·명령 최대 변화 0.176°, 최소 한계 여유 68.594°. C가 빨강에 놓였다는 현장 보고는 이보다 앞서 있으나, **이 정확한 시각의 테두리 이탈은 영상으로 확인되지 않았다.** 이 점 뒤 13,247주기 및 Elbow 초과 부분은 후보에서 제외하며 clipping 없음.
- 후보 `seq 28363–94174` 65,812주기의 command·feedback 팔 5축은 모두 URDF 안이며 전체 최소 여유는 접근 `seq 32208`의 Elbow 7.583°. `approach/grasp/transport/place/retreat` 이벤트 양쪽, 각 단계 완료점, 방향 전환 82개, gripper 임계값 통과 91개를 보존한 시간기반 균형안은 1,512점/43.5배 압축. 원 command에 대한 보간 오차 팔 축별 <0.5°·gripper <1%p, 인접 목표 변화 팔 <2°·gripper <2%p를 원본 전 표본과 대조했다. 그러나 실제 command−feedback 오차는 Lift 최대 8.659°·Elbow 최대 8.747°이며, 환경/물체·충돌·속도 검증은 없다. 결과는 Git 제외 `.local/teleop-cycle-traces/2026-10-09-c-red/analysis/{analysis,trajectory_candidate}.json`, `motion_authorized=false`다. 자동 송신/실기 `NOT_RUN`, 추출 단위 시험 2/2, 원본 SHA 불변, 이슈 갱신 `NOT_RUN`, `NOT_COMMITTED/NOT_PUSHED`.

## 첫 자동 접근 시험 연결 준비

- `scripts/replay_c_red_approach.py`는 후보 파일 SHA를 고정하고 safe_start~approach 640개 목표/원 67.250초만 선택한다. 최소 시간 배율 2.0(약 134.5초), 첫 점은 시작 피드백 확인에만 쓰고 재송신하지 않는다. 그 뒤 각 점은 원 시각 간격을 배율로 늘려 `send_action`하고 새 follower feedback을 기록된 정상 추종 범위 및 URDF 5° 여유와 비교해 벗어나면 다음 송신을 중단한다. 기존 live adapter의 LeRobot 클래스 이름도 설치 성공 viewer와 같은 `SO101Follower`/`SO101FollowerConfig`로 수정하고 Mac 설치 패키지에서 생성자 옵션을 읽기 전용으로 확인했다. 기본 dry-run은 포트 접근 없음. 실제 실행은 별도 현장 승인과 Jetson 배포가 필요하다.
- 현재 follower Elbow +96.571°이므로 자동 시작 불가. 사용자 감독 LeLab 수동 복귀 후 종료·포트 해제·fresh feedback·C 제거/공간 여유 확인이 선행되어야 한다. 모의/독점 adapter 시험 12개 통과, 실제 송신·수동 복귀 `NOT_RUN`; 커밋/푸시/이슈 갱신 `NOT_RUN`.

## 수동 safe_start 복귀를 위한 한시 손목 정렬 준비

- 이전 수동 복귀에서 LeLab 종료 시 follower 자세가 변한 것을 사용자가 확인했다. 별도 승인으로 설치 follower 설정의 `disable_torque_on_disconnect=False` 한 줄을 먼저 적용했고, 이번에는 손목 리더 기구 범위 차이를 위해 `LELAB_TEMP_WRIST_ALIGN=1`을 한시 적용했다. 손목만 시작 시 fresh leader/follower 차이로 오프셋을 잡으며 다른 축·그리퍼 차이 >2.5°, 손목 차이 >15°, cycle trace 활성화는 첫 송신 전에 거부한다. calibration/URDF/자동 경로는 변경하지 않았다.
- Jetson LeLab 텔레옵 inactive·ACM0/ACM1 무점유 확인 뒤 원 설치본 SHA `cfe3e9426748692bc292ff09f142107476f118d3f13f3c2de96f0dd1faa75dd3` 백업과 일치를 검증했다. 한시 파일 SHA `19436c2424730a502b70e26bddb700512bc59973ff2c1c7c71b1c0f9a995d5e9` 설치, Python 3.14 문법 통과, 서비스 재시작 후 inactive. 가짜 버스 3건(정상 첫 손목 목표 일치, 다른 축 불일치 차단, 손목 차이 과대 차단) 통과; 물리 명령 `NOT_RUN`.
- 읽기 전용 정렬 화면은 Jetson localhost 8031/Mac localhost 8033으로만 열었다. 마지막 fresh 값의 리더−팔로워 차이는 Pan +1.67°, Lift +1.98°, Elbow −1.19°, Flex −7.96°, Roll +0.48°로 다른 팔 4축은 ±2° 안, 손목은 한시 오프셋 ±15° 안이다. 화면은 두 버스를 읽기 전용으로 소유하므로 종료·포트 해제 전 LeLab 시작 금지. 사용자 리더 정지 확인 및 현장 재확인 대기. 세션 후 한시 소스와 환경변수 복원 필수; 자동 접근 `NOT_RUN`, 로컬 `NOT_COMMITTED/NOT_PUSHED`.
- 정렬 완료 후 두 번 같은 fresh 값: 리더 `(Pan −7.780, Lift −98.198, Elbow +94.593, Flex +55.297, Roll −22.154)°`, 팔로워 `(−9.538, −100.088, +97.538, +57.714, −20.176)°`. 차이는 `( +1.758, +1.890, −2.945, −2.418, −1.978)°`; gripper 차이는 약 +0.002%p. 사용자가 리더 Elbow를 더 높일 수 없다고 확인했다. 현재 한시 손목 패치는 비손목 차이 >2.5°를 첫 송신 전에 거부하므로 텔레옵 시작 금지/실제 송신 `NOT_RUN`; 읽기 화면이 계속 포트 소유. 추가 세션 한정 Elbow 오프셋 준비는 별도 승인 대기.
- 추가 승인 후 [최소 패치](../../patches/lelab-20261009/teleoperate-temp-wrist-elbow-align.patch)는 팔꿈치 첫 오프셋을 fresh 차이로 계산하고 절댓값 3.5°를 상한으로 둔다. 고정 3.5°를 더하지 않으며 이번 측정상 보정량은 +2.945°다. 손목 +2.417°도 첫 목표를 follower 현재값에 맞춘다. 이후 팔꿈치 목표가 시작값보다 0.5° 넘게 높아지면 다음 송신을 막는다. 다른 축·gripper 2.5°/%p 차단은 유지한다. Jetson 시험 폴더 patch dry-run 통과, 설치 Python 문법, 가짜 버스 정상/팔꿈치 과대/다른 축 불일치/손목 과대/이후 팔꿈치 상향 5건 통과. 설치 파일 SHA `a5ac255d15cbba05d0c095ec927106c303ef50790291566fb29f383cb8102576`, 서비스 재시작 후 inactive. 재시작 뒤 fresh 값 동일, 읽기 화면 종료 및 ACM0/ACM1 무점유. 실제 텔레옵·자동 송신 `NOT_RUN`; 현장 확인과 사용자 직접 시작은 별도, 세션 뒤 원 설치본으로 복원한다.

## LeLab 시작 후 3초 정지 시험

- 승인 범위는 빈 그리퍼·주변 여유·리더 고정의 시작/정지만이다. 기존 CycleTrace를 [한시 기록 연결](../../patches/lelab-20261009/teleoperate-temp-wrist-elbow-trace.patch)해 raw leader와 보정 후 `send_action` 반환 command, 매 주기 fresh feedback을 분리하고 [3.2초 자동 종료](../../patches/lelab-20261009/teleoperate-temp-stillness-window.patch)를 붙였다. 가짜 버스 기록/자동 종료 확인 2건 통과(두 번째 3.202초/744주기). Jetson 설치 SHA `09f58bb7...87d1b`; 1회용 기록 티켓으로 다른 세션 재시작 차단. 시작 전 리더 `(−7.780,−98.198,+94.593,+55.297,−22.154)°`, follower `(−9.538,−100.088,+97.538,+57.714,−20.176)°`, gripper 약 2.45%였다. 두 포트 해제 후 사용자가 직접 LeLab 시작했다.
- 실기 기록 Jetson `/home/jetson3/so101-approach-trial/stillness-traces/1791532404670180932/`: 16:53:24.796–16:53:27.998 KST, 796주기/3.202초, 오류 0, stop_reason `stillness_window_complete`, `cycles.jsonl` SHA-256 `013a3eb6110c5670c39e0aef90a807bf0da0d6bcc22bc1b886770d412ac12a70`. 매 축 첫 leader/command/feedback, 마지막 feedback, 3초 최대 feedback 변화는 다음과 같다(arm °, gripper %p).

  | 축 | leader | 첫 command | 첫 feedback | 끝 feedback | 최대 변화 |
  |---|---:|---:|---:|---:|---:|
  | Pan | −7.780 | −7.780 | −9.538 | −8.132 | 1.407 |
  | Lift | −98.110 | −98.110 | −100.088 | −98.857 | 1.231 |
  | Elbow | +94.593 | +97.538 | +97.538 | +97.538 | 0 |
  | Flex | +55.297 | +57.714 | +57.714 | +57.626 | 0.088 |
  | Roll | −22.066 | −22.066 | −20.088 | −21.670 | 1.582 |
  | Gripper | 2.450 | 2.450 | 2.448 | 2.448 | 0 |

- 전 축 command 변화 0; 첫 command는 전송 호출 반환이지 motor ack가 아니다. 팔 이동은 fresh feedback으로 별도 확인했고 사용자는 급격/이상 움직임 없고 팔 정지를 현장 확인했다. 종료 뒤 16:54:54 및 16:55:21 KST 별도 read-only 측정이 같은 follower raw `(2009,830,3093,2736,1617,453)`/degree `(−8.132,−98.857,+97.538,+57.626,−21.758,2.448)`로 유지됐다. viewer 종료·LeLab inactive·두 포트 해제 확인. Elbow +97.538°는 계속 URDF 밖이며 safe_start 수동 복귀 및 자동 접근 `NOT_RUN`. 이 기록은 3초 정지 시험이므로 phase markers/data_complete/physical task success는 false가 정상이다. 임시 환경·소스는 아직 설치돼 있으나 1회 티켓 소모로 재시작이 차단되며 후속 정리가 필요하다. 로컬 `NOT_COMMITTED/NOT_PUSHED`.

## 첫 자동 접근 실기: 일부 구간만 움직인 뒤 추종 차단

- 리더·팔로워를 read-only로 재정렬한 마지막 차이는 팔 5축 최대 1.37°. 정렬 viewer를 종료하고 두 USB 포트를 해제한 뒤 사용자가 LeLab을 직접 시작했다. 방송·현장 여유를 보며 전체 팔을 safe_start 근처로 수동 복귀, 리더 유지 상태에서 LeLab 종료. 종료 뒤 raw `(2258,1686,2374,2134,1618,453)`/degree `(Pan +13.758,Lift −23.604,Elbow +34.330,Flex +4.703,Roll −21.670,gripper 2.448%)`로 새로 읽었다. 팔 5축 목표 ±3°·URDF 안, 두 번 같은 피드백, follower 6개 축 torque register 모두 1, LeLab inactive·포트 무점유. 사용자는 C 범위 밖·주변 여유를 확인했다.
- Jetson 시험 폴더의 `replay_c_red_approach.py`, `so101_follower_transport.py`, `trajectory_candidate.json` SHA를 로컬과 대조했고 LeLab Python 3.14.7 dry-run은 640개 목표/134.5초, 순서·timestamp·URDF PASS(최소 margin 7.582°). dry-run 포트 개방·모터 송신 0회. 첫 live 시작은 `/proc` 접근 제한이 있는 일반 권한 `fuser`의 점유 불명에서 차단돼 **포트 개방 전** 종료. 같은 파일의 `owner_pids`가 그 경우에만 `sudo -n fuser` 읽기 전용 재확인을 수행하도록 최소 수정해 단위 시험 10/10·Jetson 실제 점유자 없음 확인 후 다시 dry-run PASS. 안전 검사를 우회하지 않았다.
- 별도 현장 재확인·재승인 후 C 없는 `safe_start→approach`를 2배 시간축으로 시작했다. 송신 28개(`seq 31733`) 뒤 `tracking_outside_demo_envelope:shoulder_lift`로 중단, 이후 목표 전송 없음. `seq 31723` Lift command `−24.791°`/fresh feedback `−21.407°`; 실패 목표 `−26.374°`, demo reference `−22.022°`. 실패 표본 actual은 현재 출력 순서상 기록되지 않아 어느 비교가 차단했는지 확정하지 않는다. 프로그램 encoder stillness PASS 뒤 사용자도 팔 정지·접촉/위험 없음을 확인. 종료 뒤 새 follower `(Pan +17.802,Lift −23.341,Elbow +38.637,Flex +0.835,Roll −20.791°,gripper 3.182%)`, URDF 안. LeLab inactive·포트 무점유. 로그는 Jetson `/home/jetson3/so101-approach-trial/approach-live-20261009-1727.log` SHA `1158054672189065d380f3442d02cb1fa8e1b53813a376336672bff73b235aea`, Git 제외.
- 이 시험은 **첫 프로그램 제어 움직임은 관측됐으나 approach 미완료**다. 목표 28/640, 완전 자동 C→빨강 `NOT_RUN`. 사용자는 움직임이 천천히 예상 방향이었고 버벅임·급격함·접촉 우려는 없었다고 보고했다. 실패 시 실제 Lift feedback을 확인하기 전 같은 시험을 자동 재시도하지 않는다. 임시 LeLab 정렬 패치·토크 유지 설정은 설치 상태이며 복원 여부와 다음 실기 범위는 현장 계획 후 결정한다. 이슈 갱신 `NOT_RUN`, 로컬 변경 `NOT_COMMITTED/NOT_PUSHED`.

### 재시도 코드 준비와 수동 복귀 중단

- 기존 guard는 목표와 시연 feedback 모두 같은 작은 허용 오차에 들어오도록 요구했다. 접근 후보에서는 gripper 명령−시연 feedback 격차 최대 30.721%p로 두 8%p 검사 동시 만족이 불가능한 지점이 있다. 경로·URDF는 그대로 두고 목표 대비 tracking guard를 유지하며 초과 때 **새 목표를 보내지 않고** 최대 2초만 새 feedback 수렴을 기다리는 로직으로 수정했다. 멀리 벗어남·오차 증가·한계 접근·통신 문제는 중단한다. 실패 표본도 출력하게 바꿨다. 로컬 관련 시험 15/15, Jetson 설치 Python dry-run 640개/134.5초/URDF PASS; 수정 로직 실제 송신 `NOT_RUN`.
- 재정렬 viewer에서 팔 5축 리더−팔로워 차이 최대 1.802° 확인 후 viewer 종료·포트 해제. 사용자가 현장 여유와 별도 **수동 복귀만** 승인해 LeLab을 직접 시작, 3초 정지·이상 없음을 보고했다. safe_start 쪽으로 움직이던 중 8032 방송 마지막 값 `(Pan +17.538,Lift −22.462,Elbow +40.044,Flex +1.011,Roll −20.352)°` 뒤 갱신이 끊겨 조작 중단을 요청했다. 사용자가 직접 LeLab을 종료했고 팔 정지·접촉/위험 없음. 종료 뒤 두 번 같은 fresh follower raw `(2303,1723,2510,2093,1632,459)`/degree `(Pan +17.714,Lift −20.352,Elbow +46.286,Flex +1.099,Roll −20.440,gripper 2.815%)`; URDF 내부, LeLab inactive·포트 무점유.
- 마지막 방송과 종료 뒤 실측 사이의 Elbow +6.242°는 전송 명령 기록이 없어 원인/정확한 시점 `NOT_VERIFIED`. 사용자가 직접 종료했으나 방송 지연이 종료 전인지 후인지는 불명확하다. safe_start 재복귀·수정 실행부 live 재시험을 진행하지 않는다. 다음은 읽기 화면의 신선도/LeLab 종료 시점 관계를 최소 범위에서 확인하고 새 현장 승인 후에만 다시 움직인다. 로컬 변경 `NOT_COMMITTED/NOT_PUSHED`.

### 수정 실행부 2배·4배 실기 결과

- 최소 재점검에서 LeLab teleop/recording/inference inactive·ACM0/ACM1 무점유를 확인했다. follower 단독 읽기 전용 연속 6회는 값이 동일했고, 당시 `(Pan +17.714,Lift −20.352,Elbow +46.286,Flex +1.099,Roll −20.440)°`였다. 방송 마지막값과의 Elbow +6.242° 원인은 `NOT_VERIFIED`로 유지했다.
- 사용자가 리더를 정렬하고 LeLab 사람 감독으로 safe_start에 복귀했다. LeLab 종료 뒤 두 fresh follower 값 `(Pan +10.418,Lift −19.912,Elbow +33.099,Flex +5.143,Roll −19.033)°`가 동일하고 목표 ±3°·URDF 내부였다. C는 작업 범위 밖, 현장 여유·정지·LeLab OFF·포트 무점유를 확인했다.
- 설치 Python dry-run은 수정본 `--time-scale 2`에서 640개/약 134.5초, `--time-scale 4`에서 640개/약 269.0초, URDF 최소 여유 7.582°로 통과했다. 각 live는 별도 사용자 현장 승인 뒤 C 없는 `safe_start→approach` 범위만 시행했다. 2배 `approach-live-20261009-1758.log`와 4배 `approach-live-20261009-1809.log`는 모두 29번째 `seq 31743` 뒤 `tracking_error_growing_during_settle:elbow_flex`로 추가 송신을 막았다. 4배 실패 지점의 첫 fresh Elbow는 command +38.769°/feedback +38.725°, Lift는 command −27.868°/feedback −23.516°다. 코드상 Lift 수렴 대기 중 Elbow 오차가 최초보다 0.5° 넘게 증가했지만 차단을 유발한 추가 피드백 표본은 기록되지 않아 정확한 값·물리 원인은 `NOT_VERIFIED`. 4배 로그 SHA-256 `d4c96999a2c415e0086c163e6c9a1a2853dcc3dd712f61fc19ba31b4027e96c6`.
- 두 실기 모두 encoder stillness PASS와 사용자 실제 팔 정지·비접촉·위험 없음 확인 후 종료했다. 4배 종료 뒤 follower만 읽기 전용으로 0.5초 간격 6회 검사한 raw `(2304,1674,2433,2090,1632,465)`와 degree `(Pan +17.802,Lift −24.659,Elbow +39.516,Flex +0.835,Roll −20.440,gripper 3.182%)`는 모두 동일했고 URDF 내부다. write/torque API 차단·토크 미변경 disconnect 후 포트 무점유 확인. LeLab 비활성. 첫 자동 움직임은 성공했지만 approach 완주 실패, 자동 C→빨강 `NOT_RUN`. 동일 설정 재시도 금지, 추가 모터 명령은 새 원인/변경안과 별도 현장 승인 전 `NOT_RUN`. 원본 실기 로그는 Git 제외, 이슈 API `NOT_RUN`, 로컬 변경 `NOT_COMMITTED/NOT_PUSHED`.

### target 20–35 보정 경로 재검사 — 코드·기존 로그만

- `trajectory_candidate.json`의 `goal_source=follower_command_not_follower_feedback`; 추출 코드가 각 waypoint `goal`에 시연의 `follower_command`를 복사한다. 자동 replay는 `point["goal"]`을 adapter에 넘기고 adapter는 값 변형 없이 `.pos` action으로 `SO101Follower.send_action()`에 넘긴다. 설치 `send_action()`은 `max_relative_target=None`에서 별도 절단/오프셋 없이 `bus.sync_write("Goal_Position", goal_pos)` 후 같은 goal을 반환한다. Elbow +2.945°와 Wrist 한시 오프셋은 Jetson 설치 LeLab `teleoperate.py`의 리더 텔레옵 worker 지역 변수에만 있으며 자동 replay 경로에 없다. 실제 target 20–29 로그의 반환 command는 JSON과 축별 일치; target 30–35는 송신되지 않았다. 이중 보정 없음.
- 설치 follower calibration SHA `2f74c1303b2fce03576eff539329e1185a652e2d551caa1ec82b026dafe29c2e`; Elbow raw range 880–3087/mid 1983.5, Wrist Flex 936–3225/mid 2080.5. 설치 `_unnormalize()`의 DEGREES 가지 `int(deg*4095/360+mid)`를 20–35에 직접 적용해 계산 raw를 확인했다. 이는 degree→raw calibration이지 +2.945° 재보정이 아니며, `sync_write`는 motor ack가 없어 실제 전선 패킷·수신 raw의 독립 증거는 없다.
- 4배 target 28 `seq 31733` 마지막 로그: Elbow command +37.890110°/feedback +38.549451°(오차 0.659341°), Wrist −0.263736°/+0.835165°(오차 1.098901°), Lift −26.373626°/−22.989011°(오차 3.384615°). target 29 `seq 31743` 첫 로그: Elbow +38.769231°/+38.725275°(오차 0.043956°), Wrist −0.263736°/+0.835165°(오차 1.098901°), Lift −27.868132°/−23.516484°(오차 4.351648°). 목표·반환 명령 변화 Elbow +0.879121°/계산 raw +10(2414→2424), Wrist 0°/raw 0(2077→2077); 첫 feedback 변화 Elbow +0.175824°, Wrist 0°, Lift −0.527473°. Lift가 4° guard 밖이라 수렴 대기 진입; 그 다음 첫 fresh 표본의 Elbow 절대오차가 첫 0.043956°에서 **0.543956° 초과**가 되어 `tracking_error_growing_during_settle:elbow_flex`가 발생했다. callback 전에 차단되므로 표본의 정확한 값·방향은 미기록. 2배도 같은 seq/판정이다. 이후 독립 정지값 Elbow +39.516°는 abort 시점 값이 아니다.
- 원인 범위: temp offset의 재적용은 배제. 코드상 직접 차단 원인은 Lift 수렴 대기 중 전체 축에 적용되는 0.5° error-growth guard다. 해당 Elbow 움직임이 정상 지연/기구 overshoot인지, 패킷/피드백 문제인지는 기존 기록만으로 특정할 수 없다. guard 완화·새 trajectory·time-scale/URDF 변경 없음. 설치 Python 4배 dry-run 640개/269.0초·URDF PASS(포트 미개방·send_action 0회), 로컬 관련 시험 5/5. 새 live `NOT_RUN`; 원본 로그 Git 제외·`NOT_COMMITTED/NOT_PUSHED`.

### settle guard 최소 수정 — live 미실행

- 사용자 지시에 따라 replay의 settle 루프만 수정했다. 모든 읽기 피드백을 abort 검사 전에 기록하고, 팔 관절 절대오차 1.5° 미만·gripper 4%p 미만에서는 작은 growth를 무시한다. 그 이상에서는 관절별 독립 count로 연속 두 표본의 증가(팔 각 >0.5°, gripper >1%p)일 때만 growth 차단한다. 사용자가 명시적으로 확인한 기존 4° 기준은 최대 2초 수렴 대기 진입선으로 유지한다. URDF 5° margin은 표본마다 즉시 검사하고, 목표 변화량을 포함한 기존 far-error 기준도 모든 settle 표본에서 즉시 검사한다. 경로·calibration·time-scale은 불변.
- target 20–35 실제 command 수치와 target 20–28의 기존 4배 피드백을 이용한 가짜 버스 시험에서 target 29 Elbow 0.044°→0.75°는 허용하고 35까지 전송했다. Elbow 2.0°→2.7° 연속 증가, Elbow 4.1°가 2초 내 수렴하지 않음, far error 6°, Elbow 90.1° URDF 초과는 모두 다음 목표 전 중단했다. 차단 표본이 콜백 로그에 먼저 들어감을 확인했다. replay 10/10, 독점 버스 10/10 PASS.
- Jetson 시험 폴더의 구 replay SHA `9a1015bea4fa593b27a2a271c336c543e5a602418b59877fe41ae025d1201456`을 `replay_c_red_approach.py.before-settle-guard-20261009`로 백업했다. 새 파일 SHA `ae43090978de7d267cfd236a7bf3e480ebb99fb2d982d441362492f8f1a82ea7`; adapter `4c1872a1...e071f2d71`, 후보 `684d90e6...f265fa` 불변. 설치 Python 4배 dry-run 640개/269.0초·시각 순서·URDF 최소 여유 7.582° PASS, serial·`send_action` 0회. 마지막 `sudo -n fuser`는 비밀번호를 요구해 현재 포트 점유를 재확인하지 못했으며 live preflight에서 다시 확인해야 한다. 현재 팔은 safe_start가 아니고 실제 모터 송신·LeLab 수동 복귀 `NOT_RUN`; 별도 현장 승인 전 live 금지. 로컬 변경 `NOT_COMMITTED/NOT_PUSHED`.

### 다음 수동 복귀와 재시험 직전 준비

- LeLab OFF에서 Jetson localhost 8031/Mac localhost 8033 읽기 전용 정렬 화면으로 follower `(Pan +17.802,Lift −24.747,Elbow +39.516,Flex +0.835,Roll −20.440)°`에 리더만 맞췄다. 최종 리더−팔로워 최대 차이 Elbow 1.099°. viewer 종료·두 포트 해제 뒤 사용자가 C 제거·빈 gripper·주변 여유를 확인하고 LeLab을 직접 시작했다. 3초 정지·이상 없음, 8032 방송 갱신 확인 후 사람 감독으로 전체 팔을 safe_start 근처에 맞춰 정지, 리더 유지 상태에서 직접 종료했다. 종료 표시·팔 정지·비접촉 보고와 서버 teleop/recording/inference inactive를 각각 확인했다.
- 종료 뒤 follower canonical `/dev/ttyACM0` serial `5AE6058306`을 write/torque API가 차단된 읽기 전용 버스로 열어 0.5초 간격 4회 측정했고 raw `(2265,1688,2321,2127,1635,458)`, degree `(Pan +14.374,Lift −23.429,Elbow +29.670,Flex +4.088,Roll −20.176,gripper 2.754%)`가 반복 동일했다. safe_start 대비 팔 5축 `( +2.637,−1.099,−2.769,−1.451,+0.220)°`, 모두 ±3° 및 URDF 내부, 최소 arm limit margin Elbow 60.330°. 토크 변경 없이 연결을 닫았다.
- sudo 없는 `lsof -nP -- /dev/ttyACM0 /dev/ttyACM1`은 viewer 실행 중 PID `533997`의 두 장치 점유를 표시하고, viewer·follower reader 종료 뒤 대상 장치 점유를 표시하지 않았다. mount 접근 경고로 스캔 전체의 완전성은 제한된다. 일반 `fuser`는 타 프로세스 `/proc`에서 Permission denied가 나고, 기존 프로그램 preflight는 `sudo -n fuser` fallback이 필요하지만 현 sudo 인증은 없다. `sudo -v` 인증 갱신 시도는 auto-review에서 불필요한 권한 작업으로 거절됐고 이를 우회하지 않았다. 따라서 현장·자세 준비는 통과했지만 **설치 실행부의 독점 포트 gate는 미통과**, 4배 live와 자동 `send_action`은 `NOT_RUN`. trajectory/calibration/time-scale/URDF/guard 변경 없음; 사용자에게 인증 방법 또는 `lsof` 대안의 코드 반영 중 무엇을 허용할지 요청한다. 원본 로그 Git 제외, 로컬 `NOT_COMMITTED/NOT_PUSHED`.

### 최종 재시험 게이트 — 포트·fresh pose 확인, live 미실행

- 사용자가 sudo 인증을 포트 독점 `fuser`에만 허용했다. 사용자 Jetson 터미널에서 `sudo fuser /dev/ttyACM0 /dev/ttyACM1` 결과 PID 없음/exit 1, 읽기 전용 측정 종료 후 `sudo -n fuser`도 PID 없음/exit 1. 기타 root 작업 없음. 에이전트 SSH tty의 별도 sudo 캐시는 활성화되지 않았으므로 live를 거기서 실행하면 내장 preflight가 다시 인증 문제로 차단될 수 있다.
- LeLab teleop/recording/inference 새 상태가 모두 inactive. canonical follower serial `5AE6058306`의 읽기 전용 4회/0.5초 간격 fresh feedback은 매번 `(Pan +14.374,Lift −23.429,Elbow +29.670,Flex +4.088,Roll −20.264,gripper 2.754%)`로 동일했다. write/sync_write 차단 및 `disconnect(disable_torque=False)` 후 닫음. safe_start와 차이 `(+2.638,−1.099,−2.770,−1.450,+0.132)°`, 팔 5축 전부 ±3°·URDF 내부, 최소 한계 여유 Elbow 60.330°.
- 사용자가 C 제거 지속, 접근 경로 사람·장애물·접촉 우려 없음, 팔 정지를 현장에서 재확인했다. 수정본 4배 dry-run은 기존 640개/269.0초/URDF PASS 그대로이며 새 live·모터 명령은 `NOT_RUN`. 실행 예정 범위는 `safe_start→approach`만; trajectory/calibration/time-scale/URDF/guard 변경 없음. 비밀번호·원본 로그는 저장하지 않았고 이슈 API `NOT_RUN`, 로컬 `NOT_COMMITTED/NOT_PUSHED`.

### 수정본 4배 접근 live — 105/640 scheduler 중단

- 사용자 승인 범위는 C 없는 `safe_start→approach` 한 구간. 실행 직전 현장 C 제거·사람/장애물/접촉 우려 없음·팔 정지·약 4.5분 감독 준비를 재확인했고 LeLab 세 제어 상태 inactive였다. canonical follower fresh 3회는 `(14.374,−23.429,+29.670,+4.088,−20.176°,gripper 2.754%)`로 동일해 safe_start ±3°·URDF 내부. 인증된 사용자 Jetson tty에서 `sudo -n fuser` 결과 두 포트 PID 없음/exit 1; 에이전트 SSH tty의 별도 sudo 캐시는 없어서 사용자 터미널에서 승인 명령을 실행했다.
- 첫 프롬프트 입력 `RUN APPRACH` 오타는 `NOT_RUN`/송신 0회로 끝났고 별도 `approach-live-20261009-settle-retrial.log`에 남겼다. 재차 포트·현장·LeLab을 확인한 뒤 같은 코드·후보·4배 시간축으로 정확한 `RUN APPROACH`를 입력했다. 실제 로그 `approach-live-20261009-settle-retrial-2.log` SHA-256 `5bf06f94850bc2762ca514cd89ecc036a7065ea67e03af1f69194ec90bc38164`(Jetson 시험 폴더, Git 제외).
- 두 번째 실행은 이전 29번째 차단을 넘어 105/640 목표(`seq 34182`)까지 전송한 뒤 `ABORT: TrialAbort: scheduler_overrun`; 새 목표 송신 중단. 113개 fresh feedback 로그에서 최대 팔 command−feedback 절대오차 Shoulder Lift 4.791°(`seq 31733`), gripper 2.199%p(`seq 34166`). 기록된 command·feedback 최소 URDF margin Elbow feedback 7.495°(`seq 32193`). URDF/tracking guard 또는 feedback timeout 발동 기록 없음. 물리 원인 또는 스케줄 초과의 구체 원인은 이 기록만으로 `NOT_VERIFIED`.
- 프로그램 `encoder_stillness=PASS` 뒤 사용자가 실제 팔 정지·접촉/걸림·사람 위험 없음 확인 및 `STOPPED` 입력, 로그 `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`. 별도 읽기 전용 follower 5회/0.5초 간격 자세 `(Pan +18.505,Lift −32.132,Elbow +82.505,Flex −32.220,Roll −7.692,gripper 20.135%)`가 모두 동일, disconnect 토크 변경 없음, LeLab inactive·두 포트 대상 PID 미검출. 사용자는 시연과 같은 방향으로 움직였고 버벅임도 보였다고 답했다. 4배 시간축 때문이라는 해석은 추정이며 원인은 `NOT_VERIFIED`. 640/640·grasp·전체 사이클은 미완료; 추가 송신 `NOT_RUN`. 코드·trajectory·calibration·time-scale·URDF·guard 변경 없음, 이슈 API `NOT_RUN`, 로컬 `NOT_COMMITTED/NOT_PUSHED`.

### scheduler_overrun 원인 확인·일정 한 곳 수정 — 오프라인만

- 기존 로그 target 95–105의 계획 송신시각(안전 시작 후 4배 초), fresh feedback의 `time.monotonic()` 및 target 95 대비 추가 지연은 아래와 같다. `send_action` 호출시각과 `settle_start/end`는 **기존 로그에 없으므로 정확한 값 미확인**이다. 모든 행에서 feedback은 한 번뿐이라 settle 재읽기/대기 0회였다.

  | target / seq | 계획 s | 실제 send 호출 | feedback monotonic | settle 재읽기 | target 95 대비 추가 지연 s |
  |---|---:|---|---:|---:|---:|
  | 95 / 34157 | 92.764902 | 미기록 | 1488654.040461 | 0 | 0.000 |
  | 96 / 34161 | 92.829373 | 미기록 | 1488654.127736 | 0 | 0.023 |
  | 97 / 34162 | 92.846194 | 미기록 | 1488654.214983 | 0 | 0.093 |
  | 98 / 34166 | 92.910144 | 미기록 | 1488654.301523 | 0 | 0.116 |
  | 99 / 34168 | 92.941776 | 미기록 | 1488654.385915 | 0 | 0.169 |
  | 100 / 34171 | 92.989554 | 미기록 | 1488654.473466 | 0 | 0.208 |
  | 101 / 34173 | 93.021753 | 미기록 | 1488654.562246 | 0 | 0.265 |
  | 102 / 34176 | 93.069336 | 미기록 | 1488654.648747 | 0 | 0.304 |
  | 103 / 34178 | 93.101402 | 미기록 | 1488654.736827 | 0 | 0.360 |
  | 104 / 34181 | 93.149325 | 미기록 | 1488654.825640 | 0 | 0.401 |
  | 105 / 34182 | 93.165423 | 미기록 | 1488654.913243 | 0 | 0.472 |

- 106번째 `seq 34184` 계획은 93.197328초였으나 송신 전 `scheduler_overrun` 차단. 95–105의 4배 목표 간격은 16–64ms인 반면 feedback 간격은 84–89ms로 거의 고정되어 0.472초 추가 지연이 쌓였다. 앞선 8개 settle 추가 feedback-span 합은 0.757974초; 기존 코드의 `hold_extension`은 이 settle 구간만 일정에 더하고 일반 send/read/안전검사 소요를 제외했다. 이 밀집 구간에는 settle이 없어서 원인은 속도 배율이나 Elbow 보정이 아니라 절대 deadline 기준과 처리시간의 불일치다. 현장 버벅임이 이 불일치 때문인지는 동기 영상/송신 호출시각 부재로 확정하지 않는다.
- `scripts/replay_c_red_approach.py`의 일정 부분만 바꿔 다음 deadline을 **직전 목표의 feedback·모든 안전검사·로그 완료 시각 + 원래 4배 목표 간격**으로 재기준화한다. 기존 0.5초 스케줄 차단·모든 URDF/tracking/freshness/settle 검사는 그대로다. 목표를 건너뛰거나 밀린 점을 몰아서 보내지 않는다. 후속 live 진단에서 정확히 확인할 수 있도록 nominal/유효 deadline, `send_action` 호출시각(실제 버스 wire timestamp는 아님), feedback read 시작/완료, settle 재읽기/시간, 누적 지연을 timing JSON으로 남긴다.
- 로컬 targeted unittest 첫 `tests.test_replay_c_red_approach` 모듈 지정은 import 경로 오류였고 discover 재실행 12/12 PASS. 실제 후보 640개/4배 간격을 87ms 가짜 bus로 모의해 640/640, no-catch-up 간격 PASS; nominal 269.000초 대비 가짜 완료 324.680초로 물리 실기 duration은 미확인이다. Jetson 직접 scp는 인증 실패, 기존 SSH에서 백업 SHA `ae430909...a82ea7` 생성 후 원격 `patch --dry-run`/적용·로컬 SHA `782a6cd3e5a7142163cf3ae1c5caac48f7bc2945c803d229e6c1c9e798a43540` 일치 확인. 설치 Python 문법 및 `--time-scale 4` dry-run 640개/nominal 269.0초/URDF 최소 margin 7.582° PASS, serial·모터 명령 0회. adapter/trajectory/calibration/URDF/tracking guard/time-scale 미변경; 새 live `NOT_RUN`, 이슈 API `NOT_RUN`, 로컬 `NOT_COMMITTED/NOT_PUSHED`.

## 2026-10-10 방향 Elbow guard 배포와 수동 복귀 중단

- Jetson 원본/백업 `teleoperate.py` SHA `a5ac255d15cbba05d0c095ec927106c303ef50790291566fb29f383cb8102576` 일치. 방향별 Elbow 패치를 한 번 적용한 뒤 사용자의 중복 실행으로 역적용된 최초 실수를 포착했고, 원본 해시 선행검사·`--forward`로 재적용해 예상 설치 SHA `e4f6462cb92cefd882b5b2f2076b315ecd8ae8537f00b5b4a33a69d316b9bb6a`를 확인했다. 설치 보조 모듈 SHA `c08806d55c5f33b7e00d37f139ae402e4761a7f8176d112e6cdcb732f82ca7ef`. 설치 Python 문법·숫자 가짜 입력 PASS; LeLab 세 제어 작업 inactive에서 서비스 재시작 뒤 health/teleop inactive 확인. trajectory/calibration/time-scale/URDF/replay safety 로직 불변.
- 설치 Python dry-run: approach 640/640·nominal 269초·URDF min margin 7.582°, grasp 459·transport 141·place 199 목표 각각 가짜 버스 PASS. 모두 `--live` 없이 serial·motor 명령 0회. 후속 phase는 실제 물리 추종·충돌을 검증한 결과가 아니다.
- 현장 C 제거·빈 gripper·비접촉·정지 확인 후 읽기 전용 정렬: leader Elbow +86.857143°/follower +87.076923°, 시작 차이 `E=+0.219780°`; leader Wrist Flex −29.802198°/follower −31.164835°, `W=−1.362637°`. 리더 대응 safe_start Elbow +32.220220°, Flex +6.900637°. 5축 ±2° 정렬, viewer 종료·두 USB 포트 해제 후 LeLab 텔레옵 시작. 8032 fresh stream 확인. 수동 복귀 첫 이동에서 방송 Elbow +88.04°→+88.75° 증가·방송 단절. 설치 guard 로그는 current +88.747°, requested +88.835°, delta +0.088°, upper margin 1.253°, `toward_upper_limit`; 명령 전에 차단됐다. 이는 보호선 의도대로이며 guard 완화/같은 조건 재시도 없음. 해당 목표 상승이 리더 실제 조작 방향·시작 후 드리프트 중 무엇 때문인지는 `NOT_VERIFIED`.
- 사용자 종료·실제 팔/그리퍼 정지·비접촉 확인, API teleop inactive. 별도 read-only follower 최종 `(Pan +20.967,Lift −42.769,Elbow +89.275,Flex −30.989,Roll +2.857°,gripper 22.032%)`가 반복 동일, Elbow URDF 상한까지 0.725° 여유. 리더는 팔로워와 큰 차이로 재시작 정렬 상태가 아니다. viewer PID `538464`만 종료하고 두 USB 포트 해제 확인. 안전상 safe_start 복귀와 approach/grasp/transport/place live는 `NOT_RUN/BLOCKED`; 새로운 모터 송신·torque 변경 없음. 비밀정보·원본 로그 Git 제외, 이슈 API `NOT_RUN`, 로컬 변경 `NOT_COMMITTED/NOT_PUSHED`.

### 2026-10-10 상한 방향 작은 요청의 세션 종료를 HOLD로 변경

- 설치 `teleoperate.py`와 guard를 각각 `.before-hold-20261010`으로 백업하고 기존 SHA `e4f6462cb92cefd882b5b2f2076b315ecd8ae8537f00b5b4a33a69d316b9bb6a` / `c08806d55c5f33b7e00d37f139ae402e4761a7f8176d112e6cdcb732f82ca7ef`를 대조했다. LeLab 세 제어 상태 inactive에서 `patch --dry-run --fuzz=0` 뒤 한 줄 호출부 패치를 적용, 설치 결과 SHA `e3ac75258f221251d013c5b95d23cffd6bdf96459aa6418a2c8e224839028d89` / `2e5ffa308e97ff7b6392d5f7497ec4b97078b166c015f15ceb6d9137c0118362` 확인. trajectory, calibration, URDF, replay 코드는 변경하지 않았다.
- 상한 근처의 `88.747→88.835°`는 `blocked_toward_upper_limit`, `action=HOLD`를 송신 전에 기록하며 `send_action` 0회다. 이어 `88.747→88.0°`, `88.0→86.0°`는 `SEND`다. 하한 대칭 HOLD/탈출, URDF 초과 ABORT, 연속 요청 목표 2° 초과 ABORT, feedback·전송 오류의 예외 유지가 로컬 10/10 및 Jetson 설치 Python 가짜 버스에서 확인됐다. HOLD 중 이전 송신 목표를 갱신하지 않는다. 실제 물리 정지/추종은 이 시험으로 검증되지 않았다.
- 설치 Python 문법 검사 PASS. 비활성 LeLab 서비스를 재시작해 초기 8000 연결 거부 뒤 health `ok`, teleop inactive를 확인했다. read-only 8031 뷰어에서 follower `(Pan +20.967,Lift −42.769,Elbow +89.275,Flex −30.989,Roll +2.857°,gripper 22.032%)`가 반복 동일, leader `(−6.549,−98.022,+97.407,+42.462,+3.780°,gripper 21.899%)`로 시작 정렬에 부적합하다. Elbow 상한 여유 0.725°다. viewer PID `538710`은 종료해 8031 LISTEN 해제·두 USB 포트 대상 점유 PID 없음(`lsof`의 무관한 mount 경고) 확인. 사용자 현장 정렬·안전 확인 전 LeLab 시작, safe_start 복귀, 자동 approach는 `NOT_RUN/BLOCKED`. 모터 송신·torque 변경 0회; 원본 로그·비밀정보 Git 제외, 이슈 API `NOT_RUN`, `NOT_COMMITTED/NOT_PUSHED`.

### 2026-10-10 리더 정렬 뒤 첫 LeLab 시작 — hard URDF 차단

- 사용자 현장 팔·그리퍼 정지/비접촉/C 제거 확인. LeLab teleop/recording/inference inactive, 두 USB 포트 점유 PID 없음(`lsof`의 mount 경고). read-only 8031 viewer에서 follower `(Pan +20.967,Lift −42.769,Elbow +89.275,Flex −30.989,Roll +2.857°,gripper 22.032%)`를 새로 읽었다. 리더만 조정해 최종 차이는 `(Pan +0.967,Lift +0.923,Elbow +1.275,Flex −1.011,Roll −0.484)°`로 모두 ±2° 이내. 사용자가 리더 고정·경로 여유·즉시 종료 준비를 확인했고 viewer PID `538747`을 종료해 두 포트를 해제했다.
- 사용자가 LeLab을 직접 한 번 시작해 3초 고정·실제 팔 점프/접촉 없음이라고 보고했다. 그러나 서버 API는 이미 inactive, 두 포트 점유 PID 없음. 설치 서비스 로그의 이번 시도 첫 guard 기록(16:07:49 KST)은 `current=+90.154`, `requested_target=+90.154`, `delta=0`, `upper_margin=−0.154`, `action=ABORT`, `reason=feedback_outside_urdf`. `guarded_elbow_send`는 `send_action` 전에 예외를 냈다. 이는 작은 상한 방향 `HOLD`가 아니라 기존 URDF hard failure다. 정렬 viewer의 +89.275°에서 시작 시 +90.154°로 변한 직접 물리 원인/정확한 시점은 `NOT_VERIFIED`; LeLab 연결 과정의 torque/기존 목표 영향도 입증되지 않았다.
- 사용자가 종료·실제 정지·비접촉을 재확인했다. 별도 read-only viewer 두 번의 follower raw `(2340,1471,3011,1728,1897,773)`/degree `(Pan +20.967,Lift −42.505,Elbow +90.330,Flex −30.989,Roll +2.857°,gripper 22.032%)`는 동일하며 Elbow가 URDF +90°보다 0.330° 높다. leader는 종료 뒤 큰 불일치 상태. viewer PID `538814` 종료·8031 LISTEN 해제, LeLab inactive·두 포트 대상 점유 PID 없음(`lsof` mount 경고). hard limit/코드 변경 금지 범위에서 텔레옵 재시작·safe_start 복귀·approach 640/640은 `NOT_RUN/BLOCKED`; 수동으로 follower를 재배치하거나 torque를 변경하지 않았다. 새 물리 복구 방법·승인 없이 추가 구동 없음. 원본 로그/비밀정보 Git 제외, 이슈 API `NOT_RUN`, `NOT_COMMITTED/NOT_PUSHED`.
