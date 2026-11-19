"""The Findcheap API in Python: where the product on a page is sold for less.

    from findcheap import Findcheap
    fc = Findcheap()                      # FINDCHEAP_API_KEY in the environment
    answer = fc.search("https://findcheap.ai/sample-product")

Reference: https://findcheap.ai/developers/docs.md
"""
from .client import (
    Findcheap,
    FindcheapApiError,
    FindcheapConnectionError,
    FindcheapError,
    Card,
    CheaperElsewhere,
    FeedbackAnswer,
    NextStep,
    ReadAnswer,
    ResolveAnswer,
    SearchAnswer,
    SearchEcho,
    UsefulCard,
    WrongCard,
    __version__,
)

__all__ = [
    "Findcheap", "FindcheapError", "FindcheapApiError", "FindcheapConnectionError",
    "Card", "CheaperElsewhere", "FeedbackAnswer", "NextStep", "ReadAnswer", "ResolveAnswer", "SearchAnswer",
    "SearchEcho", "UsefulCard", "WrongCard", "__version__",
]
