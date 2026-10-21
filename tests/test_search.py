from app.collector.parser import parse_search

HTML = """
<ul>
  <li class="prod_item">
    <p class="prod_name"><a href="https://prod.danawa.com/info/?pcode=111&keyword=x">삼성 <b>SSD</b> 1TB</a></p>
    <p class="price_sect"><a><strong>129,000</strong>원</a></p>
  </li>
  <li class="prod_item">
    <p class="prod_name"><a href="https://prod.danawa.com/info/?pcode=111&keyword=x">중복 상품</a></p>
  </li>
  <li class="prod_item">
    <p class="prod_name"><a href="https://prod.danawa.com/info/?pcode=222">가격 없는 상품</a></p>
  </li>
  <li class="prod_item ad"><p class="prod_name"><a href="https://ad.example.com">광고</a></p></li>
</ul>
"""


def test_검색_결과에서_상품코드_이름_가격을_읽는다():
    results = parse_search(HTML)
    assert [r.pcode for r in results] == ["111", "222"]
    assert results[0].name == "삼성 SSD 1TB"
    assert results[0].price == 129000
    assert results[1].price is None
