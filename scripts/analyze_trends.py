#!/usr/bin/env python3
import sys
import argparse
import yfinance as yf
import pandas as pd

def extract_3y_trends(ticker_symbol):
    ticker_symbol = ticker_symbol.upper()
    print(f"Downloading historical financials for {ticker_symbol} from Yahoo Finance...")
    
    try:
        ticker = yf.Ticker(ticker_symbol)
        
        financials = ticker.financials
        cashflow = ticker.cashflow
        balance_sheet = ticker.balance_sheet
        
        if financials.empty or cashflow.empty:
            # Try to fetch history to check if symbol exists
            hist = ticker.history(period="1d")
            if hist.empty:
                print(f"Error: Ticker '{ticker_symbol}' not found or has no active data.")
                return None
            print(f"Error: Annual financial statements not available for '{ticker_symbol}'.")
            return None
            
        # Get up to the last 3 fiscal years (columns)
        years = financials.columns[:3]
        
        data_years = []
        for yr in years:
            year_str = str(yr)[:10]  # Format as YYYY-MM-DD
            
            try:
                # 1. Revenue & Net Income
                rev = financials.loc['Total Revenue', yr]
                net_income = financials.loc['Net Income', yr]
                net_margin = (net_income / rev) * 100.0 if rev > 0 else 0.0
                
                # 2. Operating Cash Flow & CapEx to get FCF
                ocf = cashflow.loc['Operating Cash Flow', yr]
                capex = 0.0
                for label in ['Capital Expenditure', 'Capital Expenditures']:
                    if label in cashflow.index:
                        capex = abs(cashflow.loc[label, yr])
                        break
                
                fcf = ocf - capex
                fcf_margin = (fcf / rev) * 100.0 if rev > 0 else 0.0
                
                # 3. Cash Position
                cash = 0.0
                for label in ['Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments', 'Cash And Short Term Investments']:
                    if label in balance_sheet.index and yr in balance_sheet.columns:
                        cash = balance_sheet.loc[label, yr]
                        break
                
                # 4. Debt Position
                debt = 0.0
                for label in ['Total Debt', 'Long Term Debt', 'Long Term Debt Total']:
                    if label in balance_sheet.index and yr in balance_sheet.columns:
                        debt = balance_sheet.loc[label, yr]
                        break
                        
                net_cash = cash - debt
                
                data_years.append({
                    "Year": year_str,
                    "Revenue": rev,
                    "Net Income": net_income,
                    "Net Margin (%)": net_margin,
                    "FCF": fcf,
                    "FCF Margin (%)": fcf_margin,
                    "Cash": cash,
                    "Debt": debt,
                    "Net Cash": net_cash
                })
            except Exception as e:
                # Proceed even if a specific line item fails for one year
                continue
                
        if not data_years:
            print(f"Error: Failed to parse required annual line items for {ticker_symbol}.")
            return None
            
        return data_years
    except Exception as e:
        print(f"An error occurred fetching {ticker_symbol}: {e}")
        return None

def analyze_trend_portfolio(tickers):
    for t in tickers:
        data = extract_3y_trends(t)
        if not data:
            print(f"Skipping {t.upper()} due to parsing error.\n")
            continue
            
        print("\n" + "=" * 85)
        print(f" 3-YEAR TRAILING ANNUAL HISTORICAL FINANCIAL TRENDS: {t.upper()}")
        print("=" * 85)
        print(f"{'Fiscal Year':<12} | {'Revenue':<10} | {'Net Margin':<10} | {'FCF':<10} | {'FCF Margin':<10} | {'Net Cash/Debt':<18}")
        print("-" * 85)
        
        # Sort chronologically (oldest to newest)
        for yr_data in reversed(data):
            rev_b = yr_data["Revenue"] / 1e9
            fcf_m = yr_data["FCF"] / 1e6
            net_c_m = yr_data["Net Cash"] / 1e6
            
            # Format cash/debt label
            net_cash_label = f"${net_c_m:+.1f}M"
            
            print(f"{yr_data['Year']:<12} | ${rev_b:<8.2f}B | {yr_data['Net Margin (%)']:<8.2f}% | ${fcf_m:<8.1f}M | {yr_data['FCF Margin (%)']:<8.2f}% | {net_cash_label:<18}")
        print("=" * 85 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Generalized 3-Year Trailing Annual Trend Financial Checker.")
    parser.add_argument("tickers", nargs="+", help="One or more ticker symbols to analyze (e.g., URBN EXPE DECK CROX).")
    
    if len(sys.argv) == 1:
        ticker_input = input("Enter ticker symbols separated by spaces: ").strip()
        if ticker_input:
            tickers = ticker_input.split()
            analyze_trend_portfolio(tickers)
        else:
            parser.print_help()
    else:
        args = parser.parse_args()
        analyze_trend_portfolio(args.tickers)

if __name__ == "__main__":
    main()
