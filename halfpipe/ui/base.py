# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:

import os
from pathlib import Path

from .. import __version__
from ..ingest.database import Database
from ..logging import logging_context
from ..model.spec import Spec, SpecSchema, load_spec, save_spec
from ..utils import logger
from ..workdir import init_workdir
from .components import (
    App,
    DirectoryInputView,
    GiantTextView,
    SingleChoiceInputView,
    SpacerView,
    TextView,
)
from .components.config import Config as UIConfig
from .feature import FeaturesStep
from .file import BidsStep
from .model import ModelsStep
from .step import Step


class Context:
    def __init__(self):
        spec_schema = SpecSchema()
        spec = spec_schema.load(spec_schema.dump({}), partial=True)
        assert isinstance(spec, Spec)
        self.spec: Spec = spec  # initialize with defaults

        self.database = Database(self.spec)

        self.workdir = None
        self.use_existing_spec = False
        self.debug = False

        self.already_checked = set()

    def put(self, fileobj):
        self.database.put(fileobj)
        return len(self.spec.files) - 1


class UseExistingSpecStep(Step):
    options = [
        "Run without modification",
        "Start over at beginning",
        "Start over at features",
        "Add another feature",
        "Start over at models",
        "Add another model",
    ]

    def setup(self, ctx):
        self.is_first_run = True
        self.existing_spec = load_spec(workdir=ctx.workdir, logger=logger)
        self.choice = None
        if self.existing_spec is not None:
            self._append_view(TextView("Found spec file in working directory"))

            options = self.options[:3]

            if len(self.existing_spec.features) > 0:
                options.append(self.options[3])
                options.append(self.options[4])
            if len(self.existing_spec.models) > 0:
                options.append(self.options[5])

            self.input_view = SingleChoiceInputView(options, isVertical=True)
            self._append_view(self.input_view)
            self._append_view(SpacerView(1))

    def run(self, _):
        if self.existing_spec is not None:
            self.choice = self.input_view()
            if self.choice is None:
                return False
            return True
        else:
            return self.is_first_run

    def next(self, ctx):
        if self.is_first_run or self.existing_spec is not None:
            self.is_first_run = False

            if self.choice is None or self.existing_spec is None:
                return BidsStep(self.app)(ctx)

            choice_index = self.options.index(self.choice)

            global_settings = self.existing_spec.global_settings
            files = self.existing_spec.files
            settings = self.existing_spec.settings
            features = self.existing_spec.features
            models = self.existing_spec.models

            if choice_index > 1:
                ctx.spec.global_settings = global_settings
                for fileobj in files:
                    ctx.put(fileobj)
            if choice_index > 2:
                ctx.spec.settings = settings
                ctx.spec.features = features

            if choice_index == 0:
                ctx.use_existing_spec = True
                return ctx
            elif choice_index == 1:
                return BidsStep(self.app)(ctx)
            elif choice_index in frozenset([2, 3]):
                return FeaturesStep(self.app)(ctx)
            elif choice_index in frozenset([4, 5]):
                if choice_index == 5:
                    ctx.spec.models = models
                return ModelsStep(self.app)(ctx)


class WorkingDirectoryStep(Step):
    def setup(self, ctx):
        self.predefined_workdir = True
        self.is_first_run = True

        self.workdir = ctx.workdir

        if self.workdir is None:
            self._append_view(TextView("Specify working directory"))
            self.input_view = DirectoryInputView(exists=False)
            self._append_view(self.input_view)
            self._append_view(SpacerView(1))
            self.predefined_workdir = False

    def run(self, _):
        if self.predefined_workdir:
            return self.is_first_run

        self.workdir = self.input_view()
        return self.workdir is not None

    def next(self, ctx):
        workdir = init_workdir(self.workdir)
        ctx.workdir = workdir

        if self.is_first_run or not self.predefined_workdir:
            self.is_first_run = False
            return UseExistingSpecStep(self.app)(ctx)


class FirstStep(Step):
    def _welcome_text(self):
        return ["Welcome to ENIGMA HALFpipe!", f"You are using version {__version__}"]

    def setup(self, _):
        self._append_view(GiantTextView("HALFpipe"))
        self._append_view(SpacerView(2))
        for line in self._welcome_text():
            self._append_view(TextView(line))
        self._append_view(SpacerView(1))
        self._append_view(
            TextView("Please report any problems or leave suggestions at")
        )
        self._append_view(TextView("https://github.com/HALFpipe/HALFpipe/issues"))
        self._append_view(SpacerView(1))
        self.is_first_run = True

    def run(self, _):
        return self.is_first_run

    def next(self, ctx):
        if self.is_first_run:
            self.is_first_run = False
            return WorkingDirectoryStep(self.app)(ctx)
        else:
            return


def init_spec_ui(workdir=None, debug=False):
    logging_context.disable_print()

    fs_root = Path(UIConfig.fs_root)

    cur_dir = str(Path.cwd())
    new_dir = fs_root / cur_dir[1:]
    if new_dir.is_dir():
        os.chdir(new_dir)
    else:
        os.chdir(fs_root)

    app = App()
    ctx = Context()
    ctx.debug = debug
    if workdir is not None:
        ctx.workdir = workdir

    with app:
        ctx = FirstStep(app)(ctx)

    logging_context.enable_print()

    if ctx is not None:
        assert ctx.workdir is not None
        workdir = ctx.workdir
        if not ctx.use_existing_spec:
            save_spec(ctx.spec, workdir=ctx.workdir, logger=logger)
    else:
        import sys

        logger.info("Cancelled")
        sys.exit(0)

    return workdir
