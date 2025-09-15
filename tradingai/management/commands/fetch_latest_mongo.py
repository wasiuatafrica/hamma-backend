import json
import os

from django.core.management.base import BaseCommand
from pymongo import MongoClient


class Command(BaseCommand):
    help = "Fetch the last items from risk, signal, and merged_live_price_trdv collections and save to JSON files."

    def handle(self, *args, **options):
        # Connect to MongoDB
        client = MongoClient(
            os.environ.get("MONGO_STRING"), tls=True, tlsAllowInvalidCertificates=True
        )

        # Fetch last item from risk_classification
        riskdb = client["stock_classification"]
        risk_collection = riskdb["risk_classification"]
        last_risk = risk_collection.find_one(sort=[("_id", -1)])
        if last_risk and "_id" in last_risk:
            last_risk.pop("_id")
        with open("last_risk.json", "w") as f:
            json.dump(last_risk, f, indent=2)
        self.stdout.write(
            self.style.SUCCESS("Saved last risk_classification to last_risk.json")
        )

        # Fetch last item from signals
        signal_db = client["trade_signals"]
        signal_collection = signal_db["signals"]
        last_signal = signal_collection.find_one(sort=[("_id", -1)])
        if last_signal and "_id" in last_signal:
            last_signal.pop("_id")
        with open("last_signal.json", "w") as f:
            json.dump(last_signal, f, indent=2)
        self.stdout.write(self.style.SUCCESS("Saved last signals to last_signal.json"))

        # Fetch last item from merged_live_price_trdv
        db_merged = client["livelake3"]
        merged_collection = db_merged["merged_live_price_trdv"]
        last_merged = merged_collection.find_one(sort=[("_id", -1)])
        if last_merged and "_id" in last_merged:
            last_merged.pop("_id")
        with open("last_merged_live_price_trdv.json", "w") as f:
            json.dump(last_merged, f, indent=2)
        self.stdout.write(
            self.style.SUCCESS(
                "Saved last merged_live_price_trdv to last_merged_live_price_trdv.json"
            )
        )
