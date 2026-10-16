from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_config
from .errors import SorterError
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
