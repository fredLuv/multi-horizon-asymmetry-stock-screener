#!/usr/bin/env python3
import sys
import argparse
import yfinance as yf

def analyze_ticker(ticker_symbol, verbose=False):
    ticker_symbol = ticker_symbol.upper()
    print(f"Downloading financial data for {ticker_symbol} from Yahoo Finance...")
    
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        
        if not info or 'regularMarketPrice' not in info and 'previousClose' not in info:
            # Try to fetch history to check if the ticker exists
            hist = ticker.history(period="1d")
            if hist.empty:
                print(f"Error: Ticker '{ticker_symbol}' not found or has no active data.")
                return False
        
        # Extract Key Metrics
        price = info.get('regularMarketPrice') or info.get('previousClose') or info.get('currentPrice')
        mcap = info.get('marketCap')
        ev = info.get('enterpriseValue')
        
        cash = info.get('totalCash')
        debt = info.get('totalDebt')
        
        pe_trailing = info.get('trailingPE')
        pe_forward = info.get('forwardPE')
        peg = info.get('pegRatio')
        
        ebitda = info.get('ebitda')
        fcf = info.get('freeCashflow')
        operating_cashflow = info.get('operatingCashflow')
        
        rev = info.get('totalRevenue')
        gross_margin = info.get('grossMargins')
        ebitda_margin = info.get('ebitdaMargins')
        net_margin = info.get('profitMargins')
        
        # Title Card
        name = info.get('longName', ticker_symbol)
        sector = info.get('sector', 'N/A')
        industry = info.get('industry', 'N/A')
        
        print("\n" + "=" * 60)
        print(f" FINANCIAL ANALYSIS DASHBOARD: {ticker_symbol}")
        print(f" {name}")
        print(f" Sector: {sector} | Industry: {industry}")
        print("=" * 60)
        
        # 1. Market & Balance Sheet Pricing
        print(f"Current Stock Price:   ${price:.2f}" if price else "Current Price:          N/A")
        print(f"Market Capitalization: ${mcap/1e9:.3f}B" if mcap else "Market Cap:            N/A")
        print(f"Enterprise Value (EV): ${ev/1e9:.3f}B" if ev else "Enterprise Value (EV):  N/A")
        
        if cash is not None and debt is not None:
            net_debt = debt - cash
            net_debt_str = f"${net_debt/1e6:+.2f}M"
            print(f"Balance Sheet Cash:    ${cash/1e6:.2f}M | Debt: ${debt/1e6:.2f}M (Net Debt: {net_debt_str})")
        else:
            print(f"Balance Sheet Cash:    ${cash/1e6:.2f}M" if cash else "Cash: N/A")
            print(f"Balance Sheet Debt:    ${debt/1e6:.2f}M" if debt else "Debt: N/A")
            
        print("-" * 60)
        
        # 2. Valuation Multiples
        print(f"Trailing P/E:          {pe_trailing:.2f}x" if pe_trailing else "Trailing P/E:          N/A")
        print(f"Forward P/E:           {pe_forward:.2f}x" if pe_forward else "Forward P/E:           N/A")
        print(f"PEG Ratio:             {peg:.2f}x" if peg else "PEG Ratio:             N/A")
        
        if ebitda and ev:
            ev_ebitda = ev / ebitda
            print(f"EV/EBITDA Multiple:    {ev_ebitda:.2f}x")
        else:
            print("EV/EBITDA Multiple:    N/A")
            
        if fcf and mcap:
            p_fcf = mcap / fcf
            print(f"P/FCF Multiple:        {p_fcf:.2f}x")
        elif operating_cashflow and mcap:
            p_ocf = mcap / operating_cashflow
            print(f"P/OCF Multiple:        {p_ocf:.2f}x (FCF not available)")
        else:
            print("P/FCF Multiple:        N/A")
            
        print("-" * 60)
        
        # 3. Core Income Statement & Cash Flows
        print(f"Revenue (TTM):         ${rev/1e9:.3f}B" if rev else "Revenue (TTM):         N/A")
        print(f"EBITDA (TTM):          ${ebitda/1e6:.2f}M" if ebitda else "EBITDA (TTM):          N/A")
        print(f"Free Cash Flow (TTM):  ${fcf/1e6:.2f}M" if fcf else "Free Cash Flow (TTM):  N/A")
        
        print("-" * 60)
        
        # 4. Margin Profiles
        print("Profitability Margins:")
        print(f"  - Gross Margin:      {gross_margin*100:.2f}%" if gross_margin else "  - Gross Margin:      N/A")
        print(f"  - EBITDA Margin:     {ebitda_margin*100:.2f}%" if ebitda_margin else "  - EBITDA Margin:     N/A")
        print(f"  - Net profit Margin: {net_margin*100:.2f}%" if net_margin else "  - Net profit Margin: N/A")
        
        print("=" * 60 + "\n")
        return True
        
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False

def main():
    parser = argparse.ArgumentParser(description="Generalized Stock Analysis Script utilizing yfinance.")
    parser.add_argument("ticker", help="The ticker symbol to analyze (e.g., AAPL, URBN, AGX).")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print complete error traceback if an exception is thrown.")
    
    # If no arguments provided in CLI, ask user interactively
    if len(sys.argv) == 1:
        ticker = input("Enter Stock Ticker to Analyze: ").strip()
        if ticker:
            analyze_ticker(ticker)
        else:
            parser.print_help()
    else:
        args = parser.parse_args()
        analyze_ticker(args.ticker, args.verbose)

if __name__ == "__main__":
    main()
