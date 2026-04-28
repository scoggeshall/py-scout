from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from pyscout import __version__
from pyscout.cli import main as cli_main


class CliTests(unittest.TestCase):
    def test_version_command(self) -> None:
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = cli_main(["version"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue().strip(), f"pyscout {__version__}")

    def test_help_is_minimal(self) -> None:
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as exit_context:
                cli_main(["--help"])

        self.assertEqual(exit_context.exception.code, 0)
        output = stdout.getvalue()
        self.assertIn("usage: pyscout", output)
        self.assertIn("Npcap", output)
        self.assertIn("version", output)
        self.assertNotIn("TShark", output)
        self.assertNotIn("subnet", output)
        self.assertNotIn("scan", output)
        self.assertNotIn("mapper", output)


if __name__ == "__main__":
    unittest.main()
