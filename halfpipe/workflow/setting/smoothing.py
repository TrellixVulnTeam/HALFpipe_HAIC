# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import nipype.pipeline.engine as pe
import nipype.interfaces.utility as niu

from ...interface.utility.ops.select import Select
from ...interface.imagemaths.lazyblur import LazyBlurToFWHM

from ..memory import MemoryCalculator


def init_smoothing_wf(fwhm=None, memcalc=MemoryCalculator.default(), name=None, suffix=None):
    """
    Smooths a volume within a mask while correcting for the mask edge
    """
    if name is None:
        if fwhm is not None:
            name = f"smoothing_{int(float(fwhm) * 1e3):d}_wf"
        else:
            name = "smoothing_wf"
    if suffix is not None:
        name = f"{name}_{suffix}"

    workflow = pe.Workflow(name=name)

    inputnode = pe.Node(
        interface=niu.IdentityInterface(fields=["files", "mask", "vals", "fwhm"]), name="inputnode",
    )
    outputnode = pe.Node(interface=niu.IdentityInterface(fields=["files", "mask", "vals"]), name="outputnode")

    workflow.connect(inputnode, "mask", outputnode, "mask")
    workflow.connect(inputnode, "vals", outputnode, "vals")

    if fwhm is not None:
        inputnode.inputs.fwhm = float(fwhm)

    select = pe.Node(
        Select(regex=r".+\.nii(\.gz)?"), name="select"
    )  # smooth only spatial files
    workflow.connect(inputnode, "files", select, "in_list")

    smooth = pe.MapNode(
        LazyBlurToFWHM(outputtype="NIFTI_GZ"),
        iterfield="in_file",
        name="smooth",
        mem_gb=memcalc.series_std_gb * 1.5,
    )
    workflow.connect(select, "match_list", smooth, "in_file")
    workflow.connect(inputnode, "mask", smooth, "mask")
    workflow.connect(inputnode, "fwhm", smooth, "fwhm")

    merge = pe.Node(
        niu.Merge(2), name="merge"
    )
    workflow.connect(smooth, "out_file", merge, "in1")
    workflow.connect(select, "other_list", merge, "in2")

    workflow.connect(merge, "out", outputnode, "files")

    return workflow
