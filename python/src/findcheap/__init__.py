"""The Findcheap API in Python: where the product on a page is sold for less.

    from findcheap import Findcheap
    fc = Findcheap()                      # FINDCHEAP_API_KEY in the environment
    answer = fc.search("https://www.jlab.com/products/jbuds-lux-anc-headphones")

Reference: https://findcheap.ai/developers/docs.md
"""
from .client import (
    Findcheap,
    FindcheapApiError,
    FindcheapConnectionError,
    FindcheapError,
    Card,
    ReadAnswer,
    ResolveAnswer,
    SearchAnswer,
    SearchEcho,
    __version__,
)

__all__ = [
    "Findcheap", "FindcheapError", "FindcheapApiError", "FindcheapConnectionError",
    "Card", "ReadAnswer", "ResolveAnswer", "SearchAnswer", "SearchEcho", "__version__",
]
