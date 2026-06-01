from datetime import datetime, timedelta, timezone
import unittest

from monitor import Quote, WatchItem, build_alert_message, should_alert


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


if __name__ == "__main__":
    unittest.main()
