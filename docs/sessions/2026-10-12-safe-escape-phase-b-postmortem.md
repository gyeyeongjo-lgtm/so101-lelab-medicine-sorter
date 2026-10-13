# SAFE_ESCAPE_2DEG Phase-B postmortem

날짜: 2026-10-12
상태: `Phase C = HOLD`
하드웨어 명령: `0`

## 1. 실제 이동량 재구성

실기 직전 fresh feedback, 단일 commanded target, 종료 후 read-only 3표본의
동일한 settled feedback을 사용했다. 새 포트 read는 하지 않았다.

| 축 | Present before raw / deg | target raw / deg | Present after raw / deg | commanded delta | achieved delta | achieved ratio | direction |
|---|---|---|---|---:|---:|---:|---|
| Pan | `2106 / +0.395604°` | `2128 / +2.395604°` | `2118 / +1.450549°` | `+2.000000°` | `+1.054945°` | `52.747%` | MATCH |
| Lift | `2161 / +18.153846°` | `2138 / +16.153846°` | `2161 / +18.153846°` | `-2.000000°` | `0.000000°` | `0.000%` | NO MOTION |
| Elbow | `2153 / +14.901099°` | `2130 / +12.901099°` | `2151 / +14.725275°` | `-2.000000°` | `-0.175824°` | `8.791%` | MATCH, INEFFECTIVE |
| Flex | `2193 / +9.890110°` | `2170 / +7.890110°` | `2175 / +8.307692°` | `-2.000000°` | `-1.582418°` | `79.121%` | MATCH |
| Roll | `2031 / +14.637363°` | `2053 / +16.637363°` | `2049 / +16.219780°` | `+2.000000°` | `+1.582418°` | `79.121%` | MATCH |
| Gripper | `446 / 2.019584%` | `446 / 2.019584%` | `446 / 2.019584%` | `0` | `0` | N/A | HOLD |

raw 기준 achieved delta는 Pan/Lift/Elbow/Flex/Roll `+12/0/-2/-18/+18`이고,
commanded raw delta는 `+22/-23/-23/-23/+22`이다. 실제 calibrated-degree 비율을
판정에 사용했다.

PICK GRASP TCP offset `[-4.748354,-12.033741,-124.531737] mm`와 고정 URDF로
FK를 재계산한 결과다.

```text
GRASP_TCP_before = [+5.406137,-365.783675,+50.496139] mm
GRASP_TCP_after  = [-1.047681,-369.737597,+55.316363] mm
delta_Z          = +4.820224 mm
```

Pan/Flex/Roll과 TCP Z는 escape 방향으로 유효하게 변했다. 그러나 Lift는
전혀 이동하지 않았고 Elbow는 요청량의 `8.791%`만 이동했다. 이는
모든 축이 안전 방향으로 유효하게 이동했지만 50% 숫자에만 못 미친
`THRESHOLD_ONLY`가 아니다. 지배적 병목축에 대해 `NO_EFFECTIVE_MOVEMENT`로
판정한다.

## 2. Present_Load 근거 조사

실제 Jetson 설치본은 LeRobot `0.6.0`, `feetech-servo-sdk 1.0.0`이다.

| 항목 | 확인 결과 | 근거 |
|---|---|---|
| register | `Present_Load`, address 60, 2 bytes, read-only | installed `lerobot/motors/feetech/tables.py:85` |
| encoding | sign-magnitude, sign bit index 10 | installed `tables.py:207–224` |
| decoded raw range | `-1023…+1023` | `encoding_utils.py` magnitude mask `(1<<10)-1` |
| driver return | `normalize=False`에서도 sign decode 후 signed integer 반환 | installed `motors_bus.py:991–1024` |
| sign | firmware direction bit을 음/양으로 표현; 축별 물리 CW/CCW/위험 의미는 미정의 | installed encoding code; physical mapping 없음 |
| physical unit | torque/current/percent 변환 없음 | installed LeRobot/LeLab 전체 search |
| nominal/allowed range | 정의 없음 | repository/config/installed source search |
| numeric safety threshold | 정의 없음 | repository/config/installed source search |

관련되어 보이지만 cutoff으로 쓸 수 없는 항목:

- `SO101Follower.configure()`는 **gripper에만** `Max_Torque_Limit=500`,
  `Protection_Current=250`, `Overload_Torque=25`를 write한다. 설치 주석의
  50%/25%는 보호 register 설정의 의도이며 `Present_Load` 판정값이 아니다.
- SDK의 `ERRBIT_OVERLOAD=32`는 servo status packet의 overload error bit이다.
  `Present_Load >= N`과 같은 numeric 관계는 코드에 없다.
- repository test의 `100/120`은 synthetic injected value이며 production 근거가 아니다.
- current live-retained protection/torque register는 이번에 읽지 않았으며
  `NOT_VERIFIED`다.

설치 소스 SHA:

```text
tables.py       71f7f7beb17169781bd26a33b165ed4c5c3df7b9c477d36860f9d6011eb00428
feetech.py      0460413cd6a641cede015ac19ac53d2cfe9c343af1bd18ed74e1951229f64ff2
so_follower.py  b7d9fcfcf67818c267d71744c993470dfb5077887f9ecedfe8cdf69f450be8fd
```

## 3. 판정

```text
SAFE_ESCAPE_2DEG:
movement = PARTIAL; Pan/Flex/Roll effective, Lift none, Elbow ineffective
achieved_ratio = Pan 52.747%, Lift 0.000%, Elbow 8.791%, Flex 79.121%, Roll 79.121%
TCP_Z_delta = +4.820224 mm

FAIL_REASON = NO_EFFECTIVE_MOVEMENT

LOAD_LIMIT = NOT_DEFINED

RECOMMENDATION = Keep Phase C HOLD. Do not retry or enlarge the step. In a
code-only follow-up, keep Present_Load logged as signed diagnostic telemetry
but do not use an uncalibrated absolute value as a PASS gate. Even after that
policy correction, this physical trial remains FAIL because Lift/Elbow did not
move effectively.
```

이 postmortem 중 SSH/file/HTTP source read와 로컬 FK만 수행했다. follower port 개방,
motor/Goal/Torque write, teleop, HOME/SAFE_HIGH, service restart는 `0`회다.
