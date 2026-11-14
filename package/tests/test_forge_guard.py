"""The git guardrails also cover the forge CLIs (gh, glab): merging, approving and deleting are a person's decision.

The agent runs gh / glab as the person, so an approval would count as theirs (it could satisfy the code-owner check
without them looking at the change), and a merge would bypass the team's review.
"""
import pytest

from avflow.git_guard import evaluate


def ON_FEATURE(_cwd):
    return "feature/12-x"


BLOCKED = [
    # merge
    "gh pr merge 2",
    "gh pr merge 2 --merge --delete-branch",
    "gh pr merge --auto --squash",
    "glab mr merge 87",
    "glab mr merge 87 --squash --yes",
    "glab mr accept 87",
    "/usr/local/bin/gh pr merge 2",
    "gh.exe pr merge 2",
    "GH_REPO=org/app gh pr merge 2",
    "gh -R org/app pr merge 2",
    "glab -R group/app mr merge 87",
    "cd repo && gh pr merge 2",
    "gh pr view 2; gh pr merge 2",
    # approve
    "glab mr approve 87",
    "gh pr review 2 --approve",
    "gh pr review 2 -a",
    "gh pr review --approve -b ok",
    # delete
    "gh repo delete org/app --yes",
    "glab repo delete group/app",
    "gh release delete v3.0.0 --yes",
    "glab release delete v3.0.0",
    # the same through the API
    "glab api -X PUT projects/7/merge_requests/87/merge",
    "glab api --method PUT projects/7/merge_requests/87/merge",
    "glab api -X POST projects/7/merge_requests/87/approve",
    "glab api projects/7/merge_requests/87/approve -X POST",
    "gh api -X PUT repos/org/app/pulls/2/merge",
    "gh api --method=PUT repos/org/app/pulls/2/merge",
    "gh api repos/org/app/pulls/2/reviews -f event=APPROVE",
    "gh api -X POST repos/org/app/pulls/2/reviews -F event=APPROVE",
    "glab api -X DELETE projects/7/repository/branches/develop",
    "glab api -X DELETE projects/7/protected_branches/main",
    "gh api -X DELETE repos/org/app/branches/main/protection",
    "gh api -X DELETE repos/org/app/git/refs/heads/main",
    "gh api -X DELETE repos/org/app",
    "glab api -X DELETE projects/7",
]

ALLOWED = [
    "gh pr view 2",
    "gh pr list",
    "gh pr create --base develop --title x --body y",
    "gh pr diff 2",
    "gh pr checks 2",
    "gh pr review 2 --comment -b 'looks fine'",
    "gh pr review 2 --request-changes -b 'see notes'",
    "gh release list",
    "gh release view v3.0.0",
    "gh release download v3.0.0 --repo org/app",
    "gh auth status",
    "glab mr view 87",
    "glab mr diff 87",
    "glab mr note 87 -m 'avflow review'",
    "glab mr create --target-branch develop --title x --description y",
    "glab mr list",
    "glab ci status",
    "glab ci trace 123",
    "glab auth status",
    "glab api projects/7/merge_requests/87/approvals",
    "glab api projects/7/merge_requests/87",
    "gh api repos/org/app/pulls/2",
    "gh api repos/org/app/pulls/2/merge",                       # GET: is it merged? (read-only)
    "glab api -X POST projects/7/merge_requests/87/notes -f body=x",
    "echo 'gh pr merge 2'",                                     # text, not a command
    "grep -r 'glab mr approve' docs",
]


@pytest.mark.parametrize("cmd", BLOCKED)
def test_blocked(cmd):
    assert evaluate(cmd, current=ON_FEATURE), cmd


@pytest.mark.parametrize("cmd", ALLOWED)
def test_allowed(cmd):
    assert evaluate(cmd, current=ON_FEATURE) is None, cmd


def test_messages_name_the_action():
    assert "merg" in evaluate("gh pr merge 2", current=ON_FEATURE)
    assert "approv" in evaluate("glab mr approve 87", current=ON_FEATURE)
    assert "delet" in evaluate("gh repo delete org/app", current=ON_FEATURE)


def test_unparsable_command_is_allowed():
    assert evaluate("gh pr view 'unterminated", current=ON_FEATURE) is None
