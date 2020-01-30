import abc
import itertools
from typing import Dict, Any, List, Iterator, TypeVar, Optional

from loguru import logger

import game_pb2
import utils

Game = game_pb2.Game
Side = game_pb2.Side
Event = game_pb2.Event
Snapshot = game_pb2.Snapshot

Scenario = game_pb2.Event.Scenario
ID = game_pb2.Participant.ID
Metadata = game_pb2.Metadata

T = TypeVar('T', 'Player', 'Tracker')
KillsMap = Dict[str, List[T]]


class State(abc.ABC):

    @abc.abstractmethod
    def update(self, data: Dict[str, Any]) -> None:
        """This method should implement updating the object's stats based on
        the json data passed"""


class Player(State):

    def __init__(self, id: ID, side: Side) -> None:
        self.id = id
        self.side = side

        self.previous_deaths = 0
        self.current_deaths = 0

        self.previous_health = 0
        self.current_health = 0
        self.max_health = 0

        self.current_kills = 0

        self.last_kill_time = 0.0

        self.consecutive_kills = 0  # Used to track sprees and shutdowns
        self.multi_kills = 0  # Used to track doubles, triples, quadras

    def update(self, player_data: Dict[str, int]) -> None:
        self.previous_kills = self.current_kills
        self.current_kills = player_data['kills']

        self.consecutive_kills += self.kills

        self.previous_deaths = self.current_deaths
        self.current_deaths = player_data['deaths']

        self.previous_health = self.current_health
        self.current_health = player_data['currentHealth']
        self.max_health = player_data['maxHealth']

    def get_event(self, scenario: Scenario) -> Event:
        return Event(side=self.side, scenario=scenario, participant_id=self.id)

    @property
    def spree(self) -> Scenario:
        scenario = Scenario.KILL

        if self.consecutive_kills == 3:
            scenario = Scenario.SPREE
        elif self.consecutive_kills == 4:
            scenario = Scenario.RAMPAGE
        elif self.consecutive_kills == 5:
            scenario = Scenario.UNSTOPPABLE
        elif self.consecutive_kills == 6:
            scenario = Scenario.DOMINATING
        elif self.consecutive_kills == 7:
            scenario = Scenario.GODLIKE
        elif self.consecutive_kills >= 8:
            scenario = Scenario.LEGENDARY

        return scenario

    @property
    def kills(self) -> int:
        return self.current_kills - self.previous_kills

    @property
    def has_died(self) -> bool:
        return (self.current_deaths - self.previous_deaths) == 1

    def __repr__(self) -> str:
        response = (f'Player. Side: {self.side} ID: {self.id} '
                    f'deaths: {self.current_deaths} kills: '
                    f'{self.current_kills} health: {self.current_health} '
                    f'max_health: {self.max_health} '
                    f'multi_kills: {self.multi_kills} '
                    f'consecutive: {self.consecutive_kills}\n')

        return response


class Tracker:

    def __init__(self, player: Player) -> None:
        self.player = player
        self.kills: List[Player] = []

    def add(self, player: Player) -> None:
        if len(self.kills) < self.player.kills:
            self.kills.append(player)

    def __repr__(self) -> str:
        return f'Tracker. Player: {self.player} Kills: {self.kills}'


class Team(State):

    def __init__(self, team: Metadata.Team) -> None:
        self._team = team

        self.current_inhibs = 0
        self.current_towers = 0

        self.current_barons = 0
        self.current_dragons = 0

        self.players: List[Player] = []
        for player in self._team.participants:
            self.players.append(Player(player.id, self.side))

        self.deaths: List[Player] = []

        self._aced = False

    def update(self, team_data: Dict[str, Any]) -> None:
        self.previous_inhibs = self.current_inhibs
        self.current_inhibs = team_data['inhibitors']

        self.previous_towers = self.current_towers
        self.current_towers = team_data['towers']

        self.previous_barons = self.current_barons
        self.current_barons = team_data['barons']

        self.previous_dragons = self.current_dragons
        self.current_dragons = len(team_data['dragons'])

        for player_data in team_data['participants']:
            player = self.get_player(player_data['participantId'])
            player.update(player_data)

        for player in self.players:
            if player.has_died:
                self.deaths.append(player)

        # Removing players that have respawned
        self.deaths[:] = [player for player in self.deaths
                          if player.current_health != player.max_health]

        if len(self.deaths) < 5 and self._aced:
            self._aced = False

    def __repr__(self):
        return f'Team. side: {self._team.side}\n {self.players}'

    @property
    def inhibs(self) -> int:
        return self.current_inhibs - self.previous_inhibs

    @property
    def towers(self) -> int:
        return self.current_towers - self.previous_towers

    @property
    def barons(self) -> int:
        return self.current_barons - self.previous_barons

    @property
    def dragons(self) -> int:
        return self.current_dragons - self.previous_dragons

    @property
    def side(self) -> Side:
        return self._team.side

    def is_aced(self, save_state=False) -> bool:
        response = False

        if not self._aced and len(self.deaths) == len(self.players):
            if save_state:
                self._aced = True

            response = True

        return response

    def get_player(self, id: ID) -> Player:
        for player in self.players:
            if player.id == id:
                result = player
                break

        return result


class GameState(State):

    def __init__(self, game: Game, init_time: float) -> None:
        self._game = game

        self.init_time = init_time  # Timestamp of when the game started
        self.frame_time = init_time

        self.time_interval = float(self._game.time_interval)
        self.time_frame = game.frames.add()

        self.status = 'in_game'
        self.total_kills = 0

        for team in self._game.metadata.teams:
            if team.side == Side.BLUE:
                self.blue_team = Team(team)
            elif team.side == Side.RED:
                self.red_team = Team(team)

    def update(self, frame: Dict[str, Any]) -> None:
        self.blue_team.update(frame['blueTeam'])
        self.red_team.update(frame['redTeam'])

        self.current_time = utils.get_time_from_data(frame)

        interval = self.current_time - self.frame_time

        if interval >= self.time_interval:
            self.time_frame = self._game.frames.add()
            self.frame_time = self.current_time

        in_game_time = self.current_time - self.init_time
        snapshot = Snapshot(game_time=in_game_time)

        kills_map = self.get_kills_map(frame)
        self.process_kills(kills_map, snapshot)

        self.process_objectives(snapshot)

        game_state = frame['gameState']
        if game_state != 'in_game':
            self.status = game_state

            # Setting the vod time when the game ends
            for vod in self._game.vods:
                vod.end_time = vod.start_time + in_game_time

            snapshot.events.add(scenario=Scenario.GAME_END)

        if len(snapshot.events) > 0:
            logger.debug('Snapshot: {}', snapshot)
            self.time_frame.snapshots.append(snapshot)

    def get_kills_map(self, frame: Dict[str, Any]) -> KillsMap:
        trackers: List[Tracker] = []
        deaths: List[Player] = []

        for team in [self.blue_team, self.red_team]:
            for player in team.players:
                if player.kills > 0:
                    trackers.append(Tracker(player))

                if player.has_died:
                    deaths.append(player)

        for tracker in trackers:
            for _ in range(tracker.player.kills):
                tracker.add(deaths.pop())

        return {'kills': trackers, 'executed': deaths}

    def process_kills(self, kills_map: KillsMap, snapshot: Snapshot) -> None:
        # Executed
        if len(kills_map['executed']) > 0:
            for player in kills_map['executed']:
                snapshot.events.append(player.get_event(Scenario.EXECUTED))

        total_kills = 0
        for tracker in kills_map['kills']:
            player = tracker.player

            if player.last_kill_time == 0.0:
                player.last_kill_time = self.current_time

            # Calculating multi-kills (double, triple e.t.c)
            # Only if kill is within 10 seconds of last kill
            time_diff = self.current_time - player.last_kill_time
            if time_diff > 10.0:
                player.multi_kills = 0

            player.last_kill_time = self.current_time

            player.multi_kills += player.kills
            total_kills += player.kills

            # First Blood
            if self.total_kills == 0:
                snapshot.events.append(player.get_event(Scenario.FIRST_BLOOD))

            scenario: Optional[Scenario] = None

            if player.multi_kills == 1:
                if self.total_kills > 0:
                    killed_player = tracker.kills[0]

                    if killed_player.consecutive_kills >= 2:
                        scenario = Scenario.SHUTDOWN
                    else:
                        scenario = player.spree
            elif player.multi_kills == 2:
                scenario = Scenario.DOUBLE
            elif player.multi_kills == 3:
                scenario = Scenario.TRIPLE
            elif player.multi_kills == 4:
                scenario = Scenario.QUADRA
            elif player.multi_kills == 5:
                enemy_team = self.get_enemy_team(player.side)

                if time_diff <= 30.0 and enemy_team.is_aced():
                    scenario = Scenario.PENTA

            if scenario is not None:
                snapshot.events.append(player.get_event(scenario))

            # Reset consecutive kills
            for player in tracker.kills:
                player.consecutive_kills = 0

        self.total_kills += total_kills

        # Ace
        for team in [self.blue_team, self.red_team]:
            enemy_team = self.get_enemy_team(team.side)

            if enemy_team.is_aced(save_state=True):
                snapshot.events.add(scenario=Scenario.ACE, side=team.side)

    def get_enemy_team(self, side: Side) -> Team:
        if side == Side.BLUE:
            enemy_team = self.red_team
        else:
            enemy_team = self.blue_team

        return enemy_team

    def process_objectives(self, snapshot: Snapshot) -> None:
        for team in [self.blue_team, self.red_team]:
            events = [
                self.get_obj_events(team.inhibs, team.side,
                                    Scenario.INHIBITOR),
                self.get_obj_events(team.towers, team.side, Scenario.TURRET),
                self.get_obj_events(team.barons, team.side, Scenario.BARON),
                self.get_obj_events(team.dragons, team.side, Scenario.DRAGON)
            ]
            snapshot.events.extend(itertools.chain.from_iterable(events))

    def get_obj_events(
            self,
            value: int,
            side: Side,
            scenario: Scenario) -> Iterator[Event]:
        if value > 0:
            for _ in range(value):
                yield Event(side=side, scenario=scenario)

    @property
    def game(self) -> Game:
        return self._game

    @property
    def is_in_game(self) -> bool:
        return self.status == 'in_game'
