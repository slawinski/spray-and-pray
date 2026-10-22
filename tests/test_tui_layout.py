import pytest

from cv_optimizer.tui.layout import layout_mode, column_widths


@pytest.mark.parametrize("width", [39, 40, 79, 80, 119, 120, 160])
@pytest.mark.parametrize("height", [11, 12, 17, 18, 50])
def test_independent_size_boundaries(width, height):
    mode = layout_mode(width, height)
    assert mode.undersize == (width < 40 or height < 12)
    assert mode.compact == (width < 80)
    assert mode.short == (height < 18)
    assert mode.inspector == (width >= 120 and height >= 18)


@pytest.mark.parametrize("width", [78, 80, 100, 119, 140, 200])
def test_columns_fit_measured_budget(width):
    columns = dict(column_widths(width, 80, 100))
    assert sum(columns.values()) + 2 * len(columns) + 2 <= width
    assert {"Company", "Role", "Status", "Match"} <= columns.keys()
    if "Readiness" in columns:
        assert columns["Company"] >= 24 and columns["Role"] >= 36
    assert columns["Company"] >= 16 and columns["Role"] >= 24
