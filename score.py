"""
Score each Chinese occupation's AI exposure using an LLM via OpenRouter.

Reads occupations from data/occupations.json, sends each to an LLM with a scoring
rubric adapted for the Chinese job market context, and collects structured scores.
Results are cached incrementally to data/scores.json so the script can be resumed.

Usage:
    uv run python score.py
    uv run python score.py --model google/gemini-3-flash-preview
    uv run python score.py --start 0 --end 10   # test on first 10
    uv run python score.py --occ-code 4-04-05-01
    uv run python score.py --occ-code 4-04-05-01 --verbose
    # If default model fails on one occupation, fallback model is used automatically
"""

from pathlib import Path
import argparse
import json
import os
import time

import httpx
from dotenv import load_dotenv
from typing import Any, NotRequired, TypedDict

load_dotenv()

DEFAULT_MODEL = "google/gemini-3-flash-preview"
BACKUP_MODEL = "google/gemini-3.1-flash-lite-preview"
OUTPUT_FILE = "data/scores.json"
API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OccupationInput(TypedDict):
    code: str
    title: str
    slug: str
    category_l1_name: NotRequired[str]
    category_l2_name: NotRequired[str]
    category_l3_name: NotRequired[str]
    definition: NotRequired[str]
    tasks: NotRequired[list[str]]
    is_green: NotRequired[bool]
    is_digital: NotRequired[bool]


SYSTEM_PROMPT = """\
你是一位专家分析师，评估不同职业对人工智能的暴露程度。你将获得中国职业分类大典中的职业名称和分类信息。

对该职业的总体**AI暴露程度**进行评分，范围从0到10。

AI暴露程度衡量：人工智能将在多大程度上重塑该职业？需要考虑直接效应（AI自动化当前由人类完成的任务）和间接效应（AI使每个工作者生产力大幅提升，导致所需人数减少）。

**关键判断标准**：该职业的工作产出是否本质上是数字化的。如果该工作可以在家庭办公室完全通过计算机完成——写作、编程、分析、沟通——那么AI暴露程度天生就很高（7+），因为AI在数字领域的能力正在快速进步。即使今天的AI无法处理该工作的每个方面，发展轨迹陡峭，上限非常高。相反，需要在物理世界中进行现场工作、手工技能或实时人际互动的职业，对AI暴露有天然屏障。

**中国特定因素**：
- 中国是全球制造业中心，制造业从业者众多
- 数字经济快速发展，数字化转型深入各行各业
- 人口老龄化加速，养老服务需求增长
- 乡村振兴战略推进，农业现代化程度提升
- "双碳"目标推动绿色产业发展

**职业标识说明**：
- `L` 表示绿色职业
- `S` 表示数字职业
- `L/S` 表示同时具备绿色与数字属性
- 这些标识是官方分类标签，可作为背景信息参考，但**不能直接等同于AI暴露程度**
- 即使是 `S` 职业，也要根据该职业的实际定义和任务判断其是否真的高度可被AI重塑
- 即使是 `L` 职业，也不能默认低暴露；关键仍然是任务是否数字化、是否可计算、是否需要现场物理操作

使用以下锚点校准评分：

- **0–1分：极低暴露。** 工作几乎完全是体力、实践操作，或在不可预测的环境中需要实时人类在场。AI对日常工作基本没有影响。
  例子：建筑工人、园林绿化工人、农业一线劳动者

- **2–3分：低暴露。** 主要是体力或人际互动工作。AI可能帮助处理一些边缘任务（排程、文书），但不触及核心工作。
  例子：电工、管道工、消防员、牙科卫生员

- **4–5分：中等暴露。** 体力/人际工作与知识工作的混合。AI可以有意义地协助信息处理部分，但仍有相当比例需要人类在场。
  例子：注册护士、警察、兽医

- **6–7分：高暴露。** 以知识工作为主，有一定人类判断、关系维护或物理在场需求。AI工具已经有用，使用AI的工作者可能生产力大幅提升。
  例子：教师、管理者、会计师、记者

- **8–9分：非常高暴露。** 工作几乎完全在计算机上完成。所有核心任务——写作、编程、分析、设计、沟通——都处于AI快速改进的领域。该职业面临重大重构。
  例子：软件工程师、平面设计师、翻译、数据分析师、法律助理

- **10分：最高暴露。** 常规信息处理，完全数字化，无物理组件。AI今天已经可以完成大部分工作。
  例子：数据录入员、电话销售员

仅以以下JSON格式回复，无其他文字：
{
  "exposure": <0-10>,
  "rationale": "<2-3句话解释关键因素>"
}\

"""


def score_occupation(
    client: httpx.Client,
    occupation: OccupationInput,
    model: str,
    verbose: bool = False,
) -> dict[str, object]:
    """Send one occupation to the LLM and parse the structured response."""
    # Build the prompt with occupation info including definition and tasks
    prompt_parts = [
        f"职业名称：{occupation['title']}",
        f"职业编码：{occupation['code']}",
        f"大类：{occupation.get('category_l1_name', '未知')}",
    ]

    # Add 中类 if available
    category_l2_name = occupation.get("category_l2_name")
    if category_l2_name:
        prompt_parts.append(f"中类：{category_l2_name}")

    category_l3_name = occupation.get("category_l3_name")
    if category_l3_name:
        prompt_parts.append(f"小类：{category_l3_name}")

    prompt_parts.append(f"绿色职业：{'是' if occupation.get('is_green') else '否'}")
    prompt_parts.append(f"数字职业：{'是' if occupation.get('is_digital') else '否'}")

    # Add definition if available
    definition = occupation.get("definition")
    if definition:
        prompt_parts.append(f"职业定义：{definition}")

    # Add tasks if available
    tasks = occupation.get("tasks")
    if tasks:
        tasks_text = "；".join(tasks[:5])  # Max 5 tasks
        prompt_parts.append(f"主要工作任务：{tasks_text}")

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

    # Strip markdown code fences if present
    content = content.strip()
    if not content:
        raise ValueError(f"LLM returned empty content: {payload}")
    if content.startswith("```"):
        content = content.split("\n", 1)[1]  # remove first line
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
    if not content:
        raise ValueError(f"LLM returned empty content after fence stripping: {payload}")

    if verbose:
        print("\n=== LLM RESPONSE ===")
        print(content)

    return json.loads(content)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--occ-code", help="Only score one occupation code")
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-score selected occupations even if already scored",
    )
    args = parser.parse_args()
    # Load occupations
    occupations_path = Path("data/occupations.json")
    if not occupations_path.exists():
        print(f"Error: {occupations_path} not found. Run parse_occupations.py first.")
        return

    with open(occupations_path, "r", encoding="utf-8") as f:
        occupations = json.load(f)

    if args.occ_code:
        subset = [occ for occ in occupations if occ["code"] == args.occ_code]
        if not subset:
            print(f"Error: occupation code {args.occ_code} not found.")
            return
    else:
        subset = occupations[args.start : args.end]

    # Load existing scores
    scores = {}
    output_path = Path(OUTPUT_FILE)
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            for entry in json.load(f):
                scores[entry["slug"]] = entry

    print(f"Scoring {len(subset)} occupations with {args.model}")
    print(f"Already cached: {len(scores)}")

    # Check for API key
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("\nError: OPENROUTER_API_KEY not found in environment.")
        print("Create a .env file with: OPENROUTER_API_KEY=your_key_here")
        return

    errors = []
    client = httpx.Client()

    for i, occ in enumerate(subset):
        slug = occ["slug"]

        if slug in scores and not args.force:
            continue

        print(f"  [{i + 1}/{len(subset)}] {occ['title']}...", end=" ", flush=True)

        try:
            result = score_occupation(
                client,
                occ,
                args.model,
                verbose=args.verbose,
            )
            scores[slug] = {
                "slug": slug,
                "code": occ["code"],
                "title": occ["title"],
                **result,
            }
            print(f"exposure={result['exposure']}")
            if args.verbose:
                print("\n=== FINAL SCORE ===")
                print(f"code={occ['code']}")
                print(f"title={occ['title']}")
                print(f"exposure={result['exposure']}")
        except Exception as e:
            print(
                f"ERROR with {args.model}: {e} | retrying with backup model {BACKUP_MODEL}...",
                end=" ",
                flush=True,
            )
            try:
                result = score_occupation(
                    client, occ, BACKUP_MODEL, verbose=args.verbose
                )
                scores[slug] = {
                    "slug": slug,
                    "code": occ["code"],
                    "title": occ["title"],
                    **result,
                }
                print(f"exposure={result['exposure']} (backup)")
                if args.verbose:
                    print("\n=== FINAL SCORE ===")
                    print(f"code={occ['code']}")
                    print(f"title={occ['title']}")
                    print(f"exposure={result['exposure']}")
            except Exception as backup_error:
                print(f"ERROR with backup model: {backup_error}")
                errors.append(slug)

        # Save after each one (incremental checkpoint)
        output_path.parent.mkdir(exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(list(scores.values()), f, ensure_ascii=False, indent=2)

        if i < len(subset) - 1:
            time.sleep(args.delay)

    client.close()

    print(f"\nDone. Scored {len(scores)} occupations, {len(errors)} errors.")
    if errors:
        print(f"Errors: {errors}")

    # Summary stats
    vals = [s for s in scores.values() if "exposure" in s]
    if vals:
        avg = sum(s["exposure"] for s in vals) / len(vals)
        by_score = {}
        for s in vals:
            bucket = s["exposure"]
            by_score[bucket] = by_score.get(bucket, 0) + 1
        print(f"\nAverage exposure across {len(vals)} occupations: {avg:.1f}")
        print("Distribution:")
        for k in sorted(by_score):
            print(f"  {k}: {'█' * by_score[k]} ({by_score[k]})")


if __name__ == "__main__":
    main()
