# 프로젝트 로드맵

| 단계 | 목표 | 현재 상태 / 진입 조건 |
|---|---|---|
| M0 | LeLab 녹화·ACT 기준선 | 과거 실험 완료, 실제 집기 성능은 미달 |
| M1 | Astra RGB·intrinsic·ArUco 작업대 | RGB intrinsic과 ID0–6 live homography 검증 완료 |
| M2 | Astra RGB–Depth 정합 진단 | OpenNI2 정합·300-frame depth 진단 완료 |
| M3 | Camera 2.5D와 World frame | 300-frame 안정성 통과; full 3D PnP는 잔차 기준 미달로 제어에 사용 금지 |
| M4 | World→Robot Base 등록 | 4점 fit 거부; 닫힌 fingertip TCP로 새 6점 teach 필요 |
| M5 | 약통 검출·안전한 dry-run | YOLO live smoke 통과; grasp offset·limits·목표 안정성 필요 |
| M6 | 제한된 실제 이동 | 별도 안전 승인 후 높은 Z에서 XY-only부터 검증 |
| M7 | 분류→집기→이동→놓기 | descend/grip/lift/place와 실패 복구 검증 |
| M8 | 제한된 VLM 보조 제안 | 허용 목록과 사람/규칙 확인; 직접 모터 명령 금지 |

현재 활성 범위는 M4의 닫힌 fingertip TCP 6점 teach와 fit 재검증이다. 2026-09-30 장면에서는 X 6점이 약통·바구니에 가려져 있으므로 작업대 정리와 새 World 좌표 추출이 먼저다. 초기 실험은 빈 용기와 가상 라벨만 사용한다. VLM 결과를 직접 약품 선택이나 저수준 모터 명령으로 연결하지 않는다.
