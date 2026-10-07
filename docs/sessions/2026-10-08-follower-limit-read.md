# 2026-10-08 follower Elbow·Wrist_Pitch 위치 제한 읽기

## 범위와 사전 확인

사용자는 빈 그리퍼·팔 정지, 이동 범위 밖 사람, 이상 움직임 시 즉시 중단 준비를 확인하고, 기존 LeLab 서비스만 잠시 중지한 상태에서 follower 제한 레지스터를 읽기 전용으로 확인한 뒤 동일 서비스로 복구하는 절차를 승인했다. 이번 이어받기 시점에 `lelab.service`는 이미 inactive/dead·MainPID 0이었다. `/dev/ttyACM0`의 canonical `ID_SERIAL_SHORT=5AE6058306`은 follower, `/dev/ttyACM1`의 `5AE6085272`는 leader다. 시작 전 root `fuser -v`에는 두 포트 점유 출력이 없었다.

설치 런타임은 `/home/jetson3/.local/share/uv/tools/lelab/bin/python` Python 3.14.7이다. 실제 설치 `FeetechMotorsBus` 제어표에서 `Min_Position_Limit=(9,2)`, `Max_Position_Limit=(11,2)`를 확인했다. `connect(handshake=False)`는 시리얼 포트를 열고 타임아웃을 설정하며, `read(..., normalize=False, num_retry=0)`는 요청 레지스터를 읽는다. `disconnect()`의 기본값은 토크 끄기이므로 `disconnect(disable_torque=False)`를 명시했다. `configure`·write·sync_write·토크 API는 호출하지 않았다.

## 측정값

서비스 inactive와 follower serial을 실행 직전에 다시 검사한 뒤, follower 포트 하나를 열어 아래 네 값만 읽었다.

| 관절 | 모터 ID | Min_Position_Limit | Max_Position_Limit | 단위 |
| --- | ---: | ---: | ---: | --- |
| Elbow (`elbow_flex`) | 3 | 880 | 3087 | 모터 raw step |
| Wrist_Pitch (`wrist_flex`) | 4 | 936 | 3225 | 모터 raw step |

별도 파일 읽기에서 실제 follower 캘리브레이션 JSON의 두 관절 `range_min/range_max`가 각각 위 값과 정확히 일치했다. 이는 파일과 장치 레지스터의 일치 확인이지 물리적 하드스톱, 허용 토크, 부하 중 안전 여유의 검증이 아니다. 설치 URDF Elbow 상한 +1.5708 rad, Wrist_Pitch 상한 +1.65806 rad와 수동 관절 방송의 불일치는 남아 있다. 자동 재생 경로로 사용하지 않는다.

## 복구·미완료

읽기 후 `disconnect(disable_torque=False)`를 호출했다. 그 뒤 root `fuser` 재확인 명령은 완료되지 않아 Ctrl+C로 중단했다. 별도 서비스 시작 명령을 실행했고 `lelab.service` active/running, 8000 `/health` ok, `/teleoperation-status` inactive, `/recording-status` inactive, `/inference-status` inactive를 확인했다. 기존 서비스의 실행 경로·카메라·캘리브레이션·USB 설정은 변경하지 않았다. 로봇 동작·토크 변경·자동 집기·자동 재생 `NOT_RUN`.

이슈 API 갱신 `NOT_RUN`, 원격 push `NOT_PUSHED`. 이 기록은 원본 로그·영상·비밀번호 없이 보존한다. 로컬 커밋 상태는 최종 작업 결과에서 별도 보고한다.
