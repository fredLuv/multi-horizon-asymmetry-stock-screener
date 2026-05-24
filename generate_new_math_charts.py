#!/usr/bin/env python3
# generate_new_math_charts.py
# Generates a premium dark-mode quantitative visualization comparing the final 4 elite new math asymmetric leaders.

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# Define absolute paths
artifacts_dir = "/Users/fred/.gemini/antigravity/brain/9b6cd57c-1c8b-4d89-9e6b-8272e3a36d04"
prices_csv_path = 'outputs/daily_prices.csv'
passed_csv_path = 'outputs/new_math_filtered_asymmetric_stocks.csv'

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

# Premium Color Palette for the 4 assets
ASSET_COLORS = {
    'SEZL': '#00f2fe',    # Electric Cyan
    'ROOT': '#f59e0b',    # Golden Orange (Insurtech Bargain!)
    'DAVE': '#a78bfa',    # Laser Violet (Fintech Goliath!)
    'AHR': '#10b981'      # Emerald Green (Healthcare REIT!)
}

def main():
    print("[1/3] Loading data for final 4 new math asymmetric leaders...")
    if not os.path.exists(prices_csv_path) or not os.path.exists(passed_csv_path):
        print("[!] Missing daily prices or new math stocks. Run audit filter first.")
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
            linewidth = 2.5 if t in ['ROOT', 'SEZL'] else 1.8
            alpha = 1.0 if t in ['ROOT', 'SEZL'] else 0.8
            linestyle = '-' if t in ['ROOT', 'SEZL'] else '--'
            
            ax1.plot(normalized_series.index, normalized_series.values, 
                     color=color, linewidth=linewidth, alpha=alpha, 
                     linestyle=linestyle, label=f"{t} (Normalized)")
            
    ax1.set_title("New Math Leaders compounding comparison (Normalized to 100)", fontsize=14, fontweight='bold', pad=15, color='#38bdf8')
    ax1.set_ylabel("Normalized Growth (Start = 100)", fontsize=11)
    ax1.grid(True)
    ax1.legend(loc='upper left', framealpha=0.2)
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
        marker = '★' if t in ['ROOT', 'AHR'] else 'o'
        size = 280 if t in ['ROOT', 'AHR'] else 140
        ax2.scatter(qas, p_fcf, color=color, s=size, edgecolors='#cbd5e1', zorder=5, alpha=0.9)
        
        # Label points
        offset_y = 1.5 if p_fcf < 35 else -1.5
        ax2.annotate(t, xy=(qas, p_fcf), xytext=(qas + 0.02, p_fcf + offset_y),
                     fontsize=11, fontweight='bold', color=color,
                     arrowprops=dict(arrowstyle="->", color='#334155', lw=0.8, alpha=0.5))
                     
    # Shade deep value zone: P/FCF < 30x
    ax2.axhspan(0, 30, color='#10b981', alpha=0.1, label='Premium Value Zone (P/FCF < 30x)')
    ax2.axhline(30, color='#10b981', linestyle=':', alpha=0.5)
    
    ax2.set_title("New QAS Formula vs. P/FCF Valuation Matrix", fontsize=14, fontweight='bold', pad=15, color='#a78bfa')
    ax2.set_xlabel("Quant Asymmetry Score (Mean * AR * ln(1+GPR))", fontsize=11)
    ax2.set_ylabel("Price-to-Free Cash Flow Multiple (P/FCF)", fontsize=11)
    ax2.set_ylim(0, 55)
    ax2.set_xlim(df_passed['Quant_Asymmetry_Score_3M'].min() - 0.2, df_passed['Quant_Asymmetry_Score_3M'].max() + 0.2)
    ax2.grid(True)
    ax2.legend(loc='upper right', framealpha=0.2)
    
    # Add summary text box
    summary_text = (
        "★ Elite Asymmetric Leaders:\n"
        "  - ROOT: 5.09x FCF (Insurtech Turnaround Monster!)\n"
        "  - AHR : 26.98x FCF (Rock-Solid Healthcare REIT)\n"
        "  - DAVE: 33.88x FCF (Profitable Fintech Banking app)\n"
        "  - SEZL: 47.65x FCF (High-Growth BNPL Breakout Leader)"
    )
    ax2.text(0.05, 0.25, summary_text, transform=ax2.transAxes, fontsize=10,
             verticalalignment='top', bbox=dict(boxstyle="round,pad=0.6", fc="#0b0f19", ec="#334155", alpha=0.9))

    plt.tight_layout()
    
    # Save the output images
    output_filename = "new_math_passed_comparison.png"
    local_output_path = os.path.join("outputs", output_filename)
    artifact_output_path = os.path.join(artifacts_dir, output_filename)
    
    plt.savefig(local_output_path, facecolor='#0b0f19', edgecolor='none')
    plt.savefig(artifact_output_path, facecolor='#0b0f19', edgecolor='none')
    plt.close()
    print(f"[+] Successfully generated new math comparison charts -> {artifact_output_path}")

if __name__ == "__main__":
    main()
