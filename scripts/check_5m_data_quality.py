"""Quick check for 5m data availability in replay DBs."""
import sqlite3
import sys

def check_db(path):
    print(f"\n=== {path} ===")
    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # List tables
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in c.fetchall()]
        print(f"Tables: {tables}")
        
        # Check candles table for timeframes
        if "candles" in tables:
            c.execute("SELECT DISTINCT timeframe FROM candles")
            timeframes = [r[0] for r in c.fetchall()]
            print(f"Candle timeframes: {timeframes}")
            
            for tf in timeframes:
                c.execute(f"SELECT COUNT(*), MIN(open_time), MAX(open_time) FROM candles WHERE timeframe=?", (tf,))
                row = c.fetchone()
                print(f"  {tf}: {row[0]} bars, {row[1]} to {row[2]}")
        
        # Check aggtrade_buckets
        if "aggtrade_buckets" in tables:
            c.execute("SELECT DISTINCT timeframe FROM aggtrade_buckets")
            agg_tfs = [r[0] for r in c.fetchall()]
            print(f"Aggtrade bucket timeframes: {agg_tfs}")
        
        # Check funding
        if "funding" in tables:
            c.execute("SELECT COUNT(*), MIN(funding_time), MAX(funding_time) FROM funding")
            row = c.fetchone()
            print(f"Funding: {row[0]} rows, {row[1]} to {row[2]}")
        
        # Check open_interest
        if "open_interest" in tables:
            c.execute("SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM open_interest")
            row = c.fetchone()
            print(f"Open interest: {row[0]} rows, {row[1]} to {row[2]}")
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    paths = [
        "research_lab/snapshots/replay-run13-regime-aware-trial-00063.db",
        "research_lab/snapshots/wf-train-001.db",
    ]
    for p in paths:
        check_db(p)
