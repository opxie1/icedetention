"""Mirror the 16 deliverable files into the local Dropbox sync folder.

Dropbox sync will then push everything to the cloud automatically.
Also removes the obsolete `*_overrides_template.csv` files in `for review/`
that were superseded by the `*_need_county.csv` files.
"""
from __future__ import annotations

import shutil
from pathlib import Path

REPO = Path(r"C:\Users\xief\.local\bin\ucmerced")
DBOX = Path(r"C:\Users\xief\Dropbox\ethan xie\ice crosswalk")

LAYOUT = {
    "README_PANELS.txt": "data/processed/README_PANELS.txt",
    "panels/county_year_detention_combined.csv": "data/processed/county_year_detention_combined.csv",
    "panels/county_month_detention_combined.csv": "data/processed/county_month_detention_combined.csv",
    "panels/county_year_panel.csv": "data/processed/county_year_panel.csv",
    "panels/county_month_panel.csv": "data/processed/county_month_panel.csv",
    "panels/county_year_encounters_panel.csv": "data/processed/county_year_encounters_panel.csv",
    "panels/county_month_encounters_panel.csv": "data/processed/county_month_encounters_panel.csv",
    "panels/county_year_stays_panel.csv": "data/processed/county_year_stays_panel.csv",
    "panels/county_month_stays_panel.csv": "data/processed/county_month_stays_panel.csv",
    "crosswalks/facility_crosswalk.csv": "data/processed/facility_crosswalk.csv",
    "crosswalks/facility_crosswalk_review.csv": "data/processed/facility_crosswalk_review.csv",
    "crosswalks/site_crosswalk.csv": "data/processed/site_crosswalk.csv",
    "crosswalks/site_crosswalk_review.csv": "data/processed/site_crosswalk_review.csv",
    "crosswalks/unmapped_facilities.csv": "data/processed/unmapped_facilities.csv",
    "crosswalks/unmapped_sites.csv": "data/processed/unmapped_sites.csv",
    "crosswalks/unmapped_stays.csv": "data/processed/unmapped_stays.csv",
    "for review/facilities_need_county.csv": "references/facilities_need_county.csv",
    "for review/sites_need_county.csv": "references/sites_need_county.csv",
    "population/county_year_population.csv": "data/processed/county_year_population.csv",
    "population/county_year_detention_population.csv": "data/processed/county_year_detention_population.csv",
    "population/county_month_detention_population.csv": "data/processed/county_month_detention_population.csv",
}

OBSOLETE_FILES = [
    "for review/facility_overrides_template.csv",
    "for review/site_overrides_template.csv",
    "README_PANELS.md",
]


def main() -> None:
    missing_sources = []
    for src in LAYOUT.values():
        if not (REPO / src).is_file():
            missing_sources.append(src)
    if missing_sources:
        print("ABORT: source files missing:")
        for s in missing_sources:
            print(f"  {s}")
        return

    print(f"Source files: all {len(LAYOUT)} present.")
    print(f"Dropbox root: {DBOX}")
    print()

    for sub in {Path(p).parent for p in LAYOUT.keys()}:
        if str(sub) == ".":
            continue
        (DBOX / sub).mkdir(parents=True, exist_ok=True)

    print("Copying:")
    for dst_rel, src_rel in LAYOUT.items():
        src = REPO / src_rel
        dst = DBOX / dst_rel
        if dst.exists():
            old_size = dst.stat().st_size
            action = f"REPLACE (was {old_size} B)"
        else:
            action = "ADD"
        shutil.copy2(src, dst)
        new_size = dst.stat().st_size
        print(f"  [{action}] {dst_rel}  ({new_size} B)")

    print()
    print("Removing obsolete files:")
    for rel in OBSOLETE_FILES:
        p = DBOX / rel
        if p.exists():
            p.unlink()
            print(f"  [REMOVED] {rel}")
        else:
            print(f"  [absent]  {rel}")

    print()
    print("Final Dropbox state:")
    for sub in ["", "panels", "crosswalks", "for review"]:
        d = DBOX / sub if sub else DBOX
        items = sorted(d.iterdir())
        files = [i for i in items if i.is_file()]
        print(f"  {sub or '(root)'}/  ({len(files)} files)")
        for i in files:
            print(f"    {i.name}  ({i.stat().st_size:,} B)")


if __name__ == "__main__":
    main()
