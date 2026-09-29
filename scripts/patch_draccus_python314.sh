#!/usr/bin/env bash
# Compatibility fix for Draccus on Python 3.14.
# argparse in Python 3.14 requires type= to be callable, while this Draccus
# release forwards PEP 604 union annotations such as `str | None` unchanged.
set -euo pipefail

TARGET=/home/jetson3/.local/share/uv/tools/lelab/lib/python3.14/site-packages/draccus/wrappers/field_wrapper.py
REC=/home/jetson3/.local/share/uv/tools/lelab/bin/lerobot-record
TS=$(date +%Y%m%dT%H%M%S%z)
BACKUP=/home/jetson3/so101-recovery-backups/${TS}_draccus-python314

test -f "$TARGET"
test -x "$REC"
mkdir -p "$BACKUP"
cp -p "$TARGET" "$BACKUP/field_wrapper.py.original"
sha256sum "$TARGET" > "$BACKUP/field_wrapper.before.sha256"

apply_fix() {
  cd "$(dirname "$TARGET")"
  patch --batch --forward --dry-run -p0 <<'PATCH'
--- field_wrapper.py
+++ field_wrapper.py
@@ -308,3 +308,10 @@
     def add_action(self, parser: _ActionsContainer) -> None:
         logger.debug(f"Arg options for field '{self.name}': {self.arg_options}")
-        parser.add_argument(*self.option_strings, **self.arg_options)
+        arg_options = dict(self.arg_options)
+        type_parser = arg_options.get("type")
+        # Python 3.14 rejects non-callable union annotations passed as
+        # argparse's `type`. Draccus decodes the field after argparse, so
+        # preserving its CLI representation as text is sufficient here.
+        if type_parser is not None and not callable(type_parser):
+            arg_options["type"] = str
+        parser.add_argument(*self.option_strings, **arg_options)
PATCH
  patch --batch --forward -p0 <<'PATCH'
--- field_wrapper.py
+++ field_wrapper.py
@@ -308,3 +308,10 @@
     def add_action(self, parser: _ActionsContainer) -> None:
         logger.debug(f"Arg options for field '{self.name}': {self.arg_options}")
-        parser.add_argument(*self.option_strings, **self.arg_options)
+        arg_options = dict(self.arg_options)
+        type_parser = arg_options.get("type")
+        # Python 3.14 rejects non-callable union annotations passed as
+        # argparse's `type`. Draccus decodes the field after argparse, so
+        # preserving its CLI representation as text is sufficient here.
+        if type_parser is not None and not callable(type_parser):
+            arg_options["type"] = str
+        parser.add_argument(*self.option_strings, **arg_options)
PATCH
}

rollback() {
  cp -p "$BACKUP/field_wrapper.py.original" "$TARGET"
  sha256sum "$TARGET" > "$BACKUP/field_wrapper.rolled_back.sha256"
}

apply_fix
sha256sum "$TARGET" > "$BACKUP/field_wrapper.after.sha256"

if "$REC" --help > "$BACKUP/lerobot-record.help.after.txt" 2> "$BACKUP/lerobot-record.help.stderr"; then
  echo "RESULT=PASS"
  echo "BACKUP=$BACKUP"
  sha256sum "$TARGET"
else
  rollback
  echo "RESULT=ROLLED_BACK"
  echo "BACKUP=$BACKUP"
  cat "$BACKUP/lerobot-record.help.stderr" >&2
  exit 1
fi
