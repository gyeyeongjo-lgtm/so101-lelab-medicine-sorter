# Fixed-demo smooth 기본 profile 전환

일자: 2026-10-27

## 적용 근거

사용자는 실제 `motion-test`에서 SMOOTH의 `home → red_above` 이동을 확인했고,
shared quintic, absolute deadline, 40Hz, 20°/s 조건이 ORIGINAL보다 육안상 확실히
부드럽다고 보고했다. 이 판정은 `USER_REPORTED_PASS`이며 해당 원시 JSONL과 수치 비교
출력은 이번 변경 입력에 포함되지 않았다. 사용자의 지시에 따라 추가 live motion은
실행하지 않았다.

## 변경

- `run --step`: 기본 `smooth`
- `run --auto`: 기본 `smooth`
- `web --port 8030`: 기본 `smooth`
- rollback: `run ... --profile original`, `web ... --profile original`
- dry-run/실행 결과: `motion_profile`, `control_hz`, curve, deadline mode,
  arm velocity limit 표시
- web 상태/API/화면: 현재 `motion_profile` 표시

기본 smooth 실행 설정은 다음으로 고정했다.

```text
trajectory = shared quintic smoothstep
scheduler = absolute deadline, expired tick skip
control = 40Hz
arm velocity limit = 20 deg/s
```

기존 original rollback은 config의 기존 fixed-demo 설정인 cubic, relative sleep,
20Hz, 20°/s를 보존한다.

## 보존한 안전 계약

- arm emitted command `<=2°` hard cap
- 시작 온도 `<50°C` (감독 warm-start 명시 기능은 기존 범위 그대로)
- 실행 중 `55°C` stop
- Overload/온도/feedback 오류 시 fresh current HOLD
- CLI Ctrl+C 시 current HOLD
- web 정지 버튼 시 stop event → current HOLD
- 종료 `disconnect(disable_torque=False)`

pose, teaching, calibration, gain, Torque policy, IK, TCP, vision, basket/grasp 로직은
변경하지 않았다.

## 장비 없는 검증

- fixed-demo + web: `69/69 PASS`
- sorter: `31/31 PASS`
- CLI `run --help`, `web --help`: `PASS`
- Python compile: `PASS`
- `git diff --check`: `PASS`
- serial open / motor command: `0 / 0`

테스트는 기본 profile이 smooth인지, 모든 fixed-demo stage가 25ms period·20°/s·2° cap과
`motion_profile=smooth`를 받는지, CLI와 web server의 `--profile original` rollback,
web API와 화면 profile 표시를 포함한다.

기본 전환 후 전체 pick-and-place와 web 실제 실행은 요청에 따라 추가 시험하지 않아
`NOT_RUN`이다.
