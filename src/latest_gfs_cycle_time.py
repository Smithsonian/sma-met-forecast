#!/usr/bin/env python
#
# latest_gfs_cycle_time.py - generate a string "yyyymmdd hh"
# corresponding to the most recent GFS cycle time.

import datetime
import os
import sys

#
# The default GFS forecast production lag is 6 hours.  To get an
# earlier forecast, this might be set somewhat shorter in the
# environment, with due care taken to ensure it isn't set too short
#
gfs_lag = float(os.getenv('GFS_PRODUCTION_LAG', '6.0'))

dt_gfs_lag = datetime.timedelta(hours=gfs_lag)
dt_gfs     = datetime.datetime.utcnow() - dt_gfs_lag

print('{:04d}{:02d}{:02d} {:02d}'.format(
    dt_gfs.year, dt_gfs.month, dt_gfs.day, int(dt_gfs.hour / 6) * 6), end='')
