from dataclasses import dataclass


@dataclass(frozen=True)
class LayoutMode:
    compact: bool
    short: bool
    inspector: bool
    undersize: bool


def layout_mode(width: int, height: int) -> LayoutMode:
    return LayoutMode(width < 80, height < 18, width >= 180 and height >= 18,
                      width < 40 or height < 12)


def column_widths(width: int, company: int, role: int) -> list[tuple[str, int]]:
    """Reserve actual cell padding (two per column) and a scrollbar (two)."""
    columns = [("Company", 16), ("Role", 24), ("Status", 14), ("Match", 5)]
    spare = max(0, width - 2 - sum(size + 2 for _, size in columns))
    sizes = [16, 24]
    targets = [max(24, company), max(36, role)]
    while spare and any(sizes[i] < targets[i] for i in (0, 1)):
        for i in (0, 1, 1, 0, 1):
            if spare and sizes[i] < targets[i]:
                sizes[i] += 1
                spare -= 1
    columns[:2] = [("Company", sizes[0]), ("Role", sizes[1])]
    if sizes[0] >= 24 and sizes[1] >= 36:
        for name, size in [("Readiness", 9), ("Source", 16), ("Created", 10),
                           ("Docs", 8), ("#", 4)]:
            if spare < size + 2:
                break
            columns.append((name, size))
            spare -= size + 2
    columns[0] = ("Company", columns[0][1] + spare * 2 // 5)
    columns[1] = ("Role", columns[1][1] + spare - spare * 2 // 5)
    return columns
