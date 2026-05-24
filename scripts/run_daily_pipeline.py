#!/usr/bin/env python3
import os
import sys
import datetime
import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

def load_and_update_cache(prices_path="outputs/daily_prices.csv", volumes_path="outputs/daily_volumes.csv"):
    print("=" * 70)
    print(" DAILY PRICE CACHE UPDATE ENGINE")
    print("=" * 70)
    
    if not os.path.exists(prices_path):
        print(f"Error: Price cache '{prices_path}' not found. Cannot perform incremental update.")
        return None, None
        
    # 1. Load existing price cache
    print(f"Loading existing price cache from {prices_path}...")
    df_prices = pd.read_csv(prices_path, index_col="Date")
    print(f"  - Loaded price matrix with shape: {df_prices.shape} ({len(df_prices.columns)} tickers, {len(df_prices)} trading days)")
    
    # 2. Check last date
    last_date_str = df_prices.index[-1]
    last_date = datetime.datetime.strptime(last_date_str, "%Y-%m-%d").date()
    today = datetime.date.today()
    
    print(f"  - Last recorded date in cache: {last_date}")
    print(f"  - Today's date:                 {today}")
    
    # 3. Incremental Download if necessary
    if today > last_date:
        start_date = last_date + datetime.timedelta(days=1)
        # If start_date falls on a weekend and today is also weekend, yfinance might return empty
        # Let's try downloading
        print(f"\nIncremental update required: Downloading prices from {start_date} to {today}...")
        
        tickers = df_prices.columns.tolist()
        try:
            # Download only 'Close' or 'Adj Close'
            # Group by column to get a clean dataframe
            new_data = yf.download(tickers, start=start_date, end=today, progress=False)
            
            if not new_data.empty:
                # Handle multi-level columns if returned by yfinance
                if isinstance(new_data.columns, pd.MultiIndex):
                    if 'Adj Close' in new_data.columns.levels[0]:
                        new_prices = new_data['Adj Close']
                    else:
                        new_prices = new_data['Close']
                else:
                    new_prices = new_data
                
                # Align columns exactly
                new_prices = new_prices.reindex(columns=df_prices.columns)
                
                # Drop rows where all elements are NaN (e.g. non-trading days)
                new_prices = new_prices.dropna(how='all')
                
                if not new_prices.empty:
                    print(f"  - Downloaded {len(new_prices)} new trading days.")
                    
                    # Clean index format
                    new_prices.index = new_prices.index.strftime("%Y-%m-%d")
                    
                    # Append and deduplicate
                    df_prices = pd.concat([df_prices, new_prices])
                    df_prices = df_prices[~df_prices.index.duplicated(keep='last')]
                    
                    # Save updated cache
                    df_prices.to_csv(prices_path)
                    print(f"  - Price cache successfully updated and saved to {prices_path} (New shape: {df_prices.shape})")
                else:
                    print("  - No new trading day prices returned. Cache is already up to date.")
            else:
                print("  - No new data available (market might be closed or it is a weekend).")
        except Exception as e:
            print(f"  - Warning: Incremental download failed: {e}. Proceeding with existing cache.")
    else:
        print("\n  - Price cache is already fully up to date. Skipping download.")
        
    # Load volumes cache if available
    df_volumes = None
    if os.path.exists(volumes_path):
        print(f"Loading volumes cache from {volumes_path}...")
        df_volumes = pd.read_csv(volumes_path, index_col="Date")
        print(f"  - Loaded volume matrix with shape: {df_volumes.shape}")
        
    return df_prices, df_volumes

def compute_mhc_qas(prices_series):
    # Pre-calculate rolling 3-month (63 trading days) returns
    ret_3m = prices_series.pct_change(63).dropna().values
    
    max_len = len(ret_3m)
    if max_len < 126:  # Need at least the 0.5y horizon (126 days)
        return None
        
    # Horizons: 0.5y (126 days), 1.0y (252 days), 2.0y (504 days), 2.5y (625 days)
    # Dynamically clamp to the maximum available returns length
    horizons = [126, min(252, max_len), min(504, max_len), min(625, max_len)]
    weights = [0.40, 0.30, 0.20, 0.10]
    
    mhc_qas = 0.0
    mhc_gpr = 0.0
    mhc_mean = 0.0
    mhc_ar = 0.0
    
    for h, w in zip(horizons, weights):
        # Slice for the specific horizon
        h_ret = ret_3m[-h:]
        
        mean_h = float(np.mean(h_ret))
        q_10 = float(np.percentile(h_ret, 10))
        q_90 = float(np.percentile(h_ret, 90))
        
        denom = mean_h - q_10
        if denom < 1e-6:
            denom = 1e-6
        ar_h = (q_90 - mean_h) / denom
        
        upside = np.sum(h_ret[h_ret > 0])
        downside = abs(np.sum(h_ret[h_ret < 0]))
        gpr_h = float(upside / max(downside, 1e-4))
        
        qas_h = mean_h * ar_h * np.log(1 + gpr_h)
        
        mhc_qas += w * qas_h
        mhc_gpr += w * gpr_h
        mhc_mean += w * mean_h
        mhc_ar += w * ar_h
        
    return {
        'MHC_Mean': mhc_mean,
        'MHC_AR': mhc_ar,
        'MHC_GPR': mhc_gpr,
        'MHC_QAS': mhc_qas
    }

def run_asymmetry_screening(df_prices, df_volumes):
    print("\n" + "=" * 70)
    print(" RUNNING MULTI-HORIZON ASYMMETRY SCREENING (MHC_QAS)")
    print("=" * 70)
    
    # Filter for liquid stocks using volumes if available
    # Or select a subset of highly active common tickers
    valid_tickers = []
    if df_volumes is not None:
        print("Filtering for highly liquid tickers (Average Daily Volume > 100k shares)...")
        # Calculate average volume
        avg_vols = df_volumes.mean()
        liquid_tickers = avg_vols[avg_vols > 100000].index.tolist()
        # Intersect with prices
        valid_tickers = list(set(liquid_tickers) & set(df_prices.columns))
        print(f"  - Filtered down to {len(valid_tickers)} highly liquid candidate tickers.")
    else:
        valid_tickers = df_prices.columns.tolist()
        
    results = []
    print(f"Processing calculations for {len(valid_tickers)} tickers...")
    
    for idx, t in enumerate(valid_tickers):
        series = df_prices[t]
        # Skip if ticker has too many NaNs
        if series.isna().sum() > 50:
            continue
            
        # Forward fill any small gaps
        series = series.ffill().bfill()
        
        res = compute_mhc_qas(series)
        if res is not None:
            # Reconcile price-to-FCF or other metrics if desired, but here we focus on pure log-utility AUS
            last_price = float(series.iloc[-1])
            results.append({
                'Ticker': t,
                'Price': last_price,
                'MHC_Mean_3M_Return': res['MHC_Mean'],
                'MHC_AR': res['MHC_AR'],
                'MHC_GPR': res['MHC_GPR'],
                'MHC_QAS': res['MHC_QAS']
            })
            
    df_results = pd.DataFrame(results)
    if df_results.empty:
        print("Error: No tickers passed the multi-horizon screening baseline.")
        return None
        
    # Sort by QAS score descending
    df_results = df_results.sort_values(by="MHC_QAS", ascending=False).reset_index(drop=True)
    
    # Save results
    output_csv = "outputs/daily_pipeline_leaderboard.csv"
    df_results.to_csv(output_csv, index=False)
    print(f"Leaderboard successfully saved to {output_csv}")
    
    return df_results

def generate_performance_chart(df_prices, top_leaders, output_img="outputs/asymmetry_leaders_performance.png"):
    print("\n" + "=" * 70)
    print(" GENERATING VISUAL PERFORMANCE CHARTS")
    print("=" * 70)
    
    plt.figure(figsize=(12, 6))
    
    # Slice the last 6 months (126 trading days)
    sliced_prices = df_prices.iloc[-126:]
    
    for t in top_leaders:
        # Calculate cumulative returns
        series = sliced_prices[t].ffill().bfill()
        cum_returns = (series / series.iloc[0] - 1.0) * 100.0
        
        # Plot
        plt.plot(cum_returns.index, cum_returns.values, label=t, linewidth=2.5)
        
    plt.title("6-Month Cumulative Returns Profile of Top Asymmetry Leaders", fontsize=14, fontweight='bold', pad=15)
    plt.xlabel("Trading Date", fontsize=12)
    plt.ylabel("Cumulative Return (%)", fontsize=12)
    
    # Format X-axis labels
    plt.xticks(rotation=45)
    plt.gca().xaxis.set_major_locator(plt.MaxNLocator(10))
    
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(fontsize=11, loc="upper left")
    plt.tight_layout()
    
    plt.savefig(output_img, dpi=300)
    print(f"Performance chart successfully saved to {output_img}")
    plt.close()

def main():
    # 1. Update cache
    df_prices, df_volumes = load_and_update_cache()
    if df_prices is None:
        return
        
    # 2. Run Asymmetry Screening
    df_results = run_asymmetry_screening(df_prices, df_volumes)
    if df_results is None:
        return
        
    # 3. Print top 10 Leaders
    print("\n" + "*" * 80)
    print("           DAILY PIPELINE: TOP 10 ASYMMETRY LEADERS LEADERBOARD")
    print("*" * 80)
    
    top_10 = df_results.head(10)
    
    print(top_10.to_string(index=False, formatters={
        'Price': lambda x: f"${x:.2f}",
        'MHC_Mean_3M_Return': lambda x: f"{x*100:+.2f}%",
        'MHC_AR': lambda x: f"{x:.2f}x",
        'MHC_GPR': lambda x: f"{x:.2f}",
        'MHC_QAS': lambda x: f"{x:.4f}"
    }))
    print("*" * 80 + "\n")
    
    # 4. Generate Chart of Top 5 Leaders
    top_5_tickers = top_10['Ticker'].head(5).tolist()
    # Ensure they are in the prices dataframe
    valid_plot_tickers = [t for t in top_5_tickers if t in df_prices.columns]
    generate_performance_chart(df_prices, valid_plot_tickers)

if __name__ == "__main__":
    main()
