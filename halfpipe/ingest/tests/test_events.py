# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

from math import isclose

import pytest

from ...resource import get as getresource
from ...tests.resource import setup as setuptestresources
from ..events import ConditionFile

txt_str = """8 32 1
72 32 1
136 32 1
200 32 1
"""

tsv_str = """onset duration  trial_type  response_time stim_file
1.2 0.6 go  1.435 images/red_square.jpg
5.6 0.6 stop  1.739 images/blue_square.jpg
"""

tsv_numeric_str = """onset duration  trial_type  response_time stim_file
1.2 0.6 1  1.435 images/red_square.jpg
5.6 0.6 2  1.739 images/blue_square.jpg
"""


def test_parse_condition_file_txt(tmp_path):
    file_name = tmp_path / "faces.txt"

    with open(file_name, "w") as file_handle:
        file_handle.write(txt_str)

    cf = ConditionFile(data=((file_name, "faces"), (file_name, "shapes")))

    assert cf.conditions == ["faces", "shapes"]
    assert all(v == 32 for d in cf.durations for v in d)
    assert all(v[0] == 8 for v in cf.onsets)


@pytest.mark.parametrize(
    "tsv_str,expected_conditions",
    [
        (tsv_str, ["go", "stop"]),
        (tsv_numeric_str, ["1", "2"]),
    ],
)
def test_parse_condition_file_tsv(tmp_path, tsv_str, expected_conditions):
    file_name = tmp_path / "gonogo.tsv"

    with open(file_name, "w") as file_handle:
        file_handle.write(tsv_str)

    cf = ConditionFile(data=file_name)

    assert cf.conditions == expected_conditions
    assert all(len(v) > 0 for v in cf.durations)
    assert all(len(v) > 0 for v in cf.onsets)


def test_parse_condition_file_mat():
    setuptestresources()
    file_name = getresource("run_01_spmdef.mat")

    cf = ConditionFile(data=file_name)

    assert cf.conditions == ["Famous", "Unfamiliar", "Scrambled"]
    assert all(len(v) > 0 for v in cf.durations)
    assert all(len(v) > 0 for v in cf.onsets)

    famous_onsets, unfamiliar_onsets, scrambled_onsets = cf.onsets

    assert isclose(famous_onsets[0], 0)
    assert isclose(famous_onsets[1], 3.273)
    assert isclose(unfamiliar_onsets[0], 6.647)
    assert isclose(scrambled_onsets[0], 25.606)
