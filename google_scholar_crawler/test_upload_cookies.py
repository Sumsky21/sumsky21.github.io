import contextlib
import io
import unittest
from unittest.mock import Mock, patch

import upload_cookies


class UploadCookieTests(unittest.TestCase):
    @patch("upload_cookies.subprocess.run")
    @patch("upload_cookies.getpass.getpass", return_value="NID=test-cookie-secret")
    @patch("upload_cookies.shutil.which", return_value="gh")
    def test_upload_uses_stdin_and_hides_cookie(self, which, prompt, run):
        run.return_value = Mock(returncode=0)
        output = io.StringIO()
        with patch("sys.argv", ["upload_cookies.py"]), contextlib.redirect_stdout(output):
            upload_cookies.main()
        command = run.call_args.args[0]
        self.assertEqual(command, [
            "gh", "secret", "set", "GOOGLE_SCHOLAR_COOKIE",
            "--repo", "Sumsky21/sumsky21.github.io",
        ])
        self.assertEqual(run.call_args.kwargs["input"], b"NID=test-cookie-secret")
        self.assertNotIn("test-cookie-secret", " ".join(command))
        self.assertNotIn("test-cookie-secret", output.getvalue())

    @patch("upload_cookies.subprocess.run")
    @patch("upload_cookies.getpass.getpass", return_value="invalid-cookie")
    @patch("upload_cookies.shutil.which", return_value="gh")
    def test_invalid_cookie_is_not_uploaded(self, which, prompt, run):
        run.return_value = Mock(returncode=0)
        with patch("sys.argv", ["upload_cookies.py"]), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                upload_cookies.main()
        # Only the read-only authentication check ran.
        self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
