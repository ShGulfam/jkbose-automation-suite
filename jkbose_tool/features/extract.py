"""
Feature: "extract" -- (planned) pull PDF/CSV data from the site, e.g.
admit cards, submitted-form printouts, result sheets.

Not implemented yet. This stub exists so the CLI wiring, driver/login
handling, and folder layout stay consistent when this gets built out --
just implement run() the same way screenshots.py / submit_form.py do,
then wire it into main.py's subparsers.
"""


def run(driver, **kwargs):
    raise NotImplementedError(
        "extract feature is not implemented yet. "
        "Add the scraping/PDF logic here, following the pattern in "
        "features/screenshots.py and features/submit_form.py."
    )
