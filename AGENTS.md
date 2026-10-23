# Agent Guidelines & Automated Git Workflow

## 1. Project Context
This repository contains the institutional automation software for JKBOSE (Jammu & Kashmir State Board of School Education) examination workflows, registration forms (RR), internal assessment practical awards, and principal verification portals.

---

## 2. Strict Sensitive Data & PII Isolation Policy
**CRITICAL RULE**: Student Personally Identifiable Information (PII), academic records, exam roll numbers, marks, signatures, photos, and browser session credentials must **NEVER** be committed or pushed to Git under any circumstances.

### 2.1 Always Ignored Files and Directories (`.gitignore`)
The following files and folders are strictly ignored and must never be tracked:
- **Student Data & PII**:
  - `11th/`, `12th/` (candidate photos, signatures, personal data)
  - `ref_*.txt`, `regnos_*.txt`, `fields.csv`
  - All institutional workbooks: `*.xlsx`, `*.xls`, `*.csv` (*only blank starter schemas under `templates/` are permitted*)
  - All generated or scanned documents: `*.pdf`, `*.png`, `*.jpg`, `*.jpeg`
- **Audit Journals & Verification Receipts**:
  - `history/` (immutable audit journals, batch proofs, and screenshots)
  - `*.jsonl` (event streams)
  - `**/manifest.json`, `**/report.json`, `**/report.csv`
  - `*_Identity_Confirmations.json`, `Pending_Firebase_Updates*.json`
  - `internal-assessment.lock`
- **Browser State & Credentials**:
  - `.chrome_profile*/` (Active browser sessions, auth cookies, credentials)
  - `.env`, `.env.*`, `*serviceAccount*.json`, `credentials*.json`
  - `*.pem`, `*.key`, `*.pfx`
- **Backups & Runtime Caches**:
  - `_code_backups/`
  - `__pycache__/`, `*.pyc`, `.pytest_cache/`
  - `*.tmp`, `*.bak`, `*.log`

---

## 3. Automated Build, Add, Commit, and Push Workflow
Whenever features, bug fixes, or documentation updates are completed, follow this exact 5-step automated workflow:

### Step 1: Verification & Build Test
Run the full test suite to guarantee zero regressions:
```bash
python -m unittest discover tests
```
*Do not proceed with staging or committing if any test fails.*

### Step 2: Sensitive Data Leak Check
Inspect untracked and modified files before staging:
```bash
git status --porcelain
```
Verify that no `.xlsx`, `.pdf`, `.png`, `history/`, `11th/`, `12th/`, or `.chrome_profile` files appear in the list.

### Step 3: Stage Safe Code & Documentation
Stage only safe project files protected by `.gitignore`:
```bash
git add .
```

### Step 4: Commit with Conventional Message
Create a clear, meaningful commit message following conventional commits:
```bash
git commit -m "<type>(<scope>): <summary>"
```
Examples:
- `feat(internal-assessment): support portal award rejection workflow`
- `fix(saved-report): prevent update-panel pagination timeout`
- `chore(git): update sensitive file exclusions in .gitignore`

### Step 5: Push to Remote Repository
Push changes to the upstream branch:
```bash
git push -u origin main
```
*(Or `git push origin main` if upstream tracking is already established).*

---

## 4. One-Command Automated Synchronization
An automated synchronization tool is available to execute all 5 steps in a single command:
```bash
python -m jkbose_tool.git_sync "type(scope): your descriptive commit message"
```
This utility:
1. Executes `python -m unittest discover tests`
2. Scans git working tree for any sensitive file patterns or extensions
3. Stages valid changes (`git add .`)
4. Commits with your message (`git commit -m "..."`)
5. Pushes to `origin main` automatically if a remote repository is configured.

---

## 5. Remote Repository Setup (If not already linked)
To connect this repository to GitHub (e.g., `ShGulfam`):
```bash
# Option A: Link an existing remote GitHub repository
git remote add origin https://github.com/ShGulfam/<repo-name>.git
git branch -M main
git push -u origin main

# Option B: Create and link repository via GitHub CLI
gh repo create ShGulfam/<repo-name> --public --source=. --remote=origin --push
```
