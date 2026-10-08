# 2026-10-08 현재 Jetson 설치 URDF·정규화 대조 — 구동 없음

## 확인된 원인

- 사용자가 Jetson 설치 Python에서 수집한 현재 `lerobot/motors/motors_bus.py` SHA-256 `ade55d42046f1f0fa737eb61c360d76ed98211f200e10918dc2e6fcfd640a688`와 850–910행을 제공했다. `DEGREES` 관측 변환은 `mid=(range_min+range_max)/2`, `deg=(raw-mid)*360/(model_resolution-1)`이고 역변환은 `int(deg*(model_resolution-1)/360+mid)`다. `DEGREES` 가지는 `drive_mode`로 부호를 뒤집거나 `range_min/max`로 입력/출력을 clamp하지 않는다. `_normalize`의 `bounded_val`은 다른 정규화 가지에는 쓰이지만 `DEGREES` 가지는 원본 `val`을 사용한다. 이는 소스 그대로의 수치 계약이며 물리 회전 방향까지 증명하지 않는다.
- 현재 Jetson에 `frontend/dist/.../so101_new_calib.urdf`와 `frontend/public/.../so101_new_calib.urdf`가 각각 있고 **두 SHA가 모두** `443d38d756e01bac7d3455b24430047ddc6427105e0d3454b2003116f5f67236`이다. 따라서 현재 두 설치 사본 사이의 제한 숫자 차이는 없다. Mac의 설치 LeLab 서버 코드 `FRONTEND_DIST = .../frontend/dist`와 `/` static mount, frontend 기본 모델 URL `/so-101-urdf/urdf/so101_new_calib.urdf`에 따르면 **기본 UI의 서빙 사본은 dist**이고 public은 빌드 원본이다. 이전 Jetson 오프라인 감사 스냅샷도 dist를 출처로 기록했다. 이번에 Jetson 서버의 런타임 HTTP 응답 자체는 Mac 네트워크 접속 실패로 재확인하지 못했으며 사용자가 UI에서 별도 custom URDF를 선택했는지는 확인되지 않았다. 수동 `get_action→send_action` 제어에는 URDF가 끼지 않는다.
- 두 현재 URDF 모두 Elbow revolute 상한 `1.5708 rad`(약 90°), 하한 `-1.74533 rad`(약 -100°)다. `URDF_JOINT ... None` 중복 줄은 제한 없는 추가 가동 관절이 아니라 XML 안의 다른 `joint` 요소이므로 revolute limit 판정에서 제외한다. 기존 C 관찰 Elbow 최대 `1.685489 rad`(96.571°)는 상한보다 `0.114689 rad`(6.571°) 높다. 기존 2,298표본 중 792개 초과 결과와 일치한다. 그 판정은 저장소 **오프라인 감사기의 차단**이며 수동 모터 드라이버의 거부가 아니다.
- 현재 follower calibration SHA-256 `2f74c130...e29c2e`와 motor ID/범위/`drive_mode=0`은 기존 스냅샷과 일치한다. 후속 사용자의 현재 Jetson 출력에서 sts3215 해상도 **4096**도 확인했다. 따라서 Elbow raw 880–3087, mid 1983.5 → 정규화 상한 약 +97.011°; URDF +90°의 대응 raw는 약 3007.25, 기존 관찰 최대는 약 raw 3082다. 즉 관측된 초과는 **파일 calibration 범위 안이면서 URDF 상한 밖**인 수치 설정 불일치다. 이 사실만으로 URDF가 잘못됐거나 +97°가 자동운용에 안전하다는 뜻은 아니다.

## 아직 확인되지 않은 것 / 필요한 수정

- 후속 사용자 Jetson 출력에서 현재 `MODEL_RESOLUTION['sts3215']=4096`을 확인했다. 따라서 raw 환산의 4095 분모와 Elbow calibration 상한 약 +97.011°는 현재 설치값에 근거해 확정된다. software의 midpoint/scale 식도 이번 설치 소스로 확인됐다. `homing_offset`의 실제 모터 적용 및 URDF 축의 물리 영점·양의 방향은 파일과 정수 step 격자만으로 확정할 수 없다. 현장 승인 아래 별도의 제한된 물리 대응 검증이 필요하지만 현재는 `NOT_RUN`.
- 따라서 URDF 상한 확대, calibration 변경, 초과 표본 삭제, 충돌/한계 검사 해제는 **수정하지 않는다**. 먼저 제조사 조립체 사양 및 실제 검증 운용 범위·충돌 여유와 현재 시작 자세/경로를 비교한다. 현재 URDF 범위로 시작과 전체 경로를 검증할 수 없다면 C→ID4 프로그램 제어 시험은 차단한다. 추후 실제 모델 오류가 입증되면 영향을 받는 관절만 전후 제한값·근거·시뮬레이션 결과를 제시해 별도 변경한다.
- 실행부의 `command_stop_state=COMPLETED`는 producer/worker 및 전송 종료만 뜻하며 `arm_stop_state=NOT_VERIFIED`는 별도다. live adapter는 LeLab 수동 worker가 완전히 끝나고 follower 포트 소유권이 해제됐음을 확인한 뒤에만 유일 소유자로 연결한다. 정상 수동 제어와 동시에 버스를 열지 않는다. 중단 후에는 새 목표 송신 0건, in-flight write 종료, 신선한 follower 관절 피드백에서 일정 시간 정지 및 현장 팔/물체 안정 확인을 **각각** 기록해야 한다. `stop-teleoperation` API success만으로 완료 처리하지 않는다. 토크 무조건 해제 금지.
- 첫 실기는 C→빨강에 대해 사람 승인마다 `approach`, `grasp`, `transfer`, `place`, `retreat` 한 단계씩 프로그램 목표를 송신하는 시험이다. 실제 연결 전에 시작/배치 허용 오차·검증 경로·관절별 도달 허용 오차·시간 제한·집기/놓기 사람 확인·중단 시 안전한 물체 지지/팔 정지 절차를 수치로 정해 시험 범위와 함께 사용자에게 별도 승인받는다. 기존 수동 성공·가짜 전송기 통과는 이 시험의 성공이 아니다.

Jetson·모터·토크·서비스·USB 변경 `NOT_RUN`; live 송신 `NOT_RUN`; 이슈 API `NOT_RUN`; 로컬 변경 `NOT_COMMITTED`, 원격 `NOT_PUSHED`.
