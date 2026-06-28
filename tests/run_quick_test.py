import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import init_db, save_recommended_product, get_total_recommended_products

if __name__ == "__main__":
    init_db()
    before = get_total_recommended_products()
    print("before:", before)
    save_recommended_product(user_id=999, product_name="__TEST_PRODUCT__")
    after = get_total_recommended_products()
    print("after:", after)
    if after == before + 1:
        print("TEST PASSED")
    else:
        print("TEST FAILED")
