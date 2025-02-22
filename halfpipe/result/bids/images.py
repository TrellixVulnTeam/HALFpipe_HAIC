# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import re
from collections import defaultdict
from pathlib import Path
from typing import Mapping

from ...file_index.base import FileIndex
from ...model.tags.schema import entities
from ...stats.algorithms import algorithms
from ...utils.path import copy_if_newer, split_ext
from ..base import ResultDict
from .base import make_bids_path
from .sidecar import load_sidecar, save_sidecar

statmap_keys: frozenset[str] = frozenset(
    [
        "effect",
        "variance",
        "z",
        "t",
        "f",
        "dof",
        "sigmasquareds",
    ]
)


def _from_bids_derivatives(tags: Mapping[str, str]) -> str | None:
    suffix = tags["suffix"]
    if suffix == "statmap":

        if "stat" not in tags:
            return None

        stat = tags["stat"]

        if "algorithm" in tags:
            algorithm = tags["algorithm"]
            if algorithm in ["mcar"]:
                return f"{algorithm}{stat}"

        return stat

    return suffix


def _to_bids_derivatives(key: str, inpath: Path, tags: dict[str, str]) -> Path:
    if key in statmap_keys:  # apply rule
        return make_bids_path(inpath, "image", tags, "statmap", stat=key)

    elif key in algorithms["heterogeneity"].model_outputs:
        key = re.sub(r"^het", "", key)
        return make_bids_path(
            inpath,
            "image",
            tags,
            "statmap",
            algorithm="heterogeneity",
            stat=key,
        )

    elif key in algorithms["mcartest"].model_outputs:
        key = re.sub(r"^mcar", "", key)
        return make_bids_path(
            inpath, "image", tags, "statmap", algorithm="mcar", stat=key
        )

    else:
        return make_bids_path(inpath, "image", tags, key)


def _load_result(file_index: FileIndex, tags: Mapping[str, str]) -> ResultDict | None:
    paths = file_index.get(**tags)
    if paths is None or len(paths) == 0:
        return None

    result: ResultDict = defaultdict(dict)
    result["tags"] = dict(tags)

    for path in paths:
        if path.suffix == ".json":
            metadata, vals = load_sidecar(path)
            result["metadata"].update(metadata)
            result["vals"].update(vals)
            continue

        key = _from_bids_derivatives(file_index.get_tags(path))
        if key is None:
            continue

        result["images"][key] = path

    return dict(result)


def load_images(file_index: FileIndex) -> list[ResultDict]:

    image_group_entities = set(entities) - {"stat", "algorithm"}

    results = list()
    for group in file_index.get_tag_groups(image_group_entities):
        result = _load_result(file_index, group)
        if result is None:
            continue
        results.append(result)

    return results


def save_images(results: list[ResultDict], base_directory: Path):
    derivatives_directory = base_directory / "derivatives" / "halfpipe"
    grouplevel_directory = base_directory / "grouplevel"

    for result in results:
        tags = result.get("tags", dict())
        metadata = result.get("metadata", dict())
        vals = result.get("vals", dict())
        images = result.get("images", dict())

        # images

        for key, inpath in images.items():
            outpath = derivatives_directory

            if "sub" not in tags:
                outpath = grouplevel_directory

            outpath = outpath / _to_bids_derivatives(key, inpath, tags)

            was_updated = copy_if_newer(inpath, outpath)

            if was_updated:
                # TODO make plot
                pass

            _, extension = split_ext(outpath)
            if key in ["effect", "reho", "falff", "alff", "bold", "timeseries"]:
                if extension in [".nii", ".nii.gz", ".tsv"]:  # add sidecar
                    save_sidecar(outpath, metadata, vals)
