import math
from datetime import datetime
from typing import Dict, Any


def __get_timestamp(datetime_str: str) -> float:
    datetime_obj = datetime.fromisoformat(datetime_str)

    return datetime_obj.timestamp()


def get_timestamp(datetime_str: str) -> float:
    return __get_timestamp(datetime_str[:-1])


def get_time_from_data(frame_data: Dict[str, Any]) -> float:
    datetime_str = frame_data['rfc460Timestamp'][:-1]
    return __get_timestamp(datetime_str)


def get_iso_time(timestamp: float, normalised: bool = True) -> str:
    if normalised:
        timestamp = math.floor(timestamp / 10) * 10

    datetime_str = datetime.fromtimestamp(timestamp).isoformat()
    return f'{datetime_str}Z'
