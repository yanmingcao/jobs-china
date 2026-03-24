"""Build website data from dedicated small-category parse and score files.

Usage:
    uv run python build_site_data.py
"""

import json
from pathlib import Path
from typing import NotRequired, TypedDict, cast


SMALL_CATEGORY_FILE = Path("data/small_categories.json")
SCORES_FILE = Path("data/small_category_scores.json")
OCCUPATIONS_FILE = Path("data/occupations.json")
OUTPUT_FILE = Path("site/data.json")


class SmallCategory(TypedDict):
    code: str
    title: str
    slug: str
    definition: NotRequired[str]
    category_l1_code: NotRequired[str]
    category_l1_name: NotRequired[str]
    category_l2_code: NotRequired[str]
    category_l2_name: NotRequired[str]


class ScoreEntry(TypedDict):
    slug: str
    exposure: NotRequired[float | int]
    rationale: NotRequired[str]


class SiteEntry(TypedDict):
    code: str
    title: str
    slug: str
    category: str
    category_l1_code: str
    category_l1: str
    category_l2: str
    category_l3: str
    occupation_count: int
    scored_count: int
    exposure: float | None
    exposure_rationale: str
    definition: str
    occupation_titles: list[str]


def main() -> None:
    if not SMALL_CATEGORY_FILE.exists():
        raise FileNotFoundError(
            f"Small-category input not found: {SMALL_CATEGORY_FILE}. Run parse_small_categories.py first."
        )

    with open(SMALL_CATEGORY_FILE, "r", encoding="utf-8") as f:
        small_categories = cast(list[SmallCategory], json.load(f))

    occupation_counts: dict[str, int] = {}
    occupation_titles: dict[str, list[str]] = {}
    if OCCUPATIONS_FILE.exists():
        with open(OCCUPATIONS_FILE, "r", encoding="utf-8") as f:
            occupations = cast(list[dict[str, object]], json.load(f))
        for occupation in occupations:
            l3_code = occupation.get("category_l3_code")
            if isinstance(l3_code, str) and l3_code:
                occupation_counts[l3_code] = occupation_counts.get(l3_code, 0) + 1
                title = occupation.get("title")
                if isinstance(title, str) and title:
                    occupation_titles.setdefault(l3_code, []).append(title)

    scores: dict[str, ScoreEntry] = {}
    if SCORES_FILE.exists():
        with open(SCORES_FILE, "r", encoding="utf-8") as f:
            score_list = cast(list[ScoreEntry], json.load(f))
            for score in score_list:
                scores[score["slug"]] = score
    else:
        print(f"Warning: {SCORES_FILE} not found. Run score_small_categories.py first.")

    data: list[SiteEntry] = []
    for item in small_categories:
        score = scores.get(item["slug"], {})
        exposure = score.get("exposure")
        data.append(
            {
                "code": item["code"],
                "title": item["title"],
                "slug": item["slug"],
                "category": item.get("category_l1_name", ""),
                "category_l1_code": item.get("category_l1_code", ""),
                "category_l1": item.get("category_l1_name", ""),
                "category_l2": item.get("category_l2_name", ""),
                "category_l3": item["title"],
                "occupation_count": occupation_counts.get(item["code"], 1),
                "scored_count": 1 if exposure is not None else 0,
                "exposure": float(exposure) if exposure is not None else None,
                "exposure_rationale": score.get("rationale", ""),
                "definition": item.get("definition", ""),
                "occupation_titles": occupation_titles.get(item["code"], []),
            }
        )

    data.sort(
        key=lambda x: (
            x.get("category_l1", ""),
            x.get("category_l2", ""),
            x.get("code", ""),
        )
    )

    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    print(f"Wrote {len(data)} small categories to {OUTPUT_FILE}")
    scored = [item for item in data if item["exposure"] is not None]
    print(f"Scored small categories: {len(scored)}/{len(data)}")
    if scored:
        avg = sum(
            item["exposure"] for item in scored if item["exposure"] is not None
        ) / len(scored)
        print(f"Average small-category exposure: {avg:.2f}")


if __name__ == "__main__":
    main()
