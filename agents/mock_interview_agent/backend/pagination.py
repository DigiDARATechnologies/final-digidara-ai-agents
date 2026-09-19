"""Small, framework-independent pagination helpers."""


def pagination_metadata(total_items, page, limit):
    total_items = max(int(total_items or 0), 0)
    page = int(page)
    limit = int(limit)
    total_pages = (total_items + limit - 1) // limit if total_items else 0
    return {
        "page": page,
        "limit": limit,
        "total_items": total_items,
        "total_pages": total_pages,
        "has_more": page * limit < total_items,
    }
