# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 tw=100 et ai si
#
# Copyright (C) 2019-2022 Intel Corporation
# SPDX-License-Identifier: BSD-3-Clause
#
# Author: Artem Bityutskiy <artem.bityutskiy@linux.intel.com>

"""This module provides the API for deploying the 'stats-collect' tool."""

import logging
from pepclibs.helperlibs import ArgParse
from statscollectlibs.deploylibs import DeployBase, DeployPyHelpers

_LOG = logging.getLogger()

def add_deploy_cmdline_args(toolname, subparsers, func, argcomplete=None):
    """
    Add the the 'deploy' command to 'argparse' data. The input arguments are as follows.
      * toolname - name of the tool to add the 'deploy' command for.
      * subparsers - the 'argparse' subparsers to add the 'deploy' command to.
      * func - the 'deploy' command handling function.
      * argcomplete - optional 'argcomplete' command-line arguments completer object.
    """

    text = f"Deploy {toolname} helpers."
    descr = f"""Deploy {toolname} helpers to a remote SUT (System Under Test)."""
    parser = subparsers.add_parser("deploy", help=text, description=descr)

    text = f"""When '{toolname}' is deployed, a random temporary directory is used. Use this option
               provide a custom path instead. It will be used as a temporary directory on both
               local and remote hosts. This option is meant for debugging purposes."""
    arg = parser.add_argument("--tmpdir-path", help=text)
    if argcomplete:
        arg.completer = argcomplete.completers.DirectoriesCompleter()

    text = f"""Do not remove the temporary directories created while deploying '{toolname}'. This
               option is meant for debugging purposes."""
    parser.add_argument("--keep-tmpdir", action="store_true", help=text)

    ArgParse.add_ssh_options(parser)

    parser.set_defaults(func=func)
    return parser

class Deploy(DeployBase.DeployBase):
    """
    This class provides the 'deploy()' method which can be used for deploying the dependencies of
    the "stats-collect" tool.
    """

    def _deploy(self):
        """Deploy python helpers to the SUT."""

        deployables = self._get_deployables("pyhelpers")
        stmpdir = self._get_stmpdir()
        btmpdir = self._get_btmpdir()
        ctmpdir = self._get_ctmpdir()

        with DeployPyHelpers.DeployPyHelpers("wult", self._toolname, deployables, self._spman,
                                             self._bpman, self._cpman, stmpdir, btmpdir, ctmpdir,
                                             debug=self._debug) as depl:
            pyhelpers = list(self._cats.get("pyhelpers"))
            depl.deploy(self._toolname, pyhelpers)

    def deploy(self):
        """Deploy all the installables to the SUT."""

        if not self._cats.get("pyhelpers"):
            _LOG.info("Nothing to deploy to the local host.")
            return

        try:
            self._deploy()
        finally:
            self._remove_tmpdirs()

    def __init__(self, toolname, deploy_info, pman=None, tmpdir_path=None,
                 keep_tmpdir=False, debug=False):
        """
        The class constructor. The arguments are the same as in 'DeployBase.__init()'.
        """

        super().__init__("wult", toolname, deploy_info, pman=pman, tmpdir_path=tmpdir_path,
                         keep_tmpdir=keep_tmpdir, debug=debug)

        # Python helpers need to be deployed only to a remote host. The local host should already
        # have them:
        #   * either deployed via 'setup.py'.
        #   * or if running from source code, present in the source code.
        if not self._spman.is_remote:
            for installable in self._cats["pyhelpers"]:
                del self._insts[installable]
            self._cats["pyhelpers"] = {}
