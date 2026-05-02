from backtest.backtest_runner import BacktestConfig, BacktestRunner
from settings import load_settings
import sqlite3

conn = sqlite3.connect('storage/btc_bot.db')
conn.row_factory = sqlite3.Row
s = load_settings(profile='research')
s.strategy.min_sweep_depth_pct = 0.00286
s.strategy.confluence_min = 3.6
print(f"Profile: min_sweep_depth_pct={s.strategy.min_sweep_depth_pct} confluence_min={s.strategy.confluence_min}")
r = BacktestRunner(conn, settings=s).run(
    BacktestConfig(start_date='2022-01-01', end_date='2026-03-28', symbol='BTCUSDT')
)
print(f"trades: {len(r.trades)}")
print(f"pf: {round(r.performance.profit_factor, 2)}")
print(f"sharpe: {round(r.performance.sharpe_ratio, 2)}")
conn.close()
