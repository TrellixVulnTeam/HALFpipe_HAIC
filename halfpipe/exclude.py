# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import json
from collections import defaultdict
from enum import Enum, IntEnum, auto
from glob import glob, has_magic
from typing import Generator, Mapping

from more_itertools import powerset
from pyrsistent import pmap

from .utils import logger
from .utils.format import format_tags


class Rating(IntEnum):
    NONE = -1
    GOOD = 0
    UNCERTAIN = 1
    BAD = 2


class Decision(Enum):
    INCLUDE = auto()
    EXCLUDE = auto()


class QCDecisionMaker:
    def __init__(self, file_paths: list[str]):
        self.index: dict[Mapping[str, str], set[Rating]] = defaultdict(set)
        self.relevant_tag_names: set[str] = set()

        self.shown_warning_tags: set[Mapping[str, str]] = set()

        for file_path in file_paths:
            self._add_file(file_path)

    def _add_file(self, file_path: str) -> None:
        if has_magic(file_path):
            for e in glob(file_path, recursive=True):
                self._add_file(e)

        else:
            with open(file_path, "r") as file_handle:
                entries = json.load(file_handle)

            if not isinstance(entries, list):
                raise ValueError
            for entry in entries:
                self._add_entry(entry)

    def _add_entry(self, entry: Mapping[str, str]) -> None:
        rating_str: str | None = entry.get("rating")

        if rating_str is None:
            rating: Rating = Rating.NONE
        else:
            rating = Rating[rating_str.upper()]

        tags = pmap(
            {
                tag: value
                for tag, value in entry.items()
                if tag not in ["rating", "type"]
            }
        )

        self.index[tags].add(rating)

        self.relevant_tag_names.update(tags.keys())

    def _iter_ratings(self, tags: Mapping[str, str]) -> Generator[Rating, None, None]:
        yield Rating.NONE  # default
        for subset_items in powerset(tags.items()):
            subset = pmap(subset_items)
            if subset in self.index:
                yield from self.index[subset]

    def get(self, tags: Mapping[str, str]) -> Decision:
        if len(self.relevant_tag_names) == 0:
            relevant_tags = pmap(tags)
        else:
            relevant_tags = pmap(
                {
                    tag: value
                    for tag, value in tags.items()
                    if tag in self.relevant_tag_names
                }
            )

        rating: Rating = max(self._iter_ratings(relevant_tags))

        if rating == Rating.BAD:
            return Decision.EXCLUDE
        elif rating == Rating.GOOD:
            return Decision.INCLUDE
        elif rating == Rating.NONE or rating == Rating.UNCERTAIN:
            if relevant_tags not in self.shown_warning_tags:
                logger.warning(
                    f"Will include observation ({format_tags(relevant_tags)}) for analysis "
                    f'even though quality rating is "{rating.name}"'
                )
                self.shown_warning_tags.add(relevant_tags)

            return Decision.INCLUDE
        else:
            raise ValueError()
