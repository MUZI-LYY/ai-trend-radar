# AI Radar · GitHub AI 趋势榜

追踪 GitHub AI 项目的热度变化，通过分类、标签和中文解读，找到值得关注的项目。

**[在线查看 →](https://muzi-lyy.github.io/ai-trend-radar/)**

## 功能

- **多周期榜单**：日榜、周榜、月榜、年榜、历史总榜，以及独立的自定义时间区间。
- **分类与介绍**：按用途、项目形态、能力标签、语言和使用方式筛选，详情包含功能、场景、上手方法及来源。
- **历史回溯**：支持查看 2025 年起的历史统计；实际覆盖范围以网站为准。
- **浏览状态恢复**：默认打开日榜精选 TOP 30，每页 10 条，可选 20／50 条；从详情返回时恢复筛选、页码和滚动位置。

## 榜单规则

| 榜单 | 排序依据 |
| --- | --- |
| 日榜 | 最近已结束的来源统计日新增 Star |
| 周榜、月榜 | 所选自然周／月的每日 TOP 30 去重，合计项目上榜日新增 Star |
| 年榜 | 所选自然年内的每日新增 Star 之和，当前年截至最新统计日 |
| 历史总榜 | 最新采集的累计 Star |
| 自定义时间 | 起止日期内的每日 TOP 30 去重，合计上榜日新增 Star，包含两端日期 |

数据来自 GitHub 官方仓库与 Star 历史接口。缺失值不补零，缺少完整周期数据的项目不参加对应增长榜。日榜的“在榜时间”按实际保存的连续 TOP 30 记录计算。

榜单只比较本站收录项目，Star 代表关注度。历史回溯使用当前收录范围、分类和介绍，不等同于当时的 GitHub 全站榜单；已保存快照的原始数据保持不变。

## 自动更新

GitHub Actions 配置为**每小时第 17 分钟**分批发现项目、采集数据、提交变化并发布到 GitHub Pages。平台调度可能延迟，一次运行也不代表全部项目已更新；实际进度以网站和 [Actions 记录](https://github.com/MUZI-LYY/ai-trend-radar/actions) 为准。

网站为静态页面，采集在 GitHub 上执行，无需本地电脑开机或常驻服务器。自动提交使用 `github-actions[bot]` 身份。推送到 `main` 会部署已有数据；手动采集可在 Actions 中选择 **Run workflow**。

已整理的中文介绍会保留。新项目先展示基于 README 的来源说明与初步分类，后续再复核；目前未接入 LLM 自动生成中文介绍。

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

采集时使用已登录的 GitHub CLI，或通过环境变量提供 `GITHUB_TOKEN`，不要把令牌写入仓库。

```bash
# 发现候选并继续分批采集
python3 -B scripts/discover.py --max-requests 24
python3 -B scripts/collect.py --batch-size 600 --new-limit 40 --no-discover --refresh

# 补齐缺失的 2025 年历史，保留其他年份数据
python3 -B scripts/backfill_history.py --start 2025-01-01 --end 2025-12-31

# 修改 data/editorial.json 后应用介绍与分类
python3 -B scripts/enrich.py
python3 -B scripts/validate_data.py
```

收录不设总量上限，未完成项目留待后续批次。排除名单位于 `data/excluded.json`；最新数据、历史日值和归档快照位于 `public/data/`。

## 更多资料

[项目需求](PROJECT_BRIEF.md) · [数据来源](DATA_SOURCES.md) · [竞品调研](COMPETITIVE_RESEARCH.md)

项目代码采用 [MIT License](LICENSE)。第三方项目内容、README 摘录和模型仍遵循各自许可。
