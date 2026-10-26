# Changes since the previous commit - 26 October 2026

Exact local commit message: `fix(internal-assessment): resume approvals with live progress`

## Exact files

Modified:
- `gui_main.py`
- `main.py`
- `jkbose_tool/features/internal_assessment_approval.py`
- `jkbose_tool/internal_assessment_approval_gui.py`
- `tests/test_internal_approval.py`
- `README.md`
- `CHANGES_SINCE_LAST_COMMIT.md`

Added:
- `tests/test_internal_approval_resume.py`

No removed files. Private approval journals, screenshots, downloaded evidence, student data and browser state remain excluded from Git.

## Changes

Fixed a completed approval becoming uncertain when the portal's success toast intercepts the read-only Download Excel control. Only that read-only click is retried within a bounded wait; decision clicks are never retried. Added exact interrupted-receipt recovery from an existing submitted request and complete hashed before/after exports proving only that request disappeared. Queue absence alone is not accepted. Remaining unresolved requests are held individually instead of stopping unrelated eligible awards.

Class-wide modes now use exact popup/request binding, completed postback, target disappearance, one-record live total decrease and complete displayed-page validation after each approval. Full exported checks remain at initial verification and final queue audit, rather than downloading per award. Proofs explicitly distinguish live-page verification from full exported verification. Strict Excel approval retains its full-export checks. No source matching, absence, exclusion or identity guard was removed.

Added thread-safe UI progress: determinate bar, tracked awards, verified receipts, remaining awards, pending students and held/excluded counts. Totals include known local receipts plus the current queue, without inventing untracked external approvals. Failed GUI runs retain the browser for inspection; Force Close Browser clears the reference before another task starts.

One existing interrupted receipt was recovered locally after backing up its immutable journal and validating the recorded eight-to-seven request transition. This changed no live award and performed no approval/rejection click. Previous and recovered history are retained outside Git.

## Validation

- Full installed Python 3.12 synthetic suite: 299 tests passed, including exact recovery, tampered/unrelated/multiple-removal rejection, interrupted actions, toast interception, retained browser cleanup, fast queue transitions, no per-award class-mode downloads, final queue audit, student/award progress and existing submission/approval protections.
- Shared website `npm run build` completed with exit code 0, including SEO/privacy checks. No website source was changed for this task.
- Local backups: `_code_backups/approval_resume_20261026` (excluded from Git).
- No live browser approval/rejection and no Git push.

## Review / manual Git

Review with `git show HEAD` or `git show --stat HEAD`. To amend/recreate: `git reset --soft HEAD~1`, review staged changes, then `git commit -m "fix(internal-assessment): resume approvals with live progress"`.

Changes have been built, staged, and committed locally. Please run `git push origin main` manually whenever you are ready. The user's explicit no-push policy takes precedence over generic synchronization instructions in local guidance.
