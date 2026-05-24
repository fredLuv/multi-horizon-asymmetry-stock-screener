#!/usr/bin/env python3
# filter_and_check_fcf.py
# Performs a quick fundamental check of Price-to-Future Cash Flow (P/FCF) ratio for the Top 20 stocks.
# Keeps only those with P/FCF < 50, removing overvalued or cash-burning stocks (FCF <= 0 or P/FCF >= 50).

import os
import time
import pandas as pd
import yfinance as yf

# Set pandas printing options
pd.set_option('display.max_columns', 10)
pd.set_option('display.width', 1000)

asymmetric_csv_path = 'outputs/asymmetric_stocks.csv'
BIOTECH_BLACKLIST = {'DRUG', 'ABVX', 'RGC'}

def get_fcf_data_with_retries(ticker_symbol):
    """
    Fetches market cap and free cash flow from yfinance with a robust retry policy to handle rate limits.
    """
    ticker = yf.Ticker(ticker_symbol)
    for attempt in range(3):
        try:
            info = ticker.info
            market_cap = info.get('marketCap')
            fcf = info.get('freeCashflow')
            long_name = info.get('longName', ticker_symbol)
            sector = info.get('sector', 'N/A')
            industry = info.get('industry', 'N/A')
            
            # Fallback if freeCashflow is None but operatingCashflow is available (common for REITs or utilities)
            if fcf is None or fcf == 0:
                ocf = info.get('operatingCashflow')
                if ocf and ocf > 0:
                    # For financial stocks or asset-light firms, CapEx is tiny. Check cashflow statement if possible
                    try:
                        cf_stmt = ticker.cashflow
                        if 'Capital Expenditures' in cf_stmt.index:
                            capex = abs(cf_stmt.loc['Capital Expenditures'].iloc[0])
                            fcf = ocf - capex
                        else:
                            fcf = ocf
                    except Exception:
                        fcf = ocf
            
            return {
                'Ticker': ticker_symbol,
                'Company': long_name,
                'Sector': sector,
                'Industry': industry,
                'MarketCap': market_cap,
                'FreeCashFlow': fcf
            }
        except Exception as e:
            if "Rate limited" in str(e) or "429" in str(e):
                wait_time = (attempt + 1) * 3
                print(f"  [!] Rate limited for {ticker_symbol}. Waiting {wait_time}s (Attempt {attempt+1}/3)...")
                time.sleep(wait_time)
            else:
                # Other error, return empty/N/A
                return {
                    'Ticker': ticker_symbol,
                    'Company': ticker_symbol,
                    'Sector': 'N/A',
                    'Industry': 'N/A',
                    'MarketCap': None,
                    'FreeCashFlow': None
                }
    return {
        'Ticker': ticker_symbol,
        'Company': ticker_symbol,
        'Sector': 'N/A',
        'Industry': 'N/A',
        'MarketCap': None,
        'FreeCashFlow': None
    }

def main():
    print("="*120)
    print("           TIMESFM TOP 20 NON-BIOTECH ASYMMETRY LEADERS - PRICE-TO-FUTURE CASH FLOW AUDIT")
    print("="*120)
    
    if not os.path.exists(asymmetric_csv_path):
        print("[!] asymmetric_stocks.csv not found in outputs/ directory. Run screener first.")
        return
        
    df_results = pd.read_csv(asymmetric_csv_path)
    
    # 1. Filter out biotechs
    df_clean = df_results[~df_results['Ticker'].isin(BIOTECH_BLACKLIST)]
    
    # 2. Get Top 20 tickers
    top_20 = df_clean.head(20).copy()
    tickers = top_20['Ticker'].tolist()
    print(f"Loaded Top 20 Non-Biotech tickers by QAS Score: {tickers}\n")
    
    # 3. Fetch fundamental cash flow metrics
    fcf_results = []
    for t in tickers:
        print(f"Fetching fundamentals for {t}...")
        data = get_fcf_data_with_retries(t)
        fcf_results.append(data)
        time.sleep(0.5) # Politeness delay
        
    df_fcf = pd.DataFrame(fcf_results)
    
    # Merge with original QAS scores
    df_merged = pd.merge(top_20[['Ticker', 'Price', 'Quant_Asymmetry_Score_3M', 'Gain_to_Pain_3M', 'Asymmetry_Ratio_3M']], 
                         df_fcf, on='Ticker')
    
    # 4. Calculate P/FCF ratio
    df_merged['P_FCF'] = None
    for idx, row in df_merged.iterrows():
        mc = row['MarketCap']
        fcf = row['FreeCashFlow']
        if mc and fcf and fcf > 0:
            df_merged.at[idx, 'P_FCF'] = float(mc / fcf)
            
    print("\n" + "="*120)
    print("                             PRE-FILTERED LEADERS FUNDAMENTALS MATRIX")
    print("="*120)
    
    display_df = df_merged.copy()
    
    # Format display columns
    display_df['Price'] = display_df['Price'].map(lambda x: f"${x:.2f}")
    display_df['MarketCap'] = display_df['MarketCap'].map(lambda x: f"${x/1e9:.2f}B" if pd.notnull(x) else "N/A")
    display_df['FreeCashFlow'] = display_df['FreeCashFlow'].map(lambda x: f"${x/1e6:+.1f}M" if pd.notnull(x) else "N/A")
    display_df['P_FCF_Display'] = display_df['P_FCF'].map(lambda x: f"{x:.2f}x" if pd.notnull(x) else "N/A/Negative")
    
    print(display_df[['Ticker', 'Company', 'Price', 'MarketCap', 'FreeCashFlow', 'P_FCF_Display', 'Quant_Asymmetry_Score_3M']].to_string(index=False))
    print("="*120)
    
    # 5. Apply the FCF multiple filter: keep only ones with P/FCF < 50
    # Keep companies with positive cash flow where P/FCF < 50
    passed_stocks = []
    failed_stocks = []
    
    for idx, row in df_merged.iterrows():
        p_fcf = row['P_FCF']
        ticker = row['Ticker']
        fcf = row['FreeCashFlow']
        
        # Financial or gold trust specific exemptions (no traditional FCF reported but highly defensive/liquid)
        if ticker in ['BAR', 'ASA']:
            failed_stocks.append((ticker, "Excluded (Gold/Precious Metals Trust - No operational cash flows to value)"))
            continue
            
        if p_fcf is None or pd.isnull(p_fcf):
            if fcf and fcf <= 0:
                failed_stocks.append((ticker, f"Excluded (Negative operational cash flow: ${fcf/1e6:.1f}M)"))
            else:
                failed_stocks.append((ticker, "Excluded (Missing/Unavailable Cash Flow reporting)"))
        elif p_fcf >= 50.0:
            failed_stocks.append((ticker, f"Excluded (Overvalued: P/FCF = {p_fcf:.2f}x >= 50x)"))
        elif p_fcf <= 0.0:
            failed_stocks.append((ticker, f"Excluded (Negative P/FCF: FCF is negative)"))
        else:
            passed_stocks.append(row)
            
    df_passed = pd.DataFrame(passed_stocks)
    
    print("\n" + "="*120)
    # Highlight only ones with P/FCF < 50 (Reasonably valued compounding assets)
    print("               FINAL SELECTED ASYMMETRIC LEADERS (Price-to-Future Cash Flow < 50x) - LEADERBOARD")
    print("="*120)
    
    if not df_passed.empty:
        df_passed = df_passed.sort_values(by='Quant_Asymmetry_Score_3M', ascending=False)
        
        # Format passed display
        df_passed_display = df_passed.copy()
        df_passed_display['Price'] = df_passed_display['Price'].map(lambda x: f"${x:.2f}")
        df_passed_display['MarketCap'] = df_passed_display['MarketCap'].map(lambda x: f"${x/1e9:.2f}B")
        df_passed_display['FreeCashFlow'] = df_passed_display['FreeCashFlow'].map(lambda x: f"${x/1e6:+.1f}M")
        df_passed_display['P_FCF'] = df_passed_display['P_FCF'].map(lambda x: f"{x:.2f}x")
        df_passed_display['QAS_Score'] = df_passed_display['Quant_Asymmetry_Score_3M'].map(lambda x: f"{x:.4f}")
        df_passed_display['GPR_3M'] = df_passed_display['Gain_to_Pain_3M'].map(lambda x: f"{x:.2f}")
        df_passed_display['AR_3M'] = df_passed_display['Asymmetry_Ratio_3M'].map(lambda x: f"{x:.2f}x")
        
        print(df_passed_display[['Ticker', 'Company', 'Price', 'MarketCap', 'FreeCashFlow', 'P_FCF', 'GPR_3M', 'AR_3M', 'QAS_Score']].to_string(index=False))
    else:
        print("No stocks passed the P/FCF < 50 filter.")
    print("="*120)
    
    print("\n" + "="*120)
    print("                                      VALUATION EXCLUSIONS LOG")
    print("="*120)
    for ticker, reason in failed_stocks:
        print(f"  - {ticker:6}: {reason}")
    print("="*120 + "\n")
    
    # Save the final passed list to CSV
    if not df_passed.empty:
        output_csv = 'outputs/fcf_filtered_asymmetric_stocks.csv'
        df_passed.to_csv(output_csv, index=False)
        print(f"  [+] Saved final audited asymmetric leaders to: {output_csv}")

if __name__ == "__main__":
    main()
