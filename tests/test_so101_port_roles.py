import unittest

from scripts.so101_port_roles import PORT_ROLES, inspect_task_ports


class FakeInspector:
    def __init__(self):
        self.paths = []
        self.permission = True
        self.busy = set()
        self.serials = {role.path: role.serial for role in PORT_ROLES.values()}

    def serial_short(self, path):
        self.paths.append(path)
        return self.serials[path]

    def readable_writable(self, path):
        return self.permission

    def owner_pids(self, path):
        return self.busy


class PortRolesTests(unittest.TestCase):
    def test_follower_and_leader_only_tasks_do_not_require_other_bus(self):
        for task, expected in (("follower_read", "/dev/ttyACM0"),
                               ("follower_replay", "/dev/ttyACM0"),
                               ("leader_read", "/dev/ttyACM1")):
            inspector = FakeInspector()
            self.assertEqual(list(inspect_task_ports(task, inspector).values()), ["AVAILABLE"])
            self.assertEqual([str(path) for path in inspector.paths], [expected])

    def test_teleop_and_alignment_need_both_buses(self):
        for task in ("lelab_teleop", "alignment_view"):
            inspector = FakeInspector()
            self.assertEqual(len(inspect_task_ports(task, inspector)), 2)

    def test_permission_and_busy_are_distinct(self):
        inspector = FakeInspector()
        inspector.permission = False
        self.assertEqual(inspect_task_ports("follower_replay", inspector),
                         {"follower": "PERMISSION_DENIED"})
        inspector.permission = True
        inspector.busy = {123}
        self.assertEqual(inspect_task_ports("follower_replay", inspector),
                         {"follower": "PORT_BUSY"})


if __name__ == "__main__":
    unittest.main()
