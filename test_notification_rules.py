from __future__ import annotations

import json
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import intraday_opportunity_worker as worker
import market_scanner
from commodity_groups import build_commodity_group_snapshot


class NotificationRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base_payload = {
            "index": {"price": 14000.0, "daily": 0.25},
            "stocks": [],
            "marketBoard": [],
        }

    def _notification_count(self, stamp: str, callback) -> int:
        sent: list[str] = []
        state: dict[str, bool] = {}
        with (
            patch.object(worker, "get_tr_now", return_value=datetime.fromisoformat(stamp)),
            patch.object(worker, "_notify", side_effect=lambda message: sent.append(message) or True),
            patch.object(worker, "_load_state", return_value=state),
            patch.object(worker, "_save_state"),
            patch.object(worker, "_append_system_notification_log"),
        ):
            callback(self.base_payload)
        return len(sent)

    def test_opening_diagnostic_starts_at_0955(self) -> None:
        self.assertEqual(
            self._notification_count("2026-08-11T09:54:00+03:00", worker.check_opening_diagnostic_alert),
            0,
        )
        self.assertEqual(
            self._notification_count("2026-08-11T09:55:00+03:00", worker.check_opening_diagnostic_alert),
            1,
        )

    def test_two_hour_summary_uses_short_grace_window(self) -> None:
        self.assertEqual(
            self._notification_count("2026-08-11T10:00:00+03:00", worker.check_and_send_scheduled_summaries),
            1,
        )
        self.assertEqual(
            self._notification_count("2026-08-11T10:09:59+03:00", worker.check_and_send_scheduled_summaries),
            1,
        )
        self.assertEqual(
            self._notification_count("2026-08-11T10:10:00+03:00", worker.check_and_send_scheduled_summaries),
            0,
        )
        self.assertEqual(
            self._notification_count("2026-08-11T18:30:00+03:00", worker.check_and_send_scheduled_summaries),
            0,
        )

    def test_requested_commodity_relationships_exist(self) -> None:
        mappings = {
            row["name"]: {item["ticker"] for item in row["related"]}
            for row in worker.COMMODITY_MAPPING
        }
        self.assertTrue({"PRKAB", "RUZYE"}.issubset(mappings["Altın"]))
        self.assertIn("PRKAB", mappings["Bakır"])
        self.assertIn("TRCAS", mappings["Brent Petrol"])

    def test_commodity_alerts_advance_in_half_point_steps(self) -> None:
        state: dict[str, bool] = {}
        sent: list[str] = []
        payload = {
            "marketBoard": [{
                "label": "ONS ALTIN ($)",
                "value": 2500.0,
                "daily": 1.62,
                "shortChange": 0.60,
                "shortWindowMinutes": 15,
                "timestamp": "2026-08-11T10:00:00+03:00",
            }],
            "stocks": [
                {"ticker": "PRKAB", "price": 40.0, "daily": 0.10, "delayedQuote": {"price": 40.0}},
                {"ticker": "RUZYE", "price": 12.0, "daily": 0.20, "delayedQuote": {"price": 12.0}},
            ],
        }
        with (
            patch.object(worker, "get_tr_now", return_value=datetime.fromisoformat("2026-08-11T10:00:00+03:00")),
            patch.object(worker, "_notify", side_effect=lambda message: sent.append(message) or True),
            patch.object(worker, "_load_state", return_value=state),
            patch.object(worker, "_save_state"),
            patch.object(worker, "_append_system_notification_log"),
        ):
            worker.check_commodity_correlation_alerts(payload)
            self.assertEqual(len(sent), 1)
            self.assertTrue(state["commodity_step_Altın_2026-08-11_1.0"])
            self.assertTrue(state["commodity_step_Altın_2026-08-11_1.5"])
            self.assertIn("#PRKAB", sent[0])
            self.assertIn("#RUZYE", sent[0])
            self.assertIn("GECİKMELİ TEPKİ FIRSATI", sent[0])

            payload["marketBoard"][0]["daily"] = 2.02
            payload["marketBoard"][0]["shortChange"] = 0.10
            worker.check_commodity_correlation_alerts(payload)
            self.assertEqual(len(sent), 2)
            self.assertTrue(state["commodity_step_Altın_2026-08-11_2.0"])

            worker.check_commodity_correlation_alerts(payload)
            self.assertEqual(len(sent), 2)

    def test_expired_memory_cache_refreshes_instead_of_reloading_disk_forever(self) -> None:
        stale = {"status": "ok", "stocks": [{"ticker": "OLD"}]}
        fresh = {"status": "ok", "stocks": [{"ticker": "NEW"}]}
        cache = {"created_at": 0.0, "payload": None}
        with (
            patch.object(market_scanner, "_cache", cache),
            patch.object(market_scanner, "_load_last_successful_scan", return_value=stale),
            patch.object(market_scanner, "_scan_market_fresh", return_value=fresh) as fresh_scan,
            patch.object(market_scanner, "_latest_display_payload", side_effect=lambda payload, **_: payload),
            patch.object(market_scanner.time, "time", return_value=100.0),
        ):
            first = market_scanner.scan_market()
        self.assertTrue(first["staleData"])
        fresh_scan.assert_not_called()

        with (
            patch.object(market_scanner, "_cache", cache),
            patch.object(market_scanner, "_load_last_successful_scan", return_value=stale),
            patch.object(market_scanner, "_scan_market_fresh", return_value=fresh) as fresh_scan,
            patch.object(market_scanner, "_latest_display_payload", side_effect=lambda payload, **_: payload),
            patch.object(
                market_scanner.time,
                "time",
                return_value=100.0 + market_scanner.CACHE_TTL_SECONDS + 1,
            ),
        ):
            second = market_scanner.scan_market()
        self.assertEqual(second, fresh)
        fresh_scan.assert_called_once()

    def test_index_and_commodity_analyst_levels_can_trigger(self) -> None:
        sent: list[str] = []
        state: dict[str, bool] = {}
        levels = [
            {
                "ticker": "XU100",
                "source": "Ahmet Mergen",
                "entry": None,
                "support": None,
                "resistance": 14254.0,
                "note": "BIST ana direnç",
                "name": "BIST 100",
            },
            {
                "ticker": "BZ=F",
                "source": "Ahmet Mergen",
                "entry": None,
                "support": None,
                "resistance": 90.75,
                "note": "Brent boşluk direnci",
                "name": "Brent Petrol",
            },
        ]
        payload = {
            "index": {"price": 14254.0},
            "marketBoard": [{"label": "BRENT PETROL ($)", "value": 90.75}],
            "stocks": [],
        }
        with (
            patch.object(worker, "_load_analyst_levels", return_value=levels),
            patch.object(worker, "get_tr_now", return_value=datetime.fromisoformat("2026-08-11T12:00:00+03:00")),
            patch.object(worker, "_notify", side_effect=lambda message: sent.append(message) or True),
            patch.object(worker, "_load_state", return_value=state),
            patch.object(worker, "_save_state"),
            patch.object(worker, "_append_system_notification_log"),
        ):
            worker.check_analyst_level_alerts(payload)
        self.assertEqual(len(sent), 2)
        self.assertTrue(any("#XU100" in message for message in sent))
        self.assertTrue(any("#BZ=F" in message for message in sent))

    def test_stock_milestone_alert_is_written_to_notification_history(self) -> None:
        payload = {
            "stocks": [{
                "ticker": "ODINE",
                "price": 100.0,
                "modelScore": 81.0,
                "officialOhlc": {"previousClose": 98.5},
                "delayedQuote": {"price": 100.0},
                "analystNotes": [],
            }],
        }
        state: dict[str, bool] = {"move_step_ODINE_+1.0%_2026-08-12": True}
        with (
            patch.object(worker, "get_tr_now", return_value=datetime.fromisoformat("2026-08-12T10:30:00+03:00")),
            patch.object(worker, "_notify", return_value=True),
            patch.object(worker, "_load_state", return_value=state),
            patch.object(worker, "_save_state"),
            patch.object(worker, "_append_system_notification_log") as append_log,
        ):
            worker.check_intraday_price_movements(payload)

        append_log.assert_called_once()
        args, kwargs = append_log.call_args
        self.assertEqual(args[0], "price-movement")
        self.assertEqual(kwargs["ticker"], "ODINE")
        self.assertEqual(kwargs["context"]["trigger"], "stock_daily_milestone")
        self.assertEqual(kwargs["context"]["thresholdPercent"], 1.5)

    def test_audit_ledger_keeps_exact_message_and_delivery_id(self) -> None:
        with TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "notification_log.json"
            audit_path = Path(temp_dir) / "notification_audit.jsonl"
            message = "ODINE denetim mesajı"
            worker._remember_delivery_result(message, {
                "attemptedAt": "2026-08-12T10:30:00+03:00",
                "deliveryStatus": "sent",
                "reason": "",
                "channels": {"ntfy": {"status": "sent", "messageId": "abc123"}},
            })
            with (
                patch.object(worker, "NOTIFICATION_LOG_PATH", log_path),
                patch.object(worker, "NOTIFICATION_AUDIT_PATH", audit_path),
            ):
                worker._append_system_notification_log(
                    "price-movement",
                    message,
                    True,
                    ticker="ODINE",
                    context={"thresholdPercent": 1.5},
                )

            history = __import__("json").loads(log_path.read_text(encoding="utf-8"))
            audit = __import__("json").loads(audit_path.read_text(encoding="utf-8").strip())
            self.assertEqual(history[0]["message"], message)
            self.assertEqual(audit["delivery"]["channels"]["ntfy"]["messageId"], "abc123")
            self.assertEqual(audit["context"]["thresholdPercent"], 1.5)

    def test_commodity_dashboard_distinguishes_cost_pressure_from_lagging_stock(self) -> None:
        payload = {
            "marketBoard": [],
            "stocks": [
                {"ticker": "TUPRS", "price": 200.0, "daily": 0.20},
                {"ticker": "THYAO", "price": 300.0, "daily": -1.10},
            ],
        }
        commodities = [{
            "label": "BRENT PETROL ($)",
            "value": 92.0,
            "daily": 1.50,
            "shortChange": 0.30,
            "timestamp": "2026-08-12T10:30:00+03:00",
        }]
        snapshot = build_commodity_group_snapshot(payload, commodities, {})
        brent = next(group for group in snapshot["groups"] if group["name"] == "Brent Petrol")
        members = {item["ticker"]: item for item in brent["members"]}
        self.assertEqual(members["TUPRS"]["reaction"], "Emtianın gerisinde kaldı")
        self.assertEqual(members["THYAO"]["reaction"], "Maliyet baskısı görülüyor")
        self.assertEqual(members["THYAO"]["relationship"], "inverse")

    def test_oguz_entry_zone_creates_alarm_for_both_boundaries(self) -> None:
        with TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            oguz_path = base / "oguz.json"
            oguz_path.write_text(json.dumps([{
                "ticker": "CWENE",
                "name": "CW Enerji",
                "entry_level": 36.0,
                "entry_zone": [36.0, 37.0],
                "note": "[Oğuz Çelik] 36-37 TL ekleme bölgesi",
            }]), encoding="utf-8")
            with (
                patch.object(worker, "OGUZ_ARSIV_PATH", oguz_path),
                patch.object(worker, "MERGEN_ARSIV_PATH", base / "missing-mergen.json"),
                patch.object(worker, "EXCEL_PATH", base / "missing.xlsx"),
            ):
                levels = worker._load_analyst_levels()

        self.assertEqual([row["entry"] for row in levels], [36.0, 37.0])

    def test_stale_technical_payload_gets_current_display_quote_without_hiding_staleness(self) -> None:
        payload = {
            "status": "ok",
            "dataDate": "2026-07-27",
            "staleData": True,
            "stocks": [{"ticker": "TUPRS", "price": 292.25, "daily": -0.1}],
        }
        quotes = {
            "TUPRS": {
                "price": 336.75,
                "daily": -1.607,
                "timestamp": "2026-08-11T17:45:00+03:00",
                "source": "Yahoo Finance intraday",
            },
        }
        cache = {"created_at": 0.0, "payload": None}
        with (
            patch.object(market_scanner, "_display_quote_cache", cache),
            patch.object(market_scanner, "_download_delayed_quotes", return_value=quotes),
        ):
            result = market_scanner._latest_display_payload(payload, force=True)

        self.assertTrue(result["staleData"])
        self.assertTrue(result["technicalStale"])
        self.assertEqual(result["technicalDataDate"], "2026-07-27")
        self.assertEqual(result["displayQuoteDate"], "2026-08-11")
        self.assertEqual(result["stocks"][0]["price"], 336.75)
        self.assertEqual(result["stocks"][0]["daily"], -1.607)


if __name__ == "__main__":
    unittest.main()
