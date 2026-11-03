from unittest import mock

from django.core import mail
from django.test import TestCase

from portfolio import ngx_sync
from portfolio.models import Stock, StockChange, StockSyncRun


def row(symbol, isin, company=None, tradingview=True, ngx_status=None):
    return {
        "symbol": symbol,
        "isin": isin,
        "company": company or f"{symbol} PLC",
        "sector": "FINANCIAL SERVICES",
        "listing_date": "2020-01-01",
        "incorporation_date": "2010-01-01",
        "ngx_status": ngx_status,
        "tradingview": tradingview,
    }


class NgxSyncTests(TestCase):
    def setUp(self):
        Stock.objects.all().delete()  # migration 0079 seeds the real NGX list
        self.access = Stock.objects.create(
            symbol="ACCESSCORP", company="ACCESSCORP PLC", isin="NGACCESS0005",
            tv_symbol="NSENG:ACCESSCORP",
        )
        self.fbnh = Stock.objects.create(
            symbol="FBNH", company="FBN HOLDINGS PLC", isin="NGFBNH000009",
            tv_symbol="NSENG:FBNH",
        )
        self.base_rows = [
            row("ACCESSCORP", "NGACCESS0005"),
            row("FBNH", "NGFBNH000009", "FBN HOLDINGS PLC"),
        ]

    def sync(self, rows, **kwargs):
        plan = ngx_sync.build_plan(rows, **kwargs)
        ngx_sync.apply_plan(plan, StockSyncRun.objects.create(applied=True))
        return plan

    def kinds(self, plan):
        return [(c.kind, c.status, c.symbol) for c in plan.changes]

    def test_no_changes(self):
        plan = self.sync(self.base_rows)
        self.assertEqual(plan.changes, [])
        self.assertEqual(plan.updates, {})

    def test_rename_matched_by_isin(self):
        plan = self.sync([self.base_rows[0], row("FIRSTHOLDCO", "NGFBNH000009")])
        self.fbnh.refresh_from_db()
        self.assertEqual(self.fbnh.symbol, "FIRSTHOLDCO")
        self.assertEqual(self.fbnh.previous_symbols, ["FBNH"])
        self.assertEqual(self.fbnh.tv_symbol, "NSENG:FIRSTHOLDCO")
        self.assertEqual(
            self.kinds(plan),
            [(StockChange.RENAMED, StockChange.APPLIED, "FIRSTHOLDCO")],
        )

    def test_rename_keeps_old_tradingview_ticker_until_tradingview_renames(self):
        rows = [self.base_rows[0], row("FIRSTHOLDCO", "NGFBNH000009", tradingview=False)]
        plan = ngx_sync.build_plan(rows, tv_tickers={"ACCESSCORP", "FBNH"})
        ngx_sync.apply_plan(plan, StockSyncRun.objects.create(applied=True))
        self.fbnh.refresh_from_db()
        self.assertEqual(self.fbnh.symbol, "FIRSTHOLDCO")
        self.assertEqual(self.fbnh.tv_symbol, "NSENG:FBNH")

    def test_new_listing(self):
        plan = self.sync([*self.base_rows, row("ARADEL", "NGARADEL0004")])
        stock = Stock.objects.get(symbol="ARADEL")
        self.assertTrue(stock.active)
        self.assertEqual(stock.tv_symbol, "NSENG:ARADEL")
        change = StockChange.objects.get(kind=StockChange.LISTED)
        self.assertEqual(change.stock, stock)
        self.assertEqual(len(plan.changes), 1)

    def test_new_listing_without_tradingview_has_no_tv_symbol(self):
        self.sync([*self.base_rows, row("AVAIF", "NGAVAIF00001", tradingview=False)])
        self.assertIsNone(Stock.objects.get(symbol="AVAIF").tv_symbol)

    def test_delisted_only_on_second_missing_run(self):
        plan = self.sync([self.base_rows[0]])
        self.fbnh.refresh_from_db()
        self.assertTrue(self.fbnh.active)
        self.assertEqual(self.fbnh.ngx_missing_runs, 1)
        self.assertEqual(plan.missing_once, ["FBNH"])

        plan = self.sync([self.base_rows[0]])
        self.fbnh.refresh_from_db()
        self.assertFalse(self.fbnh.active)
        self.assertIsNone(self.fbnh.tv_symbol)
        self.assertEqual(
            self.kinds(plan), [(StockChange.DELISTED, StockChange.APPLIED, "FBNH")]
        )

    def test_reappearing_resets_missing_count(self):
        self.sync([self.base_rows[0]])
        self.sync(self.base_rows)
        self.fbnh.refresh_from_db()
        self.assertEqual(self.fbnh.ngx_missing_runs, 0)

    def test_delisting_with_open_positions_waits_for_approval(self):
        self.sync([self.base_rows[0]])
        with mock.patch.object(
            ngx_sync, "holders", return_value={"execution.Position": 3}
        ):
            plan = self.sync([self.base_rows[0]])
        self.fbnh.refresh_from_db()
        self.assertTrue(self.fbnh.active)
        change = StockChange.objects.get(kind=StockChange.DELISTED)
        self.assertEqual(change.status, StockChange.PENDING)
        self.assertEqual(change.holders, {"execution.Position": 3})

        # A pending delisting is not proposed again on the next run
        plan = self.sync([self.base_rows[0]])
        self.assertEqual(plan.changes, [])

    def test_admin_approve_deactivates_pending_delisting(self):
        from django.contrib.admin.sites import site
        from django.contrib.auth import get_user_model
        from django.test import RequestFactory

        from portfolio.admin import StockChangeAdmin

        change = StockChange.objects.create(
            run=StockSyncRun.objects.create(applied=True),
            stock=self.fbnh,
            kind=StockChange.DELISTED,
            status=StockChange.PENDING,
            symbol="FBNH",
        )
        request = RequestFactory().post("/")
        request.user = get_user_model().objects.create(email="ops@example.com")
        model_admin = StockChangeAdmin(StockChange, site)
        with mock.patch.object(model_admin, "message_user"):
            model_admin.approve(request, StockChange.objects.all())
        self.fbnh.refresh_from_db()
        change.refresh_from_db()
        self.assertFalse(self.fbnh.active)
        self.assertEqual(change.status, StockChange.APPROVED)
        self.assertEqual(change.resolved_by, request.user)

    def test_too_many_delistings_abort(self):
        for i in range(3):
            Stock.objects.create(symbol=f"X{i}", isin=f"NGX{i:09d}", ngx_missing_runs=1)
        with self.assertRaises(ngx_sync.SyncAborted):
            ngx_sync.build_plan(self.base_rows, max_delists=2)
        self.assertEqual(Stock.objects.filter(active=False).count(), 0)

    def test_ticker_reused_by_other_isin_is_left_for_review(self):
        plan = self.sync([self.base_rows[0], row("FBNH", "NGOTHER00001")])
        self.fbnh.refresh_from_db()
        self.assertEqual(self.fbnh.isin, "NGFBNH000009")
        self.assertTrue(self.fbnh.active)
        self.assertEqual(
            self.kinds(plan), [(StockChange.REVIEW, StockChange.PENDING, "FBNH")]
        )
        self.assertEqual(Stock.objects.filter(symbol="FBNH").count(), 1)

        # The same review is not logged twice
        plan = self.sync([self.base_rows[0], row("FBNH", "NGOTHER00001")])
        self.assertEqual(plan.changes, [])

    def test_possible_successor_is_flagged(self):
        Stock.objects.create(
            symbol="CHIPLC", company="CONSOLIDATED HALLMARK INSURANCE PLC",
            isin="NGCHIPLC0001",
        )
        plan = self.sync(
            [
                *self.base_rows,
                row("CONHALLPLC", "NGCONHALL001", "CONSOLIDATED HALLMARK HOLDINGS PLC"),
            ]
        )
        review = [c for c in plan.changes if c.kind == StockChange.REVIEW]
        self.assertEqual(len(review), 1)
        self.assertEqual(review[0].new_value, "CHIPLC")

    def test_status_flag_change(self):
        plan = self.sync([row("ACCESSCORP", "NGACCESS0005", ngx_status="MRF"), self.base_rows[1]])
        self.access.refresh_from_db()
        self.assertEqual(self.access.ngx_status, "MRF")
        self.assertEqual(
            self.kinds(plan),
            [(StockChange.STATUS_CHANGED, StockChange.APPLIED, "ACCESSCORP")],
        )

    def test_unknown_tradingview_keeps_tv_symbol(self):
        rows = [dict(r, tradingview=None) for r in self.base_rows]
        self.sync(rows)
        self.access.refresh_from_db()
        self.assertEqual(self.access.tv_symbol, "NSENG:ACCESSCORP")

    def test_short_ngx_response_aborts(self):
        raw = [{"Symbol": "ACCESSCORP", "InternationSecIN": "NGACCESS0005"}]
        with self.assertRaises(ngx_sync.SyncAborted):
            ngx_sync.run_sync(apply=True, raw=raw, notify=False)
        self.assertTrue(StockSyncRun.objects.get().error)
        self.assertEqual(Stock.objects.filter(active=False).count(), 0)

    def ngx_raw(self, *rows):
        return [
            {"Symbol": r["symbol"], "InternationSecIN": r["isin"], "CompanyName": r["company"]}
            for r in rows
        ]

    def test_aborted_run_emails_dev5(self):
        with self.assertRaises(ngx_sync.SyncAborted):
            ngx_sync.run_sync(apply=True, raw=self.ngx_raw(self.base_rows[0]))
        self.assertEqual(mail.outbox[0].subject, "NGX stock sync aborted")
        self.assertIn("dev5.ft9ja@gmail.com", mail.outbox[0].to)

    def test_auto_applied_changes_email_dev5(self):
        raw = self.ngx_raw(*self.base_rows, row("ARADEL", "NGARADEL0004"))
        with mock.patch.object(ngx_sync, "MIN_LISTED", 1):
            ngx_sync.run_sync(apply=True, raw=raw, followups=False)
        self.assertEqual(mail.outbox[0].subject, "NGX stock sync: changes applied")
        self.assertIn("dev5.ft9ja@gmail.com", mail.outbox[0].to)
        self.assertIn("ARADEL", mail.outbox[0].body)

    def test_pending_changes_email_dev5_as_action_needed(self):
        raw = self.ngx_raw(self.base_rows[0], row("FBNH", "NGOTHER00001"))
        with mock.patch.object(ngx_sync, "MIN_LISTED", 1):
            ngx_sync.run_sync(apply=True, raw=raw, followups=False)
        self.assertEqual(mail.outbox[0].subject, "NGX stock sync: action needed")
        self.assertIn("dev5.ft9ja@gmail.com", mail.outbox[0].to)
        self.assertIn("Django admin", mail.outbox[0].body)

    def test_parse_status(self):
        self.assertEqual(ngx_sync.parse_status("[MRF],"), "MRF")
        self.assertEqual(ngx_sync.parse_status("[MRF],[BLS],"), "MRF,BLS")
        self.assertIsNone(ngx_sync.parse_status(","))
        self.assertEqual(ngx_sync.parse_status("[MRF],[BLS],[RST],"), "MRF,BLS")
