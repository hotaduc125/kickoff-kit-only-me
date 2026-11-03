#!/usr/bin/env python3
"""Build an kickoff-kit release from this development repository.

Produces dist-release/:
  marketplace/          → push to the RELEASE repository (what team members install as the plugin marketplace)
  kickoff_kit-<v>-py3-none-any.whl   → the package (setup + MCP server), with the plugin checksums embedded
  bootstrap.sh · bootstrap.ps1 · INSTALL.md

Usage:
  python scripts/release.py --marketplace-url https://github.com/<owner>/kickoff-kit-marketplace.git
  python scripts/release.py ... --publish-to ../kickoff-kit-marketplace          # commit + tag in a local clone of the release repo
  python scripts/release.py ... --publish-to ../kickoff-kit-marketplace --push   # also push and create the GitHub Release with the wheel
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
    lv = json.loads((PLUGIN / "plugins/kickoff-kit/.claude-plugin/plugin.json").read_text())["version"]
    return pv, lv


def main() -> int:
    a = argparse.ArgumentParser()
    a.add_argument("--marketplace-url", required=True, help="git URL of the RELEASE marketplace repository")
    a.add_argument("--publish-to", help="local clone of the release repository: files are synced, committed and tagged")
    a.add_argument("--push", action="store_true", help="push the release repo and create a GitHub Release with the wheel (needs gh)")
    a.add_argument("--skip-tests", action="store_true")
    args = a.parse_args()

    pv, lv = versions()
    if pv != lv:
        print(f"Version mismatch: package {pv} ≠ plugin {lv}. Bump both."); return 1
    v = pv
    print(f"Releasing kickoff-kit {v}")

    if not args.skip_tests:
        runner = ["uv", "run", "pytest", "-q"] if shutil.which("uv") else [sys.executable, "-m", "pytest", "-q"]
        sh(runner, cwd=PKG)

    if OUT.exists():
        shutil.rmtree(OUT)
    market = OUT / "marketplace"
    shutil.copytree(PLUGIN, market, ignore=shutil.ignore_patterns(*DEV_ONLY, ".git", "__pycache__", ".DS_Store"))

    # Embed checksums of the released plugin in the package (doctor compares installed files with them).
    sys.path.insert(0, str(PKG / "src"))
    from kickoff_kit.integrity import compute_manifest  # noqa: E402
    manifest = compute_manifest(market / "plugins/kickoff-kit", v)
    data = PKG / "src/kickoff_kit/data/plugin_manifest.json"
    original_manifest = data.read_text()
    data.write_text(json.dumps(manifest, indent=2) + "\n")

    # Default marketplace URL for setup.
    cli = PKG / "src/kickoff_kit/cli.py"
    original_cli = cli.read_text()
    cli.write_text(re.sub(r'DEFAULT_MARKETPLACE = "[^"]*"', f'DEFAULT_MARKETPLACE = "{args.marketplace_url}"', original_cli))
    try:
        if shutil.which("uv"):
            sh(["uv", "build", "--wheel", "--out-dir", str(OUT)], cwd=PKG)
        else:
            sh([sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "-w", str(OUT)], cwd=PKG)
    finally:
        cli.write_text(original_cli)          # keep the dev repository generic
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
        sh(["git", "commit", "-m", f"Release kickoff-kit {v}"], cwd=dst)
        sh(["git", "tag", f"v{v}"], cwd=dst)
        if not args.push:
            print(f"\nRelease repository updated. Push with:  git -C {dst} push && git -C {dst} push --tags")
        else:
            sh(["git", "push"], cwd=dst)
            sh(["git", "push", "--tags"], cwd=dst)
            from kickoff_kit.setup_steps import github_repo_from_url  # noqa: E402
            repo = github_repo_from_url(args.marketplace_url)
            wheel = next(OUT.glob("kickoff_kit-*.whl"))
            if repo and shutil.which("gh"):
                sh(["gh", "release", "create", f"v{v}", str(wheel), "--repo", repo, "--title", f"kickoff-kit {v}",
                    "--notes", f"kickoff-kit {v}. Team members: run `kickoff-kit update`."])
                print(f"\nGitHub Release v{v} created on {repo}. Tell the team: `kickoff-kit update`.")
            else:
                print("\ngh not found or marketplace not on GitHub — upload the wheel to a release manually.")

    print(f"\nDone: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
