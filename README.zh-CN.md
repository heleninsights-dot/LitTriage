# LitTriage / 文献分诊

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Claude Code Plugin](https://img.shields.io/badge/Claude%20Code-Plugin-6E56CF)](https://claude.com/claude-code)
[![零依赖](https://img.shields.io/badge/dependencies-none-brightgreen.svg)](#快速开始)
[![English](https://img.shields.io/badge/README-English-blue)](README.md)

> 像分诊病人一样分诊文献：先诊断 → 再排序 → 先读最重要、最贴近你需求的那几篇。

一个轻量的 Claude Code / Codex **skill**，专注于**检索与分诊**医学文献：它自动规划
MeSH 检索式，从 PubMed 检索并去重，给每篇文献按相关性打 1–10 分，标注研究类型与证据
等级，最终生成一份**带评分标签的 BibTeX** 和一张**分诊表格**。

它是一整套「阅读 + 写作」工作流的**第一步** ↓

---

## 你的学术阅读与写作工作流

LitTriage 是整套流程的入口。下面每一步都是独立的工具 / skill——可以串起来用，也可以在
任意一步停下，拿到你需要的产物即可。

<p align="center">
  <img src="docs/workflow.png" alt="LitTriage 端到端工作流：LitTriage → Zotero → Bridge → phd-deepread → 写作" width="860">
</p>

<details>
<summary>📋 工作流文字版</summary>

```
①  LitTriage · 本仓库  —  搜索 + 分诊
       诊断 -> 打分 1-10 -> 给文献排序
       产物：{topic}_ranked.bib（评分作为标签）· {topic}_ranked.md（分诊表）
   |
   v
②  Zotero  —  收集 + 阅读
       导入 .bib -> "Find Available PDF" -> 按评分从高到低阅读
       边读边记简单的文献笔记
   |
   v
③  zotero-deepread-bridge  —  导出到 Obsidian
       把 PDF 从 Zotero 直接「管」进你的 Obsidian 仓库。
       或者在 Obsidian 里用 Zotero Integration + Templater，
       把你的笔记和高亮连同 PDF 一起导出到 Obsidian。
   |
   v
④  phd-deepread  —  精读 + 可视化
       每篇文献：一份 Markdown 文献笔记 + 一张 9 节点 JSON 画布
   |
   v
✍️  开始写作——基于你真正读过、亲手记下的笔记，而不是只看摘要的自动总结。
```

</details>

**可以在哪里分支 / 自定义：**

- **停在 ②**：如果你只想要一份排好序的阅读清单，这本身就是一个完整可用的成果。
- **③–④ 是可选的**：当一篇文献重要到值得做结构化笔记和可视化导图时再用。
- **替换成你自己的阅读器**：第 ② 步可以用任何支持导入 BibTeX 的文献管理器，只是评分
  标签不会像在 Zotero 里那样自动排序。
- **随时重跑 ①**：换一个更精炼的主题再检索，新命中的文献会带着新的评分标签进入同一个
  Zotero 分类。

---

## LitTriage 给你什么

两个产物，然后它就「让路」：

| 文件 | 是什么 | 怎么用 |
| :--- | :--- | :--- |
| `{topic}_ranked.rdf` | Zotero RDF：一个父合集，下设**每个主题一个子合集**（综述置顶），文献已归入各自主题。 | 一次导入 → 在 Zotero 中得到真正的主题**子文件夹**。 |
| `{topic}_ranked.bib` | 以 DOI 为 key、按主题排序的 BibTeX。每条的 `keywords` 里写入 `score-08, topic-…, type-rct, evidence-2, litriage`。 | 导入 Zotero 得到一个扁平合集——这些关键词会变成**可排序的标签**，于是你按 `score-09 → score-08 → …` 的顺序阅读。 |
| `{topic}_ranked.md` | 一份分诊笔记：开头是「如何构建」检索漏斗（检索式 → 命中 → 去重 → 打分 → 保留）与评分/证据概览，正文**按子主题分组**（综述/荟萃分析置顶，其余按最高分排序）——评分 · 证据等级 · 年份 · 第一作者 · 标题 · 期刊 · DOI。 | 先扫一眼，决定哪些值得去拉全文 PDF。 |

**它不会替你写综述**——这正是设计初衷。你（或你的学生）去读真正的原文，按最相关优先
排序，而不是依赖只看摘要的自动总结。

---

## 快速开始

```bash
# 克隆到你的 Claude Code skills 目录
git clone https://github.com/heleninsights-dot/LitTriage.git ~/.claude/skills/litriage
```

然后在 Claude Code / Codex 里直接说：

```
用 litriage 帮我检索 tPBM 在阿尔茨海默病中的应用
litriage: search the literature on tPBM for Alzheimer's-related MCI
```

或者直接运行各阶段脚本：

```bash
python3 scripts/pubmed_search.py --queries .litriage/queries.json --out .litriage/papers_pubmed.jsonl
python3 scripts/dedupe.py        --in .litriage/papers_pubmed.jsonl --out .litriage/candidates.jsonl
# （由 AI 给候选文献打分 -> .litriage/scored_papers.jsonl）
python3 scripts/build_outputs.py --scored .litriage/scored_papers.jsonl --topic "my topic" \
    --out-bib my-topic_ranked.bib --out-md my-topic_ranked.md --out-rdf my-topic_ranked.rdf
```

**环境要求：** Python 3.9+。仅此而已——无需 `pip install`，无需 LaTeX，无需 pandoc。

---

## 为什么这套工作流好用

- **先读最该读的。** 分诊评分让博士生第一天就打开最相关、证据等级最高的文献——而不是
  翻到 PubMed 结果的第 7 页。
- **带证据意识。** 每篇文献都被标注 `type-rct`、`evidence-2` 等，分诊的同时顺便熟悉
  证据等级体系。
- **评分跟着文献走。** BibTeX 的 `keywords` 会作为 Zotero 标签导入（`score-08`，零填充
  以便正确排序），你的分诊结果一路保留到阅读清单里。
- **端到端，但模块化。** 从「我有一个主题」到「我有结构化笔记和概念导图」是一条完整路径，
  但每一步都可选、可替换。
- **零依赖。** 仅用 Python 3.9+ 标准库。安装简单、易于分享、不会因依赖而崩。

---

> **设计笔记 —— 跨学科评分。** 一个好的排序算法，骨架可以跨学科通用，但评分维度
> 不能照搬。面向转化医学：把**检测技术/方法学**（HPLC-MS、ELISA、免疫组化等）
> 纳入「方法匹配」，把**模型系统**（体外→动物→人）单列为一个维度，并让**临床成熟度
> 抬高分数**——一个已进入临床的生物标志物，不该输给只在培养皿里验证过的。
> 详见 [`references/02_scoring_translational.md`](references/02_scoring_translational.md)。

---

## LitTriage 内部如何工作

```
主题 topic
  ① MeSH 检索式规划                        (AI → queries.json)
  ② PubMed 检索（OpenAlex 兜底）           (pubmed_search.py)
  ③ 去重                                   (dedupe.py)
  ④ 打分 1-10 + 研究类型标注               (AI → scored_papers.jsonl)
  ⑤ 生成产物                               (build_outputs.py)
        ↓
  {topic}_ranked.rdf   +   {topic}_ranked.bib   +   {topic}_ranked.md
```

完整的逐阶段约定见 `SKILL.md`，检索式规划与打分的提示词见 `references/`。

---

## 致谢与署名

核心的**检索 → 去重 → 1–10 相关性打分 → 高分优先选文**这一*思路*（第 1–4 阶段）
**灵感来源于** Bensz Conan（[@huangwb8](https://github.com/huangwb8)）非常出色的
[`ChineseResearchLaTeX`](https://github.com/huangwb8/ChineseResearchLaTeX) skill。

本项目是一次**独立的重写实现**——没有复制任何源码。PubMed 优先检索、
MeSH/研究类型/证据等级标注、评分进 Zotero 的衔接，以及刻意「不做写作阶段」的设计，
都是 LitTriage 原创的部分。简而言之，LitTriage 只共享第 1–4 阶段的打分思路；检索源、标注、Zotero/Obsidian 衔接与整体工作流都是它自己的。

## 许可证

MIT © 2026 Qing Wang（[@heleninsights-dot](https://github.com/heleninsights-dot)）。
详见 [LICENSE](./LICENSE)。
