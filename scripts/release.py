#!/usr/bin/env python3
"""Build an avflow release from this development repository.

Produces dist-release/:
  marketplace/          → push to the RELEASE repository (what team members install as the plugin marketplace)
  avflow-<v>-py3-none-any.whl   → the package (setup + MCP server), with the plugin checksums embedded
  bootstrap.sh · bootstrap.ps1 · INSTALL.md

Usage:
  python scripts/release.py --marketplace-url https://github.com/<owner>/avflow-marketplace.git
  python scripts/release.py ... --publish-to ../avflow-marketplace          # commit + tag in a local clone of the release repo
  python scripts/release.py ... --publish-to ../avflow-marketplace --push   # also push and create the GitHub Release with the wheel
Team members never need this repository.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG, PLUGIN, OUT = ROOT / "package", ROOT / "plugin", ROOT / "dist-release"
DEV_ONLY = {"DEV.md", "tests", ".github", ".gitlab-ci.yml"}


def sh(cmd, cwd=None):
    print("$", " ".join(map(str, cmd)))
    subprocess.run(cmd, cwd=cwd, check=True)


def versions() -> tuple[str, str]:
    pv = re.search(r'^version\s*=\s*"([^"]+)"', (PKG / "pyproject.toml").read_text(), re.M).group(1)
    lv = json.loads((PLUGIN / "plugins/avflow/.claude-plugin/plugin.json").read_text())["version"]
    return pv, lv


def main() -> int:
    a = argparse.ArgumentParser()
    a.add_argument("--marketplace-url", required=True, help="git URL of the RELEASE marketplace repository")
    a.add_argument("--publish-to", help="local clone of the release repository: files are synced, committed and tagged")
    a.add_argument("--push", action="store_true", help="push the release repo and create a GitHub Release with the wheel (needs gh)")
    a.add_argument("--skip-tests", action="store_true")
    args = a.parse_args()

    if args.push:
        from_repo = re.match(r"^(?:https://github\.com/|git@github\.com:)([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", args.marketplace_url.strip())
        if not args.publish_to:
            print("--push needs --publish-to"); return 1
        if not from_repo:
            print("--push creates a GitHub Release, so --marketplace-url must be a GitHub repository"); return 1
        if not shutil.which("gh"):
            print("GitHub CLI (gh) not found — install it (brew install gh), then: gh auth login"); return 1
        if subprocess.run(["gh", "auth", "status"], capture_output=True).returncode != 0:
            print("gh is not signed in — run: gh auth login   (then: gh auth setup-git)"); return 1

    pv, lv = versions()
    if pv != lv:
        print(f"Version mismatch: package {pv} ≠ plugin {lv}. Bump both."); return 1
    v = pv
    print(f"Releasing avflow {v}")

    if not args.skip_tests:
        runner = ["uv", "run", "pytest", "-q"] if shutil.which("uv") else [sys.executable, "-m", "pytest", "-q"]
        sh(runner, cwd=PKG)

    if OUT.exists():
        shutil.rmtree(OUT)
    market = OUT / "marketplace"
    shutil.copytree(PLUGIN, market, ignore=shutil.ignore_patterns(*DEV_ONLY, ".git", "__pycache__", ".DS_Store"))

    # Embed checksums of the released plugin in the package (doctor compares installed files with them).
    sys.path.insert(0, str(PKG / "src"))
    from avflow.integrity import compute_manifest  # noqa: E402
    manifest = compute_manifest(market / "plugins/avflow", v)
    data = PKG / "src/avflow/data/plugin_manifest.json"
    original_manifest = data.read_text()
    data.write_text(json.dumps(manifest, indent=2) + "\n")

    # Team configuration: validate it and embed it (with the version and the marketplace URL).
    team_src = ROOT / "team" / "avflow-team.toml"
    if not team_src.exists():
        print(f"Missing {team_src} — the team configuration is required for a release."); return 1
    import tomllib
    try:
        team = tomllib.loads(team_src.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        print(f"team/avflow-team.toml is not valid TOML: {e}"); return 1
    problems = [k for k, ok in (("tickets.url", (team.get("tickets") or {}).get("url")),
                                ("repo.host", (team.get("repo") or {}).get("host"))) if not ok]
    if problems:
        print("team/avflow-team.toml must set: " + ", ".join(problems)); return 1
    team_dst = PKG / "src/avflow/data/team.toml"
    original_team = team_dst.read_text(encoding="utf-8")
    team_dst.write_text(f'team_version = "{v}"\nmarketplace = "{args.marketplace_url}"\n\n' +
                        "\n".join(l for l in team_src.read_text(encoding="utf-8").splitlines()
                                  if not l.startswith(("team_version", "marketplace"))) + "\n", encoding="utf-8")

    # Default marketplace URL for setup.
    cli = PKG / "src/avflow/cli.py"
    original_cli = cli.read_text()
    cli.write_text(re.sub(r'DEFAULT_MARKETPLACE = "[^"]*"', f'DEFAULT_MARKETPLACE = "{args.marketplace_url}"', original_cli))
    try:
        if shutil.which("uv"):
            sh(["uv", "build", "--wheel", "--out-dir", str(OUT)], cwd=PKG)
        else:
            sh([sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "-w", str(OUT)], cwd=PKG)
    finally:
        cli.write_text(original_cli)          # keep the dev repository generic
        team_dst.write_text(original_team)
        data.write_text(original_manifest)    # dev builds skip the integrity check

    for f in ("bootstrap.sh", "bootstrap.ps1"):
        shutil.copy2(ROOT / "scripts" / f, OUT / f)
    shutil.copy2(ROOT / "INSTALL.md", OUT / "INSTALL.md")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    if args.publish_to:
        dst = Path(args.publish_to).resolve()
        if not (dst / ".git").exists():
            print(f"{dst} is not a git clone of the release repository"); return 1
        for p in dst.iterdir():
            if p.name != ".git":
                shutil.rmtree(p) if p.is_dir() else p.unlink()
        for p in market.iterdir():
            (shutil.copytree if p.is_dir() else shutil.copy2)(p, dst / p.name)
        sh(["git", "add", "-A"], cwd=dst)
        if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=dst).returncode != 0:
            sh(["git", "commit", "-m", f"Release avflow {v}"], cwd=dst)
        else:
            print("Release repository already up to date — no new commit.")
        if subprocess.run(["git", "rev-parse", "-q", "--verify", f"refs/tags/v{v}"], cwd=dst, capture_output=True).returncode != 0:
            sh(["git", "tag", f"v{v}"], cwd=dst)
        else:
            print(f"Tag v{v} already exists — kept.")
        if not args.push:
            print(f"\nRelease repository updated. Push with:  git -C {dst} push && git -C {dst} push --tags")
        else:
            sh(["git", "push"], cwd=dst)
            sh(["git", "push", "--tags"], cwd=dst)
            from avflow.setup_steps import github_repo_from_url  # noqa: E402
            repo = github_repo_from_url(args.marketplace_url)
            wheel = next(OUT.glob("avflow-*.whl"))
            exists = subprocess.run(["gh", "release", "view", f"v{v}", "--repo", repo], capture_output=True).returncode == 0
            assets = [str(wheel), str(OUT / "bootstrap.sh"), str(OUT / "bootstrap.ps1"), str(OUT / "INSTALL.md")]
            if exists:
                sh(["gh", "release", "upload", f"v{v}", *assets, "--repo", repo, "--clobber"])
                print(f"\nGitHub Release v{v} already existed — wheel re-uploaded.")
            else:
                sh(["gh", "release", "create", f"v{v}", *assets, "--repo", repo, "--title", f"avflow {v}",
                    "--notes", f"avflow {v}. Team members: run `avflow update`."])
                print(f"\nGitHub Release v{v} created on {repo}. Tell the team: `avflow update`.")

    print(f"\nDone: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
