# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import os
from os import path as op
from glob import glob

from nipype.interfaces.fsl.model import (
    FLAMEOInputSpec as NipypeFLAMEOInputSpec,
    FLAMEO as NipypeFLAMEO,
)
from nipype.interfaces.base import traits, isdefined, File
from nipype.utils.misc import human_order_sorted


class FLAMEOInputSpec(NipypeFLAMEOInputSpec):
    cope_file = traits.Either(
        File(exists=True),
        traits.Bool(),
        argstr="--copefile=%s",
        desc="cope regressor data file"
    )
    var_cope_file = traits.Either(
        File(exists=True),
        traits.Bool(),
        argstr="--varcopefile=%s",
        desc="varcope weightings data file",
    )
    dof_var_cope_file = traits.Either(
        File(exists=True),
        traits.Bool(),
        argstr="--dofvarcopefile=%s",
        desc="dof data file for varcope data",
    )
    f_con_file = traits.Either(
        File(exists=True),
        traits.Bool(),
        argstr="--fcontrastsfile=%s",
        desc="ascii matrix specifying f-contrasts",
    )
    mask_file = traits.Either(
        File(exists=True),
        traits.Bool(),
        argstr="--maskfile=%s",
        desc="mask file"
    )


class FLAMEO(NipypeFLAMEO):
    """
    Modified to be more robust to filtered out (missing) input files
    These are indicated by the value False
    """
    input_spec = FLAMEOInputSpec

    def _format_arg(self, name, trait_spec, value):
        if value is False:
            return None
        return super(FLAMEO, self)._format_arg(name, trait_spec, value)

    def _run_interface(self, runtime, correct_return_codes=(0,)):
        self.flameo = False

        if isdefined(self.inputs.cope_file) and self.inputs.cope_file is not False:
            if isdefined(self.inputs.mask_file) and self.inputs.mask_file is not False:
                self.flameo = True
                runtime = super(FLAMEO, self)._run_interface(runtime)

        return runtime

    def _list_outputs(self):
        outputs = self._outputs().get()

        if self.flameo is False:
            return outputs

        pth = op.join(os.getcwd(), self.inputs.log_dir)

        pes = human_order_sorted(glob(os.path.join(pth, "pe[0-9]*.*")))
        assert len(pes) >= 1, "No pe volumes generated by FSL Estimate"
        outputs["pes"] = pes

        res4d = human_order_sorted(glob(os.path.join(pth, "res4d.*")))
        assert len(res4d) == 1, "No residual volume generated by FSL Estimate"
        outputs["res4d"] = res4d[0]

        copes = human_order_sorted(glob(os.path.join(pth, "cope[0-9]*.*")))
        assert len(copes) >= 1, "No cope volumes generated by FSL CEstimate"
        outputs["copes"] = copes

        var_copes = human_order_sorted(glob(os.path.join(pth, "varcope[0-9]*.*")))
        assert len(var_copes) >= 1, "No varcope volumes generated by FSL CEstimate"
        outputs["var_copes"] = var_copes

        zstats = human_order_sorted(glob(os.path.join(pth, "zstat[0-9]*.*")))
        assert len(zstats) >= 1, "No zstat volumes generated by FSL CEstimate"
        outputs["zstats"] = zstats

        if isdefined(self.inputs.f_con_file) and self.inputs.f_con_file is not False:
            zfstats = human_order_sorted(glob(os.path.join(pth, "zfstat[0-9]*.*")))
            assert len(zfstats) >= 1, "No zfstat volumes generated by FSL CEstimate"
            outputs["zfstats"] = zfstats

            fstats = human_order_sorted(glob(os.path.join(pth, "fstat[0-9]*.*")))
            assert len(fstats) >= 1, "No fstat volumes generated by FSL CEstimate"
            outputs["fstats"] = fstats

        tstats = human_order_sorted(glob(os.path.join(pth, "tstat[0-9]*.*")))
        assert len(tstats) >= 1, "No tstat volumes generated by FSL CEstimate"
        outputs["tstats"] = tstats

        mrefs = human_order_sorted(glob(os.path.join(pth, "mean_random_effects_var[0-9]*.*")))
        assert len(mrefs) >= 1, "No mean random effects volumes generated by FLAMEO"
        outputs["mrefvars"] = mrefs

        tdof = human_order_sorted(glob(os.path.join(pth, "tdof_t[0-9]*.*")))
        assert len(tdof) >= 1, "No T dof volumes generated by FLAMEO"
        outputs["tdof"] = tdof

        weights = human_order_sorted(glob(os.path.join(pth, "weights[0-9]*.*")))
        assert len(weights) >= 1, "No weight volumes generated by FLAMEO"
        outputs["weights"] = weights

        outputs["stats_dir"] = pth

        return outputs
