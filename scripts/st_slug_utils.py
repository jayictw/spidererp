"""ST product slug heuristics.

This is a high-hit heuristic for mapping full ST orderable part numbers to
product-page slugs. It is not guaranteed to cover all ST product lines.
"""

from __future__ import annotations

import re

# Product-branch suffixes that should be preserved when present at the end.
KEEP_SUFFIXES: tuple[str, ...] = (
    "-DRE",
    "-E",
    "-W",
    "-Y",
    "-R",
    "-F",
)

# Packaging / ordering suffixes that are usually removed.
REMOVABLE_SUFFIXES: tuple[str, ...] = (
    "D1013",
    "MN6",
    "DW6",
    "CPT",
    "FP",
    "ST",
    "G",
)


def split_preserved_suffix(part: str) -> tuple[str, str]:
    for suffix in KEEP_SUFFIXES:
        if part.endswith(suffix):
            return part[: -len(suffix)], suffix
    return part, ""


def trim_ordering_suffixes(stem: str) -> str:
    changed = True
    while changed:
        changed = False

        new_stem = re.sub(r"-(TR|TP)$", "", stem)
        if new_stem != stem:
            stem = new_stem
            changed = True
            continue

        new_stem = re.sub(r"(TR|TP)$", "", stem)
        if new_stem != stem:
            stem = new_stem
            changed = True
            continue

        for suffix in REMOVABLE_SUFFIXES:
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
                changed = True
                break

    return stem


def st_part_to_product_slug(part_number: str) -> str:
    part = part_number.strip().upper()
    part = re.sub(r"-(TR|TP)$", "", part)
    stem, keep = split_preserved_suffix(part)
    stem = trim_ordering_suffixes(stem)
    return (stem + keep).lower()


def make_st_product_url(category: str, part_number: str) -> str:
    slug = st_part_to_product_slug(part_number)
    return f"https://www.st.com/en/{category}/{slug}.html"

