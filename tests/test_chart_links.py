import unittest

from qrt_platform import build_chart_link, build_chart_links


class ChartLinkTests(unittest.TestCase):
    def test_yahoo_chart_link(self) -> None:
        link = build_chart_link("AAPL", provider="yahoo")
        self.assertEqual(link.ticker, "AAPL")
        self.assertIn("finance.yahoo.com/quote/AAPL/chart", link.url)

    def test_tradingview_chart_link(self) -> None:
        link = build_chart_link("MSFT", provider="tradingview")
        self.assertIn("tradingview.com/symbols/MSFT", link.url)

    def test_batch_chart_links(self) -> None:
        links = build_chart_links(["AAPL", "NVDA"])
        self.assertEqual(set(links.keys()), {"AAPL", "NVDA"})


if __name__ == "__main__":
    unittest.main()
