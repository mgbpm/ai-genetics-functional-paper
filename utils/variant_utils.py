import re
from typing import List, Optional

def find_longest_matching_variant(text: str, variants: List[str]) -> Optional[str]:
    """
    Given a list of variants, find the longest variant that appears in the text provided.

    :param variants: a list of variants
    :param text: text to search for a match
    :return: the longest variant found in the text (if exists)
    """
    sorted_variants = sorted(variants, key=len, reverse=True)
    for variant in sorted_variants:
        if re.search(variant, text, re.IGNORECASE) is not None:
            return variant
        
    return None
