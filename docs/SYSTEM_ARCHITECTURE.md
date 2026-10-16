# 단일 약통 분류 실행 구조

## 활성 경로

```text
python -m medicine_sorter
  → command.parse_sort_command
  → vision.load_scene / target·basket selection
  → workflow.SorterApplication
  → robot.RobotController
  → mock adapter 또는 향후 검증된 SO-101 adapter
```

애플리케이션에서 하드웨어 상태 변경을 요청할 수 있는 계층은
`RobotController` 하나입니다. 명령 해석, 비전, 좌표 모듈은 LeRobot과 serial을
import하지 않습니다. import, `status`, `validate-config`, `mock-run`은 장치를 열지
않습니다.

## 책임

| 책임 | 구현 |
| --- | --- |
| 단일 진입점과 모드 | `medicine_sorter/cli.py` |
| 한국어 명령 → 구조화 작업 | `medicine_sorter/command.py` |
| 현재 관측 schema·freshness·대상 선택 | `medicine_sorter/vision.py` |
| `T_A_B`, mm/degree 규약 | `medicine_sorter/geometry.py` |
| 상태 변경 통로·lifecycle | `medicine_sorter/robot.py` |
| 한 작업 상태 흐름·중복 실행 차단 | `medicine_sorter/workflow.py` |
| 환경/보정 readiness | `medicine_sorter/config.py` |

Readiness는 장치 전체를 한 번에 여는 스위치가 아니다. `supervised_teaching`은
아직 존재하지 않는 경로를 선행 조건으로 요구하지 않고, 관절 보정·Torque lifecycle·
명시적 live enable만 요구한다. `fixed_demo`는 카메라 좌표계와 무관한 **티칭된 고정
관절 경로**용이며 검증된 관절 보정·TCP·경로·Torque lifecycle을 요구한다.
`full_sort`만 camera↔table, table↔robot, 바구니 좌표까지 모두 요구한다.

## 기존 gate 분류

| 기존 유형 | 판정 | 새 구조 |
| --- | --- | --- |
| 고정 포트·중복 소유자 | A 유지·통합 | 실제 adapter 연결 전에 한 번 검사할 제어 계층 책임 |
| 관절 범위·step·온도·Moving | A 유지·통합 | 실제 adapter 명령 검사와 상태 검사 |
| 좌표 단위·transform 방향 | A 유지·통합 | config/geometry에서 mm·degree와 `T_A_B` 명시 |
| 오래된 reference exact match | B 현재 검사로 대체 | scene/config ID, timestamp, fresh state 사용 |
| 실험별 승인 문자열·ticket | C 제거 | 실제 live 시험 한 건의 범위 승인으로 대체 예정 |
| contact release/HOLD/gripper 전용 실행기 | C 제거 | 정상 작업 lifecycle 또는 구체적 감독 시험으로 통합 |
| unknown Torque writer | D 미확정 | 확인된 관측으로 보존; 새 live lifecycle 검증 전 차단 |

## 제거한 실행기

다음 파일들은 특정 실패를 우회하거나 한 번의 실험을 실행하기 위한 독립 entrypoint로,
새 분류 lifecycle과 중복되어 삭제했습니다. 데이터·모델·보정·세션 기록은 삭제하지
않았고 Git 이력 및 `refs/backup/pre-refactor-20261016`에서 복구할 수 있습니다.

- `atomic_hold_restore.py`
- `contact_release_only.py`
- `current_hold_ui_teleop.py`
- `live_gripper_close_to_20_only.py`
- `single_session_demo.py`
- `supervised_teaching_from_current_hold.py`
- `sync_follower_goal_to_present_only.py`
- `torque_writer_diagnostic.py`

각 전용 테스트도 함께 제거했고, 새 구조의 command/config/geometry/vision/workflow/control
lifecycle 테스트로 대체했습니다. 과거 실기 결과와 실패 원인은 `docs/sessions/`에 그대로
남습니다.

## 현재 완료 수준

- 코드 구조 구현: 완료
- mock scene 전체 흐름: 구현 및 단위 검증
- 저장 실제 영상/실제 모델 통합: 미검증
- 새 환경 카메라: 미검증
- 새 환경 로봇: 미검증
- 실제 grasp/place/return: 미검증

`configs/system.example.json`은 실측값을 대신하지 않습니다. 선택한 작업의 calibration
항목이 `verified`이고 live enable이 명시되기 전 실제 동작은 포트 연결 전에
차단됩니다. 고정 티칭 데모와 전체 카메라 기반 분류는 서로 다른 readiness를 사용합니다.
예제의 바구니 ID4/5/6은 기존 배치를 기록한 초깃값일 뿐입니다. 로더는 색별
marker ID가 유효하고 서로 다른지만 검사하며, 실제 부착 상태를 확인한 후
설정과 검증 데이터를 함께 갱신해야 합니다.

## 다음 실제 adapter 원칙

새 adapter는 다음 동작을 분리해야 합니다.

1. 고정 장비 식별과 단독 포트 획득
2. port-only connect
3. Present/Goal/Torque/Moving/Temperature 읽기
4. 명시적인 motion prepare
5. 검증된 Goal 전송
6. 새 명령 중단
7. `disconnect(disable_torque=False)` 등 명시적 종료 정책

일반 `SO101Follower.connect()`가 `configure()`와 torque-disabled context 종료 시
Torque enable을 수행하는 것은 확인됐습니다. 그러나 과거 single-session 경로에서 관측한
예상 밖 Torque ON의 원인으로 확정된 것은 아닙니다. 새 adapter에서 실제 시험하기 전
connect/write call stack과 패킷 종류를 다시 검증해야 합니다.
