"""LangChain tools for the Findcheap API: where a product is sold for less.

    from langchain_findcheap import FindcheapToolkit
    tools = FindcheapToolkit().get_tools()   # FINDCHEAP_API_KEY in the environment

Reference: https://findcheap.ai/developers/docs.md
"""
from langchain_findcheap._version import __version__
from langchain_findcheap.tools import (
    FindcheapFindCheaper,
    FindcheapReadProductPage,
    FindcheapResolveListing,
    FindcheapSearchProducts,
    FindcheapSubmitFeedback,
    FindcheapToolkit,
)

__all__ = [
    "FindcheapFindCheaper",
    "FindcheapReadProductPage",
    "FindcheapResolveListing",
    "FindcheapSearchProducts",
    "FindcheapSubmitFeedback",
    "FindcheapToolkit",
    "__version__",
]
