# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import json
import os
import shutil
import tarfile
from math import inf
from multiprocessing import cpu_count
from pathlib import Path
from random import choices, normalvariate, seed

import nibabel as nib
import pandas as pd
import pytest
from fmriprep import config
from nilearn.image import new_img_like
from templateflow.api import get as get_template

from ...cli.parser import build_parser
from ...cli.run import run_stage_run
from ...ingest.database import Database
from ...model.feature import FeatureSchema
from ...model.file.schema import FileSchema
from ...model.setting import SettingSchema
from ...model.spec import Spec, SpecSchema, save_spec
from ...resource import get as get_resource
from ...utils.image import nvol
from ..base import init_workflow
from ..execgraph import init_execgraph


@pytest.fixture(scope="module")
def task_events(tmp_path_factory, bids_data):
    tmp_path = tmp_path_factory.mktemp(basename="task_events")

    os.chdir(str(tmp_path))

    seed(a=0x5E6128C4)

    spec_schema = SpecSchema()
    spec = spec_schema.load(spec_schema.dump({}), partial=True)
    assert isinstance(spec, Spec)

    spec.files = list(
        map(
            FileSchema().load,
            [
                dict(datatype="bids", path=str(bids_data)),
            ],
        )
    )

    database = Database(spec)

    bold_file_paths = database.get(datatype="func", suffix="bold")
    assert database.fillmetadata("repetition_time", bold_file_paths)

    scan_duration = inf
    for b in bold_file_paths:
        repetition_time = database.metadata(b, "repetition_time")
        assert isinstance(repetition_time, float)
        scan_duration = min(nvol(b) * repetition_time, scan_duration)

    onset = []
    duration = []

    t = 0.0
    d = 5.0
    while True:
        t += d
        t += abs(normalvariate(0, 1)) + 1.0  # jitter

        if t < scan_duration:
            onset.append(t)
            duration.append(d)
        else:
            break

    n = len(duration)
    trial_type = choices(["a", "b"], k=n)

    events = pd.DataFrame(dict(onset=onset, duration=duration, trial_type=trial_type))

    events_fname = Path.cwd() / "events.tsv"
    events.to_csv(events_fname, sep="\t", index=False, header=True)

    return events_fname


@pytest.fixture(scope="module")
def atlas_harvard_oxford(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp(basename="pcc_mask")

    os.chdir(str(tmp_path))

    inputtarpath = get_resource("HarvardOxford.tgz")

    with tarfile.open(inputtarpath) as fp:
        def is_within_directory(directory, target):
            
            abs_directory = os.path.abspath(directory)
            abs_target = os.path.abspath(target)
        
            prefix = os.path.commonprefix([abs_directory, abs_target])
            
            return prefix == abs_directory
        
        def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
        
            for member in tar.getmembers():
                member_path = os.path.join(path, member.name)
                if not is_within_directory(path, member_path):
                    raise Exception("Attempted Path Traversal in Tar File")
        
            tar.extractall(path, members, numeric_owner=numeric_owner) 
            
        
        safe_extract(fp, tmp_path)

    maps = {
        m: (
            tmp_path
            / "data"
            / "atlases"
            / "HarvardOxford"
            / f"HarvardOxford-{m}.nii.gz"
        )
        for m in ("cort-prob-1mm", "cort-prob-2mm", "sub-prob-1mm", "sub-prob-2mm")
    }
    return maps


@pytest.fixture(scope="module")
def pcc_mask(tmp_path_factory, atlas_harvard_oxford):
    tmp_path = tmp_path_factory.mktemp(basename="pcc_mask")

    os.chdir(str(tmp_path))

    atlas_img = nib.load(atlas_harvard_oxford["cort-prob-2mm"])
    atlas = atlas_img.get_fdata()

    pcc_mask = atlas[..., 29] > 10

    pcc_mask_img = new_img_like(atlas_img, pcc_mask, copy_header=True)

    pcc_mask_fname = Path.cwd() / "pcc.nii.gz"
    nib.save(pcc_mask_img, pcc_mask_fname)

    return pcc_mask_fname


@pytest.fixture(scope="function")
def mock_spec(bids_data, task_events, pcc_mask):
    spec_schema = SpecSchema()
    spec = spec_schema.load(spec_schema.dump(dict()), partial=True)  # get defaults
    assert isinstance(spec, Spec)

    spec.files = list(
        map(
            FileSchema().load,
            [
                dict(datatype="bids", path=str(bids_data)),
                dict(
                    datatype="func",
                    suffix="events",
                    extension=".tsv",
                    tags=dict(task="rest"),
                    path=str(task_events),
                    metadata=dict(units="seconds"),
                ),
                dict(
                    datatype="ref",
                    suffix="map",
                    extension=".nii.gz",
                    tags=dict(desc="smith09"),
                    path=str(get_resource("PNAS_Smith09_rsn10.nii.gz")),
                    metadata=dict(space="MNI152NLin6Asym"),
                ),
                dict(
                    datatype="ref",
                    suffix="seed",
                    extension=".nii.gz",
                    tags=dict(desc="pcc"),
                    path=str(pcc_mask),
                    metadata=dict(space="MNI152NLin6Asym"),
                ),
                dict(
                    datatype="ref",
                    suffix="atlas",
                    extension=".nii.gz",
                    tags=dict(desc="schaefer2018"),
                    path=str(
                        get_template(
                            "MNI152NLin2009cAsym",
                            resolution=2,
                            atlas="Schaefer2018",
                            desc="400Parcels17Networks",
                            suffix="dseg",
                        )
                    ),
                    metadata=dict(space="MNI152NLin2009cAsym"),
                ),
            ],
        )
    )

    setting_base = dict(
        confounds_removal=["(trans|rot)_[xyz]"],
        grand_mean_scaling=dict(mean=10000.0),
        ica_aroma=True,
    )

    spec.settings = list(
        map(
            SettingSchema().load,
            [
                dict(
                    name="dualRegAndSeedCorrAndTaskBasedSetting",
                    output_image=False,
                    bandpass_filter=dict(type="gaussian", hp_width=125.0),
                    smoothing=dict(fwhm=6.0),
                    **setting_base,
                ),
                dict(
                    name="fALFFUnfilteredSetting",
                    output_image=False,
                    **setting_base,
                ),
                dict(
                    name="fALFFAndReHoAndCorrMatrixSetting",
                    output_image=False,
                    bandpass_filter=dict(type="frequency_based", low=0.01, high=0.1),
                    **setting_base,
                ),
            ],
        )
    )

    spec.features = list(
        map(
            FeatureSchema().load,
            [
                dict(
                    name="taskBased",
                    type="task_based",
                    high_pass_filter_cutoff=125.0,
                    conditions=["a", "b"],
                    contrasts=[
                        dict(name="a>b", type="t", values=dict(a=1.0, b=-1.0)),
                    ],
                    setting="dualRegAndSeedCorrAndTaskBasedSetting",
                ),
                dict(
                    name="seedCorr",
                    type="seed_based_connectivity",
                    seeds=["pcc"],
                    setting="dualRegAndSeedCorrAndTaskBasedSetting",
                ),
                dict(
                    name="dualReg",
                    type="dual_regression",
                    maps=["smith09"],
                    setting="dualRegAndSeedCorrAndTaskBasedSetting",
                ),
                dict(
                    name="corrMatrix",
                    type="atlas_based_connectivity",
                    atlases=["schaefer2018"],
                    setting="fALFFAndReHoAndCorrMatrixSetting",
                ),
                dict(
                    name="reHo",
                    type="reho",
                    setting="fALFFAndReHoAndCorrMatrixSetting",
                    smoothing=dict(fwhm=6.0),
                ),
                dict(
                    name="fALFF",
                    type="falff",
                    setting="fALFFAndReHoAndCorrMatrixSetting",
                    unfiltered_setting="fALFFUnfilteredSetting",
                    smoothing=dict(fwhm=6.0),
                ),
            ],
        )
    )

    spec.global_settings.update(dict(sloppy=True))

    return spec


@pytest.mark.timeout(120)
def test_empty(tmp_path, mock_spec):
    mock_spec.settings = list()
    mock_spec.features = list()

    save_spec(mock_spec, workdir=tmp_path)

    with pytest.raises(RuntimeError):
        init_workflow(tmp_path)


@pytest.mark.timeout(600)
def test_with_reconall(tmp_path, mock_spec):
    mock_spec.global_settings.update(dict(run_reconall=True))

    save_spec(mock_spec, workdir=tmp_path)

    workflow = init_workflow(tmp_path)

    graphs = init_execgraph(tmp_path, workflow)

    graph = next(iter(graphs.values()))
    assert any("recon" in u.name for u in graph.nodes)


@pytest.mark.slow
@pytest.mark.timeout(3 * 3600)
def test_feature_extraction(tmp_path, mock_spec):
    save_spec(mock_spec, workdir=tmp_path)

    config.nipype.omp_nthreads = cpu_count()

    workflow = init_workflow(tmp_path)

    graphs = init_execgraph(tmp_path, workflow)
    graph = next(iter(graphs.values()))

    assert any("sdc_estimate_wf" in u.fullname for u in graph.nodes)

    parser = build_parser()
    opts = parser.parse_args(args=list())

    opts.graphs = graphs
    opts.nipype_run_plugin = "Linear"
    opts.debug = True

    run_stage_run(opts)


def test_with_fieldmaps(tmp_path, bids_data, mock_spec):
    bids_path = tmp_path / "bids"
    shutil.copytree(bids_data, bids_path)

    # delete extra files
    fmap_path = bids_path / "sub-1012" / "fmap"
    files = [
        "sub-1012_acq-3mm_phasediff.nii.gz",
        "sub-1012_acq-3mm_phasediff.json",
        "sub-1012_acq-3mm_magnitude2.nii.gz",
        "sub-1012_acq-3mm_magnitude2.json",
        "sub-1012_acq-3mm_magnitude1.nii.gz",
        "sub-1012_acq-3mm_magnitude1.json",
    ]
    for i in files:
        Path(fmap_path / i).unlink()

    # copy image file
    shutil.copy(
        os.path.join(fmap_path, "sub-1012_dir-PA_epi.nii.gz"),
        os.path.join(fmap_path, "sub-1012_dir-AP_epi.nii.gz"),
    )

    # copy metadata
    with open(fmap_path / "sub-1012_dir-PA_epi.json", "r") as json_file:
        data = json.load(json_file)
    data["PhaseEncodingDirection"] = "j-"
    with open(fmap_path / "sub-1012_dir-AP_epi.json", "w") as json_file:
        json.dump(data, json_file)

    # start testing
    workdir = tmp_path / "workdir"
    save_spec(mock_spec, workdir=workdir)

    config.nipype.omp_nthreads = cpu_count()

    workflow = init_workflow(workdir)

    graphs = init_execgraph(workdir, workflow)
    graph = next(iter(graphs.values()))

    assert any("sdc_estimate_wf" in u.fullname for u in graph.nodes)
