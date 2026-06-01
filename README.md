# A 股价格提醒

这个仓库用于定时监控 A 股和 ETF 价格。当价格跌到设定值时，通过 Telegram 发送提醒。

当前监控：

| 名称 | 代码 | 提醒价 |
| --- | --- | ---: |
| 芯片科创ETF华安 | 588290 | 3.10 |
| 中韩半导体 | 513310 | 5.65 |
| 中国移动 | 600941 | 96.00 |

> 说明：中国移动 A 股代码通常是 `600941`。如果你确实想监控别的代码，请修改 `config.json`。

## 本地运行

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python monitor.py --dry-run
```

`--dry-run` 只打印提醒内容，不会真的发送 Telegram 消息。

## Telegram 设置

1. 在 Telegram 搜索 `@BotFather`。
2. 发送 `/newbot` 创建机器人。
3. 记录 BotFather 返回的 bot token。
4. 给你的新 bot 发一条消息。
5. 获取你的 chat id。可以在浏览器打开：

```text
https://api.telegram.org/bot<你的BOT_TOKEN>/getUpdates
```

返回内容里的 `chat.id` 就是 `TELEGRAM_CHAT_ID`。

## GitHub 设置

在仓库里进入：

`Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`

添加两个 secret：

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

GitHub Actions 会每 15 分钟运行一次，也可以在 `Actions` 页面手动点击 `Run workflow` 测试。

## 修改监控清单

编辑 `config.json`：

```json
{
  "cooldown_hours": 12,
  "stocks": [
    {
      "symbol": "588290",
      "name": "芯片科创ETF华安",
      "market": "etf",
      "alert_below": 3.1
    }
  ]
}
```

字段说明：

- `symbol`：股票或 ETF 代码
- `name`：提醒里显示的名称
- `market`：`stock` 或 `etf`
- `alert_below`：价格小于等于这个值时提醒
- `cooldown_hours`：同一个代码两次提醒之间的最短间隔，默认 12 小时
