# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 tw=100 et ai si
#
# Copyright (C) 2019-2022 Intel Corporation
# SPDX-License-Identifier: BSD-3-Clause
#
# Authors: Artem Bityutskiy <artem.bityutskiy@linux.intel.com>
#          Vladislav Govtva <vladislav.govtva@intel.com>
#          Adam Hawley <adam.james.hawley@intel.com>

"""
This module defines what is expected by the JavaScript side when adding a Metric tab to HTML
reports.
"""

from pepclibs.helperlibs import Trivial
from pepclibs.helperlibs.Exceptions import Error
from wultlibs.htmlreport import _SummaryTable
from wultlibs.htmlreport.tabs import _DTabBuilder

class MetricDTabBuilder(_DTabBuilder.DTabBuilder):
    """
    This class provides the functionality to build '_Tabs.DTabDC' instances which contain data
    for a given metric.

    Public methods overview:
    1. Add a summary table to the tab.
       * 'add_smrytbl()'
    2. Add plots to the tab.
       * 'add_plots()'
    3. Generate '_Tabs.DTabDC' instance.
       * 'get_tab()'
    """

    def add_smrytbl(self, smry_funcs, defs):
        """
        Overrides 'super().add_smrytbl()', refer to that method for more information. Results have
        summaries pre-calculated therefore we do not have to calculate them in this method as the
        parent class does.
        """

        # Summaries are calculated only for numeric metrics. Tab metric name is represented by
        # 'smrytblpath.name', this should come first if it is included in 'smry_funcs'.
        tab_metric = self._tabmdef["name"]
        if tab_metric in smry_funcs and self._refres.is_numeric(tab_metric):
            metrics = [tab_metric]
        else:
            metrics = []

        metrics += [metric for metric in smry_funcs if self._refres.is_numeric(metric)]

        # Dedupe the list so that each metric only appears once.
        deduped_mdefs = [defs.info[metric] for metric in Trivial.list_dedup(metrics)]

        self._smrytbl = _SummaryTable.SummaryTable()

        for mdef in deduped_mdefs:
            # Create row in the summary table for each metric.
            fmt = "{:.2f}" if mdef["type"] == "float" else None
            self._smrytbl.add_metric(mdef["title"], mdef["short_unit"], mdef["descr"], fmt)

            # Select only those functions that are present in all test results. For example, 'std'
            # will not be present if the result has only one datapoint. In this case, we need to
            # exclude the 'std' function.
            funcs = []
            for funcname in smry_funcs[mdef["name"]]:
                if all(res.smrys[mdef["name"]].get(funcname) for res in self._rsts):
                    funcs.append(funcname)

            # Populate each row with summary functions for each result.
            for res in self._rsts:
                for funcname in funcs:
                    val = res.smrys[mdef["name"]][funcname]
                    self._smrytbl.add_smry_func(res.reportid, mdef["title"], funcname, val)
        try:
            self._smrytbl.generate(self.smry_path)
        except Error as err:
            raise Error("Failed to generate summary table.") from err

    @staticmethod
    def base_unit(df, mdef):
        """
        Convert column represented by metric in 'mdef' with 'microsecond' units to seconds, and
        return the converted column.
        """

        colname = mdef["name"]

        # This is not generic, but today we have to deal only with microseconds, so this is good
        # enough.
        if mdef.get("unit") != "microsecond":
            return df[colname]

        base_colname = f"{colname}_base"
        if base_colname not in df:
            df.loc[:, base_colname] = df[colname] / 1000000
        return df[base_colname]

    @staticmethod
    def get_base_si_unit(mdef):
        """
        Plotly will handle SI unit prefixes therefore we should provide only the base unit.
        Several defs list 'us' as the 'short_unit' which includes the prefix so should be
        reduced to just the base unit 's'. This method accepts a metric definition dictionary
        'mdef' and returns a new dictionary with units adjusted accordingly.
        """

        mdef = mdef.copy()

        # This is not generic, but today we have to deal only with microseconds, so this is good
        # enough.
        if mdef.get("short_unit") == "us":
            mdef["short_unit"] = "s"

        if mdef.get("unit") == "microsecond":
            mdef["unit"] = "second"

        return mdef

    def _add_scatter(self, xdef, ydef, hover_defs=None):
        """
        Create a scatter plot with the metric represented by 'xdef' on the X-axis and the metric
        represented by 'ydef' on the Y-axis using data from 'rsts' which is provided to the class
        during initialisation. Arguments are the same as in '_DTabBuilder._add_scatter()'.
        """

        for mdef in xdef, ydef:
            for sdf in self._reports.values():
                sdf[mdef["name"]] = self.base_unit(sdf, mdef)

        xdef = self.get_base_si_unit(xdef)
        ydef = self.get_base_si_unit(ydef)

        super()._add_scatter(xdef, ydef, hover_defs)

    def _add_histogram(self, mdef, cumulative=False, xbins=None):
        """
        Extends 'super()._add_histogram()' by addding custom binning and ensuring that the data has
        been scaled.
        """

        for sdf in self._reports.values():
            sdf[mdef["name"]] = self.base_unit(sdf, mdef)

        if xbins is None:
            # Calculate custom bins.
            xmin, xmax = (float("inf"), -float("inf"))
            for res in self._rsts:
                # In case of non-numeric column there is only one x-value per bin.
                if not res.is_numeric(mdef["name"]):
                    return {"size" : 1}

                xdata = self.base_unit(res.df, mdef)
                xmin = min(xmin, xdata.min())
                xmax = max(xmax, xdata.max())

            xbins = {"size" : (xmax - xmin) / 1000}

        return super()._add_histogram(mdef, cumulative, xbins)

    def __init__(self, rsts, outdir, metric_def, basedir=None):
        """
        The class constructor. Arguments as follows:
         * rsts - sets of results containing the data to represent in this tab.
         * outdir - the output directory, in which to create the tab sub-dictionary which will
                    contain plot HTML files and summary table files.
         * metric_def - dictionary containing the definition for the metric represented by this tab.
         * basedir - base directory of the report. All paths should be made relative to this.
                     Defaults to 'outdir'.
        """

        self._tabmdef = metric_def
        self._rsts = rsts
        self._refres = rsts[0]

        reports = {res.reportid: res.df for res in rsts}
        super().__init__(reports, outdir, metric_def, basedir)
