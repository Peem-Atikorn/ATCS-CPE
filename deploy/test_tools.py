"""Offline checks for deployment tooling decisions."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import monitor


class MonitorTests(unittest.TestCase):
    def run_snapshot(self, items: list[dict]) -> bool:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / ".env").write_text("POSTGRES_PASSWORD=test\n", encoding="utf-8")
            output = "\n".join(json.dumps(item) for item in items)
            result = subprocess.CompletedProcess(args=[], returncode=0, stdout=output, stderr="")
            with patch.object(monitor, "ROOT", root), patch.object(monitor.shutil, "which", return_value="docker"), \
                 patch.object(monitor.subprocess, "run", return_value=result):
                return monitor.snapshot()

    def test_every_service_running_and_healthy(self) -> None:
        items = [
            {"Service": name, "State": "running", "Health": "" if name in ("worker", "beat") else "healthy"}
            for name in monitor.EXPECTED
        ]
        self.assertTrue(self.run_snapshot(items))

    def test_missing_or_unhealthy_service_fails(self) -> None:
        items = [
            {"Service": name, "State": "running", "Health": "healthy"}
            for name in monitor.EXPECTED if name != "generation"
        ]
        self.assertFalse(self.run_snapshot(items))
        items.append({"Service": "generation", "State": "running", "Health": "unhealthy"})
        self.assertFalse(self.run_snapshot(items))


if __name__ == "__main__":
    unittest.main()
