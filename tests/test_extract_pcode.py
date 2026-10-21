import pytest

from app.collector.fetch import extract_pcode


@pytest.mark.parametrize(
    "text",
    [
        "https://prod.danawa.com/info/?pcode=97405013&cate=12237349",
        "https://prod.danawa.com/info/?cate=12237349&pcode=97405013&keyword=%EC%97%90",
        "https://m.danawa.com/product/product.html?code=97405013",
        "prod.danawa.com/info/?pcode=97405013",
        "  97405013  ",
    ],
)
def test_PC_모바일_숫자만_모두_상품코드를_꺼낸다(text):
    assert extract_pcode(text) == "97405013"


@pytest.mark.parametrize(
    "text, message",
    [
        ("https://www.coupang.com/vp/products/123456", "다나와 상품 페이지 링크가 아닙니다"),
        ("https://evil-danawa.com/info/?pcode=97405013", "다나와 상품 페이지 링크가 아닙니다"),
        ("https://search.danawa.com/dsearch.php?query=에어팟", "상품코드를 찾지 못했습니다"),
        ("", "링크를 입력해 주세요"),
    ],
)
def test_다나와_상품_링크가_아니면_이유를_알려준다(text, message):
    with pytest.raises(ValueError, match=message):
        extract_pcode(text)
