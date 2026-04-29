"""Unit tests for agents/secops/skills.py — pure functions only.

All tests run without the `shadi` native extension, a running GitHub server, or
any external network access.  Functions that touch the network, subprocess, or
the SHADI store are tested with lightweight mocks / tmp directories.
"""

import json
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Allow importing skills.py without the shadi native extension.
# ---------------------------------------------------------------------------
_FAKE_SHADI = MagicMock()
sys.modules.setdefault("shadi", _FAKE_SHADI)
sys.modules.setdefault("telemetry", MagicMock(tracer=MagicMock()))

sys.path.insert(0, str(Path(__file__).parent.parent))

import skills  # noqa: E402  (must come after sys.modules patching)


# ===========================================================================
# Helpers / fixtures
# ===========================================================================


@pytest.fixture()
def tmp_repo(tmp_path):
    """Return a temporary directory that looks like a cloned repository."""
    return tmp_path


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


# ===========================================================================
# get_alert_severity / is_actionable_alert
# ===========================================================================


class TestGetAlertSeverity:
    def test_from_advisory(self):
        alert = {"security_advisory": {"severity": "HIGH"}}
        assert skills.get_alert_severity(alert) == "high"

    def test_from_vulnerability(self):
        alert = {"security_vulnerability": {"severity": "Critical"}}
        assert skills.get_alert_severity(alert) == "critical"

    def test_advisory_takes_precedence(self):
        alert = {
            "security_advisory": {"severity": "high"},
            "security_vulnerability": {"severity": "low"},
        }
        assert skills.get_alert_severity(alert) == "high"

    def test_empty_alert(self):
        assert skills.get_alert_severity({}) == ""

    def test_none_values(self):
        assert skills.get_alert_severity({"security_advisory": None}) == ""


class TestIsActionableAlert:
    @pytest.mark.parametrize("severity", ["critical", "high"])
    def test_actionable(self, severity):
        alert = {"security_advisory": {"severity": severity}}
        assert skills.is_actionable_alert(alert) is True

    @pytest.mark.parametrize("severity", ["medium", "low", ""])
    def test_not_actionable(self, severity):
        alert = {"security_advisory": {"severity": severity}}
        assert skills.is_actionable_alert(alert) is False


# ===========================================================================
# get_patched_version
# ===========================================================================


class TestGetPatchedVersion:
    def test_returns_identifier(self):
        alert = {
            "security_vulnerability": {
                "first_patched_version": {"identifier": "2.1.0"}
            }
        }
        assert skills.get_patched_version(alert) == "2.1.0"

    def test_empty_when_no_patch(self):
        assert skills.get_patched_version({}) == ""

    def test_empty_when_first_patched_missing(self):
        alert = {"security_vulnerability": {"first_patched_version": {}}}
        assert skills.get_patched_version(alert) == ""


# ===========================================================================
# is_conventional_commit
# ===========================================================================


class TestIsConventionalCommit:
    @pytest.mark.parametrize(
        "msg",
        [
            "feat: add new feature",
            "fix(auth): repair token refresh",
            "chore(deps): bump cryptography",
            "docs: update README",
            "refactor: clean up parser",
            "revert: revert bad commit",
        ],
    )
    def test_valid(self, msg):
        assert skills.is_conventional_commit(msg) is True

    @pytest.mark.parametrize(
        "msg",
        [
            "random message",
            "FIX: capital type",
            "feat add missing colon",
            "",
        ],
    )
    def test_invalid(self, msg):
        assert skills.is_conventional_commit(msg) is False


# ===========================================================================
# parse_trivy_message
# ===========================================================================


class TestParseTrivyMessage:
    def test_typical_message(self):
        text = (
            "Package: zlib\n"
            "Installed Version: 1.2.11\n"
            "Fixed Version: 1.2.13\n"
            "Source SARIF File: trivy-report-frontend/trivy-frontend.sarif\n"
        )
        result = skills.parse_trivy_message(text)
        assert result["package"] == "zlib"
        assert result["installed_version"] == "1.2.11"
        assert result["fixed_version"] == "1.2.13"
        assert result["source_sarif_file"] == "trivy-report-frontend/trivy-frontend.sarif"

    def test_empty_string(self):
        assert skills.parse_trivy_message("") == {}

    def test_none(self):
        assert skills.parse_trivy_message(None) == {}

    def test_line_without_colon_ignored(self):
        result = skills.parse_trivy_message("just a plain line\nkey: value")
        assert result.get("key") == "value"
        assert "just a plain line" not in result


# ===========================================================================
# is_actionable_code_scanning_alert
# ===========================================================================


class TestIsActionableCodeScanningAlert:
    @pytest.mark.parametrize("sev", ["error", "critical", "high", "warning"])
    def test_actionable(self, sev):
        alert = {"rule": {"severity": sev}}
        assert skills.is_actionable_code_scanning_alert(alert) is True

    @pytest.mark.parametrize("sev", ["note", "info", ""])
    def test_not_actionable(self, sev):
        alert = {"rule": {"severity": sev}}
        assert skills.is_actionable_code_scanning_alert(alert) is False

    def test_missing_rule(self):
        assert skills.is_actionable_code_scanning_alert({}) is False


# ===========================================================================
# detect_dockerfile_ecosystem
# ===========================================================================


class TestDetectDockerfileEcosystem:
    def test_alpine(self, tmp_path):
        p = write(tmp_path / "Dockerfile", "FROM alpine:3.19\nRUN echo hi\n")
        assert skills.detect_dockerfile_ecosystem(p) == "alpine"

    def test_debian(self, tmp_path):
        p = write(tmp_path / "Dockerfile", "FROM debian:bookworm-slim\n")
        assert skills.detect_dockerfile_ecosystem(p) == "debian"

    def test_ubuntu(self, tmp_path):
        p = write(tmp_path / "Dockerfile", "FROM ubuntu:jammy\n")
        assert skills.detect_dockerfile_ecosystem(p) == "debian"

    def test_unknown(self, tmp_path):
        p = write(tmp_path / "Dockerfile", "FROM scratch\n")
        assert skills.detect_dockerfile_ecosystem(p) == "unknown"

    def test_missing_file(self, tmp_path):
        assert skills.detect_dockerfile_ecosystem(tmp_path / "Dockerfile") == "unknown"

    def test_multistage_uses_first_from(self, tmp_path):
        content = "FROM alpine:3.19 AS builder\nFROM ubuntu:focal\n"
        p = write(tmp_path / "Dockerfile", content)
        assert skills.detect_dockerfile_ecosystem(p) == "alpine"


# ===========================================================================
# extract_dockerfile_base_image
# ===========================================================================


class TestExtractDockerfileBaseImage:
    def test_returns_first_from_image(self, tmp_path):
        p = write(tmp_path / "Dockerfile", "FROM alpine:3.19\nRUN echo app\n")
        assert skills.extract_dockerfile_base_image(p) == "alpine:3.19"

    def test_preserves_multistage_first_image(self, tmp_path):
        p = write(
            tmp_path / "Dockerfile",
            "FROM python:3.12 AS builder\nRUN make\nFROM alpine:3.19\nRUN ./app\n",
        )
        assert skills.extract_dockerfile_base_image(p) == "python:3.12"

    def test_missing_file(self, tmp_path):
        assert skills.extract_dockerfile_base_image(tmp_path / "Dockerfile") == ""

    def test_no_from_returns_empty(self, tmp_path):
        p = write(tmp_path / "Dockerfile", "# generated elsewhere\n")
        assert skills.extract_dockerfile_base_image(p) == ""


# ===========================================================================
# update_cargo_manifest
# ===========================================================================


class TestUpdateCargoManifest:
    def test_simple_version_line(self, tmp_path):
        p = write(tmp_path / "Cargo.toml", 'serde = "1.0.0"\nother = "2.0"\n')
        assert skills.update_cargo_manifest(p, "serde", "1.0.100") is True
        assert 'serde = "1.0.100"' in p.read_text()

    def test_table_version(self, tmp_path):
        p = write(tmp_path / "Cargo.toml", 'serde = { version = "1.0.0", features = ["derive"] }\n')
        assert skills.update_cargo_manifest(p, "serde", "1.0.100") is True
        assert 'version = "1.0.100"' in p.read_text()

    def test_unrelated_package_untouched(self, tmp_path):
        p = write(tmp_path / "Cargo.toml", 'other = "2.0"\n')
        assert skills.update_cargo_manifest(p, "serde", "1.0.100") is False

    def test_missing_file(self, tmp_path):
        assert skills.update_cargo_manifest(tmp_path / "Cargo.toml", "serde", "1.0") is False


# ===========================================================================
# update_package_json
# ===========================================================================


class TestUpdatePackageJson:
    def test_updates_dependency(self, tmp_path):
        data = {"dependencies": {"lodash": "^4.17.0"}}
        p = write(tmp_path / "package.json", json.dumps(data))
        assert skills.update_package_json(p, "lodash", "4.17.21") is True
        result = json.loads(p.read_text())
        assert result["dependencies"]["lodash"] == "^4.17.21"

    def test_updates_dev_dependency(self, tmp_path):
        data = {"devDependencies": {"jest": "~29.0.0"}}
        p = write(tmp_path / "package.json", json.dumps(data))
        assert skills.update_package_json(p, "jest", "29.5.0") is True
        result = json.loads(p.read_text())
        assert result["devDependencies"]["jest"] == "~29.5.0"

    def test_not_present(self, tmp_path):
        data = {"dependencies": {"react": "18.0.0"}}
        p = write(tmp_path / "package.json", json.dumps(data))
        assert skills.update_package_json(p, "lodash", "4.17.21") is False

    def test_missing_file(self, tmp_path):
        assert skills.update_package_json(tmp_path / "package.json", "pkg", "1.0") is False


# ===========================================================================
# workspace path handling
# ===========================================================================


class TestWorkspacePaths:
    def test_resolve_workspace_path_returns_absolute_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        resolved = skills.resolve_workspace_path("./.tmp/shadi-secops")
        assert resolved == (tmp_path / ".tmp" / "shadi-secops").resolve()

    def test_write_pending_prs_creates_parent_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        path = skills.write_pending_prs("./.tmp/shadi-secops", {"repos": {}})
        assert path.exists()
        assert path.parent == (tmp_path / ".tmp" / "shadi-secops").resolve()

    def test_collect_security_report_creates_workspace_before_gh_calls(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        def fake_dependabot(api_base, token, repo):
            return []

        def fake_issues(api_base, token, repo, label):
            return []

        def fake_code_scanning(token, repo, cwd):
            assert cwd == (tmp_path / ".tmp" / "shadi-secops").resolve()
            assert cwd.exists()
            return []

        monkeypatch.setattr(skills, "fetch_dependabot_alerts", fake_dependabot)
        monkeypatch.setattr(skills, "fetch_security_issues", fake_issues)
        monkeypatch.setattr(skills, "fetch_code_scanning_alerts_gh", fake_code_scanning)

        report, total_alerts, total_issues, total_code_scanning = skills.collect_security_report(
            {"github": {}},
            "token",
            ["agntcy/shadi"],
            ["security"],
            workspace_dir="./.tmp/shadi-secops",
        )

        assert total_alerts == 0
        assert total_issues == 0
        assert total_code_scanning == 0
        assert "agntcy/shadi" in report["repos"]


class TestSubprocessEncoding:
    def test_run_git_uses_utf8_decoding(self, tmp_path):
        completed = subprocess.CompletedProcess(["git"], 0, stdout="", stderr="")
        with patch.object(skills.subprocess, "run", return_value=completed) as run_mock:
            skills.run_git(["status"], tmp_path)

        kwargs = run_mock.call_args.kwargs
        assert kwargs["encoding"] == "utf-8"
        assert kwargs["errors"] == "replace"
        assert kwargs["text"] is True

    def test_run_gh_uses_utf8_decoding(self, tmp_path):
        completed = subprocess.CompletedProcess(["gh"], 0, stdout="{}", stderr="")
        with patch.object(skills.shutil, "which", return_value="gh"):
            with patch.object(skills.subprocess, "run", return_value=completed) as run_mock:
                skills.run_gh(["api", "repos/agntcy/shadi"], tmp_path, "token")

        kwargs = run_mock.call_args.kwargs
        assert kwargs["encoding"] == "utf-8"
        assert kwargs["errors"] == "replace"
        assert kwargs["text"] is True


# ===========================================================================
# update_requirements_txt
# ===========================================================================


class TestUpdateRequirementsTxt:
    @pytest.mark.parametrize(
        "original, pkg, ver, expected",
        [
            ("authlib==1.3.0\n", "authlib", "1.4.0", "authlib==1.4.0"),
            ("nltk>=3.8,<4.0\n", "nltk", "3.9.0", "nltk==3.9.0"),
            ("pillow~=10.0\n", "pillow", "10.4.0", "pillow==10.4.0"),
            ("cryptography\n", "cryptography", "42.0.0", "cryptography>=42.0.0"),
            ("Pillow==10.0\n", "pillow", "10.4.0", "Pillow==10.4.0"),  # case-insensitive match
        ],
    )
    def test_updates(self, tmp_path, original, pkg, ver, expected):
        p = write(tmp_path / "requirements.txt", original)
        assert skills.update_requirements_txt(p, pkg, ver) is True
        assert expected in p.read_text()

    def test_untouched_package_preserved(self, tmp_path):
        p = write(tmp_path / "requirements.txt", "requests>=2.31.0\nflask==3.0\n")
        skills.update_requirements_txt(p, "flask", "3.1.0")
        assert "requests>=2.31.0" in p.read_text()

    def test_comment_preserved_on_bare_line(self, tmp_path):
        p = write(tmp_path / "requirements.txt", "cryptography  # security\n")
        skills.update_requirements_txt(p, "cryptography", "42.0.0")
        assert "# security" in p.read_text()

    def test_package_not_present(self, tmp_path):
        p = write(tmp_path / "requirements.txt", "flask==3.0\n")
        assert skills.update_requirements_txt(p, "django", "4.0") is False

    def test_missing_file(self, tmp_path):
        assert skills.update_requirements_txt(tmp_path / "requirements.txt", "x", "1.0") is False

    def test_extras_preserved(self, tmp_path):
        p = write(tmp_path / "requirements.txt", "pillow[jpeg]==10.0\n")
        skills.update_requirements_txt(p, "pillow", "10.4.0")
        assert "pillow[jpeg]==10.4.0" in p.read_text()


# ===========================================================================
# update_pyproject_toml
# ===========================================================================


class TestUpdatePyprojectToml:
    def test_pep508_array_entry(self, tmp_path):
        content = '[project]\ndependencies = [\n    "authlib>=1.3.0",\n]\n'
        p = write(tmp_path / "pyproject.toml", content)
        assert skills.update_pyproject_toml(p, "authlib", "1.4.0") is True
        assert "authlib>=1.4.0" in p.read_text()

    def test_poetry_caret(self, tmp_path):
        content = '[tool.poetry.dependencies]\npillow = "^10.0.0"\n'
        p = write(tmp_path / "pyproject.toml", content)
        assert skills.update_pyproject_toml(p, "pillow", "10.4.0") is True
        result = p.read_text()
        assert "10.4.0" in result

    def test_exact_pin_preserved(self, tmp_path):
        content = '[project]\ndependencies = [\n    "cryptography==41.0.0",\n]\n'
        p = write(tmp_path / "pyproject.toml", content)
        skills.update_pyproject_toml(p, "cryptography", "42.0.0")
        assert "42.0.0" in p.read_text()

    def test_unrelated_package_untouched(self, tmp_path):
        content = '[project]\ndependencies = [\n    "flask>=3.0",\n]\n'
        p = write(tmp_path / "pyproject.toml", content)
        assert skills.update_pyproject_toml(p, "django", "4.0") is False

    def test_missing_file(self, tmp_path):
        assert skills.update_pyproject_toml(tmp_path / "pyproject.toml", "x", "1.0") is False


# ===========================================================================
# update_dockerfile_base_image
# ===========================================================================


class TestUpdateDockerfileBaseImage:
    def test_updates_tagged_image(self, tmp_path):
        p = write(tmp_path / "Dockerfile", "FROM python:3.12\n")
        assert skills.update_dockerfile_base_image(p, "python", "3.12.4") is True
        assert "FROM python:3.12.4" in p.read_text()

    def test_preserves_as_clause(self, tmp_path):
        p = write(tmp_path / "Dockerfile", "FROM python:3.12 AS base\n")
        skills.update_dockerfile_base_image(p, "python", "3.12.4")
        assert "FROM python:3.12.4 AS base" in p.read_text()

    def test_no_match(self, tmp_path):
        p = write(tmp_path / "Dockerfile", "FROM alpine:3.19\n")
        assert skills.update_dockerfile_base_image(p, "python", "3.12.4") is False

    def test_missing_file(self, tmp_path):
        assert skills.update_dockerfile_base_image(tmp_path / "Dockerfile", "python", "3.12") is False


# ===========================================================================
# _extract_dockerfile_hints_from_workflows
# ===========================================================================


class TestExtractDockerfileHintsFromWorkflows:
    def _make_repo(self, tmp_path, dockerfiles, workflow_text):
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "build.yml").write_text(workflow_text, encoding="utf-8")
        for rel in dockerfiles:
            df = tmp_path / rel
            df.parent.mkdir(parents=True, exist_ok=True)
            df.write_text("FROM alpine:3.19\n", encoding="utf-8")
        return tmp_path

    def test_file_field(self, tmp_path):
        wf = textwrap.dedent("""\
            jobs:
              build:
                steps:
                  - name: build-frontend
                    file: frontend/Dockerfile
                    context: frontend
                    tags: ghcr.io/org/frontend:latest
        """)
        repo = self._make_repo(tmp_path, ["frontend/Dockerfile"], wf)
        results = skills._extract_dockerfile_hints_from_workflows(repo)
        assert len(results) == 1
        hints, df_path = results[0]
        assert df_path == repo / "frontend" / "Dockerfile"
        assert any("frontend" in h for h in hints)

    def test_docker_build_dash_f(self, tmp_path):
        wf = textwrap.dedent("""\
            jobs:
              build:
                steps:
                  - name: build scheduler
                    run: docker build -f scheduler/Dockerfile .
        """)
        repo = self._make_repo(tmp_path, ["scheduler/Dockerfile"], wf)
        results = skills._extract_dockerfile_hints_from_workflows(repo)
        assert any(df.name == "Dockerfile" and df.parent.name == "scheduler" for _, df in results)

    def test_no_workflow_dir(self, tmp_path):
        assert skills._extract_dockerfile_hints_from_workflows(tmp_path) == []

    def test_path_traversal_ignored(self, tmp_path):
        wf = textwrap.dedent("""\
            steps:
              - file: ../../etc/passwd
        """)
        (tmp_path / ".github" / "workflows").mkdir(parents=True)
        (tmp_path / ".github" / "workflows" / "bad.yml").write_text(wf)
        results = skills._extract_dockerfile_hints_from_workflows(tmp_path)
        assert results == []

    def test_template_variable_ignored(self, tmp_path):
        wf = textwrap.dedent("""\
            steps:
              - file: ${{ matrix.dockerfile }}
        """)
        (tmp_path / ".github" / "workflows").mkdir(parents=True)
        (tmp_path / ".github" / "workflows" / "ci.yml").write_text(wf)
        results = skills._extract_dockerfile_hints_from_workflows(tmp_path)
        assert results == []

    def test_image_tag_hint_extracted(self, tmp_path):
        wf = textwrap.dedent("""\
            steps:
              - name: push-scheduler-agent
                context: services/scheduler-agent
                tags: ghcr.io/org/scheduler-agent:latest
        """)
        repo = self._make_repo(tmp_path, ["services/scheduler-agent/Dockerfile"], wf)
        results = skills._extract_dockerfile_hints_from_workflows(repo)
        assert len(results) == 1
        hints, _ = results[0]
        assert "scheduler-agent" in hints

        def test_dockerfile_field_resolves_relative_to_context(self, tmp_path):
                wf = textwrap.dedent("""\
                        jobs:
                            build:
                                strategy:
                                    matrix:
                                        include:
                                            - name: worker-agent
                                                dockerfile: containers/worker/Dockerfile
                                                context: services/app
                """)
                repo = self._make_repo(tmp_path, ["services/app/containers/worker/Dockerfile"], wf)
                results = skills._extract_dockerfile_hints_from_workflows(repo)
                assert len(results) == 1
                hints, df_path = results[0]
                assert df_path == repo / "services" / "app" / "containers" / "worker" / "Dockerfile"
                assert "worker-agent" in hints


# ===========================================================================
# _find_dockerfile_for_alert
# ===========================================================================


class TestFindDockerfileForAlert:
    def _alert(self, alert_path="", sarif_file="", rule_desc="", severity="error"):
        return {
            "rule": {"id": "CVE-TEST", "severity": severity, "description": rule_desc},
            "most_recent_instance": {
                "location": {"path": alert_path},
                "message": {"text": f"Source SARIF File: {sarif_file}\n"},
            },
        }

    def test_direct_dockerfile_path(self, tmp_path):
        df = write(tmp_path / "services" / "api" / "Dockerfile", "FROM alpine:3\n")
        alert = self._alert(alert_path="services/api/Dockerfile")
        fields = {"source_sarif_file": ""}
        result = skills._find_dockerfile_for_alert(tmp_path, alert, fields)
        assert result == df

    def test_sarif_stem_hint_match(self, tmp_path):
        df = write(tmp_path / "frontend" / "Dockerfile", "FROM node:20\n")
        alert = self._alert(sarif_file="trivy-report-frontend/trivy-frontend.sarif")
        fields = skills.parse_trivy_message(f"Source SARIF File: trivy-report-frontend/trivy-frontend.sarif\n")
        result = skills._find_dockerfile_for_alert(tmp_path, alert, fields)
        assert result == df

    def test_single_dockerfile_fallback(self, tmp_path):
        df = write(tmp_path / "app" / "Dockerfile", "FROM debian:bookworm\n")
        alert = self._alert()
        result = skills._find_dockerfile_for_alert(tmp_path, alert, {})
        assert result == df

    def test_no_dockerfile_returns_none(self, tmp_path):
        alert = self._alert()
        assert skills._find_dockerfile_for_alert(tmp_path, alert, {}) is None

    def test_workflow_hint_match(self, tmp_path):
        # Dockerfile is in a non-obvious location; workflow maps "scheduler-agent" to it.
        df = write(tmp_path / "services" / "sched" / "Dockerfile", "FROM alpine:3\n")
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text(
            "steps:\n"
            "  - name: build-scheduler-agent\n"
            f"    file: services/sched/Dockerfile\n"
            "    tags: ghcr.io/org/scheduler-agent:latest\n",
            encoding="utf-8",
        )
        alert = self._alert(sarif_file="trivy-scheduler-agent.sarif")
        fields = skills.parse_trivy_message("Source SARIF File: trivy-scheduler-agent.sarif\n")
        result = skills._find_dockerfile_for_alert(tmp_path, alert, fields)
        assert result == df

    def test_workflow_path_preferred_over_generic_repo_match(self, tmp_path):
        workflow_df = write(
            tmp_path / "services" / "app" / "containers" / "scheduler" / "Dockerfile",
            "FROM alpine:3\n",
        )
        write(
            tmp_path / "scratch" / "scheduler" / "Dockerfile",
            "FROM alpine:3\n",
        )
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "build.yml").write_text(
            textwrap.dedent(
                """\
                jobs:
                  build:
                    strategy:
                      matrix:
                        include:
                          - name: scheduler-agent
                            dockerfile: containers/scheduler/Dockerfile
                            context: services/app
                """
            ),
            encoding="utf-8",
        )
        alert = {
            "rule": {"id": "CVE-TEST", "severity": "warning", "description": ""},
            "most_recent_instance": {
                "category": "trivy-scheduler-agent",
                "environment": json.dumps(
                    {
                        "image": "scheduler-agent",
                        "repo": "registry.example/platform/scheduler-agent",
                        "version": "latest",
                    }
                ),
                "location": {"path": "platform/images/scheduler-agent"},
                "message": {"text": "Package: libgnutls30t64\nFixed Version: 3.8.9-3+deb13u2\n"},
            },
        }
        result = skills._find_dockerfile_for_alert(tmp_path, alert, {})
        assert result == workflow_df

    def test_filesystem_hint_match_without_workflow(self, tmp_path):
        scheduler_df = write(
            tmp_path / "tourist_scheduling_system" / "containers" / "scheduler" / "Dockerfile",
            "FROM debian:bookworm\n",
        )
        write(
            tmp_path / "tourist_scheduling_system" / "containers" / "ui" / "Dockerfile",
            "FROM debian:bookworm\n",
        )
        write(
            tmp_path / "tourist_scheduling_system" / "containers" / "frontend" / "Dockerfile",
            "FROM nginx:1.27\n",
        )
        alert = {
            "rule": {"id": "CVE-TEST", "severity": "warning", "description": ""},
            "most_recent_instance": {
                "category": "trivy-scheduler-agent",
                "environment": json.dumps(
                    {
                        "image": "scheduler-agent",
                        "repo": "registry.example/platform/scheduler-agent",
                        "version": "latest",
                    }
                ),
                "location": {"path": "platform/images/scheduler-agent"},
                "message": {"text": "Package: libgnutls30t64\nFixed Version: 3.8.9-3+deb13u2\n"},
            },
        }
        result = skills._find_dockerfile_for_alert(tmp_path, alert, {})
        assert result == scheduler_df

    def test_hidden_dockerfiles_excluded(self, tmp_path):
        # A Dockerfile inside .docker should be ignored
        write(tmp_path / ".docker" / "Dockerfile", "FROM alpine:3\n")
        alert = self._alert()
        assert skills._find_dockerfile_for_alert(tmp_path, alert, {}) is None

    def test_workflow_hint_match_from_category_and_environment(self, tmp_path):
        df = write(
            tmp_path / "tourist_scheduling_system" / "containers" / "scheduler" / "Dockerfile",
            "FROM debian:bookworm\n",
        )
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "build.yml").write_text(
            textwrap.dedent(
                """\
                jobs:
                  build:
                    strategy:
                      matrix:
                        include:
                          - name: scheduler-agent
                            dockerfile: containers/scheduler/Dockerfile
                            context: tourist_scheduling_system
                """
            ),
            encoding="utf-8",
        )
        alert = {
            "rule": {"id": "CVE-TEST", "severity": "warning", "description": ""},
            "most_recent_instance": {
                "category": "trivy-scheduler-agent",
                "environment": json.dumps(
                    {
                        "image": "scheduler-agent",
                        "repo": "registry.example/platform/scheduler-agent",
                        "version": "latest",
                    }
                ),
                "location": {"path": "platform/images/scheduler-agent"},
                "message": {"text": "Package: libgnutls30t64\nFixed Version: 3.8.9-3+deb13u2\n"},
            },
        }
        result = skills._find_dockerfile_for_alert(tmp_path, alert, {})
        assert result == df

    def test_relative_repo_path_with_workflow_context(self, tmp_path, monkeypatch):
        repo_dir = tmp_path / "agentic-apps"
        df = write(
            repo_dir / "tourist_scheduling_system" / "containers" / "scheduler" / "Dockerfile",
            "FROM debian:bookworm\n",
        )
        wf_dir = repo_dir / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "build-tss-images.yml").write_text(
            textwrap.dedent(
                """\
                jobs:
                  build:
                    strategy:
                      matrix:
                        include:
                          - name: scheduler-agent
                            dockerfile: containers/scheduler/Dockerfile
                            context: tourist_scheduling_system
                """
            ),
            encoding="utf-8",
        )
        alert = {
            "rule": {"id": "CVE-TEST", "severity": "warning", "description": ""},
            "most_recent_instance": {
                "category": "trivy-scheduler-agent",
                "environment": json.dumps(
                    {
                        "image": "scheduler-agent",
                        "repo": "registry.example/platform/scheduler-agent",
                        "version": "latest",
                    }
                ),
                "location": {"path": "platform/images/scheduler-agent"},
                "message": {"text": "Package: libgnutls30t64\nFixed Version: 3.8.9-3+deb13u2\n"},
            },
        }
        monkeypatch.chdir(tmp_path)

        result = skills._find_dockerfile_for_alert(Path("agentic-apps"), alert, {})

        assert result == df


# ===========================================================================
# apply_container_cve_patch
# ===========================================================================


class TestApplyContainerCvePatch:
    def _make_alert(self, sarif_file="trivy-frontend.sarif", cve="CVE-2026-1234"):
        return {
            "rule": {"id": cve, "severity": "error"},
            "most_recent_instance": {
                "location": {"path": ""},
                "message": {
                    "text": (
                        f"Package: zlib\n"
                        f"Fixed Version: 1.2.13\n"
                        f"Source SARIF File: {sarif_file}\n"
                    )
                },
            },
        }

    def test_returns_base_image_refresh_guidance(self, tmp_path):
        write(tmp_path / "frontend" / "Dockerfile", "FROM alpine:3.19\n")
        with patch.object(skills, "run_git") as mock_git:
            result = skills.apply_container_cve_patch(tmp_path, self._make_alert())
        assert result["status"] == "base_image_refresh_recommended"
        assert result["cve_id"] == "CVE-2026-1234"
        assert result["package"] == "zlib"
        assert result["base_image"] == "alpine:3.19"
        mock_git.assert_not_called()

    def test_no_package_in_message(self, tmp_path):
        write(tmp_path / "frontend" / "Dockerfile", "FROM alpine:3.19\n")
        alert = {
            "rule": {"id": "CVE-X", "severity": "error"},
            "most_recent_instance": {
                "location": {"path": ""},
                "message": {"text": "Fixed Version: 1.2.0\n"},
            },
        }
        result = skills.apply_container_cve_patch(tmp_path, alert)
        assert result["status"] == "no_package"

    def test_no_dockerfile_found(self, tmp_path):
        result = skills.apply_container_cve_patch(tmp_path, self._make_alert())
        assert result["status"] == "no_dockerfile_found"

    def test_requires_manual_review_when_base_image_missing(self, tmp_path):
        write(tmp_path / "frontend" / "Dockerfile", "# populated by build system\n")
        result = skills.apply_container_cve_patch(tmp_path, self._make_alert())
        assert result["status"] == "base_image_review_required"

    def test_does_not_stage_container_guidance(self, tmp_path):
        write(tmp_path / "frontend" / "Dockerfile", "FROM alpine:3.19\n")
        with patch.object(skills, "run_git") as mock_git:
            skills.apply_container_cve_patch(tmp_path, self._make_alert())
        mock_git.assert_not_called()


# ===========================================================================
# apply_dependency_patch — pip / requirements.txt
# ===========================================================================


class TestApplyDependencyPatch:
    def _alert(self, ecosystem, name, manifest, patched_version):
        return {
            "dependency": {
                "package": {"ecosystem": ecosystem, "name": name},
                "manifest_path": manifest,
            },
            "security_vulnerability": {
                "first_patched_version": {"identifier": patched_version}
            },
        }

    def test_no_patch_available(self, tmp_path):
        alert = {
            "dependency": {
                "package": {"ecosystem": "pip", "name": "flask"},
                "manifest_path": "requirements.txt",
            },
            "security_vulnerability": {"first_patched_version": {}},
        }
        result = skills.apply_dependency_patch(tmp_path, alert)
        assert result["status"] == "no_patch"

    def test_requirements_txt(self, tmp_path):
        write(tmp_path / "requirements.txt", "authlib==1.3.0\n")
        alert = self._alert("pip", "authlib", "requirements.txt", "1.4.0")
        with patch.object(skills, "run_git"):
            result = skills.apply_dependency_patch(tmp_path, alert)
        assert result["status"] == "updated"
        assert "authlib==1.4.0" in (tmp_path / "requirements.txt").read_text()

    def test_requirements_txt_not_found(self, tmp_path):
        alert = self._alert("pip", "flask", "requirements.txt", "3.1.0")
        # File does not exist — update_requirements_txt returns False
        result = skills.apply_dependency_patch(tmp_path, alert)
        assert result["status"] == "not_updated"

    def test_pyproject_toml(self, tmp_path):
        write(tmp_path / "pyproject.toml", '[project]\ndependencies = [\n    "cryptography>=41.0.0",\n]\n')
        alert = self._alert("pip", "cryptography", "pyproject.toml", "42.0.0")
        with patch.object(skills, "run_git"):
            result = skills.apply_dependency_patch(tmp_path, alert)
        assert result["status"] == "updated"

    def test_uv_lock_missing(self, tmp_path):
        alert = self._alert("pip", "pillow", "uv.lock", "10.4.0")
        result = skills.apply_dependency_patch(tmp_path, alert)
        assert result["status"] == "missing_lockfile"

    def test_uv_lock_happy_path(self, tmp_path):
        (tmp_path / "uv.lock").write_text("", encoding="utf-8")
        alert = self._alert("pip", "pillow", "uv.lock", "10.4.0")
        with patch("shutil.which", return_value="/usr/bin/uv"), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run, \
             patch.object(skills, "run_git"):
            result = skills.apply_dependency_patch(tmp_path, alert)
        assert result["status"] == "updated"
        # uv lock --upgrade-package must have been called
        cmd = mock_run.call_args[0][0]
        assert "uv" in cmd and "lock" in cmd

    def test_uv_lock_git_add_uses_repo_relative_path(self, tmp_path, monkeypatch):
        repo_dir = tmp_path / "agentic-apps"
        lockfile = repo_dir / "tourist_scheduling_system" / "uv.lock"
        lockfile.parent.mkdir(parents=True)
        lockfile.write_text("", encoding="utf-8")
        alert = self._alert("pip", "pillow", "tourist_scheduling_system/uv.lock", "10.4.0")
        monkeypatch.chdir(tmp_path)

        with patch("shutil.which", return_value="/usr/bin/uv"), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)), \
             patch.object(skills, "run_git") as mock_git:
            result = skills.apply_dependency_patch(Path("agentic-apps"), alert)

        assert result["status"] == "updated"
        mock_git.assert_called_once_with(
            ["add", "tourist_scheduling_system/uv.lock"],
            Path("agentic-apps"),
            token=None,
        )

    def test_uv_not_installed(self, tmp_path):
        (tmp_path / "uv.lock").write_text("", encoding="utf-8")
        alert = self._alert("pip", "pillow", "uv.lock", "10.4.0")
        with patch("shutil.which", return_value=None):
            result = skills.apply_dependency_patch(tmp_path, alert)
        assert result["status"] == "missing_uv"

    def test_unsupported_manifest(self, tmp_path):
        write(tmp_path / "Pipfile", '[packages]\nflask = "*"\n')
        alert = self._alert("pip", "flask", "Pipfile", "3.1.0")
        result = skills.apply_dependency_patch(tmp_path, alert)
        assert result["status"] == "unsupported_manifest"

    def test_unsupported_ecosystem(self, tmp_path):
        alert = self._alert("gems", "rack", "Gemfile", "3.0.0")
        result = skills.apply_dependency_patch(tmp_path, alert)
        assert result["status"] == "unsupported"

    def test_npm(self, tmp_path):
        pkg = {"dependencies": {"lodash": "^4.17.0"}}
        write(tmp_path / "package.json", json.dumps(pkg))
        alert = self._alert("npm", "lodash", "package.json", "4.17.21")
        with patch("subprocess.run", return_value=MagicMock(returncode=0)), \
             patch.object(skills, "run_git"):
            result = skills.apply_dependency_patch(tmp_path, alert)
        assert result["status"] == "updated"
        result_pkg = json.loads((tmp_path / "package.json").read_text())
        assert result_pkg["dependencies"]["lodash"] == "^4.17.21"

    def test_cargo(self, tmp_path):
        write(tmp_path / "Cargo.toml", 'serde = "1.0.0"\n')
        alert = self._alert("cargo", "serde", "Cargo.toml", "1.0.100")
        with patch("subprocess.run", return_value=MagicMock(returncode=0)), \
             patch.object(skills, "run_git"):
            result = skills.apply_dependency_patch(tmp_path, alert)
        assert result["status"] == "updated"
        assert 'serde = "1.0.100"' in (tmp_path / "Cargo.toml").read_text()
