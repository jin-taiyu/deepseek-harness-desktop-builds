import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin/dsh-desktop"
VERSION = "0.2.1-alpha.5"
COMMIT = "1" * 40

STUB = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import plistlib
import shutil
import sys

command = Path(sys.argv[0]).name
args = sys.argv[1:]
root = Path(os.environ["DSH_TEST_ROOT"])
def option(name):
    return args[args.index(name) + 1]
if command == "gh":
    with (root / "gh-calls.jsonl").open("a") as log:
        log.write(json.dumps(args) + "\n")
    if args[0] == "auth":
        sys.exit(0)
    if args[0] == "api":
        endpoint = next(arg for arg in args if arg.startswith("repos/"))
        if "/commits/" in endpoint:
            print(os.environ.get("DSH_TEST_COMMIT", "1" * 40))
        else:
            name = "upstream.json" if "deepseek-ai/deepseek-harness/" in endpoint else "built.json"
            print(json.dumps([json.loads((root / name).read_text())]))
    elif args[:2] == ["release", "download"]:
        if "--output" in args:
            print((root / "assets/build-info.json").read_text())
        else:
            dest = Path(option("--dir"))
            dest.mkdir(parents=True, exist_ok=True)
            for name in (root / "assets").iterdir():
                shutil.copy2(name, dest / name.name)
    elif args[:2] == ["workflow", "run"]:
        request = next(x.split("=", 1)[1] for x in args if x.startswith("request_id="))
        (root / "request-id").write_text(request)
    elif args[:2] == ["run", "list"]:
        request = (root / "request-id").read_text()
        print(json.dumps([{"databaseId": 7, "displayTitle": "Desktop latest " + request}]))
    elif args[:2] == ["run", "watch"]:
        sys.exit(int(os.environ.get("DSH_TEST_WATCH_STATUS", "0")))
    else:
        raise RuntimeError(args)
elif command == "uname":
    print("Darwin" if args == ["-s"] else "arm64")
elif command == "ps":
    if os.environ.get("DSH_TEST_RUNNING"):
        print(str(root / "Applications/DeepSeek Harness.app/Contents/MacOS/DeepSeek Harness"))
elif command == "hdiutil":
    if args[0] == "attach":
        dest = Path(option("-mountpoint")) / "DeepSeek Harness.app"
        shutil.copytree(root / "source-app", dest)
    elif args[0] == "detach":
        mountpoint = Path(args[-1])
        for child in mountpoint.iterdir():
            shutil.rmtree(child)
elif command == "plutil":
    with Path(args[-1]).open("rb") as file:
        print(plistlib.load(file)[option("-extract")])
elif command == "file":
    print("Mach-O 64-bit executable arm64")
elif command == "codesign":
    target = str(root / "Applications/DeepSeek Harness.app")
    if os.environ.get("DSH_TEST_FAIL_FINAL_SIGNATURE") and args[-1] == target:
        sys.exit(9)
elif command == "ditto":
    shutil.copytree(args[0], args[1])
elif command == "mv":
    if os.environ.get("DSH_TEST_FAIL_RENAME") and "/.dsh-desktop-install." in args[0] and args[0].endswith("/DeepSeek Harness.app"):
        sys.exit(9)
    os.rename(args[0], args[1])
else:
    raise RuntimeError(command)
'''


def release(version, prefix="dsh-v", draft=False, complete=False, published="2026-10-16T12:00:00Z"):
    assets = []
    if complete:
        assets = [{"name": name, "state": "uploaded", "size": 100} for name in [
            f"deepseek-harness-{version}-mac-arm64-unsigned.dmg", "SHA256SUMS", "build-info.json"
        ]]
    return {"id": 1, "tag_name": prefix + version, "draft": draft,
            "prerelease": "-" in version, "published_at": published, "assets": assets}


class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="dsh automation ")
        self.root = Path(self.temporary.name)
        self.mock_bin = self.root / "mock-bin"
        self.mock_bin.mkdir()
        for name in ["gh", "uname", "ps", "hdiutil", "plutil", "file", "codesign", "ditto", "mv"]:
            path = self.mock_bin / name
            path.write_text(STUB)
            path.chmod(0o755)
        self.assets = self.root / "assets"
        self.assets.mkdir()
        filename = f"deepseek-harness-{VERSION}-mac-arm64-unsigned.dmg"
        payload = b"unit-test-dmg"
        (self.assets / filename).write_bytes(payload)
        metadata = {"schema_version": 1, "version": VERSION,
                    "upstream": {"repository": "deepseek-ai/deepseek-harness", "tag": "dsh-v" + VERSION, "commit": COMMIT},
                    "target": {"platform": "darwin", "arch": "arm64"},
                    "application": {"name": "DeepSeek Harness.app", "bundle_id": "com.deepseek.harness"},
                    "artifact": {"name": filename, "sha256": hashlib.sha256(payload).hexdigest()},
                    "signing": "ad-hoc", "automatic_updates": False}
        metadata_bytes = json.dumps(metadata).encode()
        (self.assets / "build-info.json").write_bytes(metadata_bytes)
        (self.assets / "SHA256SUMS").write_text(
            f"{hashlib.sha256(payload).hexdigest()}  {filename}\n"
            f"{hashlib.sha256(metadata_bytes).hexdigest()}  build-info.json\n")
        self.write_releases([release(VERSION)], [release(VERSION, "desktop-v", complete=True)])
        self.applications = self.root / "Applications"
        self.applications.mkdir()
        self.target = self.applications / "DeepSeek Harness.app"
        self.target.mkdir()
        (self.target / "old-application").write_text("old")
        contents = self.root / "source-app/Contents"
        (contents / "MacOS").mkdir(parents=True)
        (contents / "MacOS/DeepSeek Harness").write_text("new")
        with (contents / "Info.plist").open("wb") as file:
            plistlib.dump({"CFBundleShortVersionString": VERSION, "CFBundleIdentifier": "com.deepseek.harness", "CFBundleExecutable": "DeepSeek Harness"}, file)
        (self.root / "user-data").write_text("retain sessions")
        (self.root / "tmp").mkdir()
        self.env = dict(os.environ, PATH=str(self.mock_bin) + os.pathsep + os.environ["PATH"],
                        DSH_TEST_ROOT=str(self.root), DSH_APPLICATIONS_DIR=str(self.applications),
                        DSH_DESKTOP_REPO="jin-taiyu/deepseek-harness-desktop-builds",
                        TMPDIR=str(self.root / "tmp"), GITHUB_OUTPUT=str(self.root / "outputs"),
                        GITHUB_STEP_SUMMARY=str(self.root / "summary"))

    def tearDown(self):
        self.temporary.cleanup()

    def write_releases(self, upstream, built):
        (self.root / "upstream.json").write_text(json.dumps(upstream))
        (self.root / "built.json").write_text(json.dumps(built))

    def run_cli(self, *args, env=None):
        return subprocess.run(["/bin/bash", str(CLI), *args], env=env or self.env, text=True, capture_output=True)

    def source(self, code, data=""):
        return subprocess.run(["/bin/bash", "-c", 'source "$1"\n' + code, "test", str(CLI)],
                              env=self.env, input=data, text=True, capture_output=True)

    def resolve(self, **changes):
        return subprocess.run(["/bin/bash", str(ROOT / "scripts/resolve.sh")], env=dict(self.env, **changes), text=True, capture_output=True)

    def assert_clean_installation(self):
        self.assertEqual(list(self.applications.glob(".dsh-desktop-install.*")), [])
        self.assertEqual(list((self.root / "tmp").iterdir()), [])
        self.assertEqual((self.root / "user-data").read_text(), "retain sessions")

    def test_semver_order_and_invalid_versions(self):
        versions = ["1.0.0-rc.2", "1.0.0-alpha.10", "1.0.0", "1.0.0-alpha.9", "1.1.0-alpha.1", "1.0.0-beta.1", "01.0.0", "1.0.0-alpha.01"]
        result = self.source('jq -c "$DSH_JQ sorted_releases(\\\"dsh-v\\\") | map(._version)"', json.dumps([release(v) for v in versions]))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ["1.0.0-alpha.9", "1.0.0-alpha.10", "1.0.0-beta.1", "1.0.0-rc.2", "1.0.0", "1.1.0-alpha.1"])

    def test_ignore_drafts_and_other_tag_families(self):
        self.write_releases([release("99.0.0", draft=True), release("88.0.0", "vendor-v"), release(VERSION)], [])
        result = self.source('dsh_latest_upstream')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["tag_name"], "dsh-v" + VERSION)

    def test_latest_built_uses_semver_instead_of_publish_date(self):
        self.write_releases([], [release("0.1.0", "desktop-v", complete=True, published="2026-10-17T00:00:00Z"), release(VERSION, "desktop-v", complete=True), release("99.0.0", "desktop-v", complete=False)])
        result = self.source('dsh_built_release ""')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["_version"], VERSION)

    def test_no_mac_build_when_published_build_matches(self):
        result = self.resolve()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("should_build=false", (self.root / "outputs").read_text())

    def test_missing_build_requires_build(self):
        self.write_releases([release(VERSION)], [])
        result = self.resolve()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("should_build=true", (self.root / "outputs").read_text())

    def test_retargeted_upstream_tag_is_not_overwritten(self):
        result = self.resolve(DSH_TEST_COMMIT="2" * 40)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing to overwrite", result.stderr)

    def test_manual_build_requires_a_published_release(self):
        result = self.resolve(UPSTREAM_TAG="dsh-v0.0.1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no published upstream Release", result.stderr)

    def test_download_verifies_both_checksums(self):
        destination = self.root / "chosen download"
        result = self.run_cli("download", "--dest", str(destination))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(list(destination.iterdir())), 3)

    def test_checksum_failure_preserves_application(self):
        (self.assets / f"deepseek-harness-{VERSION}-mac-arm64-unsigned.dmg").write_text("corrupted")
        result = self.run_cli("install")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.target / "old-application").exists())
        self.assert_clean_installation()

    def test_running_application_is_not_replaced(self):
        result = self.run_cli("install", env=dict(self.env, DSH_TEST_RUNNING="1"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Fully quit", result.stderr)
        self.assertTrue((self.target / "old-application").exists())
        self.assert_clean_installation()

    def test_successful_install_replaces_only_the_application(self):
        result = self.run_cli("install")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.target / "old-application").exists())
        self.assertTrue((self.target / "Contents/Info.plist").exists())
        self.assert_clean_installation()

    def test_failed_rename_restores_previous_application(self):
        result = self.run_cli("install", env=dict(self.env, DSH_TEST_FAIL_RENAME="1"))
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.target / "old-application").exists())
        self.assert_clean_installation()

    def test_failed_final_signature_restores_previous_application(self):
        result = self.run_cli("install", env=dict(self.env, DSH_TEST_FAIL_FINAL_SIGNATURE="1"))
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.target / "old-application").exists())
        self.assert_clean_installation()

    def test_build_wait_uses_its_own_request(self):
        result = self.run_cli("build", "dsh-v" + VERSION, "--wait")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in (self.root / "gh-calls.jsonl").read_text().splitlines()]
        self.assertTrue(any(call[:3] == ["run", "watch", "7"] for call in calls))

    def test_failed_cloud_run_is_reported(self):
        result = self.run_cli("build", "--wait", env=dict(self.env, DSH_TEST_WATCH_STATUS="1"))
        self.assertNotEqual(result.returncode, 0)

    def test_invalid_tag_does_not_dispatch(self):
        result = self.run_cli("build", "master")
        self.assertNotEqual(result.returncode, 0)
        calls = [json.loads(line) for line in (self.root / "gh-calls.jsonl").read_text().splitlines()]
        self.assertFalse(any(call[:2] == ["workflow", "run"] for call in calls))


if __name__ == "__main__":
    unittest.main()
