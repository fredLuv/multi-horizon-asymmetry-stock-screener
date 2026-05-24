#!/usr/bin/env python3
# generate_asymmetry_charts.py
# Generates high-fidelity institutional-grade dark-mode charts for top non-biotech asymmetric assets.

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# Define absolute paths
artifacts_dir = "/Users/fred/.gemini/antigravity/brain/9b6cd57c-1c8b-4d89-9e6b-8272e3a36d04"
prices_csv_path = 'outputs/daily_prices.csv'
asymmetric_csv_path = 'outputs/asymmetric_stocks.csv'

# Set up matplotlib style for premium dark mode
plt.rcParams['figure.facecolor'] = '#0b0f19'
plt.rcParams['axes.facecolor'] = '#0d1321'
plt.rcParams['text.color'] = '#f1f5f9'
plt.rcParams['axes.labelcolor'] = '#cbd5e1'
plt.rcParams['xtick.color'] = '#94a3b8'
plt.rcParams['ytick.color'] = '#94a3b8'
plt.rcParams['axes.edgecolor'] = '#334155'
plt.rcParams['grid.color'] = '#1e293b'
plt.rcParams['grid.linestyle'] = '--'
plt.rcParams['grid.alpha'] = 0.5

# Exclude biotech symbols that are hard to understand or volatile drug developers
BIOTECH_BLACKLIST = {'DRUG', 'ABVX', 'RGC', 'AHR_BIOTECH_FALSE_ALARM'} # AHR is American Healthcare REIT, which we keep!

def main():
    print("[1/3] Loading asymmetry data and daily price matrices...")
    if not os.path.exists(prices_csv_path) or not os.path.exists(asymmetric_csv_path):
        print("[!] Missing daily prices or asymmetry screener outputs. Run screener first.")
        return
        
    df_results = pd.read_csv(asymmetric_csv_path)
    prices_df = pd.read_csv(prices_csv_path, index_col=0, parse_dates=True)
    
    # Filter out blacklisted biotech tickers
    df_clean = df_results[~df_results['Ticker'].isin(BIOTECH_BLACKLIST)]
    
    # Select top 5 non-biotech assets by QAS 3M Score
    top_5 = df_clean.head(5)
    print("\nSelected Top 5 Non-Biotech Asymmetric Leaders:")
    for idx, row in top_5.iterrows():
        print(f"  - {row['Ticker']}: Price ${row['Price']:.2f} | GPR {row['Gain_to_Pain_3M']:.2f} | AR {row['Asymmetry_Ratio_3M']:.2f}x | QAS {row['Quant_Asymmetry_Score_3M']:.4f}")
        
    print("\n[2/3] Generating custom dual-panel quantitative charts...")
    os.makedirs(artifacts_dir, exist_ok=True)
    
    for idx, row in top_5.iterrows():
        ticker = row['Ticker']
        price = row['Price']
        mean_3m = row['Mean_3M_Return']
        p10_3m = row['P10_3M_Return']
        p90_3m = row['P90_3M_Return']
        ar_3m = row['Asymmetry_Ratio_3M']
        gpr_3m = row['Gain_to_Pain_3M']
        qas_3m = row['Quant_Asymmetry_Score_3M']
        skew_3m = row['Skewness_3M']
        
        # Get historical price series
        if ticker not in prices_df.columns:
            print(f"  [!] Ticker {ticker} missing from prices cache. Skipping...")
            continue
            
        ticker_prices = prices_df[ticker].dropna()
        ticker_returns = ticker_prices.pct_change(63).dropna().values
        
        # Initialize canvas
        fig = plt.figure(figsize=(15, 6), dpi=120)
        gs = gridspec.GridSpec(1, 2, width_ratios=[1.2, 1.0])
        
        # ----------------- PANEL 1: Historical Prices (Left) -----------------
        ax1 = plt.subplot(gs[0])
        ax1.plot(ticker_prices.index, ticker_prices.values, color='#00f2fe', linewidth=2, label='Adj Close Price')
        
        # Style price chart
        ax1.set_title(f"{ticker} Historical Price Series (2.5 Years Daily)", fontsize=13, fontweight='bold', pad=15, color='#38bdf8')
        ax1.set_ylabel("Price ($)", fontsize=11)
        ax1.grid(True)
        ax1.legend(loc='upper left', framealpha=0.2)
        ax1.tick_params(axis='x', rotation=30)
        
        # Annotate last price
        ax1.annotate(f"${ticker_prices.iloc[-1]:.2f}", 
                     xy=(ticker_prices.index[-1], ticker_prices.iloc[-1]),
                     xytext=(ticker_prices.index[-1] - pd.Timedelta(days=90), ticker_prices.iloc[-1] * 1.05),
                     arrowprops=dict(arrowstyle="->", color='#38bdf8', lw=1.5),
                     fontsize=11, fontweight='bold', color='#00f2fe',
                     bbox=dict(boxstyle="round,pad=0.3", fc="#0d1321", ec="#334155", lw=1))

        # ----------------- PANEL 2: Return Distribution Histogram (Right) -----------------
        ax2 = plt.subplot(gs[1])
        
        # Plot histogram of rolling 3-month returns
        n, bins, patches = ax2.hist(ticker_returns, bins=35, density=True, color='#1e293b', edgecolor='#334155', alpha=0.8)
        
        # Color coding bins based on sign
        for patch, left_bin in zip(patches, bins[:-1]):
            if left_bin >= 0:
                patch.set_facecolor('#10b981') # Emerald green for positive
                patch.set_alpha(0.65)
            else:
                patch.set_facecolor('#f43f5e') # Red for negative
                patch.set_alpha(0.5)
                
        # Draw vertical quantiles & mean
        ax2.axvline(mean_3m, color='#f59e0b', linestyle='-', linewidth=2, label=f'Mean: {mean_3m*100:+.1f}%')
        ax2.axvline(p10_3m, color='#ef4444', linestyle='--', linewidth=1.8, label=f'P10 Down: {p10_3m*100:+.1f}%')
        ax2.axvline(p90_3m, color='#10b981', linestyle='--', linewidth=1.8, label=f'P90 Up: {p90_3m*100:+.1f}%')
        
        # Fill asymmetric upside region
        ax2.axvspan(mean_3m, p90_3m, color='#0284c7', alpha=0.15, label='Asymmetric Upside')
        
        # Style return distribution chart
        ax2.set_title(f"{ticker} 3M Return Distribution & Asymmetry", fontsize=13, fontweight='bold', pad=15, color='#a78bfa')
        ax2.set_xlabel("3-Month Return Rate", fontsize=11)
        ax2.set_ylabel("Density", fontsize=11)
        ax2.grid(True)
        ax2.legend(loc='upper right', framealpha=0.2)
        
        # Add textbox with core quantitative statistics
        stats_text = (
            f"Gain-to-Pain (GPR): {gpr_3m:.2f}\n"
            f"Asymmetry Ratio (AR): {ar_3m:.2f}x\n"
            f"QAS 3M Score: {qas_3m:.4f}\n"
            f"Skewness (3M): {skew_3m:.3f}\n"
            f"P10-to-Mean Risk: {abs(mean_3m - p10_3m)*100:.1f}%\n"
            f"Mean-to-P90 Gain: {(p90_3m - mean_3m)*100:.1f}%"
        )
        ax2.text(0.05, 0.95, stats_text, transform=ax2.transAxes, fontsize=10,
                 verticalalignment='top', bbox=dict(boxstyle="round,pad=0.5", fc="#0b0f19", ec="#334155", alpha=0.9))

        plt.tight_layout()
        
        # Save both to local outputs and directly to artifacts directory
        output_filename = f"{ticker.lower()}_asymmetry.png"
        local_output_path = os.path.join("outputs", output_filename)
        artifact_output_path = os.path.join(artifacts_dir, output_filename)
        
        plt.savefig(local_output_path, facecolor='#0b0f19', edgecolor='none')
        plt.savefig(artifact_output_path, facecolor='#0b0f19', edgecolor='none')
        plt.close()
        print(f"  [+] Generated and saved charts for {ticker} -> {artifact_output_path}")

    print("\n[3/3] Chart generation complete. All assets successfully exported to artifact space!")

if __name__ == "__main__":
    main()
