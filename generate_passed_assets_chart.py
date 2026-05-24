#!/usr/bin/env python3
# generate_passed_assets_chart.py
# Generates a premium dark-mode quantitative visualization comparing the final 8 asymmetric value leaders.

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# Define absolute paths
artifacts_dir = "/Users/fred/.gemini/antigravity/brain/9b6cd57c-1c8b-4d89-9e6b-8272e3a36d04"
prices_csv_path = 'outputs/daily_prices.csv'
passed_csv_path = 'outputs/fcf_filtered_asymmetric_stocks.csv'

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

# Premium Color Palette for the 8 assets
ASSET_COLORS = {
    'AHR': '#00f2fe',    # Electric Cyan
    'SENEA': '#f59e0b',  # Golden Yellow (Buffett Bargain!)
    'BNY': '#a78bfa',    # Laser Violet
    'TIGO': '#10b981',   # Emerald Green (Buffett Bargain!)
    'JCI': '#635bff',    # Stripe Purple
    'IAG': '#f43f5e',    # Coral Rose (Buffett Bargain!)
    'BTI': '#e2e8f0',    # Titanium White
    'AEM': '#fb7185'     # Soft Pink
}

def main():
    print("[1/3] Loading data for final 8 asymmetric leaders...")
    if not os.path.exists(prices_csv_path) or not os.path.exists(passed_csv_path):
        print("[!] Missing daily prices or filtered asymmetric stocks. Run fundamental filter first.")
        return
        
    df_passed = pd.read_csv(passed_csv_path)
    prices_df = pd.read_csv(prices_csv_path, index_col=0, parse_dates=True)
    
    tickers = df_passed['Ticker'].tolist()
    print(f"Generating comparison graphs for: {tickers}")
    
    # Initialize figure
    fig = plt.figure(figsize=(16, 7), dpi=120)
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.3, 1.0])
    
    # ----------------- PANEL 1: Normalized Cumulative Returns (Left) -----------------
    ax1 = plt.subplot(gs[0])
    
    for t in tickers:
        if t in prices_df.columns:
            series = prices_df[t].dropna()
            # Normalize series to start at 100
            normalized_series = (series / series.iloc[0]) * 100
            color = ASSET_COLORS.get(t, '#94a3b8')
            linewidth = 2.5 if t in ['SENEA', 'TIGO', 'IAG'] else 1.5
            alpha = 1.0 if t in ['SENEA', 'TIGO', 'IAG'] else 0.7
            linestyle = '-' if t in ['SENEA', 'TIGO', 'IAG'] else '--'
            
            ax1.plot(normalized_series.index, normalized_series.values, 
                     color=color, linewidth=linewidth, alpha=alpha, 
                     linestyle=linestyle, label=f"{t} (Normalized)")
            
    ax1.set_title("Historical Compounding Comparison (Normalized to 100)", fontsize=14, fontweight='bold', pad=15, color='#38bdf8')
    ax1.set_ylabel("Normalized Growth (Start = 100)", fontsize=11)
    ax1.grid(True)
    ax1.legend(loc='upper left', framealpha=0.2, ncol=2)
    ax1.tick_params(axis='x', rotation=25)
    
    # ----------------- PANEL 2: Valuation vs. Asymmetry Mapping (Right) -----------------
    ax2 = plt.subplot(gs[1])
    
    # Plot scatter
    for idx, row in df_passed.iterrows():
        t = row['Ticker']
        qas = row['Quant_Asymmetry_Score_3M']
        p_fcf = row['P_FCF']
        color = ASSET_COLORS.get(t, '#94a3b8')
        
        # Draw scatter points
        marker = '★' if t in ['SENEA', 'TIGO', 'IAG'] else 'o'
        size = 280 if t in ['SENEA', 'TIGO', 'IAG'] else 140
        ax2.scatter(qas, p_fcf, color=color, s=size, edgecolors='#cbd5e1', zorder=5, alpha=0.9)
        
        # Label points
        offset_y = 1.5 if p_fcf < 35 else -1.5
        ax2.annotate(t, xy=(qas, p_fcf), xytext=(qas + 5, p_fcf + offset_y),
                     fontsize=11, fontweight='bold', color=color,
                     arrowprops=dict(arrowstyle="->", color='#334155', lw=0.8, alpha=0.5))
                     
    # Shade Buffett bargain zone: P/FCF < 10x
    ax2.axhspan(0, 10, color='#10b981', alpha=0.1, label='Buffett Bargain Zone (P/FCF < 10x)')
    ax2.axhline(10, color='#10b981', linestyle=':', alpha=0.5)
    
    ax2.set_title("Valuation Matrix: P/FCF Multiple vs. Asymmetry Score", fontsize=14, fontweight='bold', pad=15, color='#a78bfa')
    ax2.set_xlabel("Quant Asymmetry Score (3M QAS)", fontsize=11)
    ax2.set_ylabel("Price-to-Free Cash Flow Multiple (P/FCF)", fontsize=11)
    ax2.set_ylim(0, 55)
    ax2.grid(True)
    ax2.legend(loc='upper right', framealpha=0.2)
    
    # Add summary text box
    summary_text = (
        "★ Buffett Bargains (P/FCF < 10x):\n"
        "  - SENEA: 6.30x FCF (High Compounding Food Packager)\n"
        "  - TIGO: 7.99x FCF (Defensive LatAm Telecom Goliath)\n"
        "  - IAG: 9.83x FCF (Gold Producer with Cash Surplus)"
    )
    ax2.text(0.05, 0.25, summary_text, transform=ax2.transAxes, fontsize=10,
             verticalalignment='top', bbox=dict(boxstyle="round,pad=0.6", fc="#0b0f19", ec="#334155", alpha=0.9))

    plt.tight_layout()
    
    # Save the output images
    output_filename = "passed_assets_comparison.png"
    local_output_path = os.path.join("outputs", output_filename)
    artifact_output_path = os.path.join(artifacts_dir, output_filename)
    
    plt.savefig(local_output_path, facecolor='#0b0f19', edgecolor='none')
    plt.savefig(artifact_output_path, facecolor='#0b0f19', edgecolor='none')
    plt.close()
    print(f"[+] Successfully generated comparison charts -> {artifact_output_path}")

if __name__ == "__main__":
    main()
