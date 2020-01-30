from typing import Dict, Any, Iterator, AsyncIterator

from loguru import logger

import game as game_lib
import game_pb2
import riot_api
import utils

Game = game_pb2.Game
Participant = game_pb2.Participant

Team = game_pb2.Metadata.Team

Vod = game_pb2.Game.Vod
TimeFrame = game_pb2.Game.TimeFrame


def get_teams(
        event: Dict[str, Any],
        game_data: Dict[str, Any]) -> Iterator[Team]:

    teams_data = event['match']['teams']
    for team_data in teams_data:
        team = Team()

        team.id = int(team_data['id'])
        team.name = team_data['name']
        team.code = team_data['code']

        for info in game_data['teams']:
            if int(info['id']) == team.id:
                team.side = game_pb2.Side.Value(info['side'].upper())
                break

        yield team


def get_vods(game_data: Dict[str, Any]) -> Iterator[Vod]:
    for vod_data in game_data['vods']:
        if (vod_data['offset'] != 0):
            vod = Vod()

            vod.id = int(vod_data['id'])
            vod.platform = vod_data['provider']
            vod.parameter = vod_data['parameter']
            vod.locale = vod_data['locale']

            vod.start_time = abs(vod_data['offset']) / 1000

            yield vod


def get_game(event: Dict[str, Any], game_index: int) -> Game:
    game = Game(time_interval=30)

    # Specifying the game metadata
    game.metadata.match_id = int(event['id'])

    game_data = event['match']['games'][game_index]
    game.metadata.game_id = int(game_data['id'])

    game.metadata.teams.extend(get_teams(event, game_data))

    game.vods.extend(get_vods(game_data))

    return game


async def get_games(match_id: int) -> AsyncIterator[Game]:
    event = await riot_api.get_event_details(match_id)

    for index, game in enumerate(event['match']['games']):
        if game['state'] == 'completed':
            yield get_game(event, index)


def get_participants(
        feed_data: Dict[str, Any],
        team_id: int) -> Iterator[Participant]:

    metadata = feed_data['gameMetadata']
    blue_team_id = int(metadata['blueTeamMetadata']['esportsTeamId'])
    red_team_id = int(metadata['redTeamMetadata']['esportsTeamId'])

    if team_id == blue_team_id:
        participants_data = metadata['blueTeamMetadata']['participantMetadata']
    elif team_id == red_team_id:
        participants_data = metadata['redTeamMetadata']['participantMetadata']

    for data in participants_data:
        participant = Participant()

        participant.player_id = int(data['esportsPlayerId'])
        participant.champion = data['championId']
        participant.summoner_name = data['summonerName']

        participant.id = data['participantId']
        participant.role = Participant.Role.Value(data['role'].upper())

        yield participant


async def process_game(game: Game) -> None:
    game_id = game.metadata.game_id
    logger.debug('Game ID: {}', game_id)

    initial_feed = await riot_api.get_window(game_id)

    # TODO: Handle games with missing feed info.

    game.metadata.patch = initial_feed['gameMetadata']['patchVersion']

    for team in game.metadata.teams:
        team.participants.extend(get_participants(initial_feed, team.id))

    init_timestamp = utils.get_time_from_data(initial_feed['frames'][0])
    game_state = game_lib.GameState(game, init_timestamp)

    window_time = utils.get_iso_time(init_timestamp + 20)

    while game_state.is_in_game:
        frames = (await riot_api.get_window(game_id, window_time))['frames']

        for frame in frames:
            game_state.update(frame)

        window_timestamp = utils.get_timestamp(window_time)
        window_time = utils.get_iso_time(window_timestamp + 10)


async def process_match(match_id: int) -> None:
    try:
        x = 0
        async for game in get_games(match_id):
            if x == 2:
                await process_game(game)

            x += 1

    except riot_api.ApiError:
        pass


async def init_processing() -> None:
    # match_id = 102844412693683492
    match_id = 102844412694338854
    await process_match(match_id)
