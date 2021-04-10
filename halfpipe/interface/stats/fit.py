# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

"""
"""

import os

from nipype.interfaces.base import (
    traits,
    DynamicTraitedSpec,
    isdefined,
    File,
    InputMultiPath,
)
from nipype.interfaces.io import IOBase, add_traits

from .tsv import DesignSpec
from ...stats.fit import fit, algorithms


class ModelFitInputSpec(DesignSpec):
    cope_files = InputMultiPath(
        File(exists=True),
        mandatory=True,
    )
    var_cope_files = InputMultiPath(
        File(exists=True),
        mandatory=False,
    )
    mask_files = InputMultiPath(
        File(exists=True),
        mandatory=True,
    )

    num_threads = traits.Int(1, usedefault=True)


class ModelFit(IOBase):
    input_spec = ModelFitInputSpec
    output_spec = DynamicTraitedSpec

    def __init__(self, algorithms_to_run=["flame1"], **inputs):
        super(ModelFit, self).__init__(**inputs)
        self._algorithms_to_run = algorithms_to_run
        self._results = dict()

    def _add_output_traits(self, base):
        fieldnames = [
            output
            for a in self._algorithms_to_run
            for output in algorithms[a].outputs
        ]
        return add_traits(base, fieldnames)

    def _list_outputs(self):
        return self._results

    def _run_interface(self, runtime):
        var_cope_files = self.inputs.var_cope_files

        if not isdefined(var_cope_files):
            var_cope_files = None

        prev_os_environ = os.environ.copy()
        os.environ.update({
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
        })

        self._results.update(
            fit(
                cope_files=self.inputs.cope_files,
                var_cope_files=var_cope_files,
                mask_files=self.inputs.mask_files,
                regressors=self.inputs.regressors,
                contrasts=self.inputs.contrasts,

                algorithms_to_run=self._algorithms_to_run,

                num_threads=self.inputs.num_threads,
            )
        )

        os.environ.update(prev_os_environ)

        return runtime
