# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import os
from random import seed

import nibabel as nib
import numpy as np
import pytest
from nipype.interfaces import fsl

from ..tempfilt import TemporalFilter


@pytest.mark.slow
@pytest.mark.timeout(60)
def test_TemporalFilter(tmp_path):
    seed(a=0x4D3C732F)

    array = np.random.rand(10, 10, 10, 100) * 1000 + 10000
    img = nib.Nifti1Image(array, np.eye(4))
    assert isinstance(img.header, nib.Nifti1Header)
    img.header.set_data_dtype(np.float64)

    os.chdir(str(tmp_path))

    in_file = "img.nii.gz"
    nib.save(img, in_file)

    instance = TemporalFilter()
    instance.inputs.in_file = in_file
    instance.inputs.lowpass_sigma = 12
    instance.inputs.highpass_sigma = 125
    result = instance.run()
    assert result.outputs is not None

    r0 = nib.load(result.outputs.out_file).get_fdata()

    instance = fsl.TemporalFilter()
    instance.inputs.in_file = in_file
    instance.inputs.lowpass_sigma = 12
    instance.inputs.highpass_sigma = 125
    result = instance.run()
    assert result.outputs is not None

    r1 = nib.load(result.outputs.out_file).get_fdata()
    assert np.allclose(r0, r1)
