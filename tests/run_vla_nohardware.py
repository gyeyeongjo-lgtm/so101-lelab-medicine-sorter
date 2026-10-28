"""Run unittest regressions with device/network/process guards (no live entrypoints)."""
import os
import contextlib
import io
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(os.environ.get("VLA_TEST_ROOT",Path(__file__).resolve().parents[1])).resolve()
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/"tests"))


def guard(event,args):
    if event=="open" and isinstance(args[0],(str,bytes,os.PathLike)):
        path=os.fsdecode(args[0])
        if path.startswith(("/dev/tty","/dev/video","/dev/serial","/dev/bus/usb")):
            raise PermissionError("test runner forbids hardware devices")
    if event in ("socket.connect","socket.bind"):
        raise PermissionError("test runner forbids network")
    if event=="os.system":
        raise PermissionError("test runner forbids shell execution")
    if event=="subprocess.Popen":
        argv=args[1]
        import_only="import sys, types; sys.modules['numpy'] = types.ModuleType('numpy'); from pathlib import Path; from teleop_cycle_trace import load_grasp_fk; load_grasp_fk(Path('missing.urdf'), Path('missing-tcp.json'))"
        if argv==[sys.executable,"-c",import_only]:
            return
        # Official data-only worker is guarded again in its child process.
        if not isinstance(argv,(list,tuple)) or not any(str(x)==str(ROOT/"scripts/vla_official_worker.py") for x in argv):
            raise PermissionError("test runner forbids unreviewed subprocess")


if __name__=="__main__":
    sys.addaudithook(guard)
    pattern=sys.argv[1] if len(sys.argv)>1 else "test_*.py"
    os.chdir(ROOT)
    # Preserve diagnostics without flooding the console with mocked robot telemetry.
    captured=io.StringIO()
    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        suite=unittest.defaultTestLoader.discover(str(ROOT/"tests"),pattern=pattern)
        result=unittest.TextTestRunner(verbosity=1).run(suite)
    summary={"tests":result.testsRun,"failures":[{"id":t.id(),"trace":s} for t,s in result.failures],
             "errors":[{"id":t.id(),"trace":s} for t,s in result.errors],
             "skipped":[{"id":t.id(),"reason":s} for t,s in result.skipped]}
    if os.environ.get("VLA_TEST_REPORT"):
        report=Path(os.environ["VLA_TEST_REPORT"])
        report.parent.mkdir(parents=True,exist_ok=True)
        with report.open("x") as stream: json.dump(summary,stream,indent=2)
    print(json.dumps({"tests":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),"skipped":len(result.skipped)}))
    for t,s in result.failures+result.errors: print(t.id()+": "+s.splitlines()[-1])
    raise SystemExit(not result.wasSuccessful())
