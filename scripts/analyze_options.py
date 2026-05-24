#!/usr/bin/env python3
import sys
import argparse
import math
from datetime import datetime
import yfinance as yf
import pandas as pd

# Set pandas options for cleaner printing
pd.set_option('display.max_columns', 15)
pd.set_option('display.width', 1000)

# Pure-Python Normal Distribution Functions for Greek Calculations
def norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def bsm_put_delta(S, K, r, sigma, T):
    if T <= 0:
        return -1.0 if S < K else 0.0
    if sigma <= 0:
        return -1.0 if S < K else 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return norm_cdf(d1) - 1.0

def bsm_call_delta(S, K, r, sigma, T):
    if T <= 0:
        return 1.0 if S > K else 0.0
    if sigma <= 0:
        return 1.0 if S > K else 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return norm_cdf(d1)

def analyze_options(ticker_symbol, target_min_dte=20, target_max_dte=55, option_type='put', r=0.05, verbose=False):
    ticker_symbol = ticker_symbol.upper()
    option_type = option_type.lower()
    print(f"Downloading options data for {ticker_symbol} from Yahoo Finance...")
    
    try:
        ticker = yf.Ticker(ticker_symbol)
        
        # Fetch current spot price
        info = ticker.info
        spot = info.get('regularMarketPrice') or info.get('previousClose') or info.get('currentPrice')
        
        if not spot:
            # Fallback to history to get latest price
            hist = ticker.history(period="1d")
            if hist.empty:
                print(f"Error: Ticker '{ticker_symbol}' not found or has no active price data.")
                return False
            spot = float(hist['Close'].iloc[-1])
            
        print(f"Current Stock Price: ${spot:.2f}\n")
        
        expirations = ticker.options
        if not expirations:
            print(f"No active option contracts found for {ticker_symbol}.")
            return False
            
        # Filter Expirations by target DTE window
        today = datetime.today()
        valid_expirations = []
        
        for exp in expirations:
            try:
                exp_date = datetime.strptime(exp, "%Y-%m-%d")
                dte = (exp_date - today).days
                if target_min_dte <= dte <= target_max_dte:
                    valid_expirations.append((exp, dte))
            except ValueError:
                continue
                
        if not valid_expirations:
            print(f"No expirations found in the DTE window [{target_min_dte}, {target_max_dte}] days.")
            # Fallback to closest available expiration
            closest_exp = expirations[0]
            try:
                exp_date = datetime.strptime(closest_exp, "%Y-%m-%d")
                dte = (exp_date - today).days
                valid_expirations = [(closest_exp, dte)]
                print(f"Falling back to the closest available expiration: {closest_exp} ({dte} DTE)")
            except Exception:
                return False
                
        print(f"Expirations in DTE window (analyzing top {min(3, len(valid_expirations))}):")
        for exp, dte in valid_expirations[:3]:
            print(f"  - {exp} ({dte} DTE)")
        print()
        
        for exp, dte in valid_expirations[:3]:
            T = dte / 365.0
            print("=" * 95)
            print(f" {ticker_symbol} {option_type.upper()} OPTIONS CHAIN: {exp} ({dte} DTE) | Spot: ${spot:.2f}")
            print("=" * 95)
            
            try:
                opt = ticker.option_chain(exp)
                chain = opt.puts if option_type == 'put' else opt.calls
                
                # Filter strikes within +/- 20% of spot
                lower_limit = spot * 0.80
                upper_limit = spot * 1.20
                filtered_chain = chain[(chain['strike'] >= lower_limit) & (chain['strike'] <= upper_limit)]
                
                if filtered_chain.empty:
                    # Fallback to closest 8 strikes
                    chain['dist'] = (chain['strike'] - spot).abs()
                    filtered_chain = chain.nsmallest(8, 'dist').sort_values('strike')
                    
                # Format Dataframe
                cols = ['strike', 'bid', 'ask', 'impliedVolatility']
                display_df = filtered_chain[cols].copy()
                
                # Perform Greeks & Yield Calculations
                deltas = []
                net_bases = []
                ann_yields = []
                
                for _, row in display_df.iterrows():
                    strike = row['strike']
                    bid = row['bid']
                    ask = row['ask']
                    iv = row['impliedVolatility']
                    
                    mid = (bid + ask) / 2.0 if (bid > 0 and ask > 0) else row.get('lastPrice', 0)
                    
                    # 1. Delta
                    if option_type == 'put':
                        delta = bsm_put_delta(spot, strike, r, iv, T)
                        net_basis = strike - mid
                    else:
                        delta = bsm_call_delta(spot, strike, r, iv, T)
                        net_basis = strike + mid
                        
                    # 2. Annualized Yield (assuming cash-secured collateral)
                    raw_yield = mid / strike if strike > 0 else 0.0
                    ann_yield = raw_yield * (365.0 / dte) if dte > 0 else 0.0
                    
                    deltas.append(delta)
                    net_bases.append(net_basis)
                    ann_yields.append(ann_yield)
                    
                display_df['mid'] = (display_df['bid'] + display_df['ask']) / 2.0
                display_df['delta'] = deltas
                display_df['net_basis'] = net_bases
                display_df['ann_yield'] = ann_yields
                display_df['impliedVolatility'] = display_df['impliedVolatility'] * 100.0
                
                # Order columns
                display_cols = ['strike', 'bid', 'ask', 'mid', 'impliedVolatility', 'delta', 'net_basis', 'ann_yield']
                display_df = display_df[display_cols]
                
                # Display
                print(display_df.to_string(index=False, formatters={
                    'strike': lambda x: f"${x:.2f}",
                    'bid': lambda x: f"${x:.2f}" if x > 0 else "N/A",
                    'ask': lambda x: f"${x:.2f}" if x > 0 else "N/A",
                    'mid': lambda x: f"${x:.2f}" if x > 0 else "N/A",
                    'impliedVolatility': lambda x: f"{x:.1f}%",
                    'delta': lambda x: f"{x:.3f}",
                    'net_basis': lambda x: f"${x:.2f}",
                    'ann_yield': lambda x: f"{x*100:.1f}%"
                }))
                print()
                
            except Exception as e:
                print(f"Error analyzing chain for expiration {exp}: {e}\n")
                
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False

def main():
    parser = argparse.ArgumentParser(description="Generalized Black-Scholes Options Greeks & Yield Analyzer.")
    parser.add_argument("ticker", help="The ticker symbol to analyze (e.g. AAPL, EXPE, URBN).")
    parser.add_argument("-t", "--type", choices=['put', 'call'], default='put', help="Option contract type (default: put).")
    parser.add_argument("--min-dte", type=int, default=20, help="Minimum days to expiration (default: 20).")
    parser.add_argument("--max-dte", type=int, default=55, help="Maximum days to expiration (default: 55).")
    parser.add_argument("-r", type=float, default=0.05, help="Risk-free rate as a decimal (default: 0.05).")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print complete error traceback if an exception is thrown.")
    
    if len(sys.argv) == 1:
        ticker = input("Enter Ticker to Analyze Options: ").strip()
        if ticker:
            analyze_options(ticker)
        else:
            parser.print_help()
    else:
        args = parser.parse_args()
        analyze_options(args.ticker, args.min_dte, args.max_dte, args.type, args.r, args.verbose)

if __name__ == "__main__":
    main()
