# 2026-10-08 C 고정 출발 자리 재배치 촬영

- 사용자가 C 한 병을 빨강 ID4 바구니 앞 기존 출발 자리에 배치했다고 보고했다. LeLab 홈은 `Ready`였고, 8031은 `ROBOT DISABLED`였다. 서버 API의 실제 텔레옵 상태는 이번 턴에 별도 검증하지 않았다.
- 기존 Mac 8030 천장 캐시를 8031에서 프레임 148058로 고정하고, 사용자가 확인한 C 라벨과 병 중심 클릭 `(320.46, 238.66)`을 Git 제외 `.local/medicine-manual-captures/20261008T053332_245612Z_C_148058_666bba/`에 저장했다. JPEG SHA-256은 `c233356eb120de00bfac254a47dce177665caea363a27e06ff82c8c23faa1863`이다. 원본 영상·메타데이터는 커밋하지 않는다.
- 저장 당시 화면에는 C 후보 한 개와 기준 ID0–3 및 바구니 ID4–6이 보였다. 8031 판정은 `DRY_RUN_ROUTE_ONLY`, C→빨강 ID4, `pickup_roi_match=false`, `training_ready=false`, `robot_enabled=false`, `motion_authorized=false`였다. 기존 C 고정 출발 장면의 검출 x≈304–332px와 이번 x≈302–332px는 화면상 유사하지만, 픽업 좌표나 실제 집기 성공을 의미하지 않는다.
- 저장 JPEG를 고정 바구니 기준 사진과 오프라인 비교했다. 작업대 기준 마커 최대 이동 0.088px, 바구니 마커 최대 0.073px로 `marker_layout_match_diagnostic=true`; 몸체 색 상자는 최대 크기 9px 차이로 `BODY_CANDIDATE_UNSTABLE`이다. 입구 네 모서리·높이·TCP/World→Base·연속 경로는 여전히 `NOT_VERIFIED`다.
- 첫 `python3` 실행은 `cv2` 미설치로 실패했다. 문서에 기록된 실제 `.venv/bin/python`으로 재실행해 감사가 성공했다. 이 턴에서 로봇 동작·서비스/USB/토크 변경 `NOT_RUN`, GitHub 이슈 API `NOT_RUN`, 원격 push `NOT_PUSHED`. 새 사진은 리뷰 자료이며 자동 이동 승인이 아니다.
- 후속 8031 읽기 전용 명령 미리보기에서 `C를 빨강`을 입력해 현재 프레임 149097을 판정했다. 결과는 C 고정 슬롯→빨강 ID4 `DRY_RUN_ROUTE_ONLY`, `pickup_roi_match=false`, `grasp_authorized=false`, `motion_authorized=false`였다. 해당 프레임의 C 후보 투영 x≈293.8 mm는 기존 픽업 ROI 최대 x=273 mm 밖이지만 물체 높이 보정 전 화면 투영값이므로 ROI를 즉시 확대하거나 로봇 집기 좌표로 전용하지 않는다. 명령은 저장·실행되지 않았다.
