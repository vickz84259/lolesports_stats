from typing import Dict, Any, ClassVar

import aiohttp
from loguru import logger

Session = aiohttp.ClientSession

SESSION_KEY = 'persist_session_client'


class State:
    app: ClassVar[aiohttp.web.Application]

    @classmethod
    def get_session(cls) -> Session:
        return cls.app[SESSION_KEY]


class ApiError(Exception):
    """Exception raised when there's an error accessing the api"""
    pass


def get_auth_header() -> Dict[str, str]:
    api_key = '0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z'
    return {'x-api-key': api_key}


async def fetch(url: str, auth: bool = False) -> Dict[str, Any]:
    headers = {}
    if auth:
        headers = get_auth_header()

    try:
        session = State.get_session()
        async with session.get(url, headers=headers) as response:
            return await response.json()

    except aiohttp.ClientResponseError as error:
        # TODO: Add code to handle 500 errors.

        logger.error("Couldn't retrieve data from the api")
        logger.error('Url: {} | HTTP status {} | headers {}',
                     error.request_info.url, error.status, error.headers)

        raise ApiError("Couldn't retrieve data from the api.")


async def get_window(game_id: int, start_time: str = '') -> Dict[str, Any]:
    base_url = 'https://feed.lolesports.com/livestats/v1'
    url = f'{base_url}/window/{game_id}'

    if start_time != '':
        url = f'{url}?startingTime={start_time}'

    return (await fetch(url))


async def get_endpoint(name: str, **kwargs: str) -> Dict[str, Any]:
    base_url = 'https://esports-api.lolesports.com/persisted/gw'
    url = f'{base_url}/{name}?hl=en-GB'

    for key, value in kwargs.items():
        url = f'{url}&{key}={value}'

    json_data = await fetch(url, auth=True)
    return json_data['data']


async def get_event_details(match_id: int) -> Dict[str, Any]:
    data = await get_endpoint('getEventDetails', id=str(match_id))
    return data['event']
