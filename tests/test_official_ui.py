import json
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/official-ui.mjs"
TARGET = "apps/desktop/scripts/package-target.ts"
PACK = "apps/desktop/scripts/pack-local-packages.ts"


class OfficialUiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="official ui ")
        self.root = Path(self.temporary.name)
        files = {
            TARGET: "await execute(invocation.unsigned ? ['run', 'build', '--profile', 'local'] : ['run', 'build:official'], buildEnv, REPOSITORY_ROOT)\n",
            PACK: "/** Stage local-branded DSH packages for unsigned Desktop builds without a publication record. */\n"
                  "import {\n  readClientBuildRecord,\n  repositoryClientBuildEnvironment,\n  resolveClientBuildEnvironment,\n} from '../../../scripts/client-build-environment.ts'\n"
                  "const environment = resolveClientBuildEnvironment(repositoryClientBuildEnvironment(root), 'local')\n",
            "untouched.ts": "export const unchanged = true\n",
        }
        for name, data in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data)
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture")

    def tearDown(self):
        self.temporary.cleanup()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True, text=True, capture_output=True)

    def run_patch(self, mode):
        return subprocess.run(["node", str(SCRIPT), mode, str(self.root)], text=True, capture_output=True)

    def test_patch_selects_official_build_and_matching_package_validation(self):
        result = self.run_patch("apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("execute(['run', 'build:official']", (self.root / TARGET).read_text())
        self.assertIn("officialClientBuildEnvironment(root)", (self.root / PACK).read_text())
        self.assertEqual((self.root / "untouched.ts").read_text(), "export const unchanged = true\n")
        self.assertEqual(self.run_patch("verify").returncode, 0)
        export = subprocess.run(["node", "--input-type=module", "-e",
            "const {verifyOfficialUiPatch}=await import(process.argv[1]); console.log(JSON.stringify(verifyOfficialUiPatch(process.argv[2])))",
            SCRIPT.as_uri(), str(self.root)], check=True, text=True, capture_output=True)
        record = json.loads(export.stdout)
        self.assertEqual(record["recipe"], "official-ui-v1")
        self.assertEqual({file["path"] for file in record["files"]}, {TARGET, PACK})
        self.assertTrue(all(file["upstream_sha256"] != file["patched_sha256"] for file in record["files"]))

    def test_unknown_upstream_code_fails_without_partial_patch(self):
        path = self.root / PACK
        path.write_text("unsupported upstream change\n")
        self.git("add", ".")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "upstream drift")
        original = (self.root / TARGET).read_bytes()
        result = self.run_patch("apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unsupported upstream source", result.stderr)
        self.assertEqual((self.root / TARGET).read_bytes(), original)
        self.assertEqual(self.git("diff", "--name-only").stdout, "")

    def test_dirty_source_is_rejected_before_applying(self):
        (self.root / "untouched.ts").write_text("modified\n")
        result = self.run_patch("apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("clean source checkout", result.stderr)

    def test_extra_source_change_is_rejected_when_recording(self):
        self.assertEqual(self.run_patch("apply").returncode, 0)
        (self.root / "untouched.ts").write_text("modified\n")
        result = self.run_patch("verify")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Source changes differ", result.stderr)

    def test_tampered_patch_is_rejected_when_recording(self):
        self.assertEqual(self.run_patch("apply").returncode, 0)
        with (self.root / TARGET).open("a") as file:
            file.write("unexpected change\n")
        result = self.run_patch("verify")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unexpected source changes", result.stderr)


if __name__ == "__main__":
    unittest.main()
