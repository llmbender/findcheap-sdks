# langchain-findcheap

Findcheap for LangChain agents: where a product is sold for less. Five tools over the [Findcheap API](https://findcheap.ai/developers/docs), each a thin wrapper around the [`findcheap`](https://pypi.org/project/findcheap/) client. Python 3.10+.

```bash
pip install langchain-findcheap
export FINDCHEAP_API_KEY=fc_live_...   # from https://findcheap.ai/signin?next=/dashboard/keys
```

An account is free: 1,000 credits a month, no card.

## Use with an agent

```python
from langchain.agents import create_agent
from langchain_findcheap import FindcheapToolkit

agent = create_agent("anthropic:claude-sonnet-5-5", tools=FindcheapToolkit().get_tools())

result = agent.invoke({"messages": [{"role": "user", "content":
    "Find where this is available for a lower price: https://findcheap.ai/sample-product"}]})
print(result["messages"][-1].content)
```

Any chat model that calls tools works. This example also needs `pip install langchain langchain-anthropic` and an `ANTHROPIC_API_KEY`.

## The tools

| Tool | Class | What it does | Credits |
|---|---|---|---|
| `find_cheaper` | `FindcheapFindCheaper` | Finds where the product on a page is sold for less: the same product and acceptable equivalents, cheapest first. Up to 60 seconds. | 10 |
| `search_products` | `FindcheapSearchProducts` | Finds listings that match a description in words, or a photo's link, cheapest first. | 10 |
| `read_product_page` | `FindcheapReadProductPage` | Reads what a page sells (title, price, brand, stock), without a search. | 1 |
| `resolve_listing` | `FindcheapResolveListing` | Gives the merchant's link for a card that came with a `resolve_id`. | 1 when a link came back |
| `submit_feedback` | `FindcheapSubmitFeedback` | Reports how a search went. The first report on a search gives 1 credit back. | 0 |

They carry the names and the descriptions of the tools of Findcheap's MCP server, so an answer's `next_steps` name these tools and their fields.

`find_cheaper`, `read_product_page` and `search_products` require `objective`: what the shopper wants, in one sentence. An agent writes it on every call.

`submit_feedback` is the one tool that writes: it sends Findcheap a report on a search. To leave it out, build the list yourself:

```python
from langchain_findcheap import FindcheapFindCheaper, FindcheapReadProductPage

tools = [FindcheapFindCheaper(), FindcheapReadProductPage()]
```

## Call a tool yourself

```python
from langchain_findcheap import FindcheapFindCheaper

answer = FindcheapFindCheaper().invoke({"url": "https://findcheap.ai/sample-product", "max_results": 3,
                                        "objective": "These shoes for less, new."})
print(answer["product"]["title"], answer["page_is_cheapest"])
for card in answer["same_product"]:
    print(card["price"], card["currency"], card["retailer"], card["url"] or card["resolve_id"])
```

A tool answers what the API answers, untouched: every field is in the reference, https://findcheap.ai/developers/docs.md. A call the API refuses (a page that is not a product page, credits used up, a rate limit) reaches the model as the tool's answer, in the API's own words, so the agent can act on it; it does not stop the agent.

Each tool and the toolkit take `api_key=` (in place of the environment variable), `timeout=` (seconds, for every call) and `base_url=`.

## Tests

```bash
pip install -e ".[test]" && python -m pytest
```

Offline: LangChain's standard tests for tools and this package's own, over a local stub of the API.
