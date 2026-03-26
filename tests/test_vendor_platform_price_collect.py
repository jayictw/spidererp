import unittest

from scripts.vendor_platform_price_collect import (
    extract_supplier_stock,
    infer_package,
    infer_qty,
    infer_year,
    split_inline_part_and_stock,
)


class TestVendorPlatformPriceCollect(unittest.TestCase):
    def test_split_inline_part_and_stock(self) -> None:
        part, stock = split_inline_part_and_stock("STM32F103C8T6 10K DC23+ LQFP48")
        self.assertEqual(part, "STM32F103C8T6")
        self.assertEqual(stock, "10K DC23+ LQFP48")

    def test_infer_qty_supports_k_suffix(self) -> None:
        self.assertEqual(infer_qty("qty:10K"), 10000)
        self.assertEqual(infer_qty("库存 2.5k"), 2500)

    def test_infer_year_supports_dc_short_year(self) -> None:
        self.assertEqual(infer_year("DC23+ 原装"), "2023")
        self.assertEqual(infer_year("date code 2021"), "2021")

    def test_infer_package_supports_bare_package_token(self) -> None:
        self.assertEqual(infer_package("LQFP48 dc23+"), "LQFP48")
        self.assertEqual(infer_package("package:QFN32"), "QFN32")

    def test_extract_supplier_stock_from_inline_raw(self) -> None:
        parsed = extract_supplier_stock({}, inline_raw="10K DC23+ LQFP48 lead time 4w")
        self.assertEqual(parsed["supplier_stock_qty"], "10000")
        self.assertEqual(parsed["supplier_stock_year"], "2023")
        self.assertEqual(parsed["supplier_package"], "LQFP48")
        self.assertIn("4w", parsed["supplier_lead_time"].lower())
        self.assertEqual(parsed["parse_status"], "parsed")


if __name__ == "__main__":
    unittest.main()
