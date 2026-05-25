"""
Batch-Analyse: Hurst für die gesamte Watchlist
"""
import subprocess
import sys
import json
import re

TICKERS = [
    ("MUV2.DE", "Münchener Rück"),
    ("MBG.DE", "Mercedes-Benz"),
    ("SAP.DE", "SAP"),
    ("MSFT", "Microsoft"),
    ("CRM", "Salesforce"),
    ("V", "Visa"),
    ("MA", "Mastercard"),
    ("ADBE", "Adobe"),
    ("SPY", "S&P 500"),
    ("QQQ", "Nasdaq 100"),
    ("USO", "USO (Öl)"),
    ("GLD", "Gold"),
    ("CMCSA", "Comcast"),
]

PERIOD = "2y"

def parse_output(output: str, ticker: str, name: str) -> dict:
    d = {"ticker": ticker, "name": name}
    
    # Datenpunkte
    m = re.search(r"Datenpunkte \(Returns\):?\s*(\d+)", output)
    if m: d["points"] = int(m.group(1))
    
    # R/S H
    m = re.search(r"R/S\s*.+?H\s*=\s*([\d.]+)", output)
    if m: d["rs_h"] = float(m.group(1))
    
    # R/S R²
    m = re.search(r"R/S.*?R²\s*=\s*([\d.]+)", output)
    if m: d["rs_r2"] = float(m.group(1))
    
    # DFA H
    m = re.search(r"DFA\s*.+?H\s*=\s*([\d.]+)", output)
    if m: d["dfa_h"] = float(m.group(1))
    
    # DFA R²
    m = re.search(r"DFA.*?R²\s*=\s*([\d.]+)", output)
    if m: d["dfa_r2"] = float(m.group(1))
    
    # Durchschnitt
    m = re.search(r"DURCHSCHNITT\s*.+?H\s*=\s*([\d.]+)", output)
    if m: d["avg_h"] = float(m.group(1))
    
    # Interpretation
    m = re.search(r"DURCHSCHNITT\s*.+?H\s*=\s*[\d.]+\s*\n\s*→\s*(.+?)(?:\n|$)", output)
    if m: d["interpretation"] = m.group(1).strip()
    else:
        m = re.search(r"→\s*(.+?)(?:\n|$)", output[output.find("DURCHSCHNITT"):])
        if m: d["interpretation"] = m.group(1).strip()
    
    # Rolling Hurst
    m = re.search(r"Rolling H 252d:.*?aktuell=([\d.]+)", output)
    if m: d["h_252d"] = float(m.group(1))
    m = re.search(r"Rolling H 126d:.*?aktuell=([\d.]+)", output)
    if m: d["h_126d"] = float(m.group(1))
    m = re.search(r"Rolling H 63d:.*?aktuell=([\d.]+)", output)
    if m: d["h_63d"] = float(m.group(1))
    
    return d

results = []
for ticker, name in TICKERS:
    print(f"\n{'='*60}")
    print(f"📊 {ticker:10s} — {name}")
    print(f"{'='*60}")
    sys.stdout.flush()
    
    try:
        proc = subprocess.run(
            [sys.executable, "src/hurst.py", "--ticker", ticker, "--period", PERIOD, "--no-plot"],
            capture_output=True, text=True, timeout=90
        )
        output = proc.stdout
        print(output[:1200])
        
        parsed = parse_output(output, ticker, name)
        results.append(parsed)
        print(f"\n>>> PARSED: {json.dumps(parsed, default=str)}")
        
    except Exception as e:
        print(f"❌ Fehler bei {ticker}: {e}")
    
    sys.stdout.flush()

# Final Table
print("\n\n")
print("="*100)
print("📊 HURST-EXPONENT — WATCHLIST-ÜBERSICHT (2-Jahres-Fenster)")
print("="*100)
print(f"{'Ticker':<10} {'Name':<20} {'R/S H':<8} {'DFA H':<8} {'∅ H':<8} {'H 63d':<8} {'H 126d':<8} {'Interpretation'}")
print("-"*100)
for r in results:
    rs = f"{r.get('rs_h','n/a'):.4f}" if 'rs_h' in r else "n/a"
    dfa = f"{r.get('dfa_h','n/a'):.4f}" if 'dfa_h' in r else "n/a"
    avg = f"{r.get('avg_h','n/a'):.4f}" if 'avg_h' in r else "n/a"
    h63 = f"{r.get('h_63d','n/a'):.3f}" if 'h_63d' in r else "n/a"
    h126 = f"{r.get('h_126d','n/a'):.3f}" if 'h_126d' in r else "n/a"
    interp = r.get('interpretation', '')[:50]
    print(f"{r['ticker']:<10} {r['name']:<20} {rs:<8} {dfa:<8} {avg:<8} {h63:<8} {h126:<8} {interp}")
print("="*100)

# Summary
print("\n📋 ZUSAMMENFASSUNG")
for r in results:
    avg = r.get('avg_h', 0)
    if avg < 0.45:
        tag = "🔄 Mean-Reverting"
    elif avg < 0.55:
        tag = "⚪ Random Walk"
    else:
        tag = "📈 Trending"
    
    h63 = r.get('h_63d', 0)
    if isinstance(h63, (int, float)):
        if h63 > 0.55:
            tag63 = "📈 Trending"
        elif h63 < 0.45:
            tag63 = "🔄 Mean-Reverting"
        else:
            tag63 = "⚪ Random Walk"
    else:
        tag63 = "n/a"
    
    print(f"  {r['ticker']:<10}  ∅ H={avg:.4f}  {tag:<25}  H(63d)={h63}  → {tag63}")
