# required models such as groups and matches
from dataclasses import dataclass
from datetime import date, time


@dataclass
class Team:
    name: str
    group: str
    flag: str


@dataclass
class Match:
    match_no: int
    match_date: date
    match_time: time
    group: str
    team_a: str
    team_b: str
    team_a_score: int = 0
    team_b_score: int = 0
    stage: str


@dataclass
class TeamStats:
    team: str
    played: int = 0
    won: int = 0
    draw: int = 0
    lost: int = 0
    gf: int = 0
    ga: int = 0
    gd: int = 0
    points: int = 0
    score: float = 0.0


@dataclass
class User:
    name: str
    team: str
    points: float = 0.0
