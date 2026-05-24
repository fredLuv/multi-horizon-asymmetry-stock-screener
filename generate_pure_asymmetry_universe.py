#!/usr/bin/env python3
# generate_pure_asymmetry_universe.py
# Screens the entire 3,371 stock universe strictly for Asymmetry.
# Bypasses all P/FCF, PE, or EV valuation filters, and ranks the Top 50.

import os
import time
import pandas as pd
import numpy as np
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor

# Define absolute paths
artifacts_dir = "/Users/fred/.gemini/antigravity/brain/9b6cd57c-1c8b-4d89-9e6b-8272e3a36d04"
prices_csv_path = 'outputs/daily_prices.csv'

def get_ticker_metadata(ticker_symbol):
    """
    Queries yfinance to get sector, industry, and company name.
    """
    ticker = yf.Ticker(ticker_symbol)
    for attempt in range(2):
        try:
            info = ticker.info
            long_name = info.get('longName', ticker_symbol)
            sector = info.get('sector', 'N/A')
            industry = info.get('industry', 'N/A')
            return {
                'Ticker': ticker_symbol,
                'Company': long_name,
                'Sector': sector,
                'Industry': industry
            }
        except Exception:
            time.sleep(0.4)
            
    return {
        'Ticker': ticker_symbol,
        'Company': ticker_symbol,
        'Sector': 'N/A',
        'Industry': 'N/A'
    }

def main():
    print("="*120)
    print("              PURE ASYMMETRY UNIVERSE SCREENER (3,371 STOCKS - TOP 50 LEADERBOARD)")
    print("="*120)
    
    if not os.path.exists(prices_csv_path):
        print("[!] daily_prices.csv not found. Run screener first.")
        return
        
    print("[1/4] Loading adjusted daily price series...")
    prices_df = pd.read_csv(prices_csv_path, index_col=0, parse_dates=True)
    
    print("\n[2/4] Scoring rolling asymmetry for all stocks (Disregarding FCF/PE Valuation Ratios)...")
    results = []
    
    for ticker in prices_df.columns:
        try:
            series = prices_df[ticker].dropna()
            if len(series) < 504:
                continue
                
            last_price = float(series.iloc[-1])
            if last_price < 1.0:
                continue
                
            ret_3m = series.pct_change(63).dropna().values
            if len(ret_3m) < 252:
                continue
                
            p10 = float(np.percentile(ret_3m, 10))
            p50 = float(np.percentile(ret_3m, 50))
            p90 = float(np.percentile(ret_3m, 90))
            
            # Mathematically pure asymmetry ratio calculation
            downside = abs(min(p10, 0.0))
            upside = max(p90, 0.0)
            
            if downside == 0.0 and upside > 0.0:
                tail_ratio = float("inf")
            elif downside == 0.0 and upside == 0.0:
                tail_ratio = 0.0
            else:
                tail_ratio = upside / downside
                
            # User Asymmetric Score (UAS) = (1 + P50) * Tail_Ratio
            uas_score = (1.0 + p50) * tail_ratio
            
            results.append({
                'Ticker': ticker,
                'LastPrice': last_price,
                'P10_3M': p10,
                'P50_Median': p50,
                'P90_3M': p90,
                'Tail_Ratio': tail_ratio,
                'UAS_Score': uas_score
            })
        except Exception:
            continue
            
    df_raw = pd.DataFrame(results)
    print(f"  [+] Finished scoring {len(df_raw)} liquid stocks.")
    
    # Sort strictly by Tail_Ratio descending with P50_Median as tie-breaker for infinite asymmetry
    df_sorted = df_raw.sort_values(by=['Tail_Ratio', 'P50_Median'], ascending=[False, False])
    
    # Fetch details for MU and WDC specifically to show where they rank in the whole universe!
    mu_row = df_sorted[df_sorted['Ticker'] == 'MU']
    wdc_row = df_sorted[df_sorted['Ticker'] == 'WDC']
    
    # Extract absolute Top 50
    df_top50 = df_sorted.head(50)
    top_tickers = df_top50['Ticker'].tolist()
    
    print("\n[3/4] Performing multi-threaded metadata lookups for the top leaders...")
    metadata = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        meta_results = executor.map(get_ticker_metadata, top_tickers)
        for r in meta_results:
            metadata.append(r)
            
    df_meta = pd.DataFrame(metadata)
    df_merged = pd.merge(df_top50, df_meta, on='Ticker')
    
    # Ensure it remains perfectly sorted
    df_merged = df_merged.sort_values(by=['Tail_Ratio', 'P50_Median'], ascending=[False, False])
    
    print("\n" + "="*125)
    print("                         MASTER PURE ASYMMETRY LEADERBOARD (TOP 50 RANKED)")
    print("="*125)
    
    df_display = df_merged.copy()
    df_display['LastPrice'] = df_display['LastPrice'].map(lambda x: f"${x:.2f}")
    df_display['Tail_Ratio_Disp'] = df_display['Tail_Ratio'].map(lambda x: "infx" if x == float("inf") else f"{x:.2f}x")
    df_display['UAS_Score_Disp'] = df_display['UAS_Score'].map(lambda x: "inf" if x == float("inf") else f"{x:.4f}")
    df_display['P50_Median'] = df_display['P50_Median'].map(lambda x: f"{x*100:+.2f}%")
    df_display['P10_3M'] = df_display['P10_3M'].map(lambda x: f"{x*100:+.2f}%")
    
    print(df_display[['Ticker', 'Company', 'LastPrice', 'P10_3M', 'P50_Median', 'Tail_Ratio_Disp', 'UAS_Score_Disp']].to_string(index=False))
    print("="*125)
    
    # Print MU and WDC rankings specifically
    print("\n" + "-"*80)
    print("                  DIAGNOSTIC SEARCH FOR MEMORY SEMICONDUCTORS")
    print("-"*80)
    for ticker_row, name in [(mu_row, "Micron (MU)"), (wdc_row, "Western Digital (WDC)")]:
        if not ticker_row.empty:
            idx = int(ticker_row.index[0])
            # Find its rank in the sorted dataframe
            rank = df_sorted.index.get_loc(idx) + 1
            row = ticker_row.iloc[0]
            print(f"{name}: Rank #{rank} | P10: {row['P10_3M']*100:+.2f}% | P50: {row['P50_Median']*100:+.2f}% | Tail Ratio: {row['Tail_Ratio']:.2f}x | UAS: {row['UAS_Score']:.4f}")
        else:
            print(f"{name} not found in active cached database.")
    print("-"*80 + "\n")
    
    # Save the output CSV
    output_csv = 'outputs/pure_asymmetric_breakout_stocks.csv'
    df_sorted.to_csv(output_csv, index=False)
    print(f"  [+] Saved complete pure asymmetry rankings to: {output_csv}")
    
    # Save directly to brain space
    df_sorted.to_csv(os.path.join(artifacts_dir, 'pure_asymmetric_breakout_stocks.csv'), index=False)
    print(f"  [+] Synced master sheet to brain space.")
    
    # Generate standalone report
    report_path = os.path.join(artifacts_dir, 'pure_asymmetry_report.md')
    with open(report_path, 'w') as f:
        f.write("# Pure Asymmetry Universe: Absolute Top 50 Leaders\n\n")
        f.write("> [!IMPORTANT]\n")
        f.write("> This screen ranks the entire US common stock universe strictly by your mathematically pure **Tail Asymmetry Ratio** ")
        f.write("and expected **Median Return ($P_{50}$)** tie-breaker, bypassing any fundamental valuation ratio limits.\n\n")
        
        f.write("| Rank | Ticker | Company | Sector / Industry | Last Price | P10 (Downside) | P50 (Median) | Tail Ratio | UAS Score |\n")
        f.write("| :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |\n")
        
        for rank, (_, row) in enumerate(df_merged.iterrows(), 1):
            tail_disp = "infx" if row['Tail_Ratio'] == float("inf") else f"{row['Tail_Ratio']:.2f}x"
            uas_disp = "inf" if row['UAS_Score'] == float("inf") else f"{row['UAS_Score']:.4f}"
            f.write(f"| #{rank} | **{row['Ticker']}** | {row['Company']} | {row['Sector']} / {row['Industry']} | ${row['LastPrice']:.2f} | **{row['P10_3M']*100:+.2f}%** | +{row['P50_Median']*100:.2f}% | **{tail_disp}** | **{uas_disp}** |\n")
            
        f.write("\n## Cyclical Memory Semiconductors Position Analysis\n\n")
        if not mu_row.empty:
            row_mu = mu_row.iloc[0]
            rank_mu = df_sorted.index.get_loc(mu_row.index[0]) + 1
            f.write(f"* **Micron (MU)** ranks **#{rank_mu}** in the entire 3,371-stock universe, with a **{row_mu['Tail_Ratio']:.2f}x Tail Ratio** and a median return of **+{row_mu['P50_Median']*100:.2f}%**.\n")
        if not wdc_row.empty:
            row_wdc = wdc_row.iloc[0]
            rank_wdc = df_sorted.index.get_loc(wdc_row.index[0]) + 1
            f.write(f"* **Western Digital (WDC)** ranks **#{rank_wdc}** in the entire 3,371-stock universe, with a **{row_wdc['Tail_Ratio']:.2f}x Tail Ratio** and a median return of **+{row_wdc['P50_Median']*100:.2f}%**.\n")
            
    print(f"  [+] Generated Pure Asymmetry Report at: {report_path}")

if __name__ == "__main__":
    main()
