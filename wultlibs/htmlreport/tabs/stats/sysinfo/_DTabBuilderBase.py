# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 tw=100 et ai si
#
# Copyright (C) 2022 Intel Corporation
# SPDX-License-Identifier: BSD-3-Clause
#
# Authors: Adam Hawley <adam.james.hawley@intel.com>

"""
This module provides the capability of populating a "SysInfo" data tab.

"SysInfo" tabs contain various system information about the systems under test (SUTs).
"""

import logging
from difflib import HtmlDiff
from pepclibs.helperlibs.Exceptions import Error
from wultlibs.helperlibs import FSHelpers
from wultlibs.htmlreport.tabs import _Tabs

_LOG = logging.getLogger()

class DTabBuilderBase:
    """
    This class provides the capability of populating a "SysInfo" tab.

    Public method overview:
     * get_tab() - returns a '_Tabs.DTabDC' instance which represents system information.
    """

    def _generate_diff(self, paths, fp):
        """
        Helper function for '_add_fpreviews()'. Generates an HTML diff with path 'fp' in a "diffs"
        sub-directory. Returns the path of the HTML diff relative to 'self.outdir'.
        """

        # Read the contents of the files into 'lines'.
        lines = []
        for diff_src in paths.values():
            try:
                fp = self.outdir / diff_src
                with open(fp, "r") as f:
                    lines.append(f.readlines())
            except OSError as err:
                raise Error(f"cannot open file at '{fp}' to create diff: {err}") from None

        # Store the diff in a separate directory and with the '.html' file ending.
        diff_path = (self.outdir / "diffs" / fp).with_suffix('.html')
        try:
            diff_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as err:
            raise Error(f"cannot create diffs directory '{diff_path.parent}': "
                        f"{err}") from None

        try:
            with open(diff_path, "w") as f:
                f.write(HtmlDiff().make_file(lines[0], lines[1]))
        except Exception as err:
            raise Error(f"cannot create diff at path '{diff_path}': {err}") from None

        return diff_path.relative_to(self.outdir)

    def _add_fpreviews(self, stats_paths):
        """
        Returns a list of '_Tabs.FilePreviewDC' instances to include in the tab generated by
        'get_tab()'. Adds files found in 'stats_paths'.
        """

        if any(not fp for fp in stats_paths.values()):
            raise Error("Unable to add file previews since not all reports have a statistics dir.")

        fpreviews = []
        for name, fp in self.files.items():
            paths = {}
            for reportid, stats_path in stats_paths.items():
                src_path = stats_path / fp

                if not src_path.exists():
                    # If one of the reports does not have a file, exclude the file preview entirely.
                    paths = {}
                    _LOG.debug("skipping file preview '%s' since the file '%s' doesn't exist for "
                               "all reports.", name, fp)
                    break

                # If the file is not in 'outdir' it should be copied to 'outdir'.
                if self.outdir not in src_path.parents:
                    dst_dir = self.outdir / reportid

                    try:
                        dst_dir.mkdir(parents=True, exist_ok=True)
                    except OSError as err:
                        raise Error(f"can't create SysInfo output directory '{dst_dir}': "
                                    f"{err}") from None

                    dst_path = dst_dir / fp
                    FSHelpers.move_copy_link(src_path, dst_path, "copy")
                else:
                    dst_path = src_path

                paths[reportid] = dst_path.relative_to(self.outdir)

            if len(paths) == 2:
                try:
                    diff = self._generate_diff(paths, fp)
                except Error as err:
                    _LOG.info("Unable to generate diff for file preview '%s'.", name)
                    _LOG.debug(err)
                    diff = ""
            else:
                diff = ""

            if paths:
                fpreviews.append(_Tabs.FilePreviewDC(name, paths, diff))
        return fpreviews

    def get_tab(self, stats_paths):
        """
        Returns a '_Tabs.DTabDC' instance which represents system information. Arguments are as
        follows:
         * stats_paths - a dictionary in the format '{ReportID: StatsDir}' where 'StatsDir' is the
                         path to the directory which contains raw statistics files for 'ReportID'.
        """

        fpreviews = self._add_fpreviews(stats_paths)
        if fpreviews:
            return _Tabs.DTabDC(self.name, fpreviews=fpreviews)
        raise Error(f"Unable to build '{self.name}' SysInfo tab, no file previews could be "
                    f"generated.")

    def __init__(self, name, outdir, files):
        """
        Class constructor. Arguments are as follows:
         * name - name to give the tab produced when 'get_tab()' is called.
         * outdir - the directory to store tab files in.
         * files - a dictionary containing the paths of files to include file previews for.
                   Expected to be in the format '{Name: FilePath}' where 'Name' will be the title
                   of the file preview and 'FilePath' is the path of the file to preview.
                   'FilePath' should be relative to the directories in 'stats_paths'
        """

        self.name = name
        self.outdir = outdir
        self.files = files
