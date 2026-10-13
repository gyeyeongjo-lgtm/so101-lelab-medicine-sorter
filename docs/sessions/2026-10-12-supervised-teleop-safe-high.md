# 2026-10-12 supervised teleop recovery → SAFE_HIGH

## 결과

```ini
SAFE_HIGH = RECORDED
HOME = NOT_RECORDED
physical_stop = FEEDBACK_AND_HUMAN_CONFIRMED
full_mesh_environment = NOT_VERIFIED
```

사용자 감독하에 낮은 자세에서 SAFE_HIGH로 이동했다. 사용자의 `SAFE_HIGH REACHE`는 활성 실행 문맥의 `SAFE_HIGH REACHED`로 해석했다. 도달 직후 텔레옵을 명시적으로 중지했고, follower Present를 read-only로 3회 측정했다. 세 표본은 모두 동일했고 전 축 `Moving=0`이었다. HOME 이동·기록은 실행하지 않았다.

## 실행 범위와 제어 소유권

- 기존 LeLab 설치와 relative-start 구조를 재사용했다. 새 텔레옵 프레임워크는 만들지 않았다.
- canonical 8000 프로세스에는 `LELAB_TELEOP_MODE=relative_start` 환경변수가 없었으므로, 시작 시 absolute jump 위험을 피하기 위해 같은 설치본의 임시 worker를 8003에서 relative-start로 실행했다.
- 임시 worker의 무입력 startup 3초, 58표본 최대 변화는 Pan `0.000°`, Lift `0.087912°`, Elbow `0.000°`, Flex `0.000°`, Roll `0.087912°`였다. startup jump는 없었다.
- 이동 중 Elbow relative target이 calibration 하한 `-97.010989°`를 벗어나 HOLD됐다.
- Elbow target이 범위 안으로 돌아왔을 때 Shoulder Lift target이 `42.681319° → 46.901099°`, 즉 `4.219780°` 바뀌어 기존 2° step guard가 ABORT했다. 임시 worker는 2026-10-12 20:15:06 KST에 자동 disconnect했다.
- 이후 canonical 8000 서버가 teleop active 상태로 leader/follower 포트를 소유한 것을 확인했다. 이 세션의 시작 주체는 `NOT_VERIFIED`이며, 8000 프로세스 환경에 `LELAB_TELEOP_MODE`가 없었으므로 전체 이동이 relative-start 경로만으로 수행됐다고 확정할 수 없다.
- 사용자의 도달 메시지 직후 canonical 8000 `/stop-teleoperation`을 호출했고 2026-10-12 20:19:04 KST에 정상 disconnect했다.
- 종료 시 8000 teleoperation은 inactive, 임시 8003 worker는 종료, leader/follower 포트는 무점유였다.

이 provenance 불확실성은 숨기지 않는다. HOME 기록 전에는 single-owner relative-start 실행 경로를 명시적으로 고정해야 한다.

## SAFE_HIGH 3회 read-only 기록

세 표본의 Present raw는 모두 동일했다.

| Joint | Present raw mean | Present deg mean | raw std | deg std | Goal raw | Moving | Load diagnostic | Temperature |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Shoulder Pan | 2116 | +1.274725° | 0 | 0 | 2118 | 0 | -20 | 37°C |
| Shoulder Lift | 2215 | +22.901099° | 0 | 0 | 2202 | 0 | +64 | 39°C |
| Elbow Flex | 1150 | -73.274725° | 0 | 0 | 1117 | 0 | +144 | 39°C |
| Wrist Flex | 2571 | +43.120879° | 0 | 0 | 2558 | 0 | +64 | 36°C |
| Wrist Roll | 1691 | -15.252747° | 0 | 0 | 1690 | 0 | 0 | 35°C |
| Gripper | 446 | 2.019584% | 0 | 0 | 446 | 0 | 0 | 39°C |

전 축 `Torque_Enable=1`이었다. `Present_Load`는 검증된 수치 안전 상한이 없으므로 signed diagnostic으로만 기록했으며 PASS/FAIL 판정에 사용하지 않았다.

## FK 및 SAFE_HIGH 판정

새 PICK용 GRASP TCP `[-4.748354, -12.033741, -124.531737] mm` 기준 FK는 다음과 같다.

```text
GRASP TCP = [+2.090996, -389.902432, +364.853599] mm
table reference Z = 54.659 mm
SAFE_HIGH required Z = 154.659 mm
measured height above table = 310.194599 mm
margin above SAFE_HIGH requirement = 210.194599 mm
```

따라서 수치 Z 기준은 `PASS`다. 실제 링크·테이블 비접촉은 사용자 감독과 완료 입력으로 확인했으며, full mesh/environment collision은 확보하지 못해 계속 `NOT_VERIFIED`다.

## 저장 및 검증

- canonical pose 파일: `configs/poses.yaml`
- `SAFE_HIGH=RECORDED`, `HOME=NOT_RECORDED`
- SAFE_HIGH를 HOME보다 먼저 저장할 수 있도록 partial measured pose merge를 지원하되, 자동 HOME 경로에서 `require_complete=True`이면 두 pose를 모두 요구한다.
- 관련 선택 테스트: `8/8 PASS`
- pose YAML validation: `PASS`
- `git diff --check`: `PASS`

## 다음 안전 게이트

HOME은 자동으로 연결하지 않는다. 다음 live 단계는 제어 소유권을 하나의 명시적 relative-start 세션으로 고정한 뒤 별도 사용자 승인으로만 수행한다.

```text
SAFE_HIGH
→ supervised relative-start teleop
→ HOME
→ STOP
→ follower Present 3회 read-only 기록
```

이번 변경과 기록은 `NOT_COMMITTED/NOT_PUSHED`다.
