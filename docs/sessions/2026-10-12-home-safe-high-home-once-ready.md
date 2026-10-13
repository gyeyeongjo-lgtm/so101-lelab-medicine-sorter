# 2026-10-12 HOME→SAFE_HIGH→HOME 1회 dry-run 준비

## 범위

- 기록된 `HOME`과 `SAFE_HIGH`를 기준으로 자동 왕복 **1회만** 준비했다.
- 실제 하드웨어 실행은 `NOT_RUN/NOT_AUTHORIZED`다.
- 3회 반복, grasp/place, Torque 변경, gain/register 변경은 수행하지 않았다.
- `Present_Load`는 signed diagnostic logging 전용이며 numeric PASS/FAIL gate로 사용하지 않는다.
- full-mesh/environment collision은 계속 `NOT_VERIFIED`다.

## 구현

- 기존 `scripts/safe_home_return.py`를 재사용해 왕복 순서를 다음으로 고정했다.
  1. `SAFE_HIGH_EXCEPT_PAN`
  2. `PAN_ALIGNMENT`
  3. `HOME_EXCEPT_PAN`
  4. `HOME_PAN_ALIGNMENT`
- `scripts/live_home_safe_high_home_once.py`는 기존 follower transport, exclusive bus lease, settle 검증, 저장 pose/config, GRASP TCP와 URDF FK를 재사용하는 thin runner다.
- 기본 모드는 dry-run이며 live는 scope `home_safe_high_home_once`와 정확한 사용자 문구 `RUN HOME SAFE_HIGH HOME ONCE`가 모두 있어야 시작한다.
- 각 waypoint는 fresh feedback, intended-direction movement, commanded movement 50% 이상, non-commanded drift 1° 이하, `Moving=0`, Temperature `<=55°C`, calibration bounds, table/self-collision proxy를 검사한다.
- Elbow는 모든 waypoint에서 Goal/Present/error/Moving/Load diagnostic을 별도 기록한다.
- 첫 실패 시 후속 target 생성을 중단하고 현재 Goal/torque를 유지한 채 STOP 검증으로 이동한다. 예외에서 자동 HOME recovery를 실행하지 않는다.

## 오프라인 결과

```text
HOME→SAFE_HIGH waypoint count = 78
SAFE_HIGH→HOME waypoint count = 78
total waypoint count = 156
max per-joint step = 1.982648930°
predicted GRASP TCP Z range = 99.167465 → 364.853599 mm
minimum table proxy margin = +44.508465 mm
minimum self-collision centerline proxy = 55.827804 mm
minimum calibration servo margin = 19.604396°
outbound TCP Z monotonic increase = true
return TCP Z monotonic decrease = true
final HOME exact in plan = true
offline_constraints_pass = true
full mesh/environment = NOT_VERIFIED
hardware command = 0
```

최종 HOME verification tolerance는 Pan/Flex/Roll `0.5°`, Lift/Elbow `1.5°`, gripper `1.0 pp`다. 기존 HOME 기록에서 Elbow Goal-Present가 `-3.692308°`였으므로 tolerance를 확대하지 않고 실제 1회 시험에서 최종 수렴 여부를 확인해야 한다.

## 테스트

- 로컬 `unittest`: `10/10 PASS`
- 로컬 `py_compile`: `PASS`
- 로컬 dry-run: `PASS`, `no port opened; no send_action`
- `git diff --check`: `PASS`

## Jetson 배포 및 dry-run

- 기존 `/home/jetson3/so101-approach-trial/`은 수정하지 않았다.
- 새 전용 디렉터리 `/home/jetson3/so101-home-roundtrip-20261012/`에 runner, 기존 의존 모듈, 기록 pose/config만 배포했다.
- 첫 dry-run은 `ModuleNotFoundError: safe_escape_verification`으로 실패했다. 실제 포트나 모터에는 접근하지 않았다.
- 누락 의존 모듈 하나를 같은 전용 디렉터리에 추가한 뒤 설치 Python과 설치 URDF로 `py_compile`과 dry-run을 재실행해 PASS했다.
- Jetson 최종 dry-run 출력도 `78/78`, max step `1.982648930°`, Z `99.167465…364.853599 mm`, table `+44.508465 mm`, self proxy `55.827804 mm`, servo margin `19.604396°`, `offline_constraints_pass=true`, `hardware_command=0`으로 로컬과 일치했다.
- 핵심 파일 SHA256:
  - `live_home_safe_high_home_once.py`: `e6389849f5ccacd79d90887cdc5831db0c5f7491b8b677a79f72293d198fc713`
  - `safe_home_return.py`: `53c0724ff55618b694c8ccc294e4c17afbe06b71d6b79b0b599e693bf006c962`
  - `poses.yaml`: `166ec371088e6976edda3805b787257b56a5bcd4ccb1b80051ec20e14f999793`

## 종료 상태

```ini
HOME_SAFE_HIGH_HOME_ONCE=NOT_RUN/NOT_AUTHORIZED
THREE_ROUND_TRIPS=NOT_RUN/PROHIBITED_UNTIL_FIRST_PASS
hardware_command=0
Goal_write=0
Torque_change=0
serial_port_open=0
physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED (사용자 기준선)
full_mesh_environment=NOT_VERIFIED
git=NOT_COMMITTED/NOT_PUSHED
```
