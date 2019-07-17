#!/usr/bin/env python
#
# relative_gfs_cycle_time.py - generate a string "yyyymmdd hh"
# corresponding to a GFS forecast cycle time displaced by some
# number of hours relative to another GFS cycle time.
#
# Example:
#
#   relative_gfs_cycle_time.py yyyymmdd hh -12
#
# will generate a string corresponding to a GFS cycle 12 hours
# before the cycle corresponding to yyyymmdd hh
#

import datetime
import os
import sys

dt_ref_date = datetime.datetime.strptime(sys.argv[1], '%Y%m%d')
hr_offset   = float(sys.argv[2]) + float(sys.argv[3])
dt_offset   = datetime.timedelta(hours=hr_offset)
dt_gfs      = dt_ref_date + dt_offset

print('{:04d}{:02d}{:02d} {:02d}'.format(
    dt_gfs.year, dt_gfs.month, dt_gfs.day, int(dt_gfs.hour / 6) * 6), end='')
