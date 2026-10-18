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
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    match = _VERSION.search(text)
    if match is None:
        raise ValueError(f"prompt {name}.md has no version line")
    return Prompt(_VERSION.sub("", text, count=1).strip(), match.group(1))


def system_prompt(coach: str) -> Prompt:
    """The coach's own prompt followed by the rules common to both coaches."""
    own, common = load(coach), load("common")
    return Prompt(f"{own.text}\n\n{common.text}", f"{own.version}+{common.version}")
