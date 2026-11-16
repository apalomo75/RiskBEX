"""HTTP-compatible read-only transport; Cloud reuses the existing ASGI contracts."""
import asyncio
import os
from urllib.parse import urlsplit

import requests


def get(url, **kwargs):
    if os.getenv('RISKBEX_PRESENTATION_MODE', 'api') != 'snapshot':
        return requests.get(url, **kwargs)
    # Lazy imports keep the Docker dashboard's dependency graph unchanged.
    import httpx
    from main import app

    parts = urlsplit(url)
    path = parts.path + (('?' + parts.query) if parts.query else '')

    async def read():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url='http://publication') as client:
            return await client.get(path, params=kwargs.get('params'))

    result = asyncio.run(read())
    response = requests.Response()
    response.status_code = result.status_code
    response._content = result.content
    response.headers.update(result.headers)
    response.url = str(result.url)
    return response
