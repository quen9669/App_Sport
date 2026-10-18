"""System prompts, versioned in Markdown files next to this module.

Each file starts with ``<!-- version: name-vN -->``: the version is logged with
every answer, so the evaluation (phase 5b) can compare prompt versions. To
change a coach's behaviour, edit its file and bump the version.
"""

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent
_VERSION = re.compile(r"<!--\s*version:\s*([\w.-]+)\s*-->")


@dataclass(frozen=True)
class Prompt:
    text: str
    version: str


@cache
def load(name: str) -> Prompt:
    return parse((PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8"), f"{name}.md")


def parse(text: str, where: str) -> Prompt:
    """Split a prompt file into its text and its version line."""
    match = _VERSION.search(text)
    if match is None:
        raise ValueError(f"prompt {where} has no version line")
    return Prompt(_VERSION.sub("", text, count=1).strip(), match.group(1))


def system_prompt(coach: str, own: Prompt | None = None) -> Prompt:
    """The coach's own prompt followed by the rules common to both coaches.

    ``own`` replaces the coach's file: the evaluation uses it to compare versions.
    """
    own, common = own or load(coach), load("common")
    return Prompt(f"{own.text}\n\n{common.text}", f"{own.version}+{common.version}")
