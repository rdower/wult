# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 tw=100 et ai si
#
# Copyright (C) 2019-2022 Intel Corporation
# SPDX-License-Identifier: BSD-3-Clause
#
# Author: Artem Bityutskiy <artem.bityutskiy@linux.intel.com>

"""
This module includes the "start" 'wult' command implementation.
"""

import logging
import contextlib
from pathlib import Path
from pepclibs.helperlibs import Logging, Trivial
from pepclibs.helperlibs.Exceptions import Error, ErrorNotSupported
from pepclibs.msr import PowerCtl
from pepclibs import CPUIdle, CPUInfo
from statscollectlibs.collector import StatsCollectBuilder
from wultlibs.deploylibs import _Deploy
from wultlibs.helperlibs import Human
from wultlibs.rawresultlibs import WORawResult
from wultlibs import Devices, WultRunner, _FreqNoise
from wulttools import _Common
from wulttools.wult import _WultCommon

_LOG = logging.getLogger()

def _check_settings(pman, dev, csinfo, cpunum, devid):
    """
    Some settings of the SUT may lead to results that are potentially confusing for the user. Look
    for such settings and if found, print a notice message. The arguments are as follows.
      * pman - the process manager object that defines the host to run the measurements on.
      * dev - the delayed event device object created by 'Devices.GetDevice()'.
      * devid - the ID of the device used for measuring the latency.
      * csinfo - cstate info from 'CStates.get_cstates_info()'.
      * cpunum - the logical CPU number to measure.
    """

    if dev.info.get("aspm_enabled"):
        _LOG.notice("PCI ASPM is enabled for the delayed event device '%s', and this "
                    "typically increases the measured latency", devid)

    enabled_cstates = []
    for _, info in csinfo.items():
        if info["disable"] == 0 and info["name"] != "POLL":
            enabled_cstates.append(info["name"])

    with contextlib.suppress(ErrorNotSupported), PowerCtl.PowerCtl(pman=pman) as powerctl:
        # Check for the following 3 conditions to be true at the same time.
        # * C6 is enabled.
        # * C6 pre-wake is enabled.
        # * A timer-based method is used.

        # Hackish, but only NIC-based methods have the 'aspm_enabled' key. Use this to distinguish
        # local timer-based methods.
        is_timer_based = "aspm_enabled" not in dev.info

        if is_timer_based and "C6" in enabled_cstates and \
           powerctl.is_cpu_feature_supported("cstate_prewake", cpunum) and \
           powerctl.is_cpu_feature_enabled("cstate_prewake", cpunum):
            _LOG.notice("C-state prewake is enabled, and this usually hides the real "
                        "latency when using '%s' as delayed event device", devid)

        # Check for the following 2 conditions to be true at the same time.
        # * C1 is enabled.
        # * C1E auto-promotion is enabled.
        if enabled_cstates in [["C1"], ["C1_ACPI"]]:
            if powerctl.is_cpu_feature_enabled("c1e_autopromote", cpunum):
                _LOG.notice("C1E autopromote is enabled, all %s requests are converted to C1E",
                            enabled_cstates[0])

def _generate_report(args):
    """Implement the 'report' command for start."""

    from wultlibs.htmlreport import WultReport # pylint: disable=import-outside-toplevel

    rsts = _Common.open_raw_results([args.outdir], args.toolname)
    rep = WultReport.WultReport(rsts, args.outdir / "html-report", report_descr=args.reportid)
    rep.relocatable = False
    rep.set_hover_metrics(_WultCommon.HOVER_METRIC_REGEXS)
    rep.generate()

def _check_cpu_vendor(args, cpuinfo, pman):
    """
    Check if the CPU vendor is compatible with the requested measurement method.
    """

    vendor = cpuinfo.info["vendor"]
    if vendor == "GenuineIntel":
        # Every method supports at least some Intel CPUs.
        return

    if vendor != "AuthenticAMD":
        raise ErrorNotSupported(f"unsupported CPU vendor '{vendor}'{pman.hostmsg}.\nOnly Intel and "
                                f"AMD CPUs are currently supported.")

    # In case of AMD CPU the TDT-based methods are not currently supported, other methods are
    # supported.
    if "tdt" in args.devid:
        raise ErrorNotSupported("methods based on TSC deadline timer (TDT) support only Intel "
                                "CPUs.\nPlease, use a non-TDT method for measuring AMD CPUs.")

def start_command(args):
    """
    Implement the 'start' command. The arguments are as follows.
      * args - the command line arguments object.
    """

    if args.list_stats:
        _Common.start_command_list_stats()
        return

    with contextlib.ExitStack() as stack:
        pman = _Common.get_pman(args)
        stack.enter_context(pman)

        args.reportid = _Common.start_command_reportid(args, pman)

        if not args.outdir:
            args.outdir = Path(f"./{args.reportid}")
        if args.tlimit:
            if Trivial.is_num(args.tlimit):
                args.tlimit = f"{args.tlimit}m"
            args.tlimit = Human.parse_human(args.tlimit, unit="s", integer=True, name="time limit")

        args.ldist = _Common.parse_ldist(args.ldist)

        if not Trivial.is_int(args.dpcnt) or int(args.dpcnt) <= 0:
            raise Error(f"bad datapoints count '{args.dpcnt}', should be a positive integer")
        args.dpcnt = int(args.dpcnt)

        args.tsc_cal_time = Human.parse_human(args.tsc_cal_time, unit="s",
                                              name="TSC calculation time", integer=True)

        cpuinfo = CPUInfo.CPUInfo(pman=pman)
        stack.enter_context(cpuinfo)

        _check_cpu_vendor(args, cpuinfo, pman)

        args.cpunum = cpuinfo.normalize_cpu(args.cpunum)
        res = WORawResult.WORawResult(args.toolname, args.toolver, args.reportid, args.outdir,
                                      cpunum=args.cpunum)
        stack.enter_context(res)

        Logging.setup_stdout_logging(args.toolname, res.logs_path)
        _Common.set_filters(args, res)

        stcoll_builder = StatsCollectBuilder.StatsCollectBuilder()
        stack.enter_context(stcoll_builder)

        if args.stats and args.stats != "none":
            stcoll_builder.parse_stnames(args.stats)
        if args.stats_intervals:
            stcoll_builder.parse_intervals(args.stats_intervals)

        stcoll = stcoll_builder.build_stcoll_nores(pman, args.reportid, cpunum=args.cpunum,
                                                   local_outdir=res.stats_path)
        if stcoll:
            stack.enter_context(stcoll)

        dev = Devices.GetDevice(args.toolname, args.devid, pman, cpunum=args.cpunum, dmesg=True)
        stack.enter_context(dev)

        deploy_info = _Common.reduce_installables(args.deploy_info, dev)
        with _Deploy.DeployCheck("wult", args.toolname, deploy_info, pman=pman) as depl:
            depl.check_deployment()

        if getattr(dev, "netif", None):
            _Common.start_command_check_network(args, pman, dev.netif)

        cpuidle = CPUIdle.CPUIdle(pman=pman, cpuinfo=cpuinfo)
        csinfo = cpuidle.get_cpu_cstates_info(res.cpunum)

        _check_settings(pman, dev, csinfo, args.cpunum, args.devid)

        fnobj = _FreqNoise.FreqNoise(_Common.parse_freq_noise_cmdline_args(args), pman=pman)
        stack.enter_context(fnobj)

        runner = WultRunner.WultRunner(pman, dev, res, args.ldist, tsc_cal_time=args.tsc_cal_time,
                                       cpuidle=cpuidle, stcoll=stcoll, unload=not args.no_unload,
                                       fnobj=fnobj)
        stack.enter_context(runner)

        runner.prepare()
        runner.run(dpcnt=args.dpcnt, tlimit=args.tlimit, keep_rawdp=args.keep_rawdp)

    if args.report:
        _generate_report(args)
