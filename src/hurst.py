"""
Hurst Exponent Calculator
=========================
Berechnet den Hurst-Exponenten für ein gegebenes Ticker-Symbol
mittels R/S-Analyse und Detrended Fluctuation Analysis (DFA).

Abhängigkeiten:
    pip install -r requirements.txt

Verwendung:
    python src/hurst.py --ticker USO --period 2y
    python src/hurst.py --ticker SPY --start 2022-01-01 --end 2024-12-31
    python src/hurst.py --ticker MA --period 5y --method both
"""

import argparse
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.stats import linregress
from datetime import datetime, timedelta

try:
    import yfinance as yf
except ImportError:
    print("yfinance nicht installiert. Bitte: pip install yfinance")
    sys.exit(1)


# ─────────────────────────────────────────────
# 1. DATEN LADEN UND RETURNS BILDEN
# ─────────────────────────────────────────────

def load_prices(ticker: str, period: str = None, start: str = None, end: str = None) -> pd.Series:
    """Lädt Schlusskurse via yfinance."""
    t = yf.Ticker(ticker)

    # Warnen, wenn nur start oder nur end angegeben wurde
    if (start and not end) or (end and not start):
        print("⚠ --start ohne --end (oder --end ohne --start), "
              "fälle auf period=2y zurück")
        start = end = None

    if start and end:
        df = t.history(start=start, end=end)
    elif period:
        df = t.history(period=period)
    else:
        df = t.history(period="2y")

    if df.empty:
        raise ValueError(f"Keine Daten für '{ticker}' gefunden.")

    prices = df["Close"].dropna()
    print(f"\n✓ {ticker}: {len(prices)} Datenpunkte "
          f"({prices.index[0].date()} → {prices.index[-1].date()})")
    return prices


def log_returns(prices: pd.Series) -> np.ndarray:
    return np.log(prices / prices.shift(1)).dropna().values


# ─────────────────────────────────────────────
# 2. R/S-ANALYSE (KLASSISCH NACH HURST)
# ─────────────────────────────────────────────

def compute_rs(series: np.ndarray, n: int) -> float:
    """Berechnet den R/S-Wert für ein Segment der Länge n."""
    n_segments = len(series) // n
    if n_segments == 0:
        return np.nan

    rs_values = []
    for i in range(n_segments):
        seg = series[i * n: (i + 1) * n]
        mean = np.mean(seg)
        deviation = np.cumsum(seg - mean)
        r = np.max(deviation) - np.min(deviation)
        s = np.std(seg, ddof=1)
        if s > 0:
            rs_values.append(r / s)

    return np.mean(rs_values) if rs_values else np.nan


def hurst_rs(series: np.ndarray, min_window: int = 10) -> tuple:
    """
    Hurst-Exponent via R/S-Analyse (Rescaled Range).
    Gibt (H, n_list, rs_list, slope_info) zurück.
    """
    n = len(series)
    # Fenstergrößen: logarithmisch verteilt zwischen min_window und n/4
    max_window = n // 4
    windows = np.unique(
        np.logspace(np.log10(min_window), np.log10(max_window), num=30).astype(int)
    )
    windows = windows[windows >= min_window]

    rs_list = []
    valid_windows = []
    for w in windows:
        rs = compute_rs(series, w)
        if not np.isnan(rs) and rs > 0:
            rs_list.append(rs)
            valid_windows.append(w)

    if len(valid_windows) < 5:
        raise ValueError("Zu wenige Datenpunkte für R/S-Analyse.")

    log_n = np.log10(valid_windows)
    log_rs = np.log10(rs_list)
    slope, intercept, r_value, p_value, std_err = linregress(log_n, log_rs)

    return slope, valid_windows, rs_list, (slope, intercept, r_value**2, std_err)


# ─────────────────────────────────────────────
# 3. DFA - DETRENDED FLUCTUATION ANALYSIS
# ─────────────────────────────────────────────

def hurst_dfa(series: np.ndarray, min_window: int = 10) -> tuple:
    """
    Hurst-Exponent via Detrended Fluctuation Analysis (DFA).
    Robuster als R/S bei nicht-stationären Reihen.
    """
    n = len(series)
    # Kumulierte Abweichung vom Mittelwert.
    y = np.cumsum(series - np.mean(series))

    max_window = n // 4
    windows = np.unique(
        np.logspace(np.log10(min_window), np.log10(max_window), num=30).astype(int)
    )
    windows = windows[windows >= min_window]

    fluctuations = []
    valid_windows = []

    for w in windows:
        n_segments = n // w
        if n_segments < 2:
            continue

        f_list = []
        for i in range(n_segments):
            seg = y[i * w: (i + 1) * w]
            x = np.arange(w)
            # Linearer Trend innerhalb des Segments (DFA-1).
            coeffs = np.polyfit(x, seg, 1)
            trend = np.polyval(coeffs, x)
            f_list.append(np.sqrt(np.mean((seg - trend) ** 2)))

        if f_list:
            fluctuation = np.mean(f_list)
            if fluctuation > 1e-10:
                fluctuations.append(fluctuation)
                valid_windows.append(w)

    if len(valid_windows) < 5:
        raise ValueError("Zu wenige Datenpunkte für DFA.")

    log_n = np.log10(valid_windows)
    log_f = np.log10(fluctuations)
    slope, intercept, r_value, p_value, std_err = linregress(log_n, log_f)

    return slope, valid_windows, fluctuations, (slope, intercept, r_value**2, std_err)


# ─────────────────────────────────────────────
# 4. INTERPRETATION DER H-WERTE
# ─────────────────────────────────────────────

def interpret_hurst(h: float) -> tuple:
    """Gibt (Label, Farbe, Beschreibung) zurück."""
    if h < 0.40:
        return "Stark Mean-Reverting", "#e74c3c", \
               "Starke Rückkehr zum Mittel → ideales Umfeld für Stillhalter / Short-Vol"
    elif h < 0.48:
        return "Leicht Mean-Reverting", "#e67e22", \
               "Tendenz zur Rückkehr → günstig für Stillhalter-Strategien"
    elif h < 0.52:
        return "Random Walk", "#f1c40f", \
               "Kein klares Gedächtnis → neutrales Umfeld"
    elif h < 0.60:
        return "Leicht Trending", "#2ecc71", \
               "Schwache Persistenz → Trend Following leicht begünstigt"
    else:
        return "Stark Trending", "#27ae60", \
               "Starke Persistenz → Trend Following begünstigt, Stillhalter erhöhtes Risiko"


def rolling_hurst(series: np.ndarray, window: int = 252, step: int = 21) -> tuple:
    """Berechnet den rollierenden Hurst-Exponenten (R/S) über gleitende Fenster."""
    positions = []
    h_values = []
    for i in range(0, len(series) - window, step):
        seg = series[i: i + window]
        try:
            h, _, _, _ = hurst_rs(seg)
            h_values.append(h)
            positions.append(i + window)
        except Exception:
            pass
    return positions, h_values


# ─────────────────────────────────────────────
# 5. VISUALISIERUNG UND EXPORT
# ─────────────────────────────────────────────

def plot_results(ticker, prices, returns, results: dict, rolling: dict = None):
    """Erstellt ein 4-Panel-Dashboard."""
    fig = plt.figure(figsize=(16, 12))
    fig.patch.set_facecolor("#0d1117")
    gs = gridspec.GridSpec(2, 2, hspace=0.45, wspace=0.35)

    COLORS = {
        "bg":    "#0d1117",
        "panel": "#161b22",
        "text":  "#e6edf3",
        "grid":  "#21262d",
        "rs":    "#58a6ff",
        "dfa":   "#3fb950",
        "price": "#f78166",
        "roll_252": "#d2a8ff",
        "roll_126": "#79c0ff",
        "roll_63":  "#ffa657",
    }

    def style_ax(ax, title):
        ax.set_facecolor(COLORS["panel"])
        ax.tick_params(colors=COLORS["text"], labelsize=9)
        ax.xaxis.label.set_color(COLORS["text"])
        ax.yaxis.label.set_color(COLORS["text"])
        ax.title.set_color(COLORS["text"])
        ax.set_title(title, fontsize=11, fontweight="bold", pad=10)
        for spine in ax.spines.values():
            spine.set_edgecolor(COLORS["grid"])
        ax.grid(color=COLORS["grid"], linestyle="--", linewidth=0.5, alpha=0.7)

    # ── Panel 1: Kursverlauf ──────────────────
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(prices.index, prices.values, color=COLORS["price"], linewidth=1.0)
    ax1.fill_between(prices.index, prices.values,
                     alpha=0.15, color=COLORS["price"])
    style_ax(ax1, f"{ticker} – Schlusskurs")
    ax1.set_ylabel("Preis (USD)")

    # ── Panel 2: R/S Log-Log Plot ─────────────
    ax2 = fig.add_subplot(gs[0, 1])
    if "rs" in results:
        h_rs, windows_rs, rs_vals, info_rs = results["rs"]
        log_n = np.log10(windows_rs)
        log_rs = np.log10(rs_vals)
        ax2.scatter(log_n, log_rs, color=COLORS["rs"], s=20, zorder=3, label="R/S Werte")
        fit_y = np.array(log_n) * info_rs[0] + info_rs[1]
        ax2.plot(log_n, fit_y, color=COLORS["rs"], linewidth=1.5, linestyle="--",
                 label=f"H = {h_rs:.4f}  (R² = {info_rs[2]:.3f})")
        style_ax(ax2, "R/S-Analyse (Log-Log)")
        ax2.set_xlabel("log₁₀(n)")
        ax2.set_ylabel("log₁₀(R/S)")
        ax2.legend(fontsize=9, facecolor=COLORS["panel"],
                   labelcolor=COLORS["text"], framealpha=0.8)

    # ── Panel 3: DFA Log-Log Plot ─────────────
    ax3 = fig.add_subplot(gs[1, 0])
    if "dfa" in results:
        h_dfa, windows_dfa, fluct, info_dfa = results["dfa"]
        log_n = np.log10(windows_dfa)
        log_f = np.log10(fluct)
        ax3.scatter(log_n, log_f, color=COLORS["dfa"], s=20, zorder=3, label="DFA Werte")
        fit_y = np.array(log_n) * info_dfa[0] + info_dfa[1]
        ax3.plot(log_n, fit_y, color=COLORS["dfa"], linewidth=1.5, linestyle="--",
                 label=f"H = {h_dfa:.4f}  (R² = {info_dfa[2]:.3f})")
        style_ax(ax3, "DFA – Detrended Fluctuation Analysis (Log-Log)")
        ax3.set_xlabel("log₁₀(n)")
        ax3.set_ylabel("log₁₀(F(n))")
        ax3.legend(fontsize=9, facecolor=COLORS["panel"],
                   labelcolor=COLORS["text"], framealpha=0.8)

    # ── Panel 4: Rollierender Hurst ───────────
    ax4 = fig.add_subplot(gs[1, 1])
    if rolling and any(data["positions"] for data in rolling.values()):
        idx = prices.index
        ax4.axhline(0.5, color=COLORS["text"], linewidth=0.8,
                    linestyle=":", alpha=0.6, label="H = 0.5 (Random Walk)")
        ax4.axhspan(0.0, 0.5, alpha=0.08, color="#e74c3c", label="Mean-Reverting Zone")
        ax4.axhspan(0.5, 1.0, alpha=0.08, color="#2ecc71", label="Trending Zone")

        for window, color in ((252, COLORS["roll_252"]), (126, COLORS["roll_126"]), (63, COLORS["roll_63"])):
            data = rolling.get(window)
            if not data or not data["positions"]:
                continue
            roll_dates = [idx[min(p, len(idx) - 1)] for p in data["positions"]]
            ax4.plot(roll_dates, data["h_values"], color=color,
                     linewidth=1.2, label=f"Rolling H ({window}d)")

        ax4.set_ylim(0.0, 1.0)
        style_ax(ax4, "Rollierender Hurst-Exponent (R/S, 63/126/252 Tage)")
        ax4.set_ylabel("H")
        ax4.legend(fontsize=8, facecolor=COLORS["panel"],
                   labelcolor=COLORS["text"], framealpha=0.8)
    else:
        ax4.text(0.5, 0.5, "Zu wenige Daten\nfür Rolling-Analyse",
                 ha="center", va="center", color=COLORS["text"],
                 fontsize=11, transform=ax4.transAxes)
        style_ax(ax4, "Rollierender Hurst-Exponent")

    # ── Titel ─────────────────────────────────
    # Durchschnittlichen H-Wert über alle berechneten Methoden bilden.
    h_vals = [v[0] for v in results.values()]
    h_avg = np.mean(h_vals)
    label, color, desc = interpret_hurst(h_avg)

    fig.suptitle(
        f"Hurst-Exponent Analyse: {ticker}   |   H ≈ {h_avg:.4f}   [{label}]",
        fontsize=14, fontweight="bold",
        color=color, y=0.98
    )

    plt.savefig(f"hurst_{ticker}.png", dpi=150, bbox_inches="tight",
                facecolor=COLORS["bg"])
    print(f"\n✓ Chart gespeichert: hurst_{ticker}.png")
    plt.show()


# ─────────────────────────────────────────────
# 6. REPORT FÜR DIE KONSOLE
# ─────────────────────────────────────────────

def print_report(ticker: str, results: dict, n_samples: int):
    """Gibt eine formatierte Zusammenfassung aus."""
    line = "─" * 55

    print(f"\n{line}")
    print(f"  HURST-EXPONENT ANALYSE  │  {ticker}")
    print(f"{line}")
    print(f"  Datenpunkte (Returns):  {n_samples}")
    print()

    for method, (h, *_, info) in results.items():
        label, color, desc = interpret_hurst(h)
        method_name = "R/S-Analyse    " if method == "rs" else "DFA            "
        print(f"  {method_name} H = {h:.4f}   R² = {info[2]:.3f}   StdErr = {info[3]:.4f}")
        print(f"  {'':15} → {label}")
        print(f"  {'':15}   {desc}")
        print()

    if len(results) > 1:
        h_avg = np.mean([v[0] for v in results.values()])
        label, _, desc = interpret_hurst(h_avg)
        print(f"  DURCHSCHNITT     H = {h_avg:.4f}")
        print(f"  → {label}")
        print(f"  → {desc}")

    print(f"\n{line}")
    print("  INTERPRETATION FÜR STILLHALTER-STRATEGIEN")
    print(f"{line}")

    h_ref = np.mean([v[0] for v in results.values()])
    if h_ref < 0.48:
        print("  ✅ Günstiges Umfeld für Short-Vol / Stillhalter:")
        print("     Geringe Trendpersistenz → Prämien können gut vereinnahmt werden.")
        print("     Iron Condors / Short Strangles haben strukturellen Vorteil.")
    elif h_ref < 0.55:
        print("  ⚠️  Neutrales Umfeld:")
        print("     Weder klarer Trend noch starke Mean-Reversion.")
        print("     Enge Spreads und konservative Strikes empfohlen.")
    else:
        print("  ❌ Erhöhtes Risiko für Stillhalter:")
        print("     Starke Trendpersistenz → eine Seite des Strangles")
        print("     kann tief ITM laufen (wie bei USO März 2026).")
        print("     Defensivere Positionierung oder Trend-Filter einsetzen.")

    print(f"{line}\n")


# ─────────────────────────────────────────────
# 7. CLI UND HAUPTPROGRAMM
# ─────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Hurst-Exponent Kalkulator für Finanzzeitreihen",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python src/hurst.py --ticker USO --period 2y
  python src/hurst.py --ticker SPY --start 2020-01-01 --end 2024-12-31
  python src/hurst.py --ticker MA --period 5y --method dfa --no-plot
        """
    )
    parser.add_argument("--ticker",  type=str, required=True, help="Ticker-Symbol (z.B. SPY, USO, MA)")
    parser.add_argument("--period",  type=str, default="2y",
                        help="Zeitraum: 1mo 3mo 6mo 1y 2y 5y 10y ytd max (Standard: 2y)")
    parser.add_argument("--start",   type=str, default=None,
                        help="Startdatum YYYY-MM-DD (optional; zusammen mit --end verwendet)")
    parser.add_argument("--end",     type=str, default=None,
                        help="Enddatum YYYY-MM-DD (optional; zusammen mit --start verwendet)")
    parser.add_argument("--method",  type=str, default="both",
                        choices=["rs", "dfa", "both"], help="Berechnungsmethode (Standard: both)")
    parser.add_argument("--no-rolling", action="store_true",
                        help="Rollierenden Hurst deaktivieren (standardmäßig aktiv)")
    parser.add_argument("--no-plot", action="store_true",
                        help="Kein Chart anzeigen oder speichern")
    parser.add_argument("--min-window", type=int, default=10,
                        help="Minimale Fenstergröße für die Regression (Standard: 10)")
    return parser.parse_args()


def main():
    args = parse_args()

    # Schlusskurse laden und daraus Log-Returns berechnen.
    prices = load_prices(
        ticker=args.ticker.upper(),
        period=args.period if not (args.start and args.end) else None,
        start=args.start,
        end=args.end
    )

    returns = log_returns(prices)

    if len(returns) < 50:
        print("❌ Fehler: Mindestens 50 Datenpunkte erforderlich.")
        sys.exit(1)

    # Gewählte Hurst-Methoden berechnen.
    results = {}

    if args.method in ("rs", "both"):
        print("  Berechne R/S-Analyse...")
        try:
            h, windows, rs_vals, info = hurst_rs(returns, min_window=args.min_window)
            results["rs"] = (h, windows, rs_vals, info)
            print(f"  R/S  → H = {h:.4f}")
        except Exception as e:
            print(f"  R/S fehlgeschlagen: {e}")

    if args.method in ("dfa", "both"):
        print("  Berechne DFA...")
        try:
            h, windows, fluct, info = hurst_dfa(returns, min_window=args.min_window)
            results["dfa"] = (h, windows, fluct, info)
            print(f"  DFA  → H = {h:.4f}")
        except Exception as e:
            print(f"  DFA fehlgeschlagen: {e}")

    if not results:
        print("❌ Keine Berechnungen erfolgreich.")
        sys.exit(1)

    # Konsolenreport ausgeben.
    print_report(args.ticker.upper(), results, len(returns))

    # Rolling Hurst ist standardmäßig aktiv und kann per --no-rolling deaktiviert werden.
    rolling_data = {window: {"positions": [], "h_values": []} for window in (252, 126, 63)}
    if not args.no_rolling:
        for window in (252, 126, 63):
            if len(returns) < window:
                continue

            print(f"  Berechne rollierenden Hurst ({window}d)...")
            positions, h_vals = rolling_hurst(returns, window=window, step=21)
            rolling_data[window] = {"positions": positions, "h_values": h_vals}

            if h_vals:
                print(
                    f"  Rolling H {window}d: min={min(h_vals):.3f}  max={max(h_vals):.3f}  aktuell={h_vals[-1]:.3f}"
                )

    # Plot nur erzeugen, wenn er nicht explizit deaktiviert wurde.
    if not args.no_plot:
        plot_results(
            ticker=args.ticker.upper(),
            prices=prices,
            returns=returns,
            results=results,
            rolling=rolling_data
        )


if __name__ == "__main__":
    main()
