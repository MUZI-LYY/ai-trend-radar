# 本地候选核验

`scripts/local_backfill.py` 使用当前 `data/discovery.json` 和已发布项目作为输入，按 GitHub ID 去重，只考虑累计至少 10 Star 的仓库。每个候选的真实仓库元数据、README 和官方 Star 日历史核验结果会立即写入本地 SQLite；中断后再次运行会跳过已完成项。不可公开访问、非 AI 相关、Fork 或归档的仓库记为拒绝；API 临时失败隔日重试。核验结果先暂存，**不会直接进入线上榜单**。

```bash
python3 -B scripts/local_backfill.py --batch-size 1000 --rest-budget 3000 --workers 4
python3 -B scripts/export_backfill.py
python3 -B scripts/export_backfill.py --verify-only
```

默认数据库位于 `data/local-backfill.sqlite3`，已被 Git 忽略。导出的 `data/backfill-shards/` 含 64 个按 GitHub ID 分配的 gzip 分片和带 SHA-256 校验的清单，可纳入版本库。新工作区可用以下命令恢复进度，再继续运行：

```bash
python3 -B scripts/export_backfill.py --restore-to data/local-backfill.sqlite3
```

恢复要求目标数据库为空。核验数据只有通过站点数据构建与校验后才能更新 `public/data`；分片清单中的 `admitted` 表示本地核验通过，不等于线上已收录。

`scripts/pack_latest.py` 可把当前完整的 `public/data/latest.json` 无损拆成 64 个压缩分片，恢复时对完整 JSON 做 SHA-256 校验。采集、资料整理和历史导入写入 `latest.json` 时会同步更新这些分片，CI 会检查恢复后的文件与原文件一致。部署构建使用 `scripts/compact_dist.py` 压缩站点副本的日快照：移除可从最新资料恢复的 README 和重复来源文本，旧项目或需保留人工整理版本的 README 不删除；每个项目保留最近 365 条真实日历史，以维持现有 14/30/90/365 天曲线。仓库中的完整快照不变。站点目前仍使用完整 `latest.json`，只有网页读取和快照校验流程全部接通后才能移除原文件。
