# 本地候选核验

`scripts/local_backfill.py` 使用当前 `data/discovery.json` 和已发布项目作为输入，按 GitHub ID 去重。每个候选的真实仓库元数据、README 和官方 Star 日历史核验结果会立即写入本地 SQLite；中断后再次运行会跳过已完成项。不可公开访问、非 AI 相关、Fork 或归档的仓库记为拒绝；API 临时失败隔日重试。核验结果先暂存，**不会直接进入线上榜单**。

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
