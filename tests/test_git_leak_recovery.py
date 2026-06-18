import os
import subprocess
import pytest
from git_leak_recovery import find_secret, clean_repo, recover


def git_run(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def leaked_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    git_run(repo, "init")
    git_run(repo, "config", "user.email", "test@test.com")
    git_run(repo, "config", "user.name", "Test")

    (repo / "readme.txt").write_text("normal content")
    git_run(repo, "add", ".")
    git_run(repo, "commit", "-m", "initial commit")

    (repo / "credentials.txt").write_text("secret[supersecret42]")
    git_run(repo, "add", ".")
    git_run(repo, "commit", "-m", "add credentials")

    git_run(repo, "reset", "--hard", "HEAD~1")

    return str(repo)


@pytest.fixture
def clean_git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    git_run(repo, "init")
    git_run(repo, "config", "user.email", "test@test.com")
    git_run(repo, "config", "user.name", "Test")

    (repo / "readme.txt").write_text("nothing sensitive here")
    git_run(repo, "add", ".")
    git_run(repo, "commit", "-m", "initial commit")

    return str(repo)


def test_find_secret_in_dangling_objects(leaked_repo):
    assert find_secret(leaked_repo) == "secret[supersecret42]"


def test_find_secret_returns_none_when_no_secret(clean_git_repo):
    assert find_secret(clean_git_repo) is None


def test_secret_not_recoverable_after_cleanup(leaked_repo):
    clean_repo(leaked_repo)
    assert find_secret(leaked_repo) is None


def test_recover_writes_secret_to_file(leaked_repo, tmp_path):
    secret_file = str(tmp_path / "secret.txt")
    result = recover(leaked_repo, secret_file)

    assert result == "secret[supersecret42]"
    assert os.path.exists(secret_file)
    assert open(secret_file).read().strip() == "secret[supersecret42]"


def test_recover_cleans_repo_after_writing(leaked_repo, tmp_path):
    secret_file = str(tmp_path / "secret.txt")
    recover(leaked_repo, secret_file)
    assert find_secret(leaked_repo) is None


def test_normal_files_untouched_after_cleanup(leaked_repo):
    assert os.path.exists(os.path.join(leaked_repo, "readme.txt"))
    clean_repo(leaked_repo)
    assert os.path.exists(os.path.join(leaked_repo, "readme.txt"))


def test_commit_messages_untouched_after_cleanup(leaked_repo):
    log = subprocess.run(
        ["git", "-C", leaked_repo, "log", "--oneline"],
        capture_output=True, text=True
    )
    assert "initial commit" in log.stdout
    clean_repo(leaked_repo)
    log_after = subprocess.run(
        ["git", "-C", leaked_repo, "log", "--oneline"],
        capture_output=True, text=True
    )
    assert "initial commit" in log_after.stdout


def test_recover_raises_when_no_secret(tmp_path):
    repo = tmp_path / "empty"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)

    with pytest.raises(ValueError, match="Secret not found"):
        recover(str(repo), str(tmp_path / "secret.txt"))
