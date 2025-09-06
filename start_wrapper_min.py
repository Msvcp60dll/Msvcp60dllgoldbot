#!/usr/bin/env python3
"""
Minimal health server for first Railway deploy.
No project imports. Serves /health and /healthz on 0.0.0.0:$PORT
"""

import os
import sys
import asyncio
from aiohttp import web


async def health(_):
    return web.json_response({
        "status": "healthy",
        "service": "telegram-stars-membership",
        "mode": "min",
    })


def make_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/healthz", health)
    app.router.add_get("/", health)
    return app


def main():
    port = int(os.getenv("PORT", 8080))
    app = make_app()
    web.run_app(app, host="0.0.0.0", port=port, print=None)


if __name__ == "__main__":
    main()

