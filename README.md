# AI Radar · GitHub AI 趋势榜

每天收集 GitHub AI 项目的官方数据，用中文介绍项目用途，并提供年榜、月榜、周榜、日榜和历史总榜。默认打开最新日榜 TOP 30，支持按年月周日查找历史回溯与已保存快照，以及项目分类、能力标签、语言和使用方式筛选。

- 公开仓库：[MUZI-LYY/ai-trend-radar](https://github.com/MUZI-LYY/ai-trend-radar)
- 网站部署地址：[AI Radar](https://muzi-lyy.github.io/ai-trend-radar/)
- 产品需求：[PROJECT_BRIEF.md](PROJECT_BRIEF.md)
- 数据来源：[DATA_SOURCES.md](DATA_SOURCES.md) · [竞品调研](COMPETITIVE_RESEARCH.md)

## 榜单怎么算

| 榜单 | 排序依据 | 时间范围 |
| --- | --- | --- |
| 年榜 | 官方 Star 历史日统计之和 | 来源日期所在自然年，截至最近完整统计日 |
| 月榜 | 官方 Star 历史日统计之和 | 来源日期所在自然月，截至最近完整统计日 |
| 周榜 | 官方 Star 历史日统计之和 | 周一开始的自然周，截至最近完整统计日 |
| 日榜 | 官方 Star 历史日统计 | 最近完整来源统计日 |
| 历史总榜 | 仓库当前累计 Star | 所选采集快照时的累计值 |

周期指标来自 GitHub 官方 `stargazers/history`，不等于两次累计 Star 相减的净增长。日期按接口 `week` 时间戳的 UTC 日期展开，源统计日边界不保证恰好是 UTC 或北京时间午夜。当天未完成的来源统计日不进入排名；缺失数据不补零。所有榜单只在本站收录范围内比较，Star 表示关注度，不代表质量或实际用户数。

首页日榜只展示正增长的全站前 30 名；“全部项目数据”可查看完整收录集合。收录项目数不是当天新建项目数；页面单独显示当日有增长和零增长的数量。点击品牌或“发现榜单”回到最新日榜。

日榜的“在榜时间”指连续进入本站全站日榜前 30 名的天数，从首次真实保存的每日榜单开始计算。缺少相邻日期、落榜后重新上榜均从 1 天开始；同日刷新不累计，搜索或分类筛选也不改变全站在榜记录。

历史入口分为“历史回溯”和“已存快照”，都按年、月、周、日查找。已补齐 2025-01-01 至 2026-09-13 的 621 个来源日期，共 47,296 条官方日统计，每个仓库从创建日起覆盖。回溯页依据这些日值重算当前收录项目的日、周、月、年增长；只纳入所选日期已经创建的仓库，完整周期缺失时不参榜。回溯使用当前分类与介绍，存在当前收录范围偏差，不声称是当时的 GitHub 全量榜或本站真实快照；当时累计 Star 留空，增长同分按仓库名排序，也不计算实际在榜天数。

历史总榜和历史快照是两件事：总榜比较累计 Star；快照保留当时的数据、分类和介绍。官方 Star 历史可以提供过去的周期统计，但不能还原本站上线前的榜单、收录范围、分类或在榜天数。没有保存的日期不会生成虚构快照。

## 项目介绍与分类

首批 106 个项目提供基于来源整理的中文编辑介绍，详情包含具体工作流程、应用场景、功能解释、适合人群、上手步骤、准备条件、项目特有限制和 README 来源。榜单行直接展示概述节选，能力说明不再只重复标签。项目按主要用途分为 10 个方向，并带有能力标签、项目形态、使用方式、语言及维护状态。

人工整理内容保存在 `data/editorial.json`，自动采集优先保留这些修正。未来新发现项目先通过规则和 README 提供初步介绍、分类及标签，并标记为待核实；当前没有接入 LLM 自动生成中文摘要。维护者核对官方材料后可补充编辑记录，再运行：

```bash
python3 -B scripts/enrich.py
python3 -B scripts/validate_data.py
```

更新编辑内容只应用到最新数据，不改写已经保存的历史快照。明显无关的项目可加入 `data/excluded.json`。

## 本地运行

需要 Node.js 22.13 或更高版本、npm、Python 3。采集本地数据时可使用已登录的 GitHub CLI（`gh auth login`），或通过环境变量提供有权读取公开仓库的 `GITHUB_TOKEN`。前端直接读取现有 JSON，运行网站不需要令牌。

```bash
npm ci
npm run dev
```

默认本地地址为 `http://localhost:5173/`。生产构建与检查：

```bash
npm run test
npm run lint
python3 -B scripts/validate_data.py
npm run build
npm run preview
```

重新采集（当天已有快照时，`--refresh` 只更新最新数据）：

```bash
python3 -B scripts/collect.py --limit 180 --new-limit 8 --refresh
```

补充历史（默认自 2025-01-01 起，断点重跑复用已取得的日期）：

```bash
python3 -B scripts/backfill_history.py --start 2025-01-01
```

每日采集会把新获得的日值合并到历史文件，保留较早的已验证数据；新收录仓库的早期历史不足时，运行上述命令补全。不会把当前仓库资料写成过去的采集快照。

`--no-discover` 可跳过搜索与 Trending 发现；已收录项目仍继续更新。`--limit` 是新增收录的总量预算，不会删除或停止更新已有项目；`--new-limit` 限制每轮尝试的新候选数量，不保证每个候选都通过收录检查。不要把令牌写入代码、JSON、Git 提交或前端配置。

## 自动更新与发布

`.github/workflows/update-and-deploy.yml` 在 GitHub Actions 中运行：

1. 每日北京时间 **08:17** 定时采集，保存 JSON 和日期快照。
2. 验证数据并提交变化到仓库。
3. 构建静态网站，发布到 GitHub Pages。

推送到 `main` 会验证、构建和部署已有数据。手动拉取新数据：在仓库 **Actions → Collect AI trends and deploy → Run workflow** 中选择 `main`；当天已经采集过时勾选 `refresh`。手动刷新不会重写当日已保存的历史快照。

初次部署需在仓库 **Settings → Pages → Build and deployment** 中选择 **GitHub Actions**。Actions 使用仓库内置的 `GITHUB_TOKEN` 读取公开数据和提交更新，不需要另外配置长期个人令牌。工作流包含所需的仓库写入和 Pages 发布权限；组织策略仍可能限制这些权限。

GitHub Pages 只负责托管静态页面，后台采集由定时启动的 Actions 完成，所以不需要购买或运行常驻服务器，也不依赖本地电脑持续开机。定时任务可能因平台排队而延迟，不是准点保证；公开仓库连续 60 天无活动时，GitHub 可能停用定时工作流，可在 Actions 中重新启用。失败应查看工作流日志和网站更新时间。

默认保留更新所有已收录项目，总量预算为 180 个，每轮最多尝试 8 个新候选；达到预算后暂停新发现。GitHub Actions 内置令牌常规 REST 额度为每仓库每小时 1,000 次，搜索和次级限流另计。扩大收录范围前需同时评估历史分页、README 请求和执行时长，不能只提高数量参数。

## 文件结构

```text
src/                          React 网站及排名交互
scripts/collect.py            官方数据采集与归档
scripts/enrich.py             应用中文编辑资料
scripts/validate_data.py      发布数据检查
data/editorial.json          编辑介绍、分类与标签
data/excluded.json           排除的仓库
public/data/latest.json       最新数据
public/data/snapshots/         每日保存的历史快照
public/data/index.json        历史日期索引
public/data/board-history.json 全站日榜前 30 名记录
public/data/history.json       回溯用官方每日 Star 统计
public/data/history-index.json 可回溯日期索引
scripts/backfill_history.py    历史补采与每日增量合并
tests/                        统计边界与数据逻辑测试
.github/workflows/            自动采集和 Pages 发布
```

## 许可

本项目代码采用 [MIT License](LICENSE)。第三方仓库名称、标识、README 摘录和项目内容的权利归原作者，仍受各自许可约束；本站代码许可不替代来源项目的许可。访问项目详情中的原始来源以确认最新功能、部署要求和使用条款。
