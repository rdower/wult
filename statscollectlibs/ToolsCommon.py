
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 tw=100 et ai si
#
# Copyright (C) 2019-2022 Intel Corporation
# SPDX-License-Identifier: BSD-3-Clause
#
# Author: Artem Bityutskiy <artem.bityutskiy@linux.intel.com>

"""
This module contains miscellaneous functions used by the 'stats-collect', 'wult' and 'ndl' tools.
There is really no single clear purpose this module serves, it is just a collection of shared code.
Many functions in this module require the 'args' object which represents the command-line arguments.
"""

# Description for the '--outdir' option of the 'report' command.
def get_report_outdir_descr(toolname):
    """
    Returns description for the '--outdir' option of the 'report' command for the 'toolname' tool.
    """

    descr = f"""Path to the directory to store the report at. By default the report is stored in the
                '{toolname}-report-<reportid>' sub-directory of the test result directory. If there
                are multiple test results, the report is stored in the current directory. The
                '<reportid>' is report ID of {toolname} test result."""
    return descr
