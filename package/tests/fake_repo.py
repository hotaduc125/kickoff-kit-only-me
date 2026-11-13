"""A project repository for ticket-tool tests: a profile, changed files and MR notes, without git or glab."""
from avflow import risk
from avflow.tickets.repo import RepoError

MATEO = """
[[risk.area]]
name   = "Machine control"
paths  = ["source/Zmotion/**"]
owners = ["@q"]
checks = ["plan-confirmation", "independent-review", "code-owner", "checklist:Tested on the test bench"]

[[risk.area]]
name   = "Build and CI"
paths  = [".gitlab-ci.yml"]
owners = ["@alvin"]
checks = ["code-owner"]
"""


class FakeRepo:
    def __init__(self, profile=MATEO, files=(), target="develop", post_error=None):
        self.profile_text, self.files, self.target, self.post_error = profile, list(files), target, post_error
        self.posted, self.bases, self.description = [], [], ""

    def profile(self):
        if self.profile_text is None:
            return None
        return risk.ensure_valid(risk.parse(self.profile_text))

    def mr_target(self, url):
        return self.target

    def changed_files(self, base=None):
        self.bases.append(base)
        return list(self.files), f"origin/{base or 'main'}"

    def post_mr_note(self, url, text):
        if self.post_error:
            raise RepoError(self.post_error)
        self.posted.append((url, text))

    def mr_description(self, url):
        if self.post_error:
            raise RepoError(self.post_error)
        return self.description

    def set_mr_description(self, url, text):
        if self.post_error:
            raise RepoError(self.post_error)
        self.description = text
