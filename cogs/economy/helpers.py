from typing import List 
from typing import TYPE_CHECKING
from fuzzywuzzy import fuzz


if TYPE_CHECKING:
    from .items import BaseItem


def search_item(items: List['BaseItem'], query: str, threshold: int = 70) -> List['BaseItem']:
    results = []
    
    # Iterate over each item and compare the query to both the display_name and qualified_name
    for item in items:
        for name in item.as_list():
            similarity = fuzz.ratio(query.lower(), name.lower())
            if similarity > threshold:
                results.append((item, similarity))
                break

    # Sort results by similarity ratio in decreasing order
    results.sort(key=lambda x: x[1], reverse=True)

    # Return only the items, not the similarity scores
    return [item for item, _ in results]