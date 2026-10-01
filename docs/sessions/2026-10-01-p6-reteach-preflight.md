# 2026-10-01 P6 재측정 재개 사전 점검

## 의도와 승인 범위

- 전날 사용자는 P6 재측정 텔레옵을 승인하고 작업대 정리·팔로워 범위 이탈·즉시 중단 준비·시작 자세 정렬을 확인했다. 이후 같은 손가락에 표식을 다시 붙였다고 답했다.
- 이번 재개 요청에 따라 상태·장면을 새로 검사했다. 전날의 물리 배치와 안전 확인을 오늘의 현재 상태로 간주하지 않는다.

## 읽기 전용 검사와 웹 서비스 복구

- Jetson `192.168.50.20`은 ping과 SSH 22에 응답했다. LeLab 8000은 처음에 연결되지 않았다.
- `systemctl --user show lelab.service`에서 `ActiveState=inactive`, `MainPID=0`, `Result=success`, `ExecMainStatus=15`, `InactiveEnterTimestamp=2026-09-30 22:20:10 KST`를 확인했다. 종료 원인의 세부 사항은 `NOT_VERIFIED`다.
- canonical USB 링크는 Leader `5AE6085272`→ACM1, Follower `5AE6058306`→ACM0였다. 8002·8022 LeLab 서버는 떠 있었으나 두 서버의 teleoperation·recording·inference 모두 inactive였다.
- 기존 설정을 변경하지 않고 `systemctl --user start lelab.service`를 한 번 실행했다. 8000의 `ActiveState=active`, `MainPID=393471`, health 정상, teleoperation·recording·inference active=false를 확인했다. recording의 `current_phase=preparing`, `session_ended=false` 내부 정리 여부는 `NOT_VERIFIED`다. serial bus·토크·캘리브레이션·USB·전원은 건드리지 않았다.

## 카메라 확인과 중단 판정

- 손목 `/camera-preview/6` 새 프레임에는 그리퍼 안쪽 두 면이 보였다. 한 손가락에 붙였다는 표식과 실제 접촉할 단단한 플라스틱 끝 한 점은 영상에서 식별되지 않았다.
- 정면 Astra `/camera-preview/8` 새 프레임에는 약통 모형 3개와 바구니 3개가 다시 배치돼 P6 X가 가려져 있었다. 분홍색 조각은 작업대 왼쪽에 보였다. 이 조각이 손가락 표식에서 떨어진 것인지는 `NOT_VERIFIED`다.
- 따라서 물리 장면이 전날의 승인 조건과 다르다. `/move-arm`은 호출하지 않았고 P6 joint sample·fit은 `NOT_RUN`. 현재 거부된 robot-world 변환, `robot_enabled=false`, `motion_authorized=false`를 유지한다.
- 다음은 약통·바구니를 잠시 치워 P6과 ID0–3을 노출하고, 동일 손가락 표식이 실제로 붙어 있으며 단단한 플라스틱 접촉점은 노출됐는지 현장에서 확인하는 것이다. 이후 사람의 범위 이탈·즉시 중단 준비·리더/팔로워 시작 자세와 저속 조작 승인을 현재 시점에 다시 확인해야 한다.

## 기록 경계

- 원본 카메라 프레임, 원본 로그, 인증정보는 Git에 넣지 않는다.
- 이 문서·상태 갱신의 Git commit/push 결과는 작업 종료 시 별도로 검증한다.
