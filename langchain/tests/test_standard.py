"""LangChain's own standard tests for tools, run on the five tools. Offline: the
unit tests build each tool and check its name and schema; the integration tests
call each tool, here over the local stub of the API, so no network, no key, no spend.

    cd findcheap-sdks/langchain && pip install -e ".[test]" && python -m pytest
"""
import pytest
from langchain_tests.integration_tests import ToolsIntegrationTests
from langchain_tests.unit_tests import ToolsUnitTests

from langchain_findcheap import (
    FindcheapFindCheaper,
    FindcheapReadProductPage,
    FindcheapResolveListing,
    FindcheapSearchProducts,
    FindcheapSubmitFeedback,
)

from . import stub as api

# Each tool with one example of what a model would send it.
TOOLS = {
    "find_cheaper": (FindcheapFindCheaper, {"url": "https://shop.example.com/p/1"}),
    "read_product_page": (FindcheapReadProductPage, {"url": "https://shop.example.com/p/1"}),
    "resolve_listing": (FindcheapResolveListing, {"resolve_id": "abc"}),
    "search_products": (FindcheapSearchProducts, {"query": "Insignia Fire TV", "market": "US",
                                                  "objective": "A small TV for a bedroom, as cheap as possible."}),
    "submit_feedback": (FindcheapSubmitFeedback, {"request_id": "r-1", "rating": "good",
                                                  "useful_cards": [{"list": "same_product", "position": 1}]}),
}


@pytest.fixture(scope="module")
def server():
    stub = api.Stub()
    yield stub
    stub.close()


def unit_tests(name):
    cls, example = TOOLS[name]

    class Unit(ToolsUnitTests):
        @property
        def tool_constructor(self):
            return cls

        @property
        def tool_constructor_params(self):
            return {"api_key": api.KEY}

        @property
        def tool_invoke_params_example(self):
            return example

        @property
        def init_from_env_params(self):
            return {"FINDCHEAP_API_KEY": "fc_live_from_env"}, {}, {"api_key": "fc_live_from_env"}

    Unit.__name__ = Unit.__qualname__ = f"TestUnit_{name}"
    return Unit


def integration_tests(name):
    cls, example = TOOLS[name]

    class Integration(ToolsIntegrationTests):
        @property
        def tool_constructor(self):
            return cls

        @property
        def tool_invoke_params_example(self):
            return example

        # The standard fixture builds the tool from `tool_constructor_params`;
        # this one adds the stub's address, which is only known once it runs.
        @pytest.fixture
        def tool(self, server):
            return cls(api_key=api.KEY, base_url=server.url)

    Integration.__name__ = Integration.__qualname__ = f"TestIntegration_{name}"
    return Integration


TestUnit_find_cheaper = unit_tests("find_cheaper")
TestUnit_read_product_page = unit_tests("read_product_page")
TestUnit_resolve_listing = unit_tests("resolve_listing")
TestUnit_search_products = unit_tests("search_products")
TestUnit_submit_feedback = unit_tests("submit_feedback")

TestIntegration_find_cheaper = integration_tests("find_cheaper")
TestIntegration_read_product_page = integration_tests("read_product_page")
TestIntegration_resolve_listing = integration_tests("resolve_listing")
TestIntegration_search_products = integration_tests("search_products")
TestIntegration_submit_feedback = integration_tests("submit_feedback")
