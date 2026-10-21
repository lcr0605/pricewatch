import pytest

from app.collector.fetch import PRODUCT_URL, assert_allowed


def test_상품_상세_페이지는_허용():
    assert_allowed(PRODUCT_URL.format(pcode="97405013"))


@pytest.mark.parametrize(
    "url",
    [
        "https://prod.danawa.com/info/ajax/getProductPriceList.ajax.php",
        "https://prod.danawa.com/list/ajax/x",
        "https://prod.danawa.com/api/x",
    ],
)
def test_robots_금지_경로는_요청하지_않는다(url):
    with pytest.raises(ValueError):
        assert_allowed(url)
