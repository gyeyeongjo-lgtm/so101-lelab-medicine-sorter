# 2026-10-17 고정 데모 자동 실행·웹 UI

## 실기 성공 근거

사용자가 Jetson에서 다음을 실제 성공했다고 보고했다.

```text
약통 1개 분류 = SUCCESS
약통 2개 분류 = SUCCESS
약통 3개 분류 = SUCCESS
3개 동시 분류 = SUCCESS
verified fixed layout = A slot1 / B slot2 / C slot3
```

이는 현재 고정 배치 티칭 데모의 실기 성공이며 자유 배치 자율 집기나 카메라→로봇
좌표 변환 검증으로 확대 해석하지 않는다.

## 자동 실행

- `run --auto --rule ...`를 추가했다. 계획 확인 Enter와 stage별 Enter 없이 선택된
  약통당 기존 11단계를 연속 실행한다.
- 실행 mode를 명시하지 않은 `run`은 motion을 시작하지 않는다. `--dry-run`,
  `--step`, `--auto`는 CLI에서 상호 배타적이다.
- `slot_roi_status=verified`, `expected_bottle_slots={A:slot1,B:slot2,C:slot3}`로
  설정했다.
- 매 계획/실행은 fresh Astra snapshot에서 ID9(A), ID8(B), ID7(C) 세 마커가 모두
  보이고 기대 칸에 있는지 검사한다. 실패하면 robot session 생성 전에 원인을
  출력한다.
- 실제 실행은 follower port connect 뒤 어떤 Goal/Torque write보다 먼저
  `Present_Temperature`를 읽는다. 6개 motor 중 하나라도 50°C 이상이면 motor
  name/ID/value를 보고하고 motion 없이 종료한다.
- 기존 max velocity/acceleration, emitted step, settle, Torque, Overload/Overheat,
  stage temperature gate와 current-position HOLD는 그대로 유지했다.

## 웹 UI

단일 진입점에 다음을 추가했다.

```bash
python -m medicine_sorter --config configs/system.example.json web --port 8030
```

- `0.0.0.0:8030` 바인딩
- A/B/C 각각 red/blue/green/skip 선택
- preset 3개
- camera-only 계획 확인
- 기존 `run --auto` 경로를 호출하는 실행 버튼
- 실행 중 선택·계획·실행 버튼 비활성화 및 controller-level 중복 차단
- 보간·settle loop에서도 확인되는 정지 event와 fresh Present raw→Goal raw HOLD
- 현재 stage index/count/name, 최신 motor temperature, 마지막 오류 표시
- 현재 Jetson hostname의 `:8020/stream.mjpg` Astra 표시와 8020 화면 링크
- 실행 시에만 robot session open, 완료/오류/정지에서 기존 finally close
- 완료 후 `전원을 뽑고 식히세요` 표시
- 브라우저 연결은 실행 생명주기를 소유하지 않는다. 끊겨도 현재 1회만 계속되고
  다음 실행을 자동 예약하지 않는다.

## 오프라인 검증

```text
fixed-demo + web tests = 50/50 PASS
sorter tests = 30/30 PASS
CLI run --help / web --help = PASS
Python compile = PASS
git diff --check = PASS
hardware serial open = 0
motor command = 0
Jetson deploy/web live = NOT_RUN
```

검증에는 verified layout pass/missing/wrong-slot, mismatch의 pre-session block,
50°C의 pre-write block, auto 11단계에서 input 0회, stage progress, web rule/skip,
preset/control markup, background single-run, stop event와 stopped state가 포함된다.
