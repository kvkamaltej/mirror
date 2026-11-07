"""Unit tests for the pure helpers in devtools.py:  python -m unittest test_devtools"""
import unittest

import devtools as d


class Helpers(unittest.TestCase):
    def test_sh_quote(self):
        self.assertEqual(d.sh_quote("abc"), "'abc'")
        self.assertEqual(d.sh_quote("it's; rm -rf /"), "'it'\\''s; rm -rf /'")

    def test_parse_line(self):
        line = "11-07 12:34:56.789  1234  5678 E AndroidRuntime: FATAL EXCEPTION: main"
        self.assertEqual(d.parse_line(line), (1234, "E"))
        self.assertEqual(d.parse_line("--------- beginning of main"), (None, None))

    def test_logcat_args(self):
        self.assertEqual(d.logcat_args("W", tail=0), ["logcat", "-v", "threadtime", "*:W"])
        a = d.logcat_args("D", "crash", "ActivityManager, flutter", "user (id|name)", 100)
        # regex unquoted: `adb logcat` quotes each argument for the phone itself
        self.assertEqual(a, ["logcat", "-v", "threadtime", "-T", "100", "-b", "crash", "-e", "user (id|name)",
                             "ActivityManager:D", "flutter:D", "*:S"])
        for bad in (dict(level="X"), dict(buffer="nope"), dict(tags="bad tag;rm"), dict(regex="x" * 300)):
            with self.assertRaises(ValueError):
                d.logcat_args(**{**dict(level="V"), **bad})

    def test_parse_packages(self):
        out = "package:com.example.app versionCode:42\npackage:org.b versionCode:7\njunk\npackage:x\n"
        self.assertEqual(d.parse_packages(out), [("com.example.app", "42"), ("org.b", "7")])
        self.assertEqual(d.parse_packages("package:com.old.app\n"), [("com.old.app", "")])

    def test_parse_forward_list(self):
        out = "49e4f79c tcp:8000 tcp:8000\nhost-12 tcp:9222 localabstract:chrome_devtools_remote\n"
        self.assertEqual(d.parse_forward_list(out), [("49e4f79c", "tcp:8000", "tcp:8000"),
                                                     ("host-12", "tcp:9222", "localabstract:chrome_devtools_remote")])

    def test_package_details(self):
        out = ("    versionCode=1042 minSdk=24 targetSdk=34\n    versionName=2.3.1\n"
               "    firstInstallTime=2026-11-01 10:00:00\n    lastUpdateTime=2026-11-06 18:22:05\n")
        got = d.parse_package_details(out)
        self.assertEqual((got["versionName"], got["versionCode"], got["targetSdk"], got["minSdk"]),
                         ("2.3.1", "1042", "34", "24"))
        self.assertEqual(got["lastUpdateTime"], "2026-11-06 18:22:05")

    def test_patterns(self):
        self.assertTrue(d.PKG_RE.match("com.ecil.bihar_ems"))
        self.assertFalse(d.PKG_RE.match("com"))
        self.assertFalse(d.PKG_RE.match("com.x; reboot"))
        self.assertTrue(d.URL_RE.match("myapp://orders/42"))
        self.assertTrue(d.URL_RE.match("https://example.com/a?b=1"))
        self.assertFalse(d.URL_RE.match("example.com"))
        self.assertFalse(d.URL_RE.match("https://a b"))


if __name__ == "__main__":
    unittest.main()
