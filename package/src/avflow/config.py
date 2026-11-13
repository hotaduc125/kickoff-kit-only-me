"""Configuration in ~/.avflow/config.toml (no secrets) + secrets in the OS keyring."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

import keyring

HOME = Path(os.environ.get("AVFLOW_HOME", Path.home() / ".avflow"))
CONFIG_FILE = HOME / "config.toml"
KEYRING_SERVICE = "avflow"


@dataclass
class TicketConfig:
    provider: str = "redmine"          # redmine | jira | gitlab | github (only redmine in v1)
    url: str = ""
    status_ready: str = "Ready"
    status_in_progress: str = "In progress"
    status_in_review: str = "In review"
    status_ready_for_test: str = "Ready for test"   # set by the CI job after a merge
    field_mode: str = "Mode"                   # 2.x only: no longer read since 3.0 (kept so old files load)
    field_machine_side: str = "Machine-side"   # read during the transition: "yes" → machine_side_area
    field_hotspot: str = "Hotspot"
    field_risk_area: str = "Risk area"         # list field; without it, the "Risk area:" description line
    machine_side_area: str = ""                # risk area for Machine-side = yes ("" → Other high risk)
    tracker_bug: str = "Bug"
    blocker_done: list[str] = field(default_factory=lambda: ["Ready for test", "Resolved", "Closed"])
    mr_url_prefix: str = ""
    project: str = ""                 # default project identifier for `avflow report`


@dataclass
class RepoConfig:
    provider: str = "gitlab"           # gitlab | github (only gitlab in v1)
    host: str = "gitlab.com"


@dataclass
class WorkflowConfig:
    profile: str = "superpowers"      # superpowers | pocock
    git_guardrails: bool = True
    protected_branches: list[str] = field(default_factory=lambda: ["main", "master", "develop", "release/*"])


MODEL_CHOICES = ("opus", "sonnet", "haiku", "inherit")


@dataclass
class ModelsConfig:
    plan: str = "opus"            # avflow-planner subagent
    implement: str = "sonnet"     # avflow-implementer subagent
    review: str = "opus"          # avflow-reviewer subagent


@dataclass
class MonitorConfig:
    enabled: bool = True
    warn_tokens: int = 300_000        # warn the person and the agent
    critical_tokens: int = 400_000    # ask for a handoff and a new session
    enforce: bool = False             # true: refuse new prompts past critical_tokens


@dataclass
class Config:
    tickets: TicketConfig = field(default_factory=TicketConfig)
    repo: RepoConfig = field(default_factory=RepoConfig)
    marketplace: str = ""             # git URL of the avflow plugin marketplace
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)
    models: ModelsConfig = field(default_factory=ModelsConfig)
    monitor: MonitorConfig = field(default_factory=MonitorConfig)

    # ---------- dict form
    SECTIONS = ("tickets", "repo", "workflow", "models", "monitor")

    def to_dict(self) -> dict:
        d = {"marketplace": self.marketplace}
        for sec in self.SECTIONS:
            d[sec] = dict(getattr(self, sec).__dict__)
        return d

    @staticmethod
    def from_dict(data: dict) -> "Config":
        def build(cls, sec):
            return cls(**{k: v for k, v in (data.get(sec) or {}).items() if k in cls.__dataclass_fields__})
        return Config(build(TicketConfig, "tickets"), build(RepoConfig, "repo"), data.get("marketplace", "") or "",
                      build(WorkflowConfig, "workflow"), build(ModelsConfig, "models"), build(MonitorConfig, "monitor"))

    # ---------- file: team defaults (shipped with the release) + personal overrides (~/.avflow/config.toml)
    @staticmethod
    def load(path: Path = CONFIG_FILE, team: dict | None = None) -> "Config":
        if not path.exists():
            raise SystemExit(f"{path} not found — run `avflow setup` first.")
        personal = tomllib.loads(path.read_text(encoding="utf-8"))
        return Config.from_dict(merge(team_defaults() if team is None else team, personal))

    @staticmethod
    def team(team: dict | None = None) -> "Config":
        """The team's configuration alone (no personal overrides)."""
        return Config.from_dict(team_defaults() if team is None else team)

    def overrides(self, team: dict | None = None) -> dict:
        """Only the values that differ from the team configuration."""
        base = Config.team(team).to_dict()
        mine = self.to_dict()
        out = {}
        if mine["marketplace"] != base["marketplace"]:
            out["marketplace"] = mine["marketplace"]
        for sec in self.SECTIONS:
            diff = {k: v for k, v in mine[sec].items() if base[sec].get(k) != v}
            if diff:
                out[sec] = diff
        return out

    def save(self, path: Path = CONFIG_FILE, team: dict | None = None) -> None:
        """Write only the personal overrides; everything else comes from the team configuration."""
        path.parent.mkdir(parents=True, exist_ok=True)
        ov = self.overrides(team)
        lines = ["# avflow personal configuration — only what differs from the team configuration.",
                 "# The team configuration comes with each avflow release (`avflow config` shows both).",
                 "# No secrets here: tokens are in the OS keyring."]
        if "marketplace" in ov:
            lines += [f"marketplace = {_val(ov['marketplace'])}"]
        for sec in self.SECTIONS:
            if sec in ov:
                lines += ["", f"[{sec}]"] + [f"{k} = {_val(v)}" for k, v in ov[sec].items()]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def merge(base: dict, over: dict) -> dict:
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in (base or {}).items()}
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = {**out[k], **v}
        else:
            out[k] = v
    return out


def team_defaults() -> dict:
    """The team configuration embedded in this release (data/team.toml); empty if absent."""
    from importlib import resources
    try:
        return tomllib.loads(resources.files("avflow").joinpath("data/team.toml").read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        return {}


def team_version() -> str:
    return str(team_defaults().get("team_version", "") or "")


def sources(path: Path = CONFIG_FILE, team: dict | None = None) -> dict:
    """For each 'section.key': 'personal' when overridden in the personal file, else 'team'."""
    personal = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    out = {}
    cfg = Config.team(team).to_dict()
    for sec in Config.SECTIONS:
        for k in cfg[sec]:
            out[f"{sec}.{k}"] = "personal" if k in (personal.get(sec) or {}) else "team"
    out["marketplace"] = "personal" if "marketplace" in personal else "team"
    return out


def _val(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_q(x) for x in v) + "]"
    return _q(v)


def _q(s: str) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


# ---------- secrets
def secret_name(provider: str, url: str) -> str:
    return f"{provider}:{url.rstrip('/')}"


def set_secret(provider: str, url: str, token: str) -> None:
    keyring.set_password(KEYRING_SERVICE, secret_name(provider, url), token)


def get_secret(provider: str, url: str) -> str:
    env = os.environ.get("AVFLOW_TICKET_TOKEN")      # CI or advanced use only
    if env:
        return env
    tok = keyring.get_password(KEYRING_SERVICE, secret_name(provider, url))
    if not tok:
        raise SystemExit(f"No token stored for {provider} at {url} — run `avflow setup`.")
    return tok


def delete_secret(provider: str, url: str) -> None:
    try:
        keyring.delete_password(KEYRING_SERVICE, secret_name(provider, url))
    except keyring.errors.PasswordDeleteError:
        pass
