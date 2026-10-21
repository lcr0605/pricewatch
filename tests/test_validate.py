from app.collector.parser import ProductSnapshot
from app.collector.validate import check_snapshot, needs_inspection


def snap(price: int) -> ProductSnapshot:
    return ProductSnapshot(name="상품", lowest_price=price)


def test_정상_변동은_문제없음():
    assert check_snapshot(snap(95_000), previous_price=100_000) == []


def test_첫_수집은_비교_대상이_없어도_정상():
    assert check_snapshot(snap(100_000), previous_price=None) == []


def test_하루에_70퍼센트_넘게_바뀌면_의심():
    assert check_snapshot(snap(20_000), previous_price=100_000)


def test_너무_낮은_가격은_의심():
    assert check_snapshot(snap(10), previous_price=None)


def test_실패율_30퍼센트_초과면_점검_필요():
    assert needs_inspection(total=10, failed=4)
    assert not needs_inspection(total=10, failed=3)
    assert not needs_inspection(total=0, failed=0)


def test_대표_묶음_옵션이_바뀌면_가격_급변으로_보지_않는다():
    today = ProductSnapshot(name="칫솔 (10개)", lowest_price=3_500)
    assert check_snapshot(today, previous_price=10_390, previous_name="칫솔 (30개)") == []


def test_같은_옵션에서_급변하면_의심():
    today = ProductSnapshot(name="칫솔 (30개)", lowest_price=2_000)
    assert check_snapshot(today, previous_price=10_390, previous_name="칫솔 (30개)")
