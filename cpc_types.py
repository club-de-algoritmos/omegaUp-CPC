from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class SuspiciousActivity:
    username: str
    name: Optional[str]
    problem_alias: str
    similarity_perc: Optional[int]
    reason: str
    details: str

    @property
    def display_name(self) -> str:
        return self.name or self.username


@dataclass(frozen=True)
class MossHtml:
    problem_alias: str
    language: str
    html_path: str


@dataclass(frozen=True)
class Plagiarism:
    usernames: Tuple[str, str]
    names: Tuple[Optional[str], Optional[str]]
    results_url: str
    problem_alias: str
    language: str
    file_names: Tuple[str, str]
    status: str
    similarity_perc: int

    @property
    def display_names(self) -> Tuple[str, str]:
        return self.names[0] or self.usernames[0], self.names[1] or self.usernames[1]
