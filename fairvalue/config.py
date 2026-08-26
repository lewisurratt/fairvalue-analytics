from __future__ import annotations

from pathlib import Path

APP_NAME = "FairValue Analytics"
APP_TAGLINE = "Trade decisions, turned into durable edge."

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_ROOT = ROOT_DIR / "data"
DEMO_DATA_DIR = DATA_ROOT / "demo"
PRIVATE_DATA_DIR = DATA_ROOT / "private"
# Kept as the local-first default for scripts and backward-compatible imports.
DATA_DIR = PRIVATE_DATA_DIR

ACCOUNT_STATUSES = ["Eval", "Funded", "Breached", "Passed", "Closed"]
ACCOUNT_TYPES = ["Evaluation", "Performance", "Live", "Sim"]
LEDGER_TYPES = ["Payout", "Expense"]
JOURNAL_SESSIONS = ["Pre-market", "New York AM", "New York PM", "London", "Asia", "Other"]
