# SO-101 약통 자율 분류

SO-101과 Orbbec Astra RGB-D를 이용해 알려진 빈 약통/모형 A·B·C 중 하나를
사용자가 지정한 고정 바구니로 분류하는 연구용 프로토타입입니다. 실제 약품의 종류,
처방 또는 복약 방법을 판단하지 않습니다.

현재 활성 애플리케이션 진입점은 하나입니다.

```bash
python3 -m medicine_sorter --help
```

기본 `status`, `validate-config`, `mock-run`은 camera·serial·모터를 열지 않습니다.
전체 좌표 기반 `live`는 새 환경 검증 전에 fail-closed합니다. 대신 아래의
`teach`/`run`은 T_B_W·IK를 쓰지 않고, 고정 칸과 티칭 관절 자세만 재생하는
제한 데모 경로입니다.

## 현재 지원 범위

- 한국어 단일 작업 명령: 큰/중간/작은 약통 하나와 빨강/초록/파랑 목적지
- 명시한 목적지가 기존 A→파랑, B→초록, C→빨강 기본 규칙보다 우선
- 저장된 mock scene을 이용한 전체 상태 흐름
- 설정 schema와 새 환경 보정 준비 상태 검사
- 중복 작업 차단, stale scene, RGB/depth 불일치, 후보/marker 모호성 오류
- 내부 길이 `mm`, 각도 `degree`; `T_A_B`는 `p_A = T_A_B × p_B`

현재 YOLO 모델은 `white_medicine_bottle_model` 단일 클래스입니다. A/B/C 구분은
실물 정의를 다시 확인할 때까지 human-verified known-object 범위이며, 처음 보는 약통의
물리 크기 자동 판정으로 표현하지 않습니다.

## 실행

설정 상태 확인:

```bash
python3 -m medicine_sorter --config configs/system.example.json status
```

실제 follower 상태만 한 번 읽는 명령:

```bash
python3 -m medicine_sorter \
  --config configs/system.example.json \
  robot-status
```

이 명령은 카메라 보정이나 분류 경로를 요구하지 않습니다. 설정된 follower 후보
`/dev/ttyACM1`의 USB serial이 `5AE6058306`인지 먼저 대조하고, 포트가 비어 있을 때만
`Present`, `Goal`, `Torque_Enable`, `Moving`, `Present_Temperature`를 raw로 각각 한 번
읽습니다. 일반 `SO101Follower.connect()`는 사용하지 않으며, 상태 변경 API를 차단한
뒤 `FeetechMotorsBus.connect(handshake=False)`로 연결하고
`disconnect(disable_torque=False)`로 종료합니다. read 요청 자체는 serial 패킷을
보내지만 Goal, Torque, config를 쓰지 않습니다. 이 경로의 Jetson 설치본 및 실제 장비
시험은 아직 `NOT_RUN`입니다.

저장 mock scene 전체 흐름:

```bash
python3 -m medicine_sorter \
  --config configs/system.example.json \
  mock-run \
  --scene configs/mock_scene.example.json \
  --command "큰 약통 하나를 빨간 바구니에 넣어"
```

설정 schema 검사:

```bash
python3 -m medicine_sorter --config configs/system.example.json validate-config
```

### 고정 칸 티칭 데모

`ID7=C`, `ID8=B`, `ID9=A`로 유형만 구분하고 목적지는 실행 시
`--rule C=green B=red A=blue`처럼 정합니다. A/B/C 각각 red/blue/green
어느 바구니든 지정할 수 있고, 여러 약통을 같은 바구니에 지정해도 됩니다.
규칙에 없는 약통은 건너뜁니다. `--rule`을 생략하면 config의
`destination_rules`를 기본값으로 쓹니다. 좌표 변환을 쓰지 않고 640×480
`undistorted_full_frame`의 픽셀 ROI로 slot1–3을 판정합니다. 현재 ROI는
`provisional_verify_in_dry_run`이므로 실물 프레임 dry-run에서 반드시 칸 판정을
확인해야 하며, 자동 실행은 차단되고 `--step`만 허용됩니다.

```bash
python3 -m medicine_sorter --config configs/system.example.json teach
python3 -m medicine_sorter --config configs/system.example.json teach --resume
python3 -m medicine_sorter --config configs/system.example.json teach --only gripper_closed_A gripper_closed_B gripper_closed_C
python3 -m medicine_sorter --config configs/system.example.json teach --only finish
python3 -m medicine_sorter --config configs/system.example.json roi-preview --output /tmp/fixed-demo-roi.png
python3 -m medicine_sorter --config configs/system.example.json run --dry-run --rule C=green B=red A=blue
python3 -m medicine_sorter --config configs/system.example.json run --step --rule C=green B=red A=blue
python3 -m medicine_sorter --config configs/system.example.json run --step --warm-start-once --rule A=green
python3 -m medicine_sorter --config configs/system.example.json run --auto --rule C=green B=red A=blue
python3 -m medicine_sorter --config configs/system.example.json web --port 8030
python3 -m medicine_sorter --config configs/system.example.json motion-compare --from-pose home --to-pose finish
```

`roi-preview`는 8020의 `/manual-frame.json`을 정확히 한 번 읽어 같은 응답의
snapshot과 JPEG를 사용합니다. `slot1/2/3` 사각형, 모든 ArUco 중심, ID7–9의
A/B/C 및 현재 칸 판정을 PNG에 그립니다. 칸 밖인 중심은 빨간색 `OUTSIDE`로
표시하고 JSON에도 중심 pixel과 판정을 출력합니다. 이 명령은 camera HTTP read와
PNG 저장만 하며 LeRobot을 import하거나 robot serial을 열지 않습니다.

`teach`는 한 follower/leader session에서 relative-start로 green above/release를
포함한 기본 18개 자세를 순서대로 저장합니다. Enter를 누를 때마다
`configs/fixed_demo_poses.partial.json`에 바로 저장하며, 중단됐다면
`teach --resume`으로 다음 자세부터 이어갑니다. 기본 파일을 만든 뒤
`teach --only gripper_closed_A gripper_closed_B gripper_closed_C`로 약통 크기별
닫힘 값을 추가하거나 해당 값만 다시 저장할 수 있습니다. 이때 기존 18개 자세는
보존되고 각 선택 자세를 저장할 때마다 최종 pose 파일이 atomic replace됩니다.

실행에서 그리퍼 값은 `gripper_open`과 현재 약통 종류의
`gripper_closed_A/B/C`에서만 바뀝니다. 기존 `gripper_closed`는 pose 파일 호환을
위해 남아 있지만 run에서는 사용하지 않습니다. home·slot·basket 자세에서는 팔
5축만 재생하고 직전 그리퍼 상태를 유지합니다. 닫기 후 물체 때문에 실제 위치가
목표보다 2 percentage point 이상 앞에서 정지하면, 원래 목표를 계속 밀지 않고
실제 위치에서 닫는 방향 1 percentage point만 더한 Goal로 재고정합니다.

Overload·Overheat 같은 servo status나 55°C 초과가 관측되면 해당 motor 이름·ID,
register, status bit 또는 실제 온도, 드라이버 원문을 출력하고 다음 단계로 진행하지
않습니다. motion이 이미 arm된 상태라면 Ctrl+C와 같은 fresh Present raw→Goal raw
현재 위치 HOLD를 한 번 요청합니다. follower는 fresh Present raw를
Goal raw로 한 번 복사합니다. 이 Goal write가 Feetech Torque를 자동으로
ALL ON하면 `AUTO_ENABLED_BY_GOAL`로 인정하고 추가 Torque write를 하지 않습니다.
여전히 ALL OFF면 Torque ON을 한 번만 쓰며 mixed state는 중단합니다.
일반 robot `connect/configure`를 우회하고 종료는
`disconnect(disable_torque=False)`로 처리합니다. Ctrl+C는 fresh Present raw를
Goal로 한 번 복사해 **현재 위치 유지**를 요청하며 Torque OFF가 아닙니다.

실물 `run --step`의 약통 1개, 2개, 3개와 3개 동시 분류 성공을 근거로 현재 고정
배치를 `A=slot1, B=slot2, C=slot3` 및 `slot_roi_status=verified`로 기록했습니다.
`finish`는 전체 분류가 끝난 뒤 마지막 `home` 다음에 한 번만 실행되는 팔 5축
마무리 자세입니다. 기존 자세 파일은 유지한 채 `teach --only finish`로 추가합니다.
그리퍼는 직전 열린 값을 유지합니다.

`run --auto`는 계획·단계별 Enter 없이 선택된 약통마다 기존 11단계를 연속 재생하고,
모든 약통 처리가 끝나면 `finish`를 한 번 더 실행합니다.
단, 매 실행마다 새 Astra 프레임에서 ID9(A)·ID8(B)·ID7(C)가 각각 기대 칸에 있는지
먼저 검사하고, 포트를 연 뒤 어떤 Goal/Torque write보다 먼저 6개 모터 온도가 모두
`50°C 미만`인지 확인합니다. 배치나 온도 조건이 다르면 동작을 시작하지 않습니다.
보간 명령 주기는 0.05초(20Hz)이며 기존 속도·가속도·관절당 2° 최대 스텝은
유지합니다. `--warm-start-once`는 감독 `--step` 한 번에서만 50–51°C 시작을
허용하며, 52°C 이상 시작 차단과 실행 중 55°C hard stop은 유지합니다. 웹 자동
실행에서는 이 완화를 사용할 수 없습니다.

### Motion smoothing A/B

기존 pick-and-place의 티칭 pose, IK, calibration, TCP와 `run`/web motion은
`original`로 보존됩니다. 현재 공간 보간도 이미 모든 관절에 같은
`s(t)=3t²-2t³`를 쓰지만, original executor는 각 serial write 뒤 상대적으로
sleep해 write/read 지연이 다음 command interval에 누적될 수 있습니다. 새
`smooth` 후보는 같은 시작·종료 pose와 같은 cubic profile을 절대시간 deadline으로
샘플링하고, 지난 tick은 몰아서 보내지 않고 건너뜁니다. 관절당 2°/gripper 2 pp는
제거하지 않고 모든 관절 비율을 함께 줄이는 hard cap으로 유지합니다. 최소 각도
step, servo gain, Torque, calibration, IK는 변경하지 않습니다.

`motion-compare`는 Jetson의 기존 ignored pose JSON을 읽어 10Hz 성공 baseline과
20Hz cubic 후보 및 20Hz quintic `10t³-15t⁴+6t⁵` 후보의 command count, delta,
최대 step, 방향 반전을 비교하지만 robot serial은 열지 않습니다. quintic은 오프라인
후보일 뿐 live motion에는 아직 연결하지 않습니다. 기존 성공 실행에는 cycle별
command/Present/Goal/Moving 원본 로그가
없으므로 계획값을 실측값으로 표현하지 않습니다.

실제 검증은 전체 pick-and-place가 아니라, 별도로 확인한 짧은 free-space 두 pose
사이 한 구간만 `motion-test`로 수행합니다. 현재 자세가 `--from-pose`의 팔 5축과
각 1° 이내가 아니면 motion 전에 중단합니다. 로그는 Git에서 제외된
`.local/fixed-demo-motion/` 아래의 새 JSONL에만 저장하며 기존 파일을 덮어쓰지
않습니다. 각 cycle에 command timestamp/position, Present, Goal, Goal−Present,
Moving을 기록합니다. 이 명령은 현장 start/end pose가 확정되기 전에는 실행하지
마세요.

```bash
python3 -m medicine_sorter --config configs/system.example.json motion-test --from-pose FROM --to-pose TO --profile smooth --log .local/fixed-demo-motion/smooth-001.jsonl --step
python3 -m medicine_sorter --config configs/system.example.json motion-compare --from-pose FROM --to-pose TO --actual-log .local/fixed-demo-motion/smooth-001.jsonl
```

fresh read-only 상태로 확인한 현재 자세에서 재배치 없이 짧은 endpoint 하나로 가는
첫 ORIGINAL 시험은 `--from-current`를 사용합니다. 이 모드는 HOLD 직후의 actual
Present를 시작점으로 고정하며, original baseline은 0.1초 relative cadence를
유지합니다. JSONL에는 absolute planned timestamp, actual write timestamp와 interval,
normalized/raw Goal·Present, Torque, error, Moving이 함께 저장됩니다. 완료 출력은
encoder raw 변화만 확인하고 외부 링크 운동은 사용자 영상 확인 전 PASS로 처리하지
않습니다. 실제 로그 분석에는 관절별 Present 속도 근사치의 평균·표준편차·최대값과
속도 부호 반전 횟수도 포함합니다.

```bash
python3 -m medicine_sorter --config configs/system.example.json motion-test --from-current --to-pose finish --profile original --log .local/fixed-demo-motion/original-current-finish-001.jsonl --step
```

`web --port 8030`은 `0.0.0.0`에 바인딩되는 같은 네트워크용 버튼 UI입니다. A/B/C별
red/blue/green/skip, 세 프리셋, 카메라 기반 계획 확인, 자동 실행, 현재 단계·온도,
큰 빨간 정지 버튼을 제공합니다. 정지는 보간 중에도 감지해 Ctrl+C와 같은 current
HOLD를 요청합니다. 실행 중에는 다른 조작을 비활성화하고 동시에 두 실행을 만들지
않습니다. 브라우저가 끊겨도 이미 시작한 한 번만 끝까지 수행하며 자동 반복은 없습니다.
로봇 session은 실행 버튼을 눌렀을 때만 열고 끝나면 Torque를 끄지 않은 채
`disconnect(disable_torque=False)`로 닫습니다.

sudo/lsof/fuser 포트 조회는 이 경로에 없습니다. 대신 연결 전에 config의
follower serial `5AE6058306`과 leader serial `5AE6085272`를 현재
`/dev/ttyACM*`의 sysfs serial에서 찾아 역할을 자동 선택합니다. 둘 중 하나를 찾지
못하거나 serial/port가 충돌·중복되면 어떤 serial도 열기 전에 중단합니다. 그 뒤
사용자 process lock과 열린 serial FD의 `TIOCEXCL`로 중복 실행을 차단합니다. 다른
컨트롤러는 실행 전 정상 종료해야 합니다.

`live` 명령은 존재하지만 현재 예제 설정에서는 의도적으로 차단됩니다. 출력은 실패
항목, 관측값, 필요한 조건과 다음 조치를 함께 제공합니다. 기존의 실험별 승인 문자열,
one-shot ticket, recovery entrypoint는 새 애플리케이션에서 사용하지 않습니다.

## 테스트

새 활성 코어:

```bash
python3 -m unittest discover -s tests -p 'test_sorter_*.py' -v
```

전체 hardware-free 발견 시험:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

mock 통과는 실제 카메라나 실제 로봇 성공을 의미하지 않습니다.

## 구조

- `medicine_sorter/command.py`: 규칙 기반 한국어 명령 해석
- `medicine_sorter/vision.py`: 저장 scene 검증, 대상·바구니 선택
- `medicine_sorter/geometry.py`: 좌표 방향과 mm 단위 변환
- `medicine_sorter/robot.py`: 상태 변경의 유일한 애플리케이션 제어 계층
- `medicine_sorter/workflow.py`: 한 번에 한 작업의 단계 흐름
- `medicine_sorter/cli.py`: 단일 CLI
- `configs/system.example.json`: 새 환경에서 채울 설정과 보정 상태

카메라 보정, 데이터 수집, 모델 평가 도구와 일부 과거 경로 재현용 스크립트는
`scripts/`에 남아 있지만 지원되는 분류 실행기가 아닙니다. 새 오류에 이 파일들을
연결하거나 새 recovery entrypoint를 추가하지 않습니다. 이번에 제거한 live/recovery
실행기는 Git 이력과 로컬 ref `refs/backup/pre-refactor-20261016`에서 복구할 수 있습니다.

## 새 환경에서 필요한 실측

1. follower 관절 calibration과 장비 식별
2. 현재 해상도의 camera intrinsic
3. ID0–3 실제 크기·배치와 camera↔table
4. table↔robot-base 독립 검증점
5. 실제 finger 접촉점 TCP와 A/B/C 파지 높이
6. ID4/5/6 실제 부착 상태와 바구니 opening·테두리
7. 약통을 포함한 전체 중간 경로와 대기 복귀 경로

자세한 현재 판정은 `docs/STATUS.md`, 구조와 이전 실행기 분류는
`docs/SYSTEM_ARCHITECTURE.md`를 확인해 주세요.

## 안전 경계

- 실제 모터, Torque, USB 재연결은 별도의 구체적인 현장 시험 승인 전에는 실행하지 않습니다.
- UI·명령 파서·비전 모듈은 serial에 직접 쓰지 않습니다.
- Stop, 현재 위치 유지, Torque OFF, disconnect, 전원 차단은 서로 다른 동작입니다.
- 데이터셋, 모델, 보정 원본, 원시 로그와 인증정보는 Git 정리 대상이 아닙니다.
