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
    field_mode: str = "Mode"
    field_machine_side: str = "Machine-side"
    field_hotspot: str = "Hotspot"
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

    # ---------- file
    @staticmethod
    def load(path: Path = CONFIG_FILE) -> "Config":
        if not path.exists():
            raise SystemExit(f"{path} not found — run `avflow setup` first.")
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        t = TicketConfig(**{k: v for k, v in data.get("tickets", {}).items() if k in TicketConfig.__dataclass_fields__})
        r = RepoConfig(**{k: v for k, v in data.get("repo", {}).items() if k in RepoConfig.__dataclass_fields__})
        w = WorkflowConfig(**{k: v for k, v in data.get("workflow", {}).items() if k in WorkflowConfig.__dataclass_fields__})
        m = ModelsConfig(**{k: v for k, v in data.get("models", {}).items() if k in ModelsConfig.__dataclass_fields__})
        mo = MonitorConfig(**{k: v for k, v in data.get("monitor", {}).items() if k in MonitorConfig.__dataclass_fields__})
        return Config(t, r, data.get("marketplace", ""), w, m, mo)

    def save(self, path: Path = CONFIG_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

        def val(v):
            if isinstance(v, bool):
                return "true" if v else "false"
            if isinstance(v, int):
                return str(v)
            if isinstance(v, list):
                return "[" + ", ".join(_q(x) for x in v) + "]"
            return _q(v)

        lines = ["# avflow configuration — no secrets here (tokens are in the OS keyring)", f"marketplace = {_q(self.marketplace)}", "", "[tickets]"]
        lines += [f"{k} = {val(v)}" for k, v in self.tickets.__dict__.items()]
        lines += ["", "[repo]"] + [f"{k} = {val(v)}" for k, v in self.repo.__dict__.items()]
        lines += ["", "[workflow]"] + [f"{k} = {val(v)}" for k, v in self.workflow.__dict__.items()]
        lines += ["", "[models]  # subagent models: opus, sonnet, haiku or inherit"] + [f"{k} = {val(v)}" for k, v in self.models.__dict__.items()]
        lines += ["", "[monitor]  # context-size monitoring (tokens)"] + [f"{k} = {val(v)}" for k, v in self.monitor.__dict__.items()]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
