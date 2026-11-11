import pytest

from avflow.git_guard import evaluate, find_secrets

ON_FEATURE = lambda _c: "feature/1"  # noqa: E731


def diff(*added, file="src/App.config"):
    body = "\n".join("+" + a for a in added)
    return f"diff --git a/{file} b/{file}\n--- a/{file}\n+++ b/{file}\n@@ -0,0 +1,{len(added)} @@\n{body}\n"


@pytest.mark.parametrize("line", [
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN OPENSSH PRIVATE KEY-----",
    "aws_key = AKIAIOSFODNN7EXAMPLE",
    "token: ghp_" + "a" * 36,
    "GITLAB_TOKEN=glpat-" + "x" * 20,
    'password = "SuperSecretValue123!"'.replace("!", ""),
    '<add key="ApiKey" value="0123456789abcdef0123456789abcdef01234567"/>',
    "redmine_key: 5d54b52dd1275dc22db62d75f7902ea051065f94",
])
def test_secret_lines_are_found(line):
    assert find_secrets(["src/App.config"], diff(line))


@pytest.mark.parametrize("line", [
    "var password = txtPassword.Text;",
    "public string Token { get; set; }",
    "token = GetToken()",
    "// TODO: read the API key from the keyring",
    'Title = "Machine settings"',
])
def test_normal_code_is_not_flagged(line):
    assert find_secrets(["src/Main.cs"], diff(line, file="src/Main.cs")) == []


@pytest.mark.parametrize("name", [".env", "config/.env.production", "certs/server.pem", "keys/id_rsa", "sign.pfx"])
def test_sensitive_files_are_flagged(name):
    assert find_secrets([name], "")


def test_line_numbers_and_no_values_in_findings():
    f = find_secrets(["a.cs"], diff("x = 1", "token: ghp_" + "b" * 36, file="a.cs"))
    assert f == ["a.cs:2 — GitHub token"]


def test_commit_blocked_and_allowed():
    bad = lambda cwd, wt: (["a.cs"], diff("token: ghp_" + "c" * 36, file="a.cs"))  # noqa: E731
    good = lambda cwd, wt: (["a.cs"], diff("int x = 1;", file="a.cs"))  # noqa: E731
    assert "secrets" in evaluate("git commit -m 'Refs #1'", current=ON_FEATURE, diff_provider=bad)
    assert evaluate("git commit -m 'Refs #1'", current=ON_FEATURE, diff_provider=good) is None


def test_commit_all_scans_worktree():
    seen = {}

    def provider(cwd, include_worktree):
        seen["wt"] = include_worktree
        return [], ""
    evaluate("git commit -am 'x'", current=ON_FEATURE, diff_provider=provider)
    assert seen["wt"] is True
    evaluate("git commit -m 'x'", current=ON_FEATURE, diff_provider=provider)
    assert seen["wt"] is False


def test_dotnet_config_normal_settings_not_flagged():
    assert find_secrets(["App.config"], diff('<add key="CameraTimeoutMs" value="1500000000000000"/>')) == []
