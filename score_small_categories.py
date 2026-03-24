"""Score each Chinese small category's AI exposure using an LLM via OpenRouter.

Reads small categories from data/small_categories.json and writes results to
data/small_category_scores.json.
"""

from pathlib import Path
import argparse
import json
import os
import time
from typing import Any, NotRequired, TypedDict

import httpx
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "google/gemini-3-flash-preview"
BACKUP_MODEL = "google/gemini-3.1-flash-lite-preview"
INPUT_FILE = Path("data/small_categories.json")
OUTPUT_FILE = Path("data/small_category_scores.json")
API_URL = "https://openrouter.ai/api/v1/chat/completions"


class SmallCategoryInput(TypedDict):
    code: str
    title: str
    slug: str
    definition: NotRequired[str]
    category_l1_name: NotRequired[str]
    category_l2_name: NotRequired[str]


SYSTEM_PROMPT = """\
你是一位专家分析师，评估不同中国职业小类对人工智能的暴露程度。你将获得《中华人民共和国职业分类大典（2022年版）》中的小类名称、层级和定义。

请对该小类的总体**AI暴露程度**进行评分，范围从0到10。

AI暴露程度衡量：人工智能将在多大程度上重塑这一整类工作？需要考虑直接效应（AI自动化当前由人类完成的任务）和间接效应（AI显著提升生产率，减少该类岗位所需人数）。

**关键判断标准**：这一小类工作的核心产出是否本质上是数字化的。如果该类工作主要可以通过计算机完成——写作、编程、分析、设计、沟通——那么AI暴露程度通常较高。相反，需要现场物理操作、精细手工、复杂真实环境执行或强实时人际互动的工作，对AI暴露有天然屏障。

请基于小类定义本身判断，不要因为它下面可能包含多种职业就回避给分；你需要给出这个小类的总体平均暴露度判断。

使用以下锚点校准评分：
- 0-1分：几乎完全依赖体力、手工或现场操作，AI影响极低
- 2-3分：AI只能辅助边缘文书/排程，核心工作仍主要在线下完成
- 4-5分：知识处理与现场执行混合，AI可部分改变工作方式
- 6-7分：知识工作为主，AI已能显著提升生产率
- 8-9分：核心任务几乎完全数字化，AI将深度重构该类工作
- 10分：高度标准化的信息处理工作，AI今天已能完成大部分核心任务

仅以以下JSON格式回复，无其他文字：
{
  "exposure": <0-10>,
  "rationale": "<2-3句话解释关键因素>"
}\
"""


def score_small_category(
    client: httpx.Client,
    small_category: SmallCategoryInput,
    model: str,
    verbose: bool = False,
) -> dict[str, object]:
    prompt_parts = [
        f"小类名称：{small_category['title']}",
        f"小类编码：{small_category['code']}",
        f"大类：{small_category.get('category_l1_name', '未知')}",
    ]

    category_l2_name = small_category.get("category_l2_name")
    if category_l2_name:
        prompt_parts.append(f"中类：{category_l2_name}")

    definition = small_category.get("definition")
    if definition:
        prompt_parts.append(f"小类定义：{definition}")

    prompt = "\n".join(prompt_parts)

    if verbose:
        print("\n=== SYSTEM PROMPT ===")
        print(SYSTEM_PROMPT)
        print("\n=== USER PROMPT ===")
        print(prompt)

    response = client.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY', '')}",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        },
        timeout=60,
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError(f"Invalid API response: missing choices: {payload}")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise ValueError(f"Invalid API response: bad choice shape: {payload}")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise ValueError(f"Invalid API response: missing message: {payload}")

    content = message.get("content")
    if content is None:
        raise ValueError(f"LLM returned null content: {payload}")
    if not isinstance(content, str):
        raise ValueError(
            f"LLM returned non-string content ({type(content).__name__}): {payload}"
        )

    content = content.strip()
    if not content:
        raise ValueError(f"LLM returned empty content: {payload}")
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
    if not content:
        raise ValueError(f"LLM returned empty content after fence stripping: {payload}")

    if verbose:
        print("\n=== LLM RESPONSE ===")
        print(content)

    return json.loads(content)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--small-code", help="Only score one small-category code")
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-score selected small categories even if already scored",
    )
    args = parser.parse_args()

    if not INPUT_FILE.exists():
        print(f"Error: {INPUT_FILE} not found. Run parse_small_categories.py first.")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        small_categories = json.load(f)

    if args.small_code:
        subset = [item for item in small_categories if item["code"] == args.small_code]
        if not subset:
            print(f"Error: small category code {args.small_code} not found.")
            return
    else:
        subset = small_categories[args.start : args.end]

    scores = {}
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            for entry in json.load(f):
                scores[entry["slug"]] = entry

    print(f"Scoring {len(subset)} small categories with {args.model}")
    print(f"Already cached: {len(scores)}")

    if not os.environ.get("OPENROUTER_API_KEY"):
        print("\nError: OPENROUTER_API_KEY not found in environment.")
        print("Create a .env file with: OPENROUTER_API_KEY=your_key_here")
        return

    errors = []
    client = httpx.Client()

    for i, item in enumerate(subset):
        slug = item["slug"]
        if slug in scores and not args.force:
            continue

        print(f"  [{i + 1}/{len(subset)}] {item['title']}...", end=" ", flush=True)
        try:
            result = score_small_category(
                client, item, args.model, verbose=args.verbose
            )
            scores[slug] = {
                "slug": slug,
                "code": item["code"],
                "title": item["title"],
                **result,
            }
            print(f"exposure={result['exposure']}")
        except Exception as e:
            print(
                f"ERROR with {args.model}: {e} | retrying with backup model {BACKUP_MODEL}...",
                end=" ",
                flush=True,
            )
            try:
                result = score_small_category(
                    client, item, BACKUP_MODEL, verbose=args.verbose
                )
                scores[slug] = {
                    "slug": slug,
                    "code": item["code"],
                    "title": item["title"],
                    **result,
                }
                print(f"exposure={result['exposure']} (backup)")
            except Exception as backup_error:
                print(f"ERROR with backup model: {backup_error}")
                errors.append(slug)

        OUTPUT_FILE.parent.mkdir(exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(list(scores.values()), f, ensure_ascii=False, indent=2)

        if i < len(subset) - 1:
            time.sleep(args.delay)

    client.close()

    print(f"\nDone. Scored {len(scores)} small categories, {len(errors)} errors.")
    if errors:
        print(f"Errors: {errors}")


if __name__ == "__main__":
    main()
