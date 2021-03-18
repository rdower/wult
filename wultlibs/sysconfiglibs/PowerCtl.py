# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 tw=100 et ai si
#
# Copyright (C) 2020-2021 Intel Corporation
# SPDX-License-Identifier: BSD-3-Clause
#
# Author: Antti Laakso <antti.laakso@linux.intel.com>

"""
This module provides API for managing settings in MSR 0x1FC (MSR_POWER_CTL). This is a
model-specific register found on many Intel platforms.
"""

from wultlibs.helperlibs import Procs
from wultlibs.sysconfiglibs import CPUInfo, MSR
from wultlibs.helperlibs.Exceptions import ErrorNotSupported

class PowerCtl:
    """
    This class provides API for managing settings in MSR 0x1FC (MSR_POWER_CTL). This is a
    model-specific register found on many Intel platforms.
    """

    def _toggle_bit(self, bitnr, bitval, cpus="all"):
        """
        Set or clear bit number 'bitnr' in POWER_CTL MSR for CPUs 'cpus'. The 'cpus' argument is the
        same as the 'cpus' argument of the 'CPUIdle.get_cstates_info()' function - please, refer to
        the 'CPUIdle' module for the exact format description.
        """

        if bitval:
            self._msr.set(MSR.MSR_POWER_CTL, MSR.bit_mask(bitnr), cpus=cpus)
        else:
            self._msr.clear(MSR.MSR_POWER_CTL, MSR.bit_mask(bitnr), cpus=cpus)

    def c1e_autopromote_enabled(self, cpu):
        """
        Returns 'True' if C1E autopromotion is enabled for CPU 'cpu', otherwise returns 'False'.
        """

        regval = self._msr.read(MSR.MSR_POWER_CTL, cpu=cpu)
        return MSR.is_bit_set(MSR.C1E_ENABLE, regval)

    def set_c1e_autopromote(self, enable: bool, cpus="all"):
        """
        Enable or disable C1E autopromote for CPUs 'cpus'. The 'cpus' argument is the same as in
        '_toggle_bit()'.
        """
        self._toggle_bit(MSR.C1E_ENABLE, int(enable), cpus)

    def cstate_prewake_enabled(self, cpu):
        """Returns 'True' if C-state prewake is enabled for CPU 'cpu', otherwise returns 'False'."""

        regval = self._msr.read(MSR.MSR_POWER_CTL, cpu=cpu)
        return not MSR.is_bit_set(MSR.CSTATE_PREWAKE_DISABLE, regval)

    def set_cstate_prewake(self, enable: bool, cpus="all"):
        """
        Enable or disable C-state prewake for CPUs 'cpus'. The 'cpus' argument is the same as in
        '_toggle_bit()'.
        """
        self._toggle_bit(MSR.CSTATE_PREWAKE_DISABLE, int(not enable), cpus)

    def __init__(self, proc=None, lscpuinfo=None):
        """
        The class constructor. The argument are as follows.
          * proc - the 'Proc' or 'SSH' object that defines the host to run the measurements on.
          * lscpuinfo - CPU information generated by 'CPUInfo.get_lscpu_info()'.
        """

        if not proc:
            proc = Procs.Proc()

        self._proc = proc
        self._lscpuinfo = lscpuinfo
        self._msr = MSR.MSR(proc=self._proc)

        if self._lscpuinfo is None:
            self._lscpuinfo = CPUInfo.get_lscpu_info(proc=self._proc)

        if self._lscpuinfo["vendor"] != "GenuineIntel":
            raise ErrorNotSupported(f"unsupported CPU model '{self._lscpuinfo['vendor']}', "
                                    f"model-specific register {hex(MSR.MSR_POWER_CTL)} "
                                    f"(MSR_POWER_CTL) is not available{self._proc.hostmsg}. "
                                    f"MSR_POWER_CTL is available only on Intel platforms")

    def close(self):
        """Uninitialize the class object."""

        if getattr(self, "_proc", None):
            self._proc = None
        if getattr(self, "_msr", None):
            self._msr.close()
            self._msr = None

    def __enter__(self):
        """Enter the runtime context."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit the runtime context."""
        self.close()
