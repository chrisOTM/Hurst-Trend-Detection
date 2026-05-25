# Watchlist Hurst-Analyse — Stand 2026-05-11

Periode: 2 Jahre (2024-05-13 → 2026-05-11)
Methode: R/S + DFA (gemittelt)
Quelle: ~/workspace/Hurst-Trend-Detection (run_batch.py)

## Ergebnisse

| Ticker | ∅ H | R/S H | DFA H | Regime | H 63d | H 126d |
|--------|------|-------|-------|--------|-------|--------|
| MUV2.DE | 0.48 | 0.55 | 0.42 | ⚪ RW | 0.64 📈 | 0.53 |
| MBG.DE  | 0.50 | 0.53 | 0.47 | ⚪ RW | 0.73 📈 | 0.52 |
| SAP.DE  | 0.48 | 0.53 | 0.43 | 🔄 MR | 0.49 ⚪ | 0.57 |
| MSFT    | 0.54 | 0.59 | 0.49 | 📈 Trend | 0.99 📈 | 0.62 |
| CRM     | 0.55 | 0.58 | 0.52 | 📈 Trend | 0.42 🔄 | 0.54 |
| V       | 0.51 | 0.55 | 0.46 | ⚪ RW | 0.32 🔄 | 0.46 |
| MA      | 0.50 | 0.54 | 0.45 | ⚪ RW | 0.52 ⚪ | 0.46 |
| ADBE    | 0.58 | 0.60 | 0.56 | 📈 Trend | 0.37 🔄 | 0.65 |
| SPY     | 0.49 | 0.54 | 0.44 | ⚪ RW | 0.69 📈 | 0.54 |
| QQQ     | 0.52 | 0.57 | 0.46 | ⚪ RW | 0.67 📈 | 0.64 |
| USO     | 0.50 | 0.57 | 0.43 | ⚪ RW | 0.43 🔄 | 0.51 |
| GLD     | 0.51 | 0.56 | 0.46 | ⚪ RW | 0.61 📈 | 0.53 |
| **CMCSA** | **0.51** | **0.54** | **0.48** | ⚪ RW | **0.65 📈** | **0.61** |

## Key Takeaways

1. **2-Jahres-Sicht:** Fast alles Random Walk (∅H ~0.48–0.52) — kein starkes Langzeitgedächtnis
2. **H(63d) zeigt Kurzfrist-Dynamik:** massive Spreads (0.32 – 0.99)
3. **MSFT H 63d = 0.99** — extrem trendstark, Short-Vol-Risiko erhöht
4. **V H 63d = 0.32** — starke Mean-Reversion, ideal für Strangles
5. **ADBE Divergenz:** H(2y)=0.58 Trend, H(63d)=0.37 MR → Regime-Wechsel
6. **CMCSA H 63d = 0.65** — starker Abwärtstrend, kein Einstiegssignal (Fair Value vs. Hurst-Konflikt)

## Batch-Skript

`run_batch.py` im Repo analysiert 13 Ticker in ~3 Minuten. Output: terminal report + strukturierte Daten.