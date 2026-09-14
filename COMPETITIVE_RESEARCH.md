# 同类产品与公开数据调研

调研日期：2026-09-14。范围：GitHub 趋势榜、项目分析、中文项目发现，以及可用于本项目的公开数据。

**实施更新：** 以下保留研究时的观察、样本和限制。后续已经成功接入 GitHub 官方 Star 历史接口，完成年／月／周／日及历史总榜；周榜按周一开始的来源日期自然周聚合。历史按年月周日选择，日榜连续在榜时间依据本站实际保存的全站前 30 名记录，不能回溯未保存的榜单。最新实现口径见 [PROJECT_BRIEF.md](PROJECT_BRIEF.md)，自动运行说明见 [README.md](README.md)。

## 1. 结论

建议结合四种已被实际产品使用的做法：

- **Star History：** 用官方历史统计提供阶段增长和项目曲线。
- **HelloGitHub／GitHubDaily：** 用中文讲清项目用途与场景，降低阅读门槛。
- **OSSInsight Collections：** 按应用方向组织项目，支持类内比较。
- **Github-Ranking：** 每日采集后保存日期文件，再生成可浏览的榜单。

数据方面出现两个关键发现：

1. Star History 在 2026-09-05 的文章中明确表示已采用 GitHub 新的 Star 历史接口。这为上一轮发现的官方接口提供了实际使用方的佐证，但不是我们自己的成功调用结果。
2. OSSInsight 当前首页明确暂停基于 Star 的排名，原因是公开事件流的分页变化导致其采集严重漏记。不能直接复用它受影响时期的 Star 增长榜。

## 2. 六个参考产品

| 产品 | 本次实际看到的能力 | 分类和项目介绍 | 数据与更新方式 | 对我们的价值 |
| --- | --- | --- | --- | --- |
| [GitHub Trending](https://github.com/trending) | 日、周、月入口；仓库简介、语言、累计 Star、周期 Star | 主要按语言等条件浏览，不是专门的 AI 场景分类；介绍较短 | GitHub 官方页面 | 用于发现热点，不能直接当作我们的完整分类榜 |
| [Star History](https://www.star-history.com/) | Star Map、Star Compare、Weekly、All-time、AI Coding 入口，以及 Star 历史曲线 | 重视趋势与比较；不能替代每个项目的中文详细介绍 | 官方文章说明已采用新历史 API；周榜展示明确日期范围 | 最值得参考的历史数据与趋势展示方案 |
| [OSSInsight](https://ossinsight.io/) | 仓库分析、技术集合、历史趋势等入口 | 集合页面包括 AI Agent、MCP、GraphRAG 等细分方向 | GitHub API 与事件数据；当前有 Star 排名暂停公告 | 借鉴分类比较和数据异常提示，暂不依赖受影响的事件排名 |
| [HelloGitHub](https://hellogithub.com/) | 月刊、榜单、热门标签、月度／年度等入口；公开月刊可阅读全文 | 中文用途介绍、图示、平台或使用条件；月刊按语言及人工智能等分组 | 编辑与社区推荐内容；仓库说明月刊每月 28 日发布 | 借鉴介绍质量与可读性；网站排名算法本次未核实，不能默认是 Star 排行 |
| [GitHubDaily](https://github.com/GitHubDaily/GitHubDaily) | 项目清单和年度复盘 | AI 工具、开发工具、媒体工具等分类；每个条目有中文用途说明 | 本次读取的 README 标题为“2025 年复盘”，不是今日实时数据集 | 可作为候选发现和文案结构参考，不能直接用来证明项目今天热门 |
| [EvanLi/Github-Ranking](https://github.com/EvanLi/Github-Ranking) | 总 Star／Fork Top 100、按语言 Top 100、自动更新时间 | 语言分类、仓库原始简介，缺少 AI 场景标签和深度解读 | 已检查 GraphQL 采集代码、CSV、Markdown 输出和 cron 脚本 | 最贴近“数据放 GitHub，每天自动更新”的可参考实现 |

## 3. 实际数据样本

以下是 2026-09-14 读取到的页面或文件数值，用于说明数据结构和口径，不代表已逐条通过官方接口复核的最终榜单。不同来源的采集时刻并不相同。

### 3.1 同一个项目，不同来源给出不同周期

样例项目：`debpalash/VoiceStudio`。

| 来源 | 页面窗口 | 页面数值 |
| --- | --- | --- |
| GitHub Trending 日榜 | `stars today` | 周期 Star 2,632；累计 Star 28,206 |
| GitHub Trending 月榜 | `stars this month` | 周期 Star 15,895；累计 Star 28,221 |
| Star History 周榜 | 2026-09-06 至 2026-09-12 | 增长展示 +5,818，页面列第 9 |

来源：[Trending 日榜](https://github.com/trending)、[Trending 月榜](https://github.com/trending?since=monthly)、[Star History](https://www.star-history.com/)。

**判断：** 这些数字不能直接比较或取平均。周期窗口不同，页面采集时刻也不同；累计 Star 的差异本身不能证明其中一方错误。我们的每条统计必须带来源、周期和采集时间，排名也不能从多个网站拼接而来。

此外，VoiceStudio 出现在 Trending 和 Star History 的样本中，但没有出现在下面的 Github-Ranking 当日 CSV 中。这说明“某来源没有收录”不等于“项目不热门”。

### 3.2 Github-Ranking 已有可下载的日度 CSV

实际读取文件：[github-ranking-2026-09-14.csv](https://github.com/EvanLi/Github-Ranking/blob/master/Data/github-ranking-2026-09-14.csv)。

- 共 **3,600 行榜单记录**，涉及 **36 个榜单组**。
- 按 `repo_url` 去重后为 **3,449 个不同仓库**，不是 3,600 个项目。
- 字段包括 `rank`、`item`、`repo_name`、`stars`、`forks`、`language`、`repo_url`、`username`、`issues`、`last_commit`、`description`。
- README 标记的自动更新时间为 `2026-09-14T04:07:36Z`，即北京时间 12:07:36；这不是保证每个仓库在同一秒采集的时间戳。

| 项目 | 所属榜单 | 文件内排名 | 累计 Star | Fork |
| --- | --- | --- | --- | --- |
| ollama/ollama | top-100-stars | 42 | 180,845 | 17,843 |
| langgenius/dify | top-100-stars | 54 | 155,637 | 24,579 |

另外成功读取了 [2018-12-18 的 CSV](https://github.com/EvanLi/Github-Ranking/blob/master/Data/github-ranking-2018-12-18.csv)，包含 2,700 行。这证明存在较早的历史文件，但本次没有验证整个日期序列是否连续，不能因此宣称它拥有完整多年日度数据。

**复用判断：** 可以作为初期候选集合、历史快照补充或核对来源。它主要覆盖各类 Top 100，不能解决全部新项目的发现，也不能保证每个 AI 项目具有连续历史。不能把未进入 Top 100 的项目历史 Star 补成 0。

### 3.3 Github-Ranking 的自动更新不是“上传后自然发生”

公开的 [auto_run.sh](https://github.com/EvanLi/Github-Ranking/blob/master/auto_run.sh) 写明使用 `crontab` 调度，并依次拉取代码、运行 Python、提交和推送。其 [process.py](https://github.com/EvanLi/Github-Ranking/blob/master/source/process.py) 使用 GitHub GraphQL 查询仓库，并生成日期 CSV 和 Markdown 榜单。

这说明我们选择“采集程序 → 日期数据文件 → 静态榜单”是有现成参考的。它展示的调度方式是外部 cron，不是已经证明由 GitHub Actions 执行；我们可以将同类采集流程部署到 Actions，仍需显式配置工作流。

## 4. 两个重要的数据质量发现

### 4.1 OSSInsight：近期 Star 排名已暂停

当前首页原文标题为 **“Star-based rankings are paused”**。公告解释：GitHub 公开事件流分页变化后，其采集只读取了第一部分，导致 2025 年中以来的 Star、PR、Issue 事件严重漏记，因此暂停依赖这些计数的排名。公告同时称 2025 年 5 月之前的历史、直接从 GitHub 同步的仓库总量以及提交活动不受该问题影响。

这是 OSSInsight 对自身数据的说明，不能据此推断所有 GH Archive 数据也存在相同缺口。

**对我们的影响：** 将 OSSInsight 从泛泛的“可参考第三方排名”进一步限定为“可参考分类与展示；受影响的事件排名停用”。采集有缺口时，本站也应明确标注，不继续发布看似完整的增长结果。

来源：[OSSInsight 首页](https://ossinsight.io/)。

### 4.2 Star History：新的官方接口已有实际采用者

[2026-09-05 官方文章](https://www.star-history.com/blog/new-github-star-history-api)称已立即采用新的 `stargazers/history` 接口，并说明：

- 过去逐个获取 Star 用户时间的方式有权限及分页限制；较大仓库的旧曲线部分使用采样和当前总数拼接。
- 新接口按周返回日数据，不再需要获取用户列表，请求量主要随仓库年龄增长，而非随 Star 人数增长。
- 每页最多 30 周；只有周期数量，没有逐周累计总数。
- 该产品说明，为绘制准确的完整累计曲线，需要向创建时间回溯获取所有相关页。

**对我们的影响：** 不必依赖它的图片 API 再二次读取数字；优先接入 GitHub 官方历史接口。首版可先实现最近一年阶段统计，再按需补齐完整累计曲线，并明确已获得的历史范围。不要把部分周期和累加值描述成完整的历史累计曲线。

这篇文章提供实际采用的佐证，但 Star 取消／重新添加的细节仍需结合官方定义与我们后续实测确认。

## 5. 分类和介绍可以怎么借鉴

### 分类：按用户任务，而不是只按编程语言

OSSInsight Collections 页面实际列出 102 个集合，包含 AI Agent Frameworks、MCP Client、GraphRAG、Vector Database 等。集合还展示收录数量，用户可以看清比较范围。

HelloGitHub 第 120 期提供了另一个例子：本地语音助手、Agent 与聊天平台集成工具、浏览器控制工具，分别放在 C++、Go 等语言分组中。对想找 AI 工具的产品经理或设计师来说，只按语言浏览不够直观。

因此，本项目继续使用“应用方向主分类 + 具体能力标签 + 项目形态 + 使用条件”。MCP 可以作为协议／能力标签，并在项目数量足够时形成专题集合；不要仅因为项目提到 MCP 就把所有项目放进同一个用途分类。

来源：[OSSInsight Collections](https://ossinsight.io/collections)、[HelloGitHub 第 120 期](https://github.com/521xueweihan/HelloGitHub/blob/master/content/HelloGitHub120.md)。

### 介绍：先说明用途，再帮助判断能否使用

HelloGitHub 的样例通常先用一句中文描述用途，再补充主要功能、平台和使用方式。GitHubDaily 的“AI 工具”分组中，本次统计到 612 个项目链接条目；这是 README 中的条目数，未去重、未逐条核验有效性，不应称为 612 个当前热门 AI 项目。

建议沿用这种易理解的表达方式，但原始事实回到 README／官方文档核验。不要把第三方推荐文案直接当作今天的项目事实，更不要直接复制其编辑内容作为我们的原创介绍。

## 6. 对需求的具体建议

1. **保留“近期增长”和“累计热度”两种入口。** 老牌大项目与新热点需要不同的排序依据。
2. **分类优先于语言。** 主分类回答用途，语言放到辅助筛选。
3. **把数据说明放在数值附近。** 展示统计周期、更新时间和来源，不只在页脚笼统写“来自 GitHub”。
4. **区分热榜、精选和新收录。** 人工推荐不是统计排名，新收录不是仓库新创建；有不同信息时使用具体标记，不混成一个热度分。
5. **每天存日期快照。** 仓库 ID 用于项目去重；榜单记录和项目记录分开，避免多分类重复计数。
6. **先做完整的项目阅读路径。** 首页短介绍，详情说明能力、场景、使用方式和来源；不引入与当前需求无关的社区、订阅等功能。

## 7. 推荐的数据组合

| 环节 | 推荐采用 | 其他来源的定位 |
| --- | --- | --- |
| 初期项目库 | GitHub Search + 分类种子项目 | Github-Ranking、HelloGitHub、GitHubDaily 提供候选线索，需去重与重新核验 |
| 每日发现 | GitHub Search + Trending | Star History 的专题和周榜可做发现参考 |
| 累计指标 | GitHub 官方仓库 API | 第三方日期 CSV 仅作明确日期的补充核对 |
| 阶段增长 | 优先验证官方 Star 历史 API | 不拼接第三方不同窗口的增长量 |
| 项目介绍与标签 | README + 官方文档 | 中文导航站只借鉴表达和组织方式 |
| 历史回看 | 我们每日保存的数据与榜单 | 旧 CSV 仅在项目、日期和指标可比时作为补充来源 |

**首版不必复制任何一家产品。** 最适合当前目标的是：官方数据的可靠性、Star History 的趋势表达、中文项目导航的可读性，以及 Github-Ranking 的每日文件归档方式。

## 8. 调研边界与材料

- 已读取公开页面、README、更新脚本及 CSV；没有登录竞品账户，也没有复制或执行竞品代码。
- HelloGitHub 的动态榜单内容和排序算法未完整核验；本次对它的介绍方式主要依据公开月刊。
- 数字为本次读取样本，可能随时间变化；第三方声明与我们实测统计已分别说明。
- 本次 Firecrawl 搜索返回 402，改为直接读取已知官网和公开仓库；不是全网穷尽式竞品检索。
- 机器可读的样本摘要见 [research/competitor-samples-2026-09-14.json](research/competitor-samples-2026-09-14.json)。
