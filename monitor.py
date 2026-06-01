from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar


CONFIG_PATH = Path("config.json")
STATE_PATH = Path(".state/alerts.json")
PRICE_COLUMNS = ("最新价", "最新", "现价", "price", "最新价格")
CODE_COLUMNS = ("代码", "证券代码", "symbol", "code")
NAME_COLUMNS = ("名称", "证券简称", "name")
CN_TZ = timezone(timedelta(hours=8))
T = TypeVar("T")


@dataclass(frozen=True)
class WatchItem:
    symbol: str
    name: str
    market: str
    alert_below: float


@dataclass(frozen=True)
class Quote:
    symbol: str
    name: str
    price: float


def load_config(path: Path) -> tuple[list[WatchItem], int]:
    with path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    cooldown_hours = int(config.get("cooldown_hours", 12))
    items = [
        WatchItem(
            symbol=str(item["symbol"]).strip(),
            name=str(item["name"]).strip(),
            market=str(item.get("market", "stock")).strip().lower(),
            alert_below=float(item["alert_below"]),
        )
        for item in config["stocks"]
    ]
    return items, cooldown_hours


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2, sort_keys=True)


def first_existing_column(columns: list[str], candidates: tuple[str, ...]) -> str:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    raise KeyError(f"Cannot find any of these columns: {', '.join(candidates)}")


def retry_call(label: str, action: Callable[[], T], attempts: int = 3, delay_seconds: int = 5) -> T:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return action()
        except Exception as error:
            last_error = error
            if attempt == attempts:
                break

            wait_seconds = delay_seconds * attempt
            print(f"{label}失败，第 {attempt}/{attempts} 次：{error}。{wait_seconds} 秒后重试。")
            time.sleep(wait_seconds)

    raise RuntimeError(f"{label}连续失败 {attempts} 次") from last_error


def fetch_quotes(items: list[WatchItem]) -> dict[str, Quote]:
    import akshare as ak

    symbols_by_market: dict[str, set[str]] = {}
    for item in items:
        symbols_by_market.setdefault(item.market, set()).add(item.symbol)

    quotes: dict[str, Quote] = {}

    if symbols_by_market.get("stock"):
        stock_data = retry_call("获取 A 股行情", ak.stock_zh_a_spot_em)
        quotes.update(extract_quotes(stock_data, symbols_by_market["stock"]))

    if symbols_by_market.get("etf"):
        etf_data = retry_call("获取 ETF 行情", ak.fund_etf_spot_em)
        quotes.update(extract_quotes(etf_data, symbols_by_market["etf"]))

    return quotes


def extract_quotes(dataframe: Any, target_symbols: set[str]) -> dict[str, Quote]:
    columns = list(dataframe.columns)
    code_column = first_existing_column(columns, CODE_COLUMNS)
    name_column = first_existing_column(columns, NAME_COLUMNS)
    price_column = first_existing_column(columns, PRICE_COLUMNS)

    quotes: dict[str, Quote] = {}
    for record in dataframe.to_dict("records"):
        symbol = str(record[code_column]).strip()
        if symbol not in target_symbols:
            continue

        price = float(record[price_column])
        quotes[symbol] = Quote(
            symbol=symbol,
            name=str(record[name_column]).strip(),
            price=price,
        )

    return quotes


def should_alert(
    item: WatchItem,
    quote: Quote,
    state: dict[str, Any],
    now: datetime,
    cooldown_hours: int,
) -> bool:
    if quote.price > item.alert_below:
        return False

    last_alert_at = state.get(item.symbol, {}).get("last_alert_at")
    if not last_alert_at:
        return True

    last_alert_time = datetime.fromisoformat(last_alert_at)
    return now - last_alert_time >= timedelta(hours=cooldown_hours)


def build_alert_message(item: WatchItem, quote: Quote, now: datetime) -> str:
    return (
        f"股票价格提醒\n"
        f"{item.name}（{item.symbol}）当前价格 {quote.price:.3f}\n"
        f"已跌到设定提醒价 {item.alert_below:.3f}\n"
        f"检查时间：{now.astimezone(CN_TZ).strftime('%Y-%m-%d %H:%M:%S')} UTC+8"
    )


def send_telegram_message(message: str) -> None:
    import requests

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    def post_message() -> None:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=30,
        )
        response.raise_for_status()

    retry_call(
        "发送 Telegram 提醒",
        post_message,
        attempts=3,
        delay_seconds=10,
    )


def run(config_path: Path, state_path: Path, dry_run: bool = False) -> int:
    items, cooldown_hours = load_config(config_path)
    state = load_state(state_path)
    quotes = fetch_quotes(items)
    now = datetime.now(timezone.utc)
    missing_symbols: list[str] = []
    sent_count = 0

    for item in items:
        quote = quotes.get(item.symbol)
        if quote is None:
            missing_symbols.append(item.symbol)
            continue

        print(f"{item.name}({item.symbol}) 当前价格: {quote.price:.3f}, 提醒价: {item.alert_below:.3f}")
        if not should_alert(item, quote, state, now, cooldown_hours):
            continue

        message = build_alert_message(item, quote, now)
        if dry_run:
            print(f"[dry-run] 将发送提醒:\n{message}")
        else:
            send_telegram_message(message)
            print(f"已发送提醒: {item.name}({item.symbol})")

        state[item.symbol] = {
            "last_alert_at": now.isoformat(),
            "last_price": quote.price,
            "alert_below": item.alert_below,
        }
        sent_count += 1

    if missing_symbols:
        print(f"未找到行情数据: {', '.join(missing_symbols)}")

    save_state(state_path, state)
    return sent_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor A-share and ETF prices, then alert via Telegram.")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--state", type=Path, default=STATE_PATH)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.config, args.state, args.dry_run)
