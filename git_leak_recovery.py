import re
import subprocess

SECRET_PATTERN = re.compile(r'secret\[[^\]]*\]')


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True,
        text=True
    )


def find_secret(repo="/app/repo"):
    all_objects = _git(repo, "cat-file", "--batch-all-objects", "--batch-check", "--unordered")

    for line in all_objects.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2 or parts[1] not in ("blob", "commit"):
            continue

        obj_hash, obj_type = parts[0], parts[1]
        content = _git(repo, "cat-file", obj_type, obj_hash)
        match = SECRET_PATTERN.search(content.stdout)
        if match:
            return match.group(0)

    return None


def clean_repo(repo="/app/repo"):
    _git(repo, "reflog", "expire", "--expire=now", "--all")
    _git(repo, "gc", "--prune=now", "--aggressive")


def recover(repo="/app/repo", secret_file="/app/secret.txt"):
    secret = find_secret(repo)
    if not secret:
        raise ValueError("Secret not found in any git object")

    with open(secret_file, "w") as f:
        f.write(secret + "\n")

    clean_repo(repo)
    return secret
