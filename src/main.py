# import sys

from aiohttp import web, ClientSession
from loguru import logger

import lol
import riot_api

# Setting up the logger
format = '{time:YYYY-MM-DD HH:mm:ss ZZ} | {level: <8} | {message}'
logger.configure(
    handlers=[
        dict(sink="file_{time}.log", format=format, level='DEBUG',
             backtrace=False, diagnose=False)
    ]
)

routes = web.RouteTableDef()


@routes.get('/')
async def index(request: web.Request) -> web.Response:
    return web.Response(text='Hello World')


@routes.get('/_ah/start')
async def init(request: web.Request) -> web.Response:
    logger.info('Service has started.')

    await lol.init_processing()

    logger.info('Completed processing.')

    return web.Response(text='Finished')


async def session_handler(app):
    # Startup code
    app[riot_api.SESSION_KEY] = ClientSession(raise_for_status=True)
    riot_api.State.app = app

    yield

    # Cleanup code
    session = app[riot_api.SESSION_KEY]
    await session.close()


async def web_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)

    app.cleanup_ctx.append(session_handler)

    return app
