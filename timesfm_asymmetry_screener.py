#!/usr/bin/env python3
# timesfm_asymmetry_screener.py
# Automated batch downloader and TimesFM Stock Asymmetry Screener pipeline.
# Identifies highly positively skewed upside return profiles (asymmetry setup like Pinduoduo).

import os
import io
import sys
import argparse
import datetime
import urllib.request
import pandas as pd
import numpy as np
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor

# Set pandas options for cleaner printing
pd.set_option('display.max_columns', 15)
pd.set_option('display.width', 1000)

def get_active_us_tickers():
    """
    Programmatically downloads active NASDAQ, NYSE, and AMEX symbols 
    from the official NASDAQ Trader FTP servers.
    """
    print("\n[1/5] Fetching active US common stock directories from NASDAQ Trader FTP...")
    all_symbols = []
    
    # 1. Fetch NASDAQ Listed Symbols
    try:
        url_nasdaq = "ftp://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqlisted.txt"
        with urllib.request.urlopen(url_nasdaq, timeout=15) as response:
            data = response.read().decode('utf-8')
        
        df_nasdaq = pd.read_csv(io.StringIO(data), sep="|")
        # Filter: Keeps standard non-test common stocks, excluding ETFs
        df_nasdaq = df_nasdaq[
            (df_nasdaq['Test Issue'] == 'N') & 
            (df_nasdaq['ETF'] == 'N') & 
            (df_nasdaq['Financial Status'] == 'N')
        ]
        symbols = df_nasdaq['Symbol'].dropna().tolist()
        all_symbols.extend(symbols)
        print(f"  - Successfully loaded {len(symbols)} active NASDAQ common stocks.")
    except Exception as e:
        print(f"  - Warning: Failed to fetch NASDAQ listed symbols: {e}")

    # 2. Fetch NYSE, AMEX, and ARCA Symbols
    try:
        url_other = "ftp://ftp.nasdaqtrader.com/SymbolDirectory/otherlisted.txt"
        with urllib.request.urlopen(url_other, timeout=15) as response:
            data = response.read().decode('utf-8')
        
        df_other = pd.read_csv(io.StringIO(data), sep="|")
        # Filter: Keeps standard non-test common stocks, excluding ETFs
        df_other = df_other[
            (df_other['Test Issue'] == 'N') & 
            (df_other['ETF'] == 'N')
        ]
        symbols = df_other['ACT Symbol'].dropna().tolist()
        all_symbols.extend(symbols)
        print(f"  - Successfully loaded {len(symbols)} active NYSE/AMEX common stocks.")
    except Exception as e:
        print(f"  - Warning: Failed to fetch NYSE/AMEX symbols: {e}")

    # Deduplicate and filter symbols containing standard letters only (excludes warrants, preferreds, units)
    valid_symbols = list(set([s for s in all_symbols if isinstance(s, str) and s.isalpha()]))
    
    if not valid_symbols:
        print("\n[!] FTP fetch returned empty list. Falling back to high-growth, mid-cap, and consumer stock ADR universe...")
        # Deep fallback list containing high-growth, consumer tech, and highly volatile tickers
        valid_symbols = [
            "PDD", "BABA", "JD", "BIDU", "OPRA", "MTCH", "BMBL", "EXPE", "BKNG", "NFLX", 
            "NVDA", "AMD", "META", "TSLA", "AMZN", "GOOGL", "MSFT", "AAPL", "PLTR", "SNOW", 
            "NET", "DDOG", "CRWD", "ZS", "OKTA", "MDB", "ESTC", "PATH", "CELH", "ELF", 
            "LI", "NIO", "XPEV", "FUTU", "TME", "SOFI", "HOOD", "BILI", "TAL", "GOTU", 
            "EDU", "SMCI", "ARM", "COIN", "U", "RBLX", "PINS", "SNAP", "DKNG", "MELI"
        ]
    
    print(f"Total candidate symbols to download: {len(valid_symbols)}")
    return valid_symbols

def download_historical_prices(symbols, years=2.5):
    """
    Downloads historical price series in highly stable multithreaded batches.
    Ingests exactly years of daily history (default 2.5 years) as requested.
    Processes sequentially in chunks to prevent 'can't start new thread' OS thread limit exhaustion.
    """
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=int(365 * years))
    print(f"\n[2/5] Downloading {years}-year daily historical price series ({start_date} to {end_date}) via robust sequential batch queries...")
    
    data_dict = {}
    chunk_size = 250
    chunks = [symbols[i:i+chunk_size] for i in range(0, len(symbols), chunk_size)]
    
    for idx, chunk in enumerate(chunks):
        print(f"  - Downloading batch {idx+1}/{len(chunks)} ({len(chunk)} symbols)...")
        try:
            # Use yfinance's internal threads, limited to a single batch at a time
            df = yf.download(chunk, start=start_date, end=end_date, progress=False, threads=True, timeout=40)
            if isinstance(df.columns, pd.MultiIndex):
                # MultiIndex Columns (newer yfinance output structure: Price, Ticker)
                ticker_level = 'Ticker' if 'Ticker' in df.columns.names else 1
                ticker_values = df.columns.get_level_values(ticker_level).unique()
                for ticker in chunk:
                    if ticker in ticker_values:
                        try:
                            ticker_df = df.xs(ticker, axis=1, level=ticker_level).dropna(subset=['Close', 'Volume'])
                            # Ensure we have Adjusted Close (fallback to Close if needed)
                            if 'Adj Close' not in ticker_df.columns and 'Close' in ticker_df.columns:
                                ticker_df['Adj Close'] = ticker_df['Close']
                            
                            # Enforce at least 450 daily bars for a 2.5y range to allow robust slicing
                            if len(ticker_df) >= 450:
                                data_dict[ticker] = ticker_df
                        except Exception:
                            pass
            else:
                # Single-level columns (fallback if single ticker is returned)
                for ticker in chunk:
                    if ticker in df.columns or len(chunk) == 1:
                        ticker_df = df.dropna(subset=['Close', 'Volume'])
                        if 'Adj Close' not in ticker_df.columns and 'Close' in ticker_df.columns:
                            ticker_df['Adj Close'] = ticker_df['Close']
                        if len(ticker_df) >= 450:
                            data_dict[ticker] = ticker_df
        except Exception as e:
            print(f"    - Warning: Failed downloading batch {idx+1}: {e}")
            
    print(f"Successfully downloaded daily history for {len(data_dict)} stocks.")
    return data_dict

def filter_liquid_universe(data_dict):
    """
    Filters tickers using specific criteria:
    1. Price > $1.00 (Includes high-spike cheap stocks, removing sub-$1 penny stock delisting noise)
    2. Average Daily Dollar Volume > $2,000,000 (Ensures robust tradeable liquidity)
    """
    print("\n[3/5] Applying quantitative filters (Price > $1.00, Daily Dollar Volume > $2.0M)...")
    filtered_data = {}
    
    for ticker, df in data_dict.items():
        try:
            last_price = float(df['Adj Close'].iloc[-1])
            # Daily dollar volume = close * volume
            daily_dollar_volume = df['Adj Close'] * df['Volume']
            avg_dollar_volume = float(daily_dollar_volume.mean())
            
            # Filter condition: Price > 1.0 (includes cheap stocks with spike potential)
            if last_price > 1.0 and avg_dollar_volume > 2000000.0:
                filtered_data[ticker] = {
                    'df': df,
                    'last_price': last_price,
                    'avg_dollar_volume': avg_dollar_volume
                }
        except Exception:
            continue
            
    print(f"Screener complete: Kept {len(filtered_data)} liquid tradeable stocks in the active universe.")
    return filtered_data

def run_asymmetry_screening(filtered_stocks):
    """
    Performs refined 3-month (63 trading days / 90 calendar days) Quantile Asymmetry and Tail Risk analytics.
    Uses Google's TimesFM time-series foundation model with a 90-day forecast horizon if available.
    Otherwise falls back to the high-performance zero-shot quantile-bootstrap statistical predictor.
    """
    print("\n[4/5] Running 3-Month (90-Day prediction horizon) Quant Asymmetry & Tail Risk screening...")
    
    # Check for TimesFM installation
    has_timesfm = False
    try:
        import timesfm
        import torch
        has_timesfm = True
    except ImportError:
        pass
        
    timesfm_results = {}
    if has_timesfm:
        try:
            print("  - TimesFM library detected. Loading Google TimesFM weights (200M Parameter model)...")
            torch.set_float32_matmul_precision("high")
            model = timesfm.TimesFm(
                context_len=256,
                horizon_len=90,  # 3-Month forecasting horizon!
                input_dim=1,
                output_dim=1,
                per_core_batch_size=32,
                backend="cpu"
            )
            model.load_from_checkpoint(repo_id="google/timesfm-1.0-200m")
            
            inputs = []
            tickers = list(filtered_stocks.keys())
            for t in tickers:
                prices = filtered_stocks[t]['df']['Adj Close'].values
                inputs.append(prices)
                
            print(f"  - Generating 90-day (3-Month) zero-shot forecasts on {len(tickers)} series...")
            forecast_output, _ = model.forecast(inputs, repo_id="google/timesfm-1.0-200m")
            
            for i, t in enumerate(tickers):
                # Extract quantiles at the end of the 90-day forecast horizon
                f_series = forecast_output[i, -1, :] # shape (num_quantiles,)
                q_10_pred = float(f_series[1])
                q_50_pred = float(f_series[5])
                q_90_pred = float(f_series[9])
                
                last_price = filtered_stocks[t]['last_price']
                pred_mean = (q_50_pred - last_price) / last_price
                
                # Check for positive predicted return
                if pred_mean > 0:
                    pred_p10 = (q_10_pred - last_price) / last_price
                    pred_p90 = (q_90_pred - last_price) / last_price
                    
                    denom = pred_mean - pred_p10
                    if denom < 1e-6:
                        denom = 1e-6
                    asymmetry_ratio_3m = (pred_p90 - pred_mean) / denom
                    qas_3m = pred_mean * asymmetry_ratio_3m
                    
                    timesfm_results[t] = {
                        'Mean_3M_Return': pred_mean,
                        'P10_3M_Return': pred_p10,
                        'P50_3M_Return': (q_50_pred - last_price) / last_price,
                        'P90_3M_Return': pred_p90,
                        'Asymmetry_Ratio_3M': asymmetry_ratio_3m,
                        'Quant_Asymmetry_Score_3M': qas_3m,
                        'DataSource': 'TimesFM 2.5 90d Forecast'
                    }
        except Exception as e:
            print(f"  - Warning: TimesFM execution failed ({e}). Reverting entirely to statistical 3M quantile bootstrapper.")

    results = []
    for t, info in filtered_stocks.items():
        try:
            # If TimesFM already successfully forecasted this ticker, use it!
            if t in timesfm_results:
                # Add skewness and GPR from historical daily returns for continuity
                df = info['df']
                close_prices = df['Adj Close']
                ret_3m = close_prices.pct_change(63).dropna().values
                mean_hist = np.mean(ret_3m)
                std_3m = np.std(ret_3m)
                skew_3m = float(np.mean((ret_3m - mean_hist)**3) / (std_3m**3)) if std_3m > 1e-6 else 0.0
                
                upside_sum = np.sum(ret_3m[ret_3m > 0])
                downside_sum = abs(np.sum(ret_3m[ret_3m < 0]))
                gpr_3m = float(upside_sum / max(downside_sum, 1e-4))
                
                stock_res = timesfm_results[t]
                stock_res['Ticker'] = t
                stock_res['Price'] = info['last_price']
                stock_res['Avg_Daily_Dollar_Volume'] = info['avg_dollar_volume']
                stock_res['Skewness_3M'] = skew_3m
                stock_res['Gain_to_Pain_3M'] = gpr_3m
                stock_res['Quant_Asymmetry_Score_3M'] = stock_res['Mean_3M_Return'] * stock_res['Asymmetry_Ratio_3M'] * np.log(1 + gpr_3m)
                stock_res['Asymmetry_Daily'] = 0.0 # Bypassed
                stock_res['Num_Bars'] = len(df)
                
                results.append(stock_res)
                continue
                
            # Otherwise run statistical rolling 3-Month Bootstrap Quantile forecaster
            df = info['df']
            close_prices = df['Adj Close']
            
            # Compute rolling 3-month (63 trading days) returns
            ret_3m = close_prices.pct_change(63).dropna().values
            
            if len(ret_3m) < 200:
                continue
                
            mean_3m = float(np.mean(ret_3m))
            
            # 1. Enforce Positive Mean return over the 3-month horizon
            if mean_3m <= 0:
                continue
                
            # 2. Extract key quantiles
            q_10_3m = float(np.percentile(ret_3m, 10))
            q_50_3m = float(np.percentile(ret_3m, 50))
            q_90_3m = float(np.percentile(ret_3m, 90))
            
            # 3. Refined Asymmetry Ratio (AR) = (P90 - Mean) / (Mean - P10)
            # Measures how many times upside surprises exceed downside surprises relative to the trend mean
            denom = mean_3m - q_10_3m
            if denom < 1e-6:
                denom = 1e-6
            asymmetry_ratio_3m = (q_90_3m - mean_3m) / denom
            
            # 4. Fisher-Pearson Standardized Skewness
            std_3m = np.std(ret_3m)
            skew_3m = float(np.mean((ret_3m - mean_3m)**3) / (std_3m**3)) if std_3m > 1e-6 else 0.0
            
            # 5. Gain-to-Pain Ratio (GPR)
            upside_sum = np.sum(ret_3m[ret_3m > 0])
            downside_sum = abs(np.sum(ret_3m[ret_3m < 0]))
            gpr_3m = float(upside_sum / max(downside_sum, 1e-4))
            
            # 6. Refined 3M Quant Asymmetry Score (QAS) = Mean * AR * ln(1 + GPR)
            qas_3m = mean_3m * asymmetry_ratio_3m * np.log(1 + gpr_3m)
            
            # 7. Keep daily skew for multi-horizon comparisons
            daily_returns = close_prices.pct_change().dropna().values
            as_daily = (np.percentile(daily_returns, 90) - np.percentile(daily_returns, 50)) / max(abs(np.percentile(daily_returns, 50) - np.percentile(daily_returns, 10)), 1e-6)
            
            results.append({
                'Ticker': t,
                'Price': info['last_price'],
                'Avg_Daily_Dollar_Volume': info['avg_dollar_volume'],
                'Mean_3M_Return': mean_3m,
                'P10_3M_Return': q_10_3m,
                'P50_3M_Return': q_50_3m,
                'P90_3M_Return': q_90_3m,
                'Asymmetry_Ratio_3M': asymmetry_ratio_3m,
                'Quant_Asymmetry_Score_3M': qas_3m,
                'Skewness_3M': skew_3m,
                'Gain_to_Pain_3M': gpr_3m,
                'Asymmetry_Daily': as_daily,
                'Num_Bars': len(df),
                'DataSource': 'Rolling 3M Quant Distribution'
            })
        except Exception:
            continue
            
    return results

def main():
    parser = argparse.ArgumentParser(description="TimesFM Asymmetry Stock Screener")
    parser.add_argument('--full', action='store_true', help="Run on full NASDAQ/NYSE universe")
    parser.add_argument('--limit', type=int, default=250, help="Limit tickers in standard run")
    parser.add_argument('--force', action='store_true', help="Force redownloading from yfinance (bypasses cache)")
    args = parser.parse_args()
    
    prices_csv_path = 'outputs/daily_prices.csv'
    volumes_csv_path = 'outputs/daily_volumes.csv'
    
    # Load from high-fidelity local cache if available and not forced
    if not args.force and os.path.exists(prices_csv_path) and os.path.exists(volumes_csv_path):
        print("\n[!] Cached 2.5-year daily historical price and volume matrices detected locally!")
        print("    Loading cache instantly to run 3-Month predictions...")
        try:
            prices_df = pd.read_csv(prices_csv_path, index_col=0, parse_dates=True)
            volumes_df = pd.read_csv(volumes_csv_path, index_col=0, parse_dates=True)
            
            # Reconstruct filtered_stocks from cache
            filtered_stocks = {}
            for ticker in prices_df.columns:
                ticker_df = pd.DataFrame({
                    'Adj Close': prices_df[ticker],
                    'Volume': volumes_df[ticker]
                }).dropna()
                if len(ticker_df) >= 450:
                    last_price = float(ticker_df['Adj Close'].iloc[-1])
                    avg_dollar_volume = float((ticker_df['Adj Close'] * ticker_df['Volume']).mean())
                    filtered_stocks[ticker] = {
                        'df': ticker_df,
                        'last_price': last_price,
                        'avg_dollar_volume': avg_dollar_volume
                    }
            print(f"Successfully loaded {len(filtered_stocks)} liquid stocks from local 2.5y cache.")
            
            if not filtered_stocks:
                print("\n[!] Cache reconstructed empty list. Falling back to fresh download...")
                filtered_stocks = None
        except Exception as e:
            print(f"  - Warning: Failed to load local cache ({e}). Reverting to download...")
            filtered_stocks = None
    else:
        filtered_stocks = None

    if filtered_stocks is None:
        # 1. Fetch active US stock symbol universe
        tickers = get_active_us_tickers()
        
        # Seed with high-conviction momentum and breakout stock lists
        high_conviction = [
            "PDD", "BABA", "JD", "OPRA", "MTCH", "BMBL", "EXPE", "BKNG", "NFLX", "NVDA", 
            "AMD", "META", "TSLA", "AMZN", "GOOGL", "MSFT", "AAPL", "PLTR", "SNOW", "NET", 
            "DDOG", "CRWD", "ZS", "OKTA", "MDB", "ESTC", "PATH", "CELH", "ELF", "LI", 
            "NIO", "XPEV", "FUTU", "TME", "SOFI", "HOOD", "BILI", "TAL", "GOTU", "EDU", 
            "SMCI", "ARM", "COIN", "U", "RBLX", "PINS", "SNAP", "DKNG", "MELI"
        ]
        
        if not args.full:
            limit = args.limit
            print(f"\n[!] Running in standard mode capped at {limit} tickers. Use --full to run the entire active universe.")
            tickers = list(set(high_conviction + tickers[:limit]))
        else:
            print(f"\n[!] Running on FULL NASDAQ/NYSE universe of {len(tickers)} tickers...")
            tickers = list(set(high_conviction + tickers))
            
        # 2. Download historical 2.5-year data
        data_dict = download_historical_prices(tickers, years=2.5)
        
        # 3. Apply Price > 1.0 and Dollar Volume > 2M liquidity filters
        filtered_stocks = filter_liquid_universe(data_dict)
        
        if not filtered_stocks:
            print("\n[!] No stocks passed the liquidity screener filters. Exiting...")
            return
            
        # 4. Save raw daily price and volume dataframes to wide CSVs (for custom slicing on client side)
        print("\n[5/5] Exporting 2.5-year daily historical prices and volumes to CSV (Wide Format)...")
        os.makedirs('outputs', exist_ok=True)
        
        prices_dict = {}
        volumes_dict = {}
        
        for ticker, info in filtered_stocks.items():
            df = info['df']
            prices_dict[ticker] = df['Adj Close']
            volumes_dict[ticker] = df['Volume']
            
        prices_df = pd.DataFrame(prices_dict)
        volumes_df = pd.DataFrame(volumes_dict)
        
        prices_df.sort_index(inplace=True)
        volumes_df.sort_index(inplace=True)
        
        prices_df.to_csv(prices_csv_path)
        volumes_df.to_csv(volumes_csv_path)
        print(f"  - Saved daily adjusted prices to: {prices_csv_path} (Shape: {prices_df.shape})")
        print(f"  - Saved daily trading volumes to: {volumes_csv_path} (Shape: {volumes_df.shape})")
        
    # 5. Run Asymmetry Screening
    results = run_asymmetry_screening(filtered_stocks)
    
    # 6. Compile Leaderboard and Export
    df_results = pd.DataFrame(results)
    
    # Rank: Sort by 3-Month Quant Asymmetry Score (descending) to find the absolute strongest asymmetric breakouts
    # Score = Mean * AR.
    df_results = df_results.sort_values(by=['Quant_Asymmetry_Score_3M'], ascending=[False])
    
    csv_path = 'outputs/asymmetric_stocks.csv'
    df_results.to_csv(csv_path, index=False)
    print(f"  - Exported complete ranked stocks summary list to: {csv_path}")
    
    print("\n" + "="*125)
    print("                TIMESFM 3-MONTH REFINED QUANT ASYMMETRY LEADERS - TOP 30 LEADERBOARD")
    print("="*125)
    
    # Select columns to display
    display_cols = [
        'Ticker', 'Price', 'Mean_3M_Return', 'P10_3M_Return', 'P90_3M_Return', 
        'Asymmetry_Ratio_3M', 'Skewness_3M', 'Gain_to_Pain_3M', 'Quant_Asymmetry_Score_3M'
    ]
    # Filter for standard display and print
    leaderboard = df_results[display_cols].head(30).copy()
    
    # Rename columns for premium terminal presentation
    leaderboard.columns = [
        'Ticker', 'Price', 'Mean 3M', 'P10 3M (Down)', 'P90 3M (Up)', 'Asy Ratio 3M', 'Skew 3M', 'GPR 3M', 'QAS 3M Score'
    ]
    
    # Format display values
    leaderboard['Price'] = leaderboard['Price'].map(lambda x: f"${x:.2f}")
    leaderboard['Mean 3M'] = leaderboard['Mean 3M'].map(lambda x: f"{x*100:+.1f}%")
    leaderboard['P10 3M (Down)'] = leaderboard['P10 3M (Down)'].map(lambda x: f"{x*100:+.1f}%")
    leaderboard['P90 3M (Up)'] = leaderboard['P90 3M (Up)'].map(lambda x: f"{x*100:+.1f}%")
    leaderboard['Asy Ratio 3M'] = leaderboard['Asy Ratio 3M'].map(lambda x: f"{x:.2f}x")
    leaderboard['Skew 3M'] = leaderboard['Skew 3M'].map(lambda x: f"{x:.3f}")
    leaderboard['GPR 3M'] = leaderboard['GPR 3M'].map(lambda x: f"{x:.2f}")
    leaderboard['QAS 3M Score'] = leaderboard['QAS 3M Score'].map(lambda x: f"{x:.4f}")
    
    print(leaderboard.to_string(index=False))
    print("="*125)
    print("* QAS 3M Score = Mean 3M Return * Asymmetry Ratio * ln(1 + GPR 3M). Enforces positive mean.")
    print("  High Asymmetry Ratio indicates that positive tail surprises vastly exceed negative tail surprises from the mean.")
    print("  Wide-format daily raw historical prices/volumes loaded from outputs/ daily cache.")
    print("="*125 + "\n")

if __name__ == "__main__":
    main()
