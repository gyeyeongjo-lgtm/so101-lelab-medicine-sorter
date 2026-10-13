# 2026-10-12 WRIST_ESCAPE_Z_PLUS_20 실기 1 및 종료 후 오프라인 판정

## 범위와 정지 상태

- 승인 범위: `CURRENT → WRIST_ESCAPE_Z_PLUS_20`만 실행.
- 실제 송신: 첫 Wrist Flex target 1개.
- 첫 step FAIL 뒤 추가 target: `0`.
- 사용자 `STOPPED`와 feedback stillness로
  `physical_stop=FEEDBACK_AND_HUMAN_CONFIRMED`.
- 종료 후 read-only 3표본은 모두 Present raw
  `2117/2167/2157/2155/2048/446`으로 동일했다.
- read-only 종료 뒤 follower port는 해제됐다.
- Phase C는 계속 `HOLD`; HOME/SAFE_HIGH/teleop은 실행하지 않았다.

## 실제 step 결과

시작 arm Present:

```text
Pan    +1.450549°
Lift  +18.153846°
Elbow +14.725275°
Flex   +8.307692°
Roll  +16.219780°
```

요청은 Wrist Flex만 `8.307692° → 6.307692°`로 `-2.0°`였고,
나머지 축은 당시 Present를 target으로 보냈다. settled feedback은:

```text
Pan    +1.362637°   delta -0.087912°
Lift  +18.681319°   delta +0.527473°
Elbow +15.252747°   delta +0.527473°
Flex   +6.549451°   delta -1.758242° (87.912%, intended direction PASS)
Roll  +16.131868°   delta -0.087912°
```

```text
Goal raw    = 2118/2161/2151/2152/2049/446
Present raw = 2117/2167/2157/2155/2048/446
Moving      = all 0
Temperature = 39/44/41/37/37/39 °C
Load before = -52/104/96/32/-28/0
Load after  = 0/36/36/24/0/0
```

GRASP TCP는 `[-1.047681,-369.737597,+55.316363] mm`에서
`[-0.540109,-370.872873,+54.317570] mm`로 변했고, Z는
`-0.998793 mm` 감소했다. 따라서 결과는:

```makefile
WRIST_ESCAPE_Z_PLUS_20 = FAIL
FAIL_REASON = TCP_Z_DID_NOT_INCREASE
```

## FK 기여도 분해

동일 before pose에서 각 축의 실제 변화만 단독 적용한 exact FK 기여는:

| 축 | 실제 delta | 단독 GRASP TCP Z 기여 |
|---|---:|---:|
| Pan | -0.087912° | -0.000001 mm |
| Lift | +0.527473° | -2.911619 mm |
| Elbow | +0.527473° | -2.339636 mm |
| Wrist Flex | -1.758242° | +4.320115 mm |
| Wrist Roll | -0.087912° | -0.014873 mm |

단독 기여 합은 `-0.946014 mm`, 비선형 interaction은 `-0.052778 mm`,
실제 합은 `-0.998793 mm`다. Wrist Flex는 의도 방향으로 충분히 움직였지만,
비명령 Lift/Elbow의 각각 `+0.527°` drift가 Wrist의 Z 상승을 초과했다.

새 종료 pose의 중앙차분 Z 민감도는:

```text
dZ/dPan   = +0.000016 mm/deg
dZ/dLift  = -5.546797 mm/deg
dZ/dElbow = -4.454551 mm/deg
dZ/dFlex  = -2.450446 mm/deg
dZ/dRoll  = +0.170971 mm/deg
```

## 다음 live 후보 판정

기존 실측에서 `50%` 이상 반응이 확인된 Pan/Flex/Roll만 사용하고,
이번 Wrist-only step에서 관측된 Lift/Elbow drift가 한 번 더 발생한다고 두면,
`2°` 한도에서 가장 유리한 조합은 `Pan +2° / Flex -2° / Roll +2°`다.
각 축에 실측 반응률을 적용한 모델에서도 예측 Z delta는 `-0.676135 mm`,
single-P1 table proxy margin은 `-1.017565 mm`다.

따라서 현재 근거와 기존 gate를 모두 유지하면:

```ini
RESPONSIVE_ONLY_NEXT_STEP = NOT_FOUND
NEXT_LIVE_COMMAND = NONE
```

Lift/Elbow에 다시 `2°`를 요구하는 후보는 이미 각각 `0%/8.791%` 반응으로
50% gate를 통과하지 못했으므로 추천하지 않는다. 작은 Wrist step은 동일 drift가
반복될 경우 Z 여유가 더 작아지며, Wrist+Roll 조합도 drift를 상쇄하지 못한다.

## 검증 및 보존 사항

- 신규 pure-offline 분석기:
  `scripts/analyze_wrist_escape_postmortem.py`
- curated fixture:
  `tests/fixtures/wrist_escape_z_plus20_attempt1.json`
- 관련 신규/기존 선택 테스트: `12/12 PASS`
- 분석기 hardware path: port open `0`, Goal/Torque write `0`, motor command `0`
- `verified_abs_load_limit=NOT_DEFINED`; Present_Load는 diagnostic only.
- GRASP TCP/C XY/calibration/endpoint/tolerance/gain/torque는 변경하지 않았다.
- full mesh/environment collision은 계속 `NOT_VERIFIED`다.
- 변경 사항은 `NOT_COMMITTED/NOT_PUSHED`.
