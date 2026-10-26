# 2026-10-26 전체 분류 종료 finish 자세

## 요청과 실행 순서

사용자는 약통을 모두 놓고 `home`으로 복귀한 뒤 데모 마무리 자세 하나를 더
원했다. 기존 약통별 경로는 유지하고 다음 순서로 구현했다.

```text
각 약통: home → open → pre → grasp → closed → lift → above → release
         → open → above → home
전체 마지막: finish
```

`finish`는 약통별로 반복하지 않고 선택된 모든 route가 끝난 뒤 정확히 한 번만
실행한다. 팔 5축만 재생하고 그리퍼는 마지막 release에서 열린 값을 유지한다.

## 자세 파일 호환과 gate

- 기본 `teach` 18개 자세 순서와 partial/resume 형식은 바꾸지 않았다.
- 기존 기본 18개와 `gripper_closed_A/B/C`가 있는 파일에
  `teach --only finish`로 한 자세만 atomic 추가한다.
- 실제 run은 `finish`까지 갖춘 자세 파일을 robot session 생성 전에 요구한다.
  누락 시 포트를 열지 않고 `pose_file_incomplete`로 중단한다.
- dry-run은 로봇을 열지 않고 계획 마지막에 `finish`를 표시한다.

## 오프라인 검증

```text
fixed-demo + web = 51/51 PASS
sorter = 30/30 PASS
Python compile = PASS
git diff --check = PASS
serial open = 0
Goal/Torque/config write = 0
motor command = 0
Jetson deploy = PASS (exact code commit 5a3edd6, clean)
finish teaching = PASS (saved 2026-10-26T11:19:03.352472+00:00)
red/blue/green step runs = USER_REPORTED_PASS
live raw motor-command count = NOT_COLLECTED
web restart = PASS (HTTP 200)
```

검증에는 한 약통의 `home → finish` 종료, 세 약통에서 `finish` 정확히 1회,
finish에서 gripper 값 유지, 기존 자세 파일에 `teach --only finish` 추가, auto에서
Enter 없이 마지막 progress stage가 finish인 조건이 포함된다.

## Jetson 배포와 실기 보고

Jetson checkout이 `5a3edd6`, clean이고 자세 JSON에 finish가 저장된 것을 확인했다.
사용자는 새 집기·release·basket above·home·finish 자세를 사용한 빨강·파랑·초록
각각의 단계 실행이 모두 성공했다고 보고했다. 이는 현장 사용자 보고이며 이 세션에서
원시 단계 출력이나 motor command 수를 별도로 수집하지 않았으므로 해당 수치를
추정하지 않는다.

기존 8030 process를 종료한 뒤 동일 checkout의 새 web process로 교체했다. 8030
LISTEN과 localhost HTTP 200을 확인했다. web 재시작 중 robot serial을 열거나 motor
명령을 보내지 않았다. 이후 web 자동 실행은 매 run의 fresh marker layout과 50°C
미만 prestart temperature gate, motion fault HOLD 및 수동 정지 경로를 그대로 사용한다.
