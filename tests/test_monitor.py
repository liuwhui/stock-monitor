from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from monitor import Quote, WatchItem, build_alert_message, load_config, parse_tencent_quotes, retry_call, should_alert


class MonitorTest(unittest.TestCase):
    def test_should_alert_when_price_is_below_threshold_without_state(self):
        item = WatchItem(symbol="600941", name="中国移动", market="stock", alert_below=96)
        quote = Quote(symbol="600941", name="中国移动", price=95.99)

        self.assertTrue(should_alert(item, quote, {}, datetime.now(timezone.utc), 12))

    def test_should_not_alert_when_price_is_above_threshold(self):
        item = WatchItem(symbol="588290", name="芯片科创ETF华安", market="etf", alert_below=3.1)
        quote = Quote(symbol="588290", name="芯片科创ETF华安", price=3.101)

        self.assertFalse(should_alert(item, quote, {}, datetime.now(timezone.utc), 12))

    def test_should_not_alert_inside_cooldown(self):
        now = datetime.now(timezone.utc)
        item = WatchItem(symbol="513310", name="中韩半导体", market="etf", alert_below=5.65)
        quote = Quote(symbol="513310", name="中韩半导体", price=5.6)
        state = {"513310": {"last_alert_at": (now - timedelta(hours=1)).isoformat()}}

        self.assertFalse(should_alert(item, quote, state, now, 12))

    def test_should_alert_after_cooldown(self):
        now = datetime.now(timezone.utc)
        item = WatchItem(symbol="513310", name="中韩半导体", market="etf", alert_below=5.65)
        quote = Quote(symbol="513310", name="中韩半导体", price=5.6)
        state = {"513310": {"last_alert_at": (now - timedelta(hours=13)).isoformat()}}

        self.assertTrue(should_alert(item, quote, state, now, 12))

    def test_build_alert_message_contains_symbol_price_and_threshold(self):
        now = datetime(2026, 6, 1, 1, 2, 3, tzinfo=timezone.utc)
        item = WatchItem(symbol="600941", name="中国移动", market="stock", alert_below=96)
        quote = Quote(symbol="600941", name="中国移动", price=95.5)

        message = build_alert_message(item, quote, now)

        self.assertIn("中国移动（600941）", message)
        self.assertIn("95.500", message)
        self.assertIn("96.000", message)

    def test_retry_call_recovers_after_temporary_failure(self):
        calls = {"count": 0}

        def flaky_action():
            calls["count"] += 1
            if calls["count"] == 1:
                raise ConnectionError("temporary failure")
            return "ok"

        result = retry_call("测试动作", flaky_action, attempts=2, delay_seconds=0)

        self.assertEqual(result, "ok")
        self.assertEqual(calls["count"], 2)

    def test_parse_tencent_quotes(self):
        text = 'v_sh600941="1~中国移动~600941~95.50~95.00~95.20";'

        quotes = parse_tencent_quotes(text, {"600941": "中国移动"})

        self.assertEqual(quotes["600941"].name, "中国移动")
        self.assertEqual(quotes["600941"].price, 95.5)

    def test_current_config_uses_correct_gold_etf_code(self):
        items, _ = load_config(Path("config.json"))
        gold_items = [item for item in items if item.name == "黄金ETF华夏"]

        self.assertEqual(len(gold_items), 1)
        self.assertEqual(gold_items[0].symbol, "518850")
        self.assertEqual(gold_items[0].alert_below, 8.2)

    def test_current_config_keeps_only_active_alerts(self):
        items, _ = load_config(Path("config.json"))

        self.assertEqual([item.symbol for item in items], ["518850", "515180", "600941"])
        dividend = next(item for item in items if item.symbol == "515180")
        self.assertEqual(dividend.name, "中证红利ETF")
        self.assertEqual(dividend.alert_below, 1.315)
        mobile = next(item for item in items if item.symbol == "600941")
        self.assertEqual(mobile.alert_below, 86)


if __name__ == "__main__":
    unittest.main()
