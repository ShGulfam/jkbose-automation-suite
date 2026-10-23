"""Local photo extraction/copy utility (does not open Chrome).

Given a text file of registration numbers, scan a source photo folder for
filenames containing each registration number and copy the matching image into
an existing destination folder. Optionally rename each copied image from a
second text/CSV file containing ``registration_no,class_roll`` pairs.
"""
from __future__ import annotations

import csv
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Optional

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


def _clean(value: str) -> str:
    return (value or "").strip().strip('"').strip("'")


def _read_reg_numbers(path: Path) -> list[str]:
    regs = []
    seen = set()
    with path.open("r", encoding="utf-8-sig") as f:
        for raw in f:
            value = _clean(raw)
            if not value or value.startswith("#"):
                continue
            # Friendly handling if the user accidentally gives comma-delimited rows:
            # use the first column as the registration number.
            reg = _clean(value.split(",", 1)[0])
            key = reg.casefold()
            if reg and key not in seen:
                regs.append(reg)
                seen.add(key)
    return regs


def _read_rename_map(path: Optional[Path]) -> Dict[str, str]:
    """Read reg,class-roll mapping. Header rows are tolerated."""
    if not path:
        return {}
    mapping: Dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            reg = _clean(row[0])
            roll = _clean(row[1]) if len(row) > 1 else ""
            if not reg or not roll:
                continue
            if reg.casefold() in {"reg", "regno", "registration", "registration no", "registration number"}:
                continue
            if roll.casefold() in {"roll", "rollno", "class roll", "class roll no", "class roll number"}:
                continue
            mapping[reg.casefold()] = roll
    return mapping


def _candidate_files(source_dir: Path, recursive: bool) -> Iterable[Path]:
    iterator = source_dir.rglob("*") if recursive else source_dir.glob("*")
    for p in iterator:
        if p.is_file() and p.suffix.casefold() in IMAGE_EXTENSIONS:
            yield p


def _safe_destination(dest: Path, overwrite: bool) -> Path:
    if overwrite or not dest.exists():
        return dest
    stem, suffix = dest.stem, dest.suffix
    n = 2
    while True:
        candidate = dest.with_name(f"{stem}_{n}{suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def _write_run_report(destination_dir: Path, *, reg_file: Path, source_dir: Path,
                      rename_map_path: Optional[Path], recursive: bool, overwrite: bool,
                      requested: int, indexed_count: int, copied: int, missing,
                      ambiguous, no_mapping) -> Path:
    """Write a compact text report with full warning/error details for this run."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = _safe_destination(destination_dir / f"photo_copy_report_{stamp}.txt", overwrite=False)

    lines = [
        "JKBOSE TOOL - PHOTO EXTRACT / RENAME REPORT",
        "=" * 72,
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Registration file: {reg_file}",
        f"Source photo folder: {source_dir}",
        f"Destination folder: {destination_dir}",
        f"Rename mapping file: {rename_map_path if rename_map_path else 'Not used'}",
        f"Recursive search: {'Yes' if recursive else 'No'}",
        f"Overwrite existing files: {'Yes' if overwrite else 'No'}",
        "",
        "SUMMARY",
        "-" * 72,
        f"Registration numbers requested: {requested}",
        f"Source images indexed: {indexed_count}",
        f"Photos copied: {copied}",
        f"Missing photos: {len(missing)}",
        f"Multiple-match warnings: {len(ambiguous)}",
        f"Missing rename mappings: {len(no_mapping) if rename_map_path else 0}",
        "",
        "MISSING PHOTOS",
        "-" * 72,
    ]
    if missing:
        lines.extend(f"{i}. {reg}" for i, reg in enumerate(missing, 1))
    else:
        lines.append("None")

    lines.extend(["", "MULTIPLE MATCHES", "-" * 72])
    if ambiguous:
        for i, (reg, matches) in enumerate(ambiguous, 1):
            chosen = matches[0]
            lines.append(f"{i}. Registration No: {reg}")
            lines.append(f"   Selected: {chosen}")
            lines.append(f"   All matches ({len(matches)}):")
            for match in matches:
                marker = " [SELECTED]" if match == chosen else ""
                lines.append(f"      - {match}{marker}")
    else:
        lines.append("None")

    lines.extend(["", "MISSING RENAME MAPPINGS", "-" * 72])
    if rename_map_path:
        if no_mapping:
            lines.extend(
                f"{i}. {reg} (photo copied using original source filename)"
                for i, reg in enumerate(no_mapping, 1)
            )
        else:
            lines.append("None")
    else:
        lines.append("Not applicable - no rename mapping file was used.")

    lines.extend(["", "=" * 72, "End of report", ""])
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def run(reg_file, source_dir, destination_dir, rename_map_file=None,
        recursive=True, overwrite=False, stop_event=None):
    reg_file = Path(reg_file).expanduser()
    source_dir = Path(source_dir).expanduser()
    destination_dir = Path(destination_dir).expanduser()
    rename_map_path = Path(rename_map_file).expanduser() if rename_map_file else None

    if not reg_file.is_file():
        raise FileNotFoundError(f"Registration-number file not found: {reg_file}")
    if not source_dir.is_dir():
        raise NotADirectoryError(f"Source photo folder not found: {source_dir}")
    if not destination_dir.is_dir():
        raise NotADirectoryError(
            f"Destination folder does not exist: {destination_dir}\n"
            "Create the folder manually first, then select it."
        )
    if rename_map_path and not rename_map_path.is_file():
        raise FileNotFoundError(f"Rename mapping file not found: {rename_map_path}")

    regs = _read_reg_numbers(reg_file)
    rename_map = _read_rename_map(rename_map_path)
    photos = list(_candidate_files(source_dir, recursive=recursive))

    print(f"[INFO] Registration numbers: {len(regs)}")
    print(f"[INFO] Source images indexed: {len(photos)}")
    print(f"[INFO] Destination: {destination_dir}")
    if rename_map_path:
        print(f"[INFO] Rename mappings loaded: {len(rename_map)}")

    copied = 0
    missing = []
    ambiguous = []
    no_mapping = []

    # Case-insensitive filename containment, exactly as requested: the
    # registration number may appear anywhere in the source filename.
    indexed = [(p, p.name.casefold()) for p in photos]

    for idx, reg in enumerate(regs, start=1):
        if stop_event is not None and stop_event.is_set():
            print("[INFO] Stop requested. Ending photo copy batch.")
            break

        needle = reg.casefold()
        matches = [p for p, name_cf in indexed if needle in name_cf]
        if not matches:
            print(f"[MISSING] {reg} — no image filename contains this registration number")
            missing.append(reg)
            continue

        matches.sort(key=lambda p: (len(p.name), p.name.casefold(), str(p).casefold()))
        src = matches[0]
        if len(matches) > 1:
            ambiguous.append((reg, matches))
            print(f"[WARN] {reg} — {len(matches)} matches; using: {src.name}")

        new_base = rename_map.get(needle)
        if rename_map_path and not new_base:
            no_mapping.append(reg)
            print(f"[WARN] {reg} — not present in rename map; keeping source filename")

        if new_base:
            # Normalize JPEG names to .jpg. Other image formats retain their
            # real extension so files are never mislabeled without conversion.
            suffix = ".jpg" if src.suffix.casefold() in {".jpg", ".jpeg"} else src.suffix.lower()
            filename = f"{new_base}{suffix}"
        else:
            filename = src.name

        dest = _safe_destination(destination_dir / filename, overwrite=overwrite)
        shutil.copy2(src, dest)
        copied += 1
        print(f"[OK] {idx}/{len(regs)}  {reg}: {src.name}  ->  {dest.name}")

    print("\n" + "=" * 58)
    print(f"[DONE] Copied: {copied}")
    print(f"[DONE] Missing photos: {len(missing)}")
    print(f"[DONE] Multiple-match warnings: {len(ambiguous)}")
    if rename_map_path:
        print(f"[DONE] Missing rename mappings: {len(no_mapping)}")
    print("=" * 58)

    report_path = _write_run_report(
        destination_dir,
        reg_file=reg_file,
        source_dir=source_dir,
        rename_map_path=rename_map_path,
        recursive=recursive,
        overwrite=overwrite,
        requested=len(regs),
        indexed_count=len(photos),
        copied=copied,
        missing=missing,
        ambiguous=ambiguous,
        no_mapping=no_mapping,
    )
    print(f"[DONE] Report saved: {report_path}")

    return {
        "copied": copied,
        "missing": missing,
        "ambiguous": ambiguous,
        "missing_rename_mapping": no_mapping,
        "report_path": str(report_path),
    }
