"""Run the same walk-forward backtest across an official BIST universe."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import sys

from backtest import backtest_ticker
from market_scanner import _latest_official_bulletin


def run(universe: str = "BIST30") -> dict:
    quotes, source, trading_date = _latest_official_bulletin()
    tickers = sorted(t for t, q in quotes.items() if q.get("bist30" if universe == "BIST30" else "bist100"))
    if not tickers:
        raise RuntimeError("Resmî BIST30 evreni boş")
    results = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(backtest_ticker, ticker): ticker for ticker in tickers}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({"ticker": ticker, "error": f"{type(exc).__name__}: {exc}"})
    results.sort(key=lambda item: item["ticker"])
    return {"universe": universe, "asOf": trading_date.isoformat(), "source": source, "count": len(results), "results": results}


if __name__ == "__main__":
    universe = sys.argv[1] if len(sys.argv) > 1 else "BIST30"
    print(json.dumps(run(universe), ensure_ascii=False, indent=2))
