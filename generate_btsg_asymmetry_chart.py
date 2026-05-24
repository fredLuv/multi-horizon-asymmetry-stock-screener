#!/usr/bin/env python3
# generate_btsg_asymmetry_chart.py
# Generates high-fidelity institutional-grade dark-mode asymmetry charts specifically for BTSG.

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.stats import skew

# Define absolute paths
artifacts_dir = "/Users/fred/.gemini/antigravity/brain/9b6cd57c-1c8b-4d89-9e6b-8272e3a36d04"
prices_csv_path = 'outputs/daily_prices.csv'

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

def main():
    print("[1/2] Loading daily price matrix for BTSG...")
    if not os.path.exists(prices_csv_path):
        print("[!] Missing daily prices CSV. Run screener first.")
        return
        
    prices_df = pd.read_csv(prices_csv_path, index_col=0, parse_dates=True)
    
    if 'BTSG' not in prices_df.columns:
        print("[!] BTSG is missing from daily_prices.csv columns.")
        return
        
    ticker_prices = prices_df['BTSG'].dropna()
    print(f"Loaded {len(ticker_prices)} daily price data points for BTSG.")
    
    # Calculate rolling 3-month returns (63 trading days)
    ticker_returns = ticker_prices.pct_change(63).dropna().values
    
    mean_3m = float(np.mean(ticker_returns))
    p10_3m = float(np.percentile(ticker_returns, 10))
    p90_3m = float(np.percentile(ticker_returns, 90))
    
    # Calculate GPR
    upside_sum = np.sum(ticker_returns[ticker_returns > 0])
    downside_sum = abs(np.sum(ticker_returns[ticker_returns < 0]))
    gpr_3m = float(upside_sum / max(downside_sum, 1e-4))
    
    # Calculate Asymmetry Ratio
    denom = mean_3m - p10_3m
    if denom < 1e-6:
        denom = 1e-6
    ar_3m = (p90_3m - mean_3m) / denom
    
    # Calculate Skewness
    skew_3m = float(skew(ticker_returns))
    
    # Calculate Dampened QAS Score
    qas_3m = mean_3m * ar_3m * np.log1p(gpr_3m)
    
    print("\nCalculated BTSG 3-Month Quant Metrics:")
    print(f"  - Last Price: ${ticker_prices.iloc[-1]:.2f}")
    print(f"  - Mean Return: {mean_3m*100:+.2f}%")
    print(f"  - P10 Downside: {p10_3m*100:+.2f}%")
    print(f"  - P90 Upside: {p90_3m*100:+.2f}%")
    print(f"  - Gain-to-Pain Ratio (GPR): {gpr_3m:.2f}")
    print(f"  - Asymmetry Ratio (AR): {ar_3m:.2f}x")
    print(f"  - Skewness: {skew_3m:.3f}")
    print(f"  - Dampened QAS Score: {qas_3m:.4f}")
    
    print("\n[2/2] Generating custom dual-panel quantitative asymmetry chart...")
    fig = plt.figure(figsize=(15, 6), dpi=120)
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.2, 1.0])
    
    # ----------------- PANEL 1: Historical Prices (Left) -----------------
    ax1 = plt.subplot(gs[0])
    # Use BrightSpring Gold theme color accent
    ax1.plot(ticker_prices.index, ticker_prices.values, color='#f2a900', linewidth=2.2, label='BTSG Adj Close Price')
    
    # Style price chart
    ax1.set_title("BrightSpring (BTSG) Historical Price Series (Post-IPO)", fontsize=13, fontweight='bold', pad=15, color='#38bdf8')
    ax1.set_ylabel("Price ($)", fontsize=11)
    ax1.grid(True)
    ax1.legend(loc='upper left', framealpha=0.2)
    ax1.tick_params(axis='x', rotation=30)
    
    # Annotate last price
    ax1.annotate(f"${ticker_prices.iloc[-1]:.2f}", 
                 xy=(ticker_prices.index[-1], ticker_prices.iloc[-1]),
                 xytext=(ticker_prices.index[-1] - pd.Timedelta(days=75), ticker_prices.iloc[-1] * 0.85),
                 arrowprops=dict(arrowstyle="->", color='#38bdf8', lw=1.5),
                 fontsize=11, fontweight='bold', color='#f2a900',
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
    ax2.set_title("BTSG 3M Return Distribution & Asymmetry", fontsize=13, fontweight='bold', pad=15, color='#a78bfa')
    ax2.set_xlabel("3-Month Return Rate", fontsize=11)
    ax2.set_ylabel("Density", fontsize=11)
    ax2.grid(True)
    ax2.legend(loc='upper right', framealpha=0.2)
    
    # Add textbox with core quantitative statistics
    stats_text = (
        f"Gain-to-Pain (GPR): {gpr_3m:.2f}\n"
        f"Asymmetry Ratio (AR): {ar_3m:.2f}x\n"
        f"Dampened QAS Score: {qas_3m:.4f}\n"
        f"Skewness (3M): {skew_3m:.3f}\n"
        f"P10-to-Mean Risk: {abs(mean_3m - p10_3m)*100:.1f}%\n"
        f"Mean-to-P90 Gain: {(p90_3m - mean_3m)*100:.1f}%"
    )
    ax2.text(0.05, 0.95, stats_text, transform=ax2.transAxes, fontsize=10,
             verticalalignment='top', bbox=dict(boxstyle="round,pad=0.5", fc="#0b0f19", ec="#334155", alpha=0.9))

    plt.tight_layout()
    
    # Save both to local outputs and directly to artifacts directory
    output_filename = "btsg_asymmetry.png"
    local_output_path = os.path.join("outputs", output_filename)
    artifact_output_path = os.path.join(artifacts_dir, output_filename)
    
    os.makedirs(os.path.dirname(local_output_path), exist_ok=True)
    os.makedirs(os.path.dirname(artifact_output_path), exist_ok=True)
    
    plt.savefig(local_output_path, facecolor='#0b0f19', edgecolor='none')
    plt.savefig(artifact_output_path, facecolor='#0b0f19', edgecolor='none')
    plt.close()
    print(f"[+] Successfully generated and saved BTSG asymmetry chart -> {artifact_output_path}")

if __name__ == "__main__":
    main()
