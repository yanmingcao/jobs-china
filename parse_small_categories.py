import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pdfplumber
from parse_occupations import (
    DEFAULT_L1,
    DEFAULT_L2,
    Line,
    PDF_PATH,
    RE_OCC,
    clean_heading_name,
    cut_at_next_heading,
    normalize_text,
    order_page_lines,
    parse_heading,
)


OUTPUT_PATH = Path("data/small_categories.json")
OCCUPATIONS_PATH = Path("data/occupations.json")
INLINE_DEFINITION_STARTERS = ("从事", "进行", "运用", "使用", "在", "担任")
RE_BARE_SMALL = re.compile(r"^(\d-\d{2}-\d{2})GBM\d{5}$")


@dataclass
class SmallCategoryRecord:
    code: str
    title: str
    definition: str
    category_l1_code: str
    category_l1_name: str
    category_l2_code: str
    category_l2_name: str

    @property
    def slug(self) -> str:
        return self.code.replace("-", "_")


def clean_definition(text: str, title: str) -> str:
    definition = normalize_text(text)
    definition = cut_at_next_heading(definition, "")
    definition = re.sub(r"^(本小类包括下列职业[:：]?)", "", definition)
    definition = definition.strip()
    if title and definition.startswith(title):
        remainder = definition[len(title) :]
        if remainder.startswith(("从事", "负责", "进行", "运用", "使用", "在")):
            definition = remainder
    if title and definition.startswith(title + title):
        definition = definition[len(title) :]
    definition = re.sub(r"\d-\d{2}-\d{2}-\d{2}.+$", "", definition)
    return definition.strip()


def merge_definition_parts(inline_definition: str, block_text: str) -> str:
    inline_definition = inline_definition.strip()
    block_text = block_text.strip()
    if not inline_definition:
        return block_text
    if not block_text:
        return inline_definition
    overlap_prefix = inline_definition[: min(8, len(inline_definition))]
    if overlap_prefix and block_text.startswith(overlap_prefix):
        return block_text
    return inline_definition + block_text


def load_occupation_fallbacks() -> dict[str, dict[str, str]]:
    if not OCCUPATIONS_PATH.exists():
        return {}
    with open(OCCUPATIONS_PATH, "r", encoding="utf-8") as f:
        occupations = json.load(f)

    fallbacks: dict[str, dict[str, str]] = {}
    for occupation in occupations:
        code = occupation.get("category_l3_code")
        title = occupation.get("category_l3_name")
        if not code or not title:
            continue
        if code not in fallbacks:
            fallbacks[code] = {
                "title": title,
                "category_l1_name": occupation.get("category_l1_name", ""),
                "category_l2_name": occupation.get("category_l2_name", ""),
            }
    return fallbacks


def build_pdf_title_fallbacks(lines: list[Line]) -> dict[str, str]:
    fallbacks: dict[str, str] = {}
    for idx, line in enumerate(lines):
        text = normalize_text(line.text)
        match = RE_BARE_SMALL.match(text)
        if not match or idx == 0:
            continue
        candidate = clean_context_title(lines[idx - 1].text)
        if is_valid_title(candidate):
            fallbacks[match.group(1)] = candidate
    return fallbacks


def is_valid_title(text: str) -> bool:
    if not text:
        return False
    if len(text) > 24:
        return False
    if any(marker in text for marker in INLINE_DEFINITION_STARTERS):
        return False
    if any(ch in text for ch in ["。", "；", ":", "："]):
        return False
    return True


def clean_context_title(text: str) -> str:
    text = clean_heading_name(text)
    text = re.sub(r"^[()（）]+", "", text)
    text = re.sub(r"^\d-\d{2}-\d{2}[（(]GBM\s*\d{5}[）)]", "", text)
    text = re.sub(r"^人员$", "", text)
    return text.strip()


def split_inline_definition(text: str) -> tuple[str, str]:
    if not text:
        return "", ""
    positions = [
        text.find(marker) for marker in INLINE_DEFINITION_STARTERS if marker in text
    ]
    positions = [pos for pos in positions if pos > 0]
    if not positions:
        return text, ""
    start = min(positions)
    return text[:start].strip(), text[start:].strip()


def title_from_context(
    lines: list[Line], idx: int, heading_name: str
) -> tuple[str, str]:
    cleaned_heading = clean_context_title(heading_name)
    heading_title, inline_definition = split_inline_definition(cleaned_heading)
    if is_valid_title(heading_title):
        return heading_title, inline_definition

    for pos in (idx - 1, idx + 1):
        if pos < 0 or pos >= len(lines):
            continue
        candidate = clean_context_title(lines[pos].text)
        candidate_title, candidate_inline_definition = split_inline_definition(
            candidate
        )
        if is_valid_title(candidate_title):
            return candidate_title, candidate_inline_definition

    return heading_title or cleaned_heading, inline_definition


def collect_small_definition_lines(
    lines: list[Line], start_idx: int
) -> tuple[str, int]:
    parts: list[str] = []
    j = start_idx
    while j < len(lines):
        text = normalize_text(lines[j].text)
        if not text:
            j += 1
            continue

        heading_code, _, _ = parse_heading(lines, j)
        if heading_code:
            break
        if RE_OCC.match(text):
            break

        bounded = cut_at_next_heading(text, "")
        if bounded:
            parts.append(bounded)
        if not bounded or bounded != text:
            break
        j += 1

    return "".join(parts), j


def parse_small_categories() -> list[SmallCategoryRecord]:
    ordered_lines: list[Line] = []
    fallbacks = load_occupation_fallbacks()
    with pdfplumber.open(str(PDF_PATH)) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        for i, page in enumerate(pdf.pages):
            ordered_lines.extend(order_page_lines(page))
            if (i + 1) % 50 == 0:
                print(f"  Ordered page {i + 1}")
    pdf_title_fallbacks = build_pdf_title_fallbacks(ordered_lines)

    current_l1_code = ""
    current_l1_name = ""
    current_l2_code = ""
    current_l2_name = ""
    records: dict[str, SmallCategoryRecord] = {}

    i = 0
    while i < len(ordered_lines):
        heading_code, heading_name, consumed = parse_heading(ordered_lines, i)
        if not heading_code:
            i += 1
            continue

        if re.fullmatch(r"\d", heading_code):
            current_l1_code = heading_code
            current_l1_name = heading_name or current_l1_name
            current_l2_code = ""
            current_l2_name = ""
            i += consumed
            continue

        if re.fullmatch(r"\d-\d{2}", heading_code):
            current_l2_code = heading_code
            current_l2_name = heading_name or current_l2_name
            i += consumed
            continue

        if re.fullmatch(r"\d-\d{2}-\d{2}", heading_code):
            title, inline_definition = title_from_context(
                ordered_lines, i, heading_name or ""
            )
            definition_text, next_idx = collect_small_definition_lines(
                ordered_lines, i + consumed
            )
            fallback = fallbacks.get(heading_code, {})
            title = pdf_title_fallbacks.get(heading_code, title)
            if not is_valid_title(title) or title in {"8-00-00GBM80000", "人员"}:
                title = fallback.get("title", title)
            records[heading_code] = SmallCategoryRecord(
                code=heading_code,
                title=title,
                definition=clean_definition(
                    merge_definition_parts(inline_definition, definition_text), title
                ),
                category_l1_code=current_l1_code,
                category_l1_name=(
                    fallback.get("category_l1_name")
                    or current_l1_name
                    or DEFAULT_L1.get(current_l1_code, "")
                ),
                category_l2_code=current_l2_code,
                category_l2_name=(
                    fallback.get("category_l2_name")
                    or current_l2_name
                    or DEFAULT_L2.get(current_l2_code, "")
                ),
            )
            i = max(i + consumed, next_idx)
            continue

        i += consumed

    return sorted(
        records.values(), key=lambda r: [int(part) for part in r.code.split("-")]
    )


def save_records(records: list[SmallCategoryRecord]) -> None:
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    payload = [
        {
            "code": record.code,
            "title": record.title,
            "slug": record.slug,
            "definition": record.definition,
            "category_l1_code": record.category_l1_code,
            "category_l1_name": record.category_l1_name,
            "category_l2_code": record.category_l2_code,
            "category_l2_name": record.category_l2_name,
        }
        for record in records
    ]
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(cast(object, payload), f, ensure_ascii=False, indent=2)


def print_stats(records: list[SmallCategoryRecord]) -> None:
    total = len(records)
    with_definition = sum(1 for record in records if record.definition)
    print(f"Small categories: {total}")
    print(
        f"With definition: {with_definition} ({with_definition * 100 // max(total, 1)}%)"
    )
    print("Sample:")
    for record in records[:8]:
        print(f"  {record.code} | {record.title} | def={bool(record.definition)}")


def main() -> None:
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"PDF not found: {PDF_PATH}")
    records = parse_small_categories()
    save_records(records)
    print_stats(records)
    print(f"Saved {len(records)} records to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
