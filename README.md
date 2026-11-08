# Findcheap SDKs

Thin clients for the Findcheap API (https://findcheap.ai/developers/docs): the three calls, the answer header, the error envelope, sensible timeouts. Each is a few hundred lines over the platform's own HTTP client, with no other dependency, so a reader can see exactly what goes on the wire.

- `python/` — the `findcheap` package (Python 3.9+, standard library only).
- `js/` — the `findcheap` package for Node 18+ and the browsers' `fetch` (TypeScript, ESM).

Neither is published yet; publishing (PyPI, npm) and the license are Jake's call. The API's own documentation for agents (llms.txt, the OpenAPI spec, the skill) is on the website, not here.
