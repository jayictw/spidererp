import unittest

from scripts.st_slug_utils import make_st_product_url, st_part_to_product_slug


class TestStSlugUtils(unittest.TestCase):
    def test_known_samples(self) -> None:
        cases = {
            "FERD40H100SG-TR": "ferd40h100s",
            "L6563ATR": "l6563a",
            "M24C02-WMN6TP": "m24c02-w",
            "TS339CPT": "ts339",
            "UC3842BD1013TR": "uc3842b",
            "VN5160STR-E": "vn5160s-e",
        }
        for part_number, expected_slug in cases.items():
            with self.subTest(part_number=part_number):
                self.assertEqual(st_part_to_product_slug(part_number), expected_slug)

    def test_make_st_product_url(self) -> None:
        self.assertEqual(
            make_st_product_url("power-management", "UC3842BD1013TR"),
            "https://www.st.com/en/power-management/uc3842b.html",
        )


if __name__ == "__main__":
    unittest.main()

