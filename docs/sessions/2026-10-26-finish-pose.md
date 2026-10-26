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
Jetson deploy = NOT_RUN
finish teaching = NOT_RUN
live run = NOT_RUN
```

검증에는 한 약통의 `home → finish` 종료, 세 약통에서 `finish` 정확히 1회,
finish에서 gripper 값 유지, 기존 자세 파일에 `teach --only finish` 추가, auto에서
Enter 없이 마지막 progress stage가 finish인 조건이 포함된다.

## 다음 단계

Jetson에서 새 commit을 pull한 뒤 현장 안전 조건과 leader/follower 단독 소유권을
확인하고 `teach --only finish`로 자세를 저장한다. 첫 실기는 한 약통 `run --step`으로
마지막 `home → finish` 경로를 확인하며, 성공 전에는 web 자동 실행을 사용하지 않는다.
