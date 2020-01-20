import sys

from aiohttp import web
from loguru import logger

# Setting up the logger
format = '{time:YYYY-MM-DD HH:mm:ss ZZ} | {level: <8} | {message}'
logger.configure(
    handlers=[
        dict(sink=sys.stderr, format=format, level='DEBUG')
    ]
)

routes = web.RouteTableDef()


@routes.get('/')
async def index(request: web.Request) -> web.Response:
    return web.Response(text='Hello World')


@routes.get('/_ah/start')
async def init(request: web.Request) -> web.Response:
    logger.info('Service has started.')

    '''
    game_id = 102844412722519367
    lol.process_match(game_id)'''

    logger.info('Completed processing.')

    return web.Response()


async def web_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)

    return app
