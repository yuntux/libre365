"""FastAPI entrypoint for the unified-search connector.

Same observable contract as the previous Express server: ``GET /search?q=``
fans out in real time to Matrix/Seafile/Vikunja/Grommunio, relaying the
user's Keycloak Bearer token as-is (study 2.2 lines 391, 394) - this
connector never authenticates itself in place of the user.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.fanout import fan_out_search, merge_results
from app.sources.grommunio import search_grommunio
from app.sources.matrix import search_matrix
from app.sources.seafile import search_seafile
from app.sources.vikunja import search_vikunja

PORT = int(os.environ.get("PORT", "4002"))
TIMEOUT_MS = int(os.environ.get("SEARCH_TIMEOUT_MS", "2000"))

app = FastAPI(title="unified-search")


@app.get("/search")
async def search(request: Request):
    query = (request.query_params.get("q") or "").strip()
    if not query:
        return JSONResponse(status_code=400, content={"error": "missing query parameter 'q'"})

    # The user's Keycloak Bearer token is relayed as-is (study 2.2 lines 391,
    # 394) to each source service: this connector never authenticates itself
    # with Matrix/Seafile/Vikunja/Grommunio in place of the user.
    auth_header = request.headers.get("authorization") or ""
    user_token = auth_header[7:] if auth_header.lower().startswith("bearer ") else auth_header
    if not user_token:
        return JSONResponse(
            status_code=401,
            content={"error": "missing Authorization: Bearer <token> header"},
        )

    outcomes = await fan_out_search(
        query,
        user_token,
        {
            "matrix": search_matrix,
            "seafile": search_seafile,
            "vikunja": search_vikunja,
            "grommunio": search_grommunio,
        },
        TIMEOUT_MS,
    )

    return {
        "query": query,
        "sources": [
            {
                "source": o.source,
                "ok": o.ok,
                "tookMs": o.took_ms,
                "error": o.error,
                "count": len(o.results),
            }
            for o in outcomes
        ],
        "results": [r.to_dict() for r in merge_results(outcomes)],
    }


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


def run() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    run()
