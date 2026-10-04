# AI Radar · GitHub 开源趋势榜

分别追踪 GitHub AI 项目与更广泛的开源仓库。两个榜单有独立数据来源、收录队列和历史记录。

**[在线查看 →](https://muzi-lyy.github.io/ai-trend-radar/)**

## 功能

- **多周期榜单**：日榜、周榜、月榜、年榜、历史总榜，以及独立的自定义时间区间。
- **GitHub 总榜**：导航中的独立榜单，覆盖 AI 以外的仓库，使用同一套周期、筛选、分页和项目详情交互。
- **分类与介绍**：按用途、项目形态、能力标签、语言和使用方式筛选，详情包含功能、场景、上手方法及来源。
- **有趣项目**：独立的编辑精选区，区分可核对的本周 Star 增长与编辑判断的玩法新意，并说明入选理由和尝试入口。
- **历史回溯**：AI 榜单支持查看 2025 年起的历史统计；GitHub 总榜独立补采，实际可选范围以各自页面为准。
- **浏览状态恢复**：默认打开日榜精选 TOP 30，每页 10 条，可选 20／50 条；从详情返回时恢复筛选、页码和滚动位置。

## 榜单规则

| 榜单 | 排序依据 |
| --- | --- |
| 日榜 | 最近已结束的来源统计日新增 Star |
| 周榜、月榜 | 所选自然周／月的每日 TOP 30 去重，合计项目上榜日新增 Star |
| 年榜 | 所选自然年内的每日新增 Star 之和，当前年截至最新统计日 |
| 历史总榜 | 最新采集的累计 Star |
| 自定义时间 | 起止日期内的每日 TOP 30 去重，合计上榜日新增 Star，包含两端日期 |

数据来自 GitHub 官方仓库与 Star 历史接口。缺失值不补零，缺少完整周期数据的项目不参加对应增长榜。日榜“累计在榜天数”从可回溯的最早日期起合计每日 TOP 30 上榜日，跨月、掉榜后重返均继续累加；已存日榜快照优先，更早日期按当前收录范围回溯，不代表当时实际保存的榜单。

榜单只比较本站收录且累计至少 10 Star 的项目，Star 代表关注度。历史回溯使用当前收录范围、分类和介绍，不等同于当时的 GitHub 全站榜单；历史快照也已按同一 Star 门槛清理。

### GitHub 总榜的数据边界

总榜的采集文件是 `data/github-repositories.json`，由 `scripts/collect_github.py` 独立读取 GitHub Search、Trending 和仓库 Star 历史接口；页面数据单独生成到 `public/data/github/`。它不读取或合并 AI 榜单的项目、历史或快照。两套榜单可以各自收录同一仓库，但数据会分别采集和更新。

首批总榜收录 291 个公开仓库。搜索和 Trending 是候选发现方式，因此“总榜”表示跨主题的本站收录榜，不宣称枚举 GitHub 全站。累计 Star 来自 GitHub 仓库元数据；日、周、月、年增长只在官方 Star 历史完整时参榜。首批仓库的历史日值已从 2025-01-01 起补齐（项目创建前的日期除外），后续新日期仍由定时工作流分批采集。中文简介独立保存在 `data/github-profiles.json`，根据各自采集时的 GitHub 简介整理并标记待复核；原文在详情保留。若仓库简介变化或新仓库尚无中文介绍，页面明确显示待整理，不沿用过期译文。用途分类来自仓库简介和 Topics 的初步归类，未经逐项人工核对。

## 自动更新

GitHub Actions 配置为**每小时第 17 分钟**分批发现项目、采集数据、提交变化并发布到 GitHub Pages。平台调度可能延迟，一次运行也不代表全部项目已更新；实际进度以网站和 [Actions 记录](https://github.com/MUZI-LYY/ai-trend-radar/actions) 为准。

同一次工作流会分别采集 AI 榜单与 GitHub 总榜；总榜每日快照在当天至少 80% 的已收录仓库取得日统计后保存，避免把首批尚未补齐的空日榜归档。
AI 采集设有每轮请求预算；总榜还会按 GitHub 响应中的 `X-RateLimit-Remaining` 分别为核心 API 和 Search API 保留额度。触及主限流或次级限流时本轮停止，保留候选分页与已采集项目，由下次定时运行续采。

网站为静态页面，采集在 GitHub 上执行，无需本地电脑开机或常驻服务器。自动提交使用 `github-actions[bot]` 身份。推送到 `main` 会部署已有数据；手动采集可在 Actions 中选择 **Run workflow**。

已有的中文档案会保留，AI 整理的内容明确标注“待复核”。新项目先显示基于 README 的来源说明；中文档案需经来源校验后导入，目前尚未在定时任务中自动生成。

## 本地运行

需要 Node.js **22.13+**、npm 和 Python 3。前端读取现有 JSON，无需 GitHub 令牌。

```bash
npm ci
npm run dev
```

```bash
npm test
npm run lint
python3 -B scripts/validate_data.py
npm run build
```

## 数据维护

两套榜单采集均使用 `GITHUB_TOKEN`，未设置时改用已登录的 GitHub CLI；不会自动退回匿名 API。本机可先运行 `gh auth status` 检查登录状态。不要把令牌写入仓库。

```bash
# 发现候选并继续分批采集
python3 -B scripts/discover.py --max-requests 24
python3 -B scripts/collect.py --batch-size 600 --new-limit 40 --no-discover --refresh

# 独立采集 GitHub 总榜并生成页面数据
python3 -B scripts/collect_github.py --limit 50 --pages 2
python3 -B scripts/build_github_data.py

# 补齐缺失的 2025 年历史，保留其他年份数据
python3 -B scripts/backfill_history.py --start 2025-01-01 --end 2025-12-31

# 修改 data/editorial.json 后应用介绍与分类
python3 -B scripts/enrich.py
python3 -B scripts/validate_data.py
```

符合至少 10 Star 门槛的仓库不设收录总量上限，未完成项目留待后续批次。排除名单位于 `data/excluded.json`；最新数据、历史日值和归档快照位于 `public/data/`。完整的 `latest.json` 与 `history.json` 在干净检出后由 `python3 -B scripts/restore_data.py` 从已校验的分片和压缩文件恢复；`npm run dev`、`npm run build` 和自动采集也会先恢复它们。部署包提供分片项目数据和 `history.json.gz`；页面按需解压历史数据，构建时会核对它与原始历史逐字节一致。

「有趣项目」的选题和简短解读维护在 `src/spotlight-data.ts`。新增条目需填写已收录 AI 项目的 `fullName`、新意标签、看点、入选理由和入门提示。编辑判断需能指出具体的交互或使用场景变化，并找到公开资料或示例作为尝试入口；不计算“趣味分”。热度展示本周官方 Star 新增，不能据此推断实际使用人数。未收录的项目先核实来源并加入 AI 项目采集数据，再添加精选条目。

## 更多资料

[项目需求](PROJECT_BRIEF.md) · [数据来源](DATA_SOURCES.md) · [竞品调研](COMPETITIVE_RESEARCH.md)

项目代码采用 [MIT License](LICENSE)。第三方项目内容、README 摘录和模型仍遵循各自许可。
