# stackcollapse.py - format perf samples with one line per distinct call stack
# SPDX-License-Identifier: GPL-2.0
#
# This script's output has two space-separated fields.  The first is a semicolon
# separated stack including the program name (from the "comm" field) and the
# function names from the call stack.  The second is a count:
#
#  swapper;start_kernel;rest_init;cpu_idle;default_idle;native_safe_halt 2
#
# The file is sorted according to the first field.
#
# Input may be created and processed using:
#
#  perf record -a -g -F 99 sleep 60
#  perf script report stackcollapse > out.stacks-folded
#
# (perf script record stackcollapse works too).
#
# Written by Paolo Bonzini <pbonzini@redhat.com>
# Based on Brendan Gregg's stackcollapse-perf.pl script.

from __future__ import print_function
from collections import defaultdict

# event handlers

lines = defaultdict(lambda: 0)
annotate_kernel=False

def process_event(param_dict ):
    def tidy_function_name(sym, dso):
        if sym is None:
            sym = '[unknown]'

        sym = sym.replace(';', ':')

        if annotate_kernel and dso == '[kernel.kallsyms]':
            return sym + '_[k]'
        else:
            return sym

    stack = list()
    if 'callchain' in param_dict:
        for entry in param_dict['callchain']:
            entry.setdefault('sym', dict())
            entry['sym'].setdefault('name', None)
            entry.setdefault('dso', None)
            stack.append(tidy_function_name(entry['sym']['name'],
                                            entry['dso']))
    else:
        param_dict.setdefault('symbol', None)
        param_dict.setdefault('dso', None)
        stack.append(tidy_function_name(param_dict['symbol'],
                                        param_dict['dso']))

    stack_string = ';'.join(reversed(stack))
    lines[stack_string] = lines[stack_string] + 1

def trace_end():
    list = sorted(lines)
    for stack in list:
        print("%s %d" % (stack, lines[stack]))
