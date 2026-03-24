import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pdfplumber


PDF_PATH = Path("data/（2022年版）中华人民共和国职业分类大典.pdf")
OUTPUT_PATH = Path("data/occupations.json")

DEFAULT_L1 = {
    "1": "党的机关、国家机关、群众团体和社会组织、企事业单位负责人",
    "2": "专业技术人员",
    "3": "办事人员和有关人员",
    "4": "社会生产服务和生活服务人员",
    "5": "农、林、牧、渔业生产及辅助人员",
    "6": "生产制造及有关人员",
    "7": "军队人员",
    "8": "不便分类的其他从业人员",
}

DEFAULT_L2 = {
    "1-01": "中国共产党机关负责人",
    "1-02": "国家机关负责人",
    "1-03": "民主党派和工商联负责人",
    "1-04": "人民团体和群众团体、社会组织及其他成员组织负责人",
    "1-05": "基层群众自治组织负责人",
    "1-06": "企事业单位负责人",
    "2-01": "科学研究人员",
    "2-02": "工程技术人员",
    "2-03": "农业技术人员",
    "2-04": "飞机和船舶技术人员",
    "2-05": "卫生专业技术人员",
    "2-06": "经济和金融专业人员",
    "2-07": "监察、法律、社会和宗教专业人员",
    "2-08": "教学人员",
    "2-09": "文学艺术、体育专业人员",
    "2-10": "新闻出版、文化专业人员",
    "2-99": "其他专业技术人员",
    "3-01": "行政办事及辅助人员",
    "3-02": "安全和消防及辅助人员",
    "3-03": "法律事务及辅助人员",
    "3-99": "其他办事人员和有关人员",
    "4-01": "批发与零售服务人员",
    "4-02": "交通运输、仓储物流和邮政业服务人员",
    "4-03": "住宿和餐饮服务人员",
    "4-04": "信息传输、软件和信息技术服务人员",
    "4-05": "金融服务人员",
    "4-06": "房地产服务人员",
    "4-07": "租赁和商务服务人员",
    "4-08": "技术辅助服务人员",
    "4-09": "水利、环境和公共设施管理服务人员",
    "4-10": "居民服务人员",
    "4-11": "电力、燃气及水供应服务人员",
    "4-12": "修理及制作服务人员",
    "4-13": "文化和教育服务人员",
    "4-14": "健康、体育和休闲服务人员",
    "4-99": "其他社会生产服务和生活服务人员",
    "5-01": "农业生产人员",
    "5-02": "林业生产人员",
    "5-03": "畜牧业生产人员",
    "5-04": "渔业生产人员",
    "5-05": "农、林、牧、渔业生产辅助人员",
    "5-99": "其他农、林、牧、渔业生产及辅助人员",
    "6-01": "农副产品加工人员",
    "6-02": "食品、饮料生产加工人员",
    "6-03": "烟草及其制品加工人员",
    "6-04": "纺织、针织、印染人员",
    "6-05": "纺织品、服装和皮革、毛皮制品加工制作人员",
    "6-06": "木材加工、家具与木制品制作人员",
    "6-07": "纸及纸制品生产加工人员",
    "6-08": "印刷和记录媒介复制人员",
    "6-09": "文教、工美、体育和娱乐用品制造人员",
    "6-10": "石油加工和炼焦、煤化工生产人员",
    "6-11": "化学原料和化学制品制造人员",
    "6-12": "医药制造人员",
    "6-13": "化学纤维制造人员",
    "6-14": "橡胶和塑料制品制造人员",
    "6-15": "非金属矿物制品制造人员",
    "6-16": "采矿人员",
    "6-17": "金属冶炼和压延加工人员",
    "6-18": "机械制造基础加工人员",
    "6-19": "金属制品制造人员",
    "6-20": "通用设备制造人员",
    "6-21": "专用设备制造人员",
    "6-22": "汽车制造人员",
    "6-23": "铁路、船舶、航空设备制造人员",
    "6-24": "电气机械和器材制造人员",
    "6-25": "计算机、通信和其他电子设备制造人员",
    "6-26": "仪器仪表制造人员",
    "6-27": "再生资源综合利用人员",
    "6-28": "电力、热力、气体、水生产和输配人员",
    "6-29": "建筑施工人员",
    "6-30": "运输设备和通用工程机械操作人员及有关人员",
    "6-31": "生产辅助人员",
    "6-99": "其他生产制造及有关人员",
    "7-01": "军官（警官）",
    "7-02": "军士（警士）",
    "7-03": "义务兵",
    "7-04": "文职人员",
    "8-00": "不便分类的其他从业人员",
}

FALLBACK_DEFINITIONS = {
    "1-01-00-01": "在中国共产党中央和地方各级机关及其工作机构中,担任领导职务的人员。",
    "1-01-00-02": "在企业、农村、机关、学校、科研院所、街道社区、社会组织等基层单位中国共产党组织中,担任领导职务的人员。",
    "8-00-00-00": "不便分类的其他从业人员。",
}

FALLBACK_TITLES = {
    "1-01-00-01": "中国共产党机关负责人",
    "1-04-03-00": "民办非企业单位负责人",
    "2-02-02-03": "摄影测量与遥感工程技术人员",
    "2-02-02-08": "导航与位置服务工程技术人员",
    "2-02-22-01": "海洋调查与监测工程技术人员",
}

FALLBACK_CLEAN_DEFINITIONS = {
    "1-02-02-00": "在各级国家行政机关及其工作机构中,担任领导职务并具有决策、管理职权的人员。",
    "7-01-00-00": "军官(警官)。",
    "7-02-00-00": "军士(警士)。",
    "7-03-00-00": "义务兵。",
    "7-04-00-00": "文职人员。",
}

CHINESE_TO_NUM = {
    "一": "1",
    "二": "2",
    "三": "3",
    "四": "4",
    "五": "5",
    "六": "6",
    "七": "7",
    "八": "8",
}

RE_MAJOR = re.compile(r"^(\d)[（(]GBM\s*(\d{5})[）)]\s*(.*)$")
RE_MAJOR_CN = re.compile(r"^第([一二三四五六七八])大类[：:]?\s*(.*)$")
RE_MIDDLE = re.compile(r"^(\d-\d{2})[（(]GBM\s*(\d{5})[）)]\s*(.*)$")
RE_SMALL = re.compile(r"^(\d-\d{2}-\d{2})[（(]GBM\s*(\d{5})[）)]\s*(.*)$")
RE_OCC = re.compile(r"^(\d-\d{2}-\d{2}-\d{2})\s*(.*)$")
RE_NEXT_HEADING = re.compile(
    r"(第[一二三四五六七八]大类|\d[（(]GBM\s*\d{5}|\d-\d{2}[（(]GBM\s*\d{5}|\d-\d{2}-\d{2}[（(]GBM\s*\d{5}|\d-\d{2}-\d{2}-\d{2})"
)
RE_NUMBER_MARK = re.compile(r"\d+\.")
RE_INCLUDE_MARKER = re.compile(
    r"(本大类包括下列中类[:：]?|本中类包括下列小类[:：]?|本小类包括下列职业[:：]?)"
)


@dataclass
class Line:
    page: int
    top: float
    x0: float
    text: str


@dataclass
class OccupationRecord:
    code: str
    title: str
    is_green: bool = False
    is_digital: bool = False
    category_l1_code: str = ""
    category_l1_name: str = ""
    category_l2_code: str = ""
    category_l2_name: str = ""
    category_l3_code: str = ""
    category_l3_name: str = ""
    definition: str = ""
    tasks: list[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return self.code.replace("-", "_")

    def quality_score(self) -> tuple[int, int, int, int]:
        return (
            1 if self.definition else 0,
            len(self.tasks),
            len(self.definition),
            len(self.title),
        )


def join_tokens(tokens: list[str]) -> str:
    out = ""
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        out += token
    return out.strip()


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", "")
    text = re.sub(r"\s+", "", text)
    text = text.replace("（GBM", "（GBM")
    return text.strip()


def looks_like_footer(text: str, page_height: float, top: float) -> bool:
    text = text.strip()
    if not text:
        return True
    if re.fullmatch(r"\d+", text) and top > page_height - 40:
        return True
    if text in {"中华人民共和国", "职业分类大典", "（2022年版）"}:
        return True
    return False


def cluster_word_dicts(
    words: list[dict[str, Any]], page_number: int, page_height: float
) -> list[Line]:
    if not words:
        return []

    words = sorted(words, key=lambda w: (float(w["top"]), float(w["x0"])))
    line_clusters: list[list[dict[str, Any]]] = []

    for word in words:
        if not line_clusters:
            line_clusters.append([word])
            continue
        prev_top = float(line_clusters[-1][0]["top"])
        if abs(float(word["top"]) - prev_top) <= 4.5:
            line_clusters[-1].append(word)
        else:
            line_clusters.append([word])

    lines: list[Line] = []
    for cluster in line_clusters:
        cluster = sorted(cluster, key=lambda w: w["x0"])
        text = join_tokens([w["text"] for w in cluster])
        top = min(float(w["top"]) for w in cluster)
        x0 = min(float(w["x0"]) for w in cluster)
        if looks_like_footer(text, page_height, top):
            continue
        lines.append(Line(page=page_number, top=top, x0=x0, text=text))
    return lines


def extract_page_words(page) -> list[dict[str, Any]]:
    return page.extract_words(use_text_flow=False, keep_blank_chars=False)


def is_two_column_page(words: list[dict[str, Any]], page_width: float) -> bool:
    body = [w for w in words if 80 <= float(w["top"]) <= 700]
    if not body:
        return False
    left = sum(1 for w in body if float(w["x0"]) < page_width * 0.46)
    right = sum(1 for w in body if float(w["x0"]) > page_width * 0.54)
    return left >= 40 and right >= 25


def order_page_lines(page) -> list[Line]:
    words = extract_page_words(page)
    if not words:
        return []

    if not is_two_column_page(words, page.width):
        lines = cluster_word_dicts(words, page.page_number, page.height)
        return sorted(lines, key=lambda ln: (ln.top, ln.x0))

    header_words = [w for w in words if float(w["top"]) < 85]
    body_words = [w for w in words if float(w["top"]) >= 85]
    left_words = [w for w in body_words if float(w["x0"]) < page.width * 0.5]
    right_words = [w for w in body_words if float(w["x0"]) >= page.width * 0.5]
    header = cluster_word_dicts(header_words, page.page_number, page.height)
    left = cluster_word_dicts(left_words, page.page_number, page.height)
    right = cluster_word_dicts(right_words, page.page_number, page.height)
    return (
        sorted(header, key=lambda ln: (ln.top, ln.x0))
        + sorted(left, key=lambda ln: (ln.top, ln.x0))
        + sorted(right, key=lambda ln: (ln.top, ln.x0))
    )


def clean_heading_name(name: str) -> str:
    name = normalize_text(name)
    name = re.sub(r"^[)）]+", "", name)
    name = re.sub(
        r"^(本大类包括下列中类|本中类包括下列小类|本小类包括下列职业)$", "", name
    )
    name = re.sub(r"^[:：]+", "", name)
    return name.strip()


def is_short_title_line(text: str) -> bool:
    text = clean_heading_name(text)
    if not text:
        return False
    if len(text) > 30:
        return False
    if RE_NEXT_HEADING.search(text):
        return False
    if any(
        marker in text
        for marker in ["主要工作任务", "本大类包括", "本中类包括", "本小类包括"]
    ):
        return False
    return True


def parse_heading(lines: list[Line], idx: int) -> tuple[str | None, str | None, int]:
    text = normalize_text(lines[idx].text)

    major_cn = RE_MAJOR_CN.match(text)
    if major_cn:
        code = CHINESE_TO_NUM.get(major_cn.group(1))
        name = clean_heading_name(major_cn.group(2))
        return code, name, 1

    for regex in (RE_MAJOR, RE_MIDDLE, RE_SMALL):
        match = regex.match(text)
        if match:
            code = match.group(1)
            suffix = clean_heading_name(match.group(3))
            if RE_OCC.match(suffix):
                suffix = ""
            if suffix:
                return code, suffix, 1
            if idx + 1 < len(lines) and is_short_title_line(lines[idx + 1].text):
                return code, clean_heading_name(lines[idx + 1].text), 2
            return code, "", 1
    return None, None, 0


def is_heading_line(text: str) -> bool:
    text = normalize_text(text)
    return bool(
        RE_MAJOR.match(text)
        or RE_MAJOR_CN.match(text)
        or RE_MIDDLE.match(text)
        or RE_SMALL.match(text)
        or RE_OCC.match(text)
    )


def cut_at_next_heading(text: str, current_code: str) -> str:
    positions: list[int] = []
    include_match = RE_INCLUDE_MARKER.search(text)
    if include_match and include_match.start() > 0:
        positions.append(include_match.start())
    elif include_match and include_match.start() == 0:
        return ""
    for match in RE_NEXT_HEADING.finditer(text):
        found = match.group(1)
        if found.startswith(current_code):
            continue
        if match.start() > 0:
            positions.append(match.start())
    if positions:
        return text[: min(positions)]
    return text


def split_definition_and_tasks(block_text: str) -> tuple[str, list[str]]:
    text = normalize_text(block_text)
    if not text:
        return "", []

    text = cut_at_next_heading(text, "")

    task_header = "主要工作任务:"
    task_idx = text.find(task_header)
    if task_idx == -1:
        task_header = "主要工作任务："
        task_idx = text.find(task_header)

    if task_idx != -1:
        definition_part = text[:task_idx]
        tasks_part = text[task_idx + len(task_header) :]
    else:
        definition_part = text
        tasks_part = ""

    definition_part = cut_at_next_heading(definition_part, "")
    tasks_part = cut_at_next_heading(tasks_part, "")

    definition = definition_part.strip()

    cleaned_tasks_text = RE_NUMBER_MARK.sub("", tasks_part)
    raw_tasks = re.split(r"(?<=[；;。])", cleaned_tasks_text)
    tasks = []
    for task in raw_tasks:
        task = task.strip()
        if not task:
            continue
        if RE_NEXT_HEADING.match(task):
            continue
        if len(task) < 6:
            continue
        tasks.append(task)

    return definition, tasks


def score_candidate(record: OccupationRecord) -> tuple[int, int, int, int]:
    return record.quality_score()


def clean_title(title: str) -> str:
    title = clean_heading_name(title)
    title = re.sub(r"^(?:L/S|S/L|L|S)", "", title)
    title = re.sub(r"(?:L/S|S/L|L|S)$", "", title)
    title = re.sub(r"\d+$", "", title)
    title = cut_at_next_heading(title, "")
    title = title.strip()
    if any(ch in title for ch in ["，", ",", "；", ";", "。", ":", "："]):
        return ""
    if title.startswith(("在", "从事", "负责", "使用", "进行", "担任")):
        return ""
    if "不便分类的其他从业人员" in title:
        return "不便分类的其他从业人员"
    if len(title) > 24:
        title = title[:24]
    return title


def title_continuation(text: str) -> str:
    text = clean_heading_name(text)
    text = re.sub(r"^(?:[LS/]+)", "", text)
    text = re.sub(r"(?:[LS/]+)$", "", text)
    text = text.strip()
    if not text:
        return ""
    if len(text) > 30:
        return ""
    if re.search(r"\d|[:：]", text):
        return ""
    if text.startswith(
        (
            "从事",
            "在",
            "使用",
            "运用",
            "驾驶",
            "操作",
            "进行",
            "担任",
            "主要工作任务",
            "本大类包括",
            "本中类包括",
            "本小类包括",
        )
    ):
        return ""
    return text


def marker_from_text(text: str) -> str:
    text = clean_heading_name(text)
    if not text:
        return ""
    if text in {"L/S", "S/L"}:
        return "L/S"
    if text == "L":
        return "L"
    if text == "S":
        return "S"
    if text.endswith("L/S") or text.endswith("S/L"):
        return "L/S"
    if text.endswith("L"):
        return "L"
    if text.endswith("S"):
        return "S"
    return ""


def assemble_multiline_title(
    lines: list[Line], idx: int, initial_title: str
) -> tuple[str, int, str]:
    parts: list[str] = []
    consumed = 1
    marker = marker_from_text(initial_title)

    if initial_title:
        parts.append(initial_title)

    lookahead = idx + 1
    while lookahead < len(lines) and consumed < 4:
        next_text = lines[lookahead].text
        if is_heading_line(next_text):
            break
        next_marker = marker_from_text(next_text)
        if next_marker:
            marker = (
                "L/S"
                if {marker, next_marker} == {"L", "S"}
                else (marker or next_marker)
            )
        continuation = title_continuation(next_text)
        if not continuation:
            if next_marker:
                consumed += 1
                lookahead += 1
                continue
            break
        parts.append(continuation)
        consumed += 1
        lookahead += 1
        combined = clean_title("".join(parts))
        if combined.endswith(
            (
                "人员",
                "负责人",
                "工程技术人员",
                "设计师",
                "技师",
                "员",
                "师",
                "长",
                "官",
                "兵",
            )
        ):
            break

    title = clean_title("".join(parts))
    return title, consumed, marker


def collect_block_lines(
    lines: list[Line], start_idx: int, current_code: str
) -> tuple[str, int]:
    block_lines: list[str] = []
    j = start_idx
    while j < len(lines):
        nxt = normalize_text(lines[j].text)
        if not nxt:
            j += 1
            continue
        nxt_heading_code, _, _ = parse_heading(lines, j)
        if nxt_heading_code:
            break
        nxt_occ = RE_OCC.match(nxt)
        if nxt_occ and nxt_occ.group(1) != current_code:
            break
        bounded = cut_at_next_heading(nxt, current_code)
        if bounded:
            block_lines.append(bounded)
        if bounded != nxt:
            break
        j += 1
    return "".join(block_lines), j


def find_nearby_title(lines: list[Line], idx: int, code: str) -> str:
    candidates: list[str] = []
    for pos in range(max(0, idx - 12), min(len(lines), idx + 13)):
        text = normalize_text(lines[pos].text)
        match = re.search(rf"{re.escape(code)}(.+)$", text)
        if not match:
            continue
        title = clean_title(match.group(1))
        if title:
            candidates.append(title)
    if idx > 0 and is_short_title_line(lines[idx - 1].text):
        title = clean_title(lines[idx - 1].text)
        if title:
            candidates.append(title)
    if candidates:
        return max(candidates, key=len)
    return ""


def find_title_globally(lines: list[Line], code: str) -> str:
    candidates: list[str] = []
    for idx, line in enumerate(lines):
        text = normalize_text(line.text)
        match = re.search(rf"{re.escape(code)}(.+)$", text)
        if not match:
            if text == code:
                if idx > 0 and is_short_title_line(lines[idx - 1].text):
                    title = clean_title(lines[idx - 1].text)
                    if title:
                        candidates.append(title)
                if idx + 1 < len(lines) and is_short_title_line(lines[idx + 1].text):
                    title = clean_title(lines[idx + 1].text)
                    if title:
                        candidates.append(title)
            continue
        title = clean_title(match.group(1))
        if title:
            candidates.append(title)
    if candidates:
        return max(candidates, key=len)
    return ""


def invalid_category_name(name: str) -> bool:
    if not name:
        return True
    if len(name) > 24:
        return True
    if re.search(r"\d|，|,|；|;|。", name):
        return True
    if name.startswith(("在", "从事", "负责", "使用", "进行", "担任")):
        return True
    return False


def clean_definition_prefix(record: OccupationRecord) -> str:
    definition = record.definition.strip()
    if not definition:
        return definition

    definition = re.sub(r"^[\/LS]+", "", definition)
    definition = re.sub(r"^[A-Z\d-]+", "", definition)
    definition = re.sub(rf"^{re.escape(record.code)}", "", definition)
    definition = re.sub(r"^[A-Z\d-]+", "", definition)
    definition = re.sub(r"^[\/LS]+", "", definition)
    if record.title:
        alt_title = record.title.replace("（", "(").replace("）", ")")
        for title_variant in [record.title, alt_title]:
            if definition.startswith(title_variant):
                remainder = definition[len(title_variant) :]
                if remainder.startswith(
                    ("从事", "使用", "运用", "驾驶", "操作", "在", "进行", "担任")
                ):
                    definition = remainder
                    break
    return definition.strip()


def recover_title_from_definition(record: OccupationRecord) -> str:
    definition = record.definition.strip()
    if not definition:
        return record.title
    match = re.match(
        r"^([^从使运驾操在进担]{2,30}?)(从事|使用|运用|驾驶|操作|在|进行|担任)",
        definition,
    )
    if match:
        candidate = clean_title(match.group(1))
        if candidate:
            return candidate
    return record.title


def merge_markers(*markers: str) -> tuple[bool, bool]:
    values = {m for m in markers if m}
    if "L/S" in values or "S/L" in values or values == {"L", "S"}:
        return True, True
    if "L" in values:
        return True, False
    if "S" in values:
        return False, True
    return False, False


def parse_pdf() -> list[OccupationRecord]:
    ordered_lines: list[Line] = []
    with pdfplumber.open(str(PDF_PATH)) as pdf:
        print(f"Total pages: {len(pdf.pages)}")
        for i, page in enumerate(pdf.pages):
            ordered_lines.extend(order_page_lines(page))
            if (i + 1) % 50 == 0:
                print(f"  Ordered page {i + 1}")

    major_names: dict[str, str] = {}
    middle_names: dict[str, str] = {}
    small_names: dict[str, str] = {}
    occupations: dict[str, OccupationRecord] = {}

    current_l1_code = ""
    current_l1_name = ""
    current_l2_code = ""
    current_l2_name = ""
    current_l3_code = ""
    current_l3_name = ""

    i = 0
    while i < len(ordered_lines):
        line = ordered_lines[i]
        text = normalize_text(line.text)
        if not text:
            i += 1
            continue

        heading_code, heading_name, consumed = parse_heading(ordered_lines, i)
        if heading_code:
            if re.fullmatch(r"\d", heading_code):
                current_l1_code = heading_code
                current_l1_name = heading_name or current_l1_name
                major_names[heading_code] = current_l1_name
                current_l2_code = ""
                current_l2_name = ""
                current_l3_code = ""
                current_l3_name = ""
            elif re.fullmatch(r"\d-\d{2}", heading_code):
                current_l2_code = heading_code
                current_l2_name = heading_name or current_l2_name
                middle_names[heading_code] = current_l2_name
                current_l3_code = ""
                current_l3_name = ""
            elif re.fullmatch(r"\d-\d{2}-\d{2}", heading_code):
                current_l3_code = heading_code
                current_l3_name = heading_name or current_l3_name
                small_names[heading_code] = current_l3_name
            i += consumed
            continue

        occ_match = RE_OCC.match(text)
        if occ_match:
            code = occ_match.group(1)
            raw_suffix = occ_match.group(2)
            suffix = clean_title(raw_suffix)
            title, consumed_occ, marker = assemble_multiline_title(
                ordered_lines, i, raw_suffix
            )

            if not suffix and i + 1 < len(ordered_lines):
                next_text = normalize_text(ordered_lines[i + 1].text)
                next_same_code = RE_OCC.match(next_text)
                if next_same_code and next_same_code.group(1) == code:
                    marker = marker or marker_from_text(next_same_code.group(2))
                    title = clean_title(next_same_code.group(2))
                    consumed_occ = 2

            if (
                not title
                and i + 1 < len(ordered_lines)
                and is_short_title_line(ordered_lines[i + 1].text)
            ):
                marker = marker or marker_from_text(ordered_lines[i + 1].text)
                title = clean_title(ordered_lines[i + 1].text)
                consumed_occ = 2

            if not title:
                title = find_nearby_title(ordered_lines, i, code)

            block_text, j = collect_block_lines(ordered_lines, i + consumed_occ, code)
            definition, tasks = split_definition_and_tasks(block_text)

            l1_code = code.split("-")[0]
            l2_code = "-".join(code.split("-")[:2])
            l3_code = "-".join(code.split("-")[:3])
            candidate = OccupationRecord(
                code=code,
                title=title,
                is_green="L" in marker,
                is_digital="S" in marker,
                category_l1_code=l1_code,
                category_l1_name=DEFAULT_L1.get(
                    l1_code, major_names.get(l1_code, current_l1_name)
                ),
                category_l2_code=l2_code,
                category_l2_name=DEFAULT_L2.get(
                    l2_code, middle_names.get(l2_code, current_l2_name)
                ),
                category_l3_code=l3_code,
                category_l3_name=small_names.get(l3_code, current_l3_name) or title,
                definition=definition,
                tasks=tasks,
            )

            previous = occupations.get(code)
            if previous is None or score_candidate(candidate) > score_candidate(
                previous
            ):
                occupations[code] = candidate
            i = max(i + 1, j)
            continue

        i += 1

    if "8-00-00-00" in occupations:
        occupations["8-00-00-00"].title = "不便分类的其他从业人员"

    for record in occupations.values():
        if record.code in FALLBACK_TITLES:
            record.title = FALLBACK_TITLES[record.code]
        if not record.title:
            record.title = find_title_globally(ordered_lines, record.code)

    l3_fallbacks: dict[str, str] = {}
    for record in occupations.values():
        if record.title and record.category_l3_code not in l3_fallbacks:
            l3_fallbacks[record.category_l3_code] = record.title

    for record in occupations.values():
        title_marker = marker_from_text(record.title)
        is_green, is_digital = merge_markers(
            ("L" if record.is_green else ""),
            ("S" if record.is_digital else ""),
            title_marker,
        )
        record.title = clean_title(record.title)
        record.is_green = is_green
        record.is_digital = is_digital
        if invalid_category_name(record.category_l3_name):
            record.category_l3_name = l3_fallbacks.get(
                record.category_l3_code, record.title
            )
        if record.code == "8-00-00-00":
            record.category_l3_name = record.title
        if record.code == "1-01-00-01" and record.code in FALLBACK_DEFINITIONS:
            record.definition = FALLBACK_DEFINITIONS[record.code]
        elif not record.definition and record.code in FALLBACK_DEFINITIONS:
            record.definition = FALLBACK_DEFINITIONS[record.code]
        if record.code in FALLBACK_CLEAN_DEFINITIONS:
            record.definition = FALLBACK_CLEAN_DEFINITIONS[record.code]
        record.definition = clean_definition_prefix(record)
        if len(record.title) <= 3 or record.title in {"/", "员"}:
            record.title = recover_title_from_definition(record)
        if record.code == "1-01-00-01":
            record.category_l3_name = record.title

    return sorted(
        occupations.values(), key=lambda r: [int(part) for part in r.code.split("-")]
    )


def save_records(records: list[OccupationRecord]) -> None:
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    payload = [
        {
            "code": r.code,
            "title": r.title,
            "slug": r.slug,
            "is_green": r.is_green,
            "is_digital": r.is_digital,
            "category_l1_code": r.category_l1_code,
            "category_l1_name": r.category_l1_name,
            "category_l2_code": r.category_l2_code,
            "category_l2_name": r.category_l2_name,
            "category_l3_code": r.category_l3_code,
            "category_l3_name": r.category_l3_name,
            "definition": r.definition,
            "tasks": r.tasks,
        }
        for r in records
    ]
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def print_stats(records: list[OccupationRecord]) -> None:
    total = len(records)
    with_definition = sum(1 for r in records if r.definition)
    with_tasks = sum(1 for r in records if r.tasks)
    with_l3 = sum(1 for r in records if r.category_l3_name)
    print(f"Occupations: {total}")
    print(
        f"With definition: {with_definition} ({with_definition * 100 // max(total, 1)}%)"
    )
    print(f"With tasks: {with_tasks} ({with_tasks * 100 // max(total, 1)}%)")
    print(f"With small-category name: {with_l3} ({with_l3 * 100 // max(total, 1)}%)")
    print("Sample:")
    for record in records[:8]:
        print(
            f"  {record.code} | {record.title} | def={bool(record.definition)} | tasks={len(record.tasks)}"
        )


def main() -> None:
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"PDF not found: {PDF_PATH}")
    records = parse_pdf()
    save_records(records)
    print_stats(records)
    print(f"Saved {len(records)} records to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
