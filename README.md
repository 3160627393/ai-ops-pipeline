# ai-ops-pipeline

把前面三个项目接成一条**自动流水**：每天自动跑一轮，生成一份合并的运维日报，推送到飞书 / 企业微信群。

## 链路

```
① 主机巡检（host-inspection） ─┐
                              ├─→ ③ 合并运维日报 ─→ ④ 机器人推送
② 日志归因（ai-log-analyzer） ─┘
   ↑ 数据源：ollama-monitor 的 monitor.log
```

## 为什么用"调脚本"而不是"重写一遍"

每个项目本身能单独跑、单独测，流水线只做编排：调用、取输出、合并、推送。这样任何一环出问题都能单独定位，也不会因为改流水线把前面踩过的坑重新踩一遍。

## 用法

```bash
python pipeline.py              # 跑全流程（按 config.json 决定推不推）
python pipeline.py --no-push    # 只生成日报，不推送
```

产出：`reports/运维日报_YYYYMMDD.md`

## 配置推送

首次运行会生成 `config.json`：

```json
{
  "webhook_type": "none",
  "webhook_url": "",
  "push_max_chars": 3000
}
```

- **飞书群机器人**：群设置 → 群机器人 → 添加 → 复制 Webhook 地址，填 `webhook_type: "feishu"`
- **企业微信群机器人**：群设置 → 群机器人 → 复制 Webhook，填 `webhook_type: "wecom"`

机器人消息有长度限制（约 4000 字符），超过 `push_max_chars` 会自动截断，完整版只在本机。

## 定时

已注册 Windows 计划任务 `AIOpsDailyReport`，每天 09:00 静默运行：

```powershell
Get-ScheduledTask -TaskName "AIOpsDailyReport" | Select State
Start-ScheduledTask -TaskName "AIOpsDailyReport"       # 手动跑一次
Unregister-ScheduledTask -TaskName "AIOpsDailyReport" -Confirm:$false
```

## 实测（2026-11-23）

```
[① 主机巡检] 健康分 75，规则命中 2 条（C 盘 94%、连续运行 41 天）
[② 日志归因] 严重程度中等，识别出 21:01:52 端口不通 → 21:02:05 自动恢复
→ 合并日报 17KB，全流程约 12 秒
```

## 已知问题

- 日志归因的命令参数可能不准（模型编过 `ping 127.0.0.1 -p 11434`），报告里已带警示
- 推送失败不会重试，只在控制台留一行输出；接生产要加重试和失败告警
- 日报按天覆盖同名文件，历史归档需要自行加日期后缀或接存储
