import unittest

from qrt_platform.stock_picker import _parse_nasdaq_listed, _parse_other_listed


NASDAQ_SAMPLE = """Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares
AAPL|Apple Inc. Common Stock|Q|N|N|100|N|N
QQQ|Invesco QQQ Trust Series 1|Q|N|N|100|Y|N
TEST|Test Corp|Q|Y|N|100|N|N
File Creation Time: 02202026
"""

OTHER_SAMPLE = """ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol
IBM|International Business Machines Common Stock|N|IBM|N|100|N|IBM
SPY|SPDR S&P 500 ETF TRUST|P|SPY|Y|100|N|SPY
ABC$|Weird Name|N|ABC$|N|100|N|ABC$
BRK.B|Berkshire Hathaway Class B Common Stock|N|BRK.B|N|100|N|BRKB
File Creation Time: 02202026
"""


class StockPickerUniverseTests(unittest.TestCase):
    def test_parse_nasdaq_filters_etf_and_test_issue(self) -> None:
        symbols = _parse_nasdaq_listed(NASDAQ_SAMPLE)
        self.assertIn("AAPL", symbols)
        self.assertNotIn("QQQ", symbols)
        self.assertNotIn("TEST", symbols)

    def test_parse_other_filters_and_normalizes(self) -> None:
        symbols = _parse_other_listed(OTHER_SAMPLE, include_nyse_arca=True, include_nyse_american=True)
        self.assertIn("IBM", symbols)
        self.assertIn("BRK-B", symbols)
        self.assertNotIn("SPY", symbols)  # ETF filtered here; SPY added by universe fetch wrapper.


if __name__ == "__main__":
    unittest.main()
