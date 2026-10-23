"""Automated, safe Git synchronization: test verification, sensitive file check, stage, commit, and push."""
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SENSITIVE_PATTERNS = [
    ".chrome_profile",
    "history/",
    "11th/",
    "12th/",
    "_code_backups/",
    ".env",
    "serviceAccount",
    "desktop.ini",
]

SENSITIVE_EXTENSIONS = {
    ".xlsx", ".xls", ".pdf", ".png", ".jpg", ".jpeg", ".crx", ".pem", ".key", ".pfx", ".jsonl"
}

ALLOWED_EXTENSIONS_UNDER_TEMPLATES = {
    ".xlsx", ".csv"
}


def run_cmd(cmd, cwd=ROOT, check=True):
    res = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)
    if check and res.returncode != 0:
        raise RuntimeError(f"Command failed ({res.returncode}): {cmd}\n{res.stderr.strip() or res.stdout.strip()}")
    return res


def run_tests():
    print("[1/5] Running test suite verification...")
    res = run_cmd(f'"{sys.executable}" -m unittest discover tests', check=False)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr)
        raise RuntimeError("Tests failed! Aborting commit and push to prevent committing broken code.")
    print("      Test suite passed cleanly (0 errors, 0 failures).")


def check_sensitive_files():
    print("[2/5] Checking for sensitive files against leak patterns...")
    res = run_cmd("git status --porcelain", check=True)
    lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
    leaks = []
    for line in lines:
        parts = line.split(maxsplit=1)
        if len(parts) < 2:
            continue
        filepath = parts[1].replace("\\", "/").strip('"')
        path_obj = Path(filepath)

        # Allow schema files explicitly inside templates/
        if filepath.startswith("templates/") and path_obj.suffix in ALLOWED_EXTENSIONS_UNDER_TEMPLATES:
            continue

        for pat in SENSITIVE_PATTERNS:
            if pat in filepath:
                leaks.append(f"{filepath} matches sensitive pattern '{pat}'")

        if path_obj.suffix.lower() in SENSITIVE_EXTENSIONS:
            leaks.append(f"{filepath} has sensitive extension '{path_obj.suffix}'")

    if leaks:
        print("[ERROR] Sensitive files detected in git working tree:")
        for leak in leaks:
            print(f"  - {leak}")
        raise RuntimeError("Sensitive files detected! Fix .gitignore before staging or committing.")
    print("      Zero sensitive files detected.")


def stage_changes():
    print("[3/5] Staging changes (git add .)...")
    run_cmd("git add .", check=True)
    res = run_cmd("git status --porcelain", check=True)
    if not res.stdout.strip():
        print("      No changes to commit. Working tree clean.")
        return False
    return True


def commit_changes(message):
    print(f"[4/5] Committing changes with message: '{message}'...")
    # Escape quotes
    escaped = message.replace('"', '\\"')
    run_cmd(f'git commit -m "{escaped}"', check=True)
    print("      Committed successfully.")


def push_changes():
    print("[5/5] Checking git remote and pushing...")
    remotes = run_cmd("git remote -v", check=False)
    if not remotes.stdout.strip():
        print("      [NOTE] No remote repository configured yet. Changes are safely committed locally on main branch.")
        print("      To push to GitHub, add a remote: git remote add origin <url> && git push -u origin main")
        return

    # Check current branch
    branch_res = run_cmd("git branch --show-current", check=True)
    branch = branch_res.stdout.strip() or "main"
    print(f"      Pushing to origin {branch}...")
    push_res = run_cmd(f"git push -u origin {branch}", check=False)
    if push_res.returncode != 0:
        # Retry with standard push
        push_res = run_cmd(f"git push origin {branch}", check=False)
    if push_res.returncode != 0:
        print(f"      [WARNING] Git push output: {push_res.stderr.strip() or push_res.stdout.strip()}")
    else:
        print(f"      Pushed successfully to origin/{branch}.")


def sync(message="chore: automated updates and verification pass"):
    print("=== Starting Automated Git Build, Add, Commit & Push ===")
    run_tests()
    check_sensitive_files()
    if stage_changes():
        commit_changes(message)
    push_changes()
    print("=== Automated Git Sync Finished Successfully ===")


if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "chore: automated updates and verification pass"
    try:
        sync(msg)
    except Exception as e:
        print(f"[FATAL] Git sync aborted: {e}")
        sys.exit(1)
