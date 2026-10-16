from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_config
from .errors import SorterError
from .fixed_demo import (load_demo_settings, parse_destination_rules, run_demo,
                         teach)
from .robot import (LiveRobotAdapter, MockRobotAdapter, RobotController,
                    SO101ReadOnlyStatusAdapter)
from .workflow import SorterApplication


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m medicine_sorter")
    parser.add_argument("--config", type=Path, default=Path("configs/system.example.json"))
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("status", help="설정 준비 상태만 확인하며 장치를 열지 않습니다")
    sub.add_parser("validate-config", help="설정 schema를 검사하며 장치를 열지 않습니다")
    sub.add_parser("robot-status", help="follower를 쓰기 없이 1회 연결·상태 조회·해제합니다")
    teach_parser = sub.add_parser("teach", help="leader relative-start로 고정 데모 자세를 저장합니다")
    teach_parser.add_argument("--overwrite", action="store_true",
                              help="기존 pose JSON을 명시적으로 교체합니다")
    teach_parser.add_argument("--resume", action="store_true",
                              help="매 자세마다 저장된 partial JSON에서 이어갑니다")
    run_parser = sub.add_parser("run", help="ArUco 고정 칸→티칭 자세 재생 데모")
    run_parser.add_argument("--dry-run", action="store_true",
                            help="카메라 1프레임으로 계획만 출력하고 로봇을 열지 않습니다")
    run_parser.add_argument("--step", action="store_true",
                            help="각 단계 Enter 확인 후 실행합니다")
    run_parser.add_argument("--rule", nargs="+", metavar="TYPE=COLOR",
                            help="예: --rule C=green B=red A=blue")
    mock = sub.add_parser("mock-run", help="저장 scene으로 전체 상태 흐름을 시험합니다")
    mock.add_argument("--scene", type=Path, required=True)
    mock.add_argument("--command", required=True)
    live = sub.add_parser("live", help="새 환경 검증 전에는 장치 연결 전에 차단됩니다")
    live.add_argument("--scene", type=Path, required=True)
    live.add_argument("--command", required=True)
    return parser


def main(argv=None, *, status_adapter_factory=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.mode in {"status", "validate-config"}:
            payload = {"status": "CONFIG_VALID",
                       "task_readiness": config.readiness_by_task(),
                       "serial_open": 0, "camera_open": 0, "motor_write": 0}
        elif args.mode == "robot-status":
            readiness = config.readiness("robot_status")
            if not readiness["ready"]:
                raise SorterError("robot_status_configuration_incomplete", readiness,
                                  "follower port·USB serial 설정",
                                  "Jetson에서 follower 식별 정보를 확인해 주세요")
            factory = status_adapter_factory or SO101ReadOnlyStatusAdapter.from_config
            payload = RobotController(factory(config)).read_status().as_dict()
        elif args.mode == "teach":
            payload = teach(config, load_demo_settings(config), overwrite=args.overwrite,
                            resume=args.resume)
        elif args.mode == "run":
            settings = load_demo_settings(config)
            rules = parse_destination_rules(args.rule, settings.destinations)
            payload = run_demo(config, settings, dry_run=args.dry_run,
                               step=args.step, rules=rules)
        elif args.mode == "mock-run":
            app = SorterApplication(config, RobotController(MockRobotAdapter()))
            payload = app.run_recorded_mock(args.command, args.scene).as_dict()
        else:
            app = SorterApplication(config, RobotController(LiveRobotAdapter(config.readiness())))
            payload = app.run_live(args.command, args.scene).as_dict()
    except SorterError as error:
        print(json.dumps(error.as_dict(), ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0
