#!/usr/bin/env python
#
# make_gfs_timestamp.py - takes the output of relative_gfs_cycle_time.py
# and an hour offset, and turns it into a timestamp for the summary data
# file.

import datetime
import dateutil.parser as dparser
import sys

cycle_date = sys.argv[1]
cycle_hour = int(sys.argv[2])
fcast_hour = int(sys.argv[3])

cycle_datetime = dparser.parse(cycle_date)
hour_offset    = datetime.timedelta(hours=(cycle_hour + fcast_hour))
fcast_datetime = cycle_datetime + hour_offset 

print('{:04d}{:02d}{:02d}_{:02d}:00:00'.format(
    fcast_datetime.year,
    fcast_datetime.month,
    fcast_datetime.day,
    fcast_datetime.hour),
    end='')
