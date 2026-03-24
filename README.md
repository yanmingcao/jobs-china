# 中国职业AI暴露度可视化

基于《中华人民共和国职业分类大典（2022年版）》的中国职业/小类 AI 暴露度分析与可视化工具。

## 项目简介

当前网站以 **小类** 为展示单位，而不是单个职业。

- 每个矩形代表一个职业小类
- 矩形面积按该小类包含的职业数量近似分配
- 颜色表示该小类的 AI 暴露度评分（0-10）
- tooltip 中展示小类定义、评分理由，以及该小类下的职业名称

项目内部仍保留职业级解析结果，但前端展示与评分主流程已经切换为 **小类专用数据管线**。

## 数据来源

- 《中华人民共和国职业分类大典（2022年版）》PDF
- 当前代码中涉及两层数据：
  - 职业级数据：用于保留完整职业信息，并给小类提供职业数量/职业名称
  - 小类级数据：用于网站评分与展示

## 当前数据管线

### 1. 解析职业数据

```bash
uv run python parse_occupations.py
```

输出：`data/occupations.json`

用途：

- 保留职业级 `code/title/definition/tasks`
- 提供 `category_l1/l2/l3` 层级信息
- 为网站提供每个小类下的职业数量与职业名称列表

### 2. 单独解析小类数据

```bash
uv run python parse_small_categories.py
```

输出：`data/small_categories.json`

字段包含：

- 小类编码
- 小类标题
- 小类定义
- 所属大类/中类

### 3. 对小类打分

需要 OpenRouter API 密钥：

```bash
# 创建 .env 文件
echo "OPENROUTER_API_KEY=your_key_here" > .env

# 对全部小类评分
uv run python score_small_categories.py
```

输出：`data/small_category_scores.json`

说明：

- 默认模型：`google/gemini-3-flash-preview`
- 主模型失败时会自动切换备用模型：`google/gemini-3.1-flash-lite-preview`
- 结果会增量写入，可中断后继续运行

常用命令：

```bash
# 只测试前 10 个小类
uv run python score_small_categories.py --start 0 --end 10

# 只重跑某一个小类
uv run python score_small_categories.py --small-code 4-04-04 --force --verbose
```

### 4. 构建前端数据

```bash
uv run python build_site_data.py
```

输出：`site/data.json`

`site/data.json` 是前端直接读取的静态数据文件。它由以下文件组合生成：

- `data/small_categories.json`
- `data/small_category_scores.json`
- `data/occupations.json`

它的作用是：

- 给前端提供小类级评分结果
- 提供 `occupation_count`
- 提供 `occupation_titles`
- 避免浏览器直接处理原始 PDF 或 Python 脚本

### 5. 启动本地网站

```bash
cd site
python -m http.server 8000
```

浏览器打开：`http://127.0.0.1:8000`

## 项目结构

```text
jobs-china/
├── data/
│   ├── （2022年版）中华人民共和国职业分类大典.pdf
│   ├── occupations.json             # 职业级解析结果
│   ├── scores.json                  # 职业级评分结果
│   ├── small_categories.json        # 小类级解析结果
│   └── small_category_scores.json   # 小类级评分结果
├── site/
│   ├── index.html                   # 前端页面
│   └── data.json                    # 前端运行时数据
├── parse_occupations.py             # 职业级 PDF 解析
├── parse_small_categories.py        # 小类级 PDF 解析
├── score.py                         # 职业级评分脚本（保留）
├── score_small_categories.py        # 小类级评分脚本
├── build_site_data.py               # 构建前端数据
├── pyproject.toml
└── README.md
```

## AI暴露度评分说明

**AI 暴露度**衡量人工智能将在多大程度上重塑一类工作：

- **0-1 分**：几乎完全依赖体力、现场操作或手工技能
- **2-3 分**：AI 只能辅助边缘任务，核心工作仍在线下
- **4-5 分**：知识处理与现场执行混合，AI 可部分改变工作方式
- **6-7 分**：知识工作为主，AI 已能显著提升生产率
- **8-9 分**：核心任务高度数字化，AI 将深度重构该类工作
- **10 分**：高度标准化的信息处理工作，AI 已能完成大部分核心任务

高分不代表职业会消失，而是表示 AI 更可能重塑这一类工作的流程、产出方式和岗位需求。

## 已知情况

- 网站当前以 **小类级** 展示，不再使用职业级平均分聚合展示
- `small_categories.json` 当前解析出 `448` 个小类
- `occupations.json` 中实际被职业使用到的小类有 `380` 个
- 因此，若要核对官方小类总数，仍需要继续打磨小类级 PDF 解析逻辑

## 与美国版本的区别

| 方面 | 美国版本 | 中国版本 |
|------|----------|----------|
| 数据来源 | BLS 网站 | PDF 文档 |
| 展示单位 | 职业 | 小类 |
| 职业级原始数据 | 有 | 有 |
| 网站评分入口 | 职业级 | 小类级 |
| 就业/薪资/增长数据 | 详细 | 当前未接入 |

## 参考项目

本项目参考并改编自 [karpathy/jobs](https://github.com/karpathy/jobs)。

## 许可证

MIT
