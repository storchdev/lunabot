from typing import TYPE_CHECKING, List

from fuzzywuzzy import process

if TYPE_CHECKING:
    from .items import BaseItem


def search_item(
    items: List["BaseItem"], query: str, threshold: int = 70
) -> List["BaseItem"]:
    # Iterate over each item and compare the query to both the display_name and qualified_name
    item_map = {}
    names = []
    for item in items:
        for name in item.as_list():
            names.append(name)
            item_map[name] = item

    results = process.extract(query.lower(), names, limit=len(items))

    output = []
    for name, sim in results:
        if item_map[name] in output or sim < threshold:
            continue
        output.append(item_map[name])

    # Return only the items, not the similarity scores
    return output
