#!/usr/bin/env python
# plot_forecast.py - generate tau forecast plot for specified
# number of hours into the future, showing the current and past
# 48 hours' forecasts.
#
# Note that this script has to make use of and interconvert
# between three different kinds of time objects, namely Python
# datetime, matplotlib plot time, and skyfield timescale.
#
# Updated 6/17/2019 for new GFS output with 3-hour resolution
# all the way out to 384 hours.

import argparse
import datetime
import matplotlib
matplotlib.use('Cairo')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import skyfield.api as sf
ts = sf.load.timescale()
e  = sf.load('de421.bsp')
from skyfield import almanac

filenames = (
        'latest-48',
        'latest-42',
        'latest-36',
        'latest-30',
        'latest-24',
        'latest-18',
        'latest-12',
        'latest-06',
        'latest'
        )
widths = (
        0.3,
        0.3,
        0.3,
        0.3,
        0.3,
        0.3,
        0.3,
        0.3,
        1.0)
colors = (
        '0.6',
        '0.6',
        '0.6',
        '0.6',
        '0.6',
        '0.6',
        '0.6',
        '0.6',
        '0.0')

nightcolor = '0.8'
nightalpha = 0.2

tz_UTC = datetime.timezone(datetime.timedelta(hours=0))

parser = argparse.ArgumentParser()
parser.add_argument("site",    help="site name",                 type=str  )
parser.add_argument("lat",     help="site latitude  [deg]",      type=float)
parser.add_argument("lon",     help="site longitude [deg]",      type=float)
parser.add_argument("alt",     help="site altitude  [m]",        type=float)
parser.add_argument("am_vers", help="am version string",         type=str  )
parser.add_argument("datadir", help="data directory",            type=str  )
parser.add_argument("hours",   help="hours forward  (0 to 384)", type=int  )
args=parser.parse_args()
if (args.lat   <  -90. or args.lat   >  90.):
    parser.error("invalid latitude")
if (args.lon   < -180. or args.lon   > 180.):
    parser.error("invalid longitude")
if (args.alt   < -100. or args.alt   > 1e5 ):
    parser.error("invalid altitude")
if (args.hours <    0  or args.hours > 384 ):
    parser.error("invalid number of hours")

site = sf.Topos(latitude_degrees=args.lat, longitude_degrees=args.lon,
        elevation_m=args.alt)

fig, axes_arr = plt.subplots(nrows=5,
        gridspec_kw={'height_ratios':[2,1,1,1,1]}, sharex=True,
        figsize=(6, 8))

for fnum, fname in enumerate(filenames): 

    fpath = args.datadir + '/' + fname

    time_str = np.loadtxt(
            fpath,
            dtype=str,
            usecols=(0,),
            skiprows=1,
            unpack=True)
    tau225, Tb, pwv, lwp, iwp, o3 = np.loadtxt(
            fpath,
            usecols=(1, 2, 3, 4, 5, 6),
            skiprows=1,
            unpack=True)

    time_datetime = []
    time_plottime = []
    for s in time_str.tolist():
        dtime = datetime.datetime.strptime(s,
                "%Y%m%d_%H:%M:%S").replace(tzinfo=tz_UTC)
        time_datetime.append(dtime)
        time_plottime.append(mdates.date2num(dtime))
    time_plottime = np.asarray(time_plottime)

    if (fnum == 0):
        #
        # x plot range is computed from the "latest-48" data set.
        #
        for axes in axes_arr:
            axes.grid(
                    b=True,
                    which="major",
                    dashes=(1.0, 1.0),
                    color="0.8")
        axes_arr[0].grid(
                which="minor",
                axis="y",
                dashes=(1.0, 1.0),
                color="0.9")

        if (args.hours <= 120):
            days = mdates.DayLocator(interval=1, tz=tz_UTC)
        else:
            days = mdates.DayLocator(interval=2, tz=tz_UTC)
        days_fmt = mdates.DateFormatter("%Y%m%d")
        hours    = mdates.HourLocator(byhour=range(0, 24, 6), tz=tz_UTC)
        axes_arr[0].xaxis.set_major_locator(days)
        axes_arr[0].xaxis.set_major_formatter(days_fmt)
        axes_arr[0].xaxis.set_minor_locator(hours)
        xmin = time_plottime[0]
        xmax = time_plottime[0] + 2. + args.hours / 24.
        #
        # Compute sunrise, sunset times across x axis with Skyfield.
        # tsun is a sequence of times, corresponding values of rise
        # are True for rising, False for setting.
        #
        tmin = ts.utc(time_datetime[0])
        tmax = ts.utc(time_datetime[0] + datetime.timedelta(hours=(48. + args.hours)))
        tsun, rise = almanac.find_discrete(tmin, tmax,
                almanac.sunrise_sunset(e, site))
        tsun_datetime = tsun.utc_datetime()
        tsun_plottime = mdates.date2num(tsun_datetime)
        #
        # Plot vspan rectangles from sunset to sunrise, handling axis
        # limits.
        #
        for axes in axes_arr:
            if (rise[0] == True):
                axes.axvspan(xmin, tsun_plottime[0],
                        facecolor=nightcolor, alpha=nightalpha)
                i = 1
            else:
                i = 0
            while(i < len(rise) - 1):
                axes.axvspan(tsun_plottime[i], tsun_plottime[i + 1],
                        facecolor=nightcolor, alpha=nightalpha)
                i += 2
            if (rise[-1] == False):
                axes.axvspan(tsun_plottime[-1], xmax,
                        facecolor=nightcolor, alpha=nightalpha)

        axes_arr[0].set_xlim(xmin, xmax)

        axes_arr[0].set_yscale('log')
        
        axes_arr[0].annotate(
                r'$\mathrm{\tau_{225}}$',
                (0.0, 1.0),
                xytext=(4.0, -4.0),
                xycoords='axes fraction',
                textcoords='offset points',
                color='1.0',
                backgroundcolor='0.3',
                horizontalalignment='left',
                verticalalignment='top')

        axes_arr[1].annotate(
                r'$\mathrm{PWV\ [mm]}$',
                (0.0, 1.0),
                xytext=(4.0, -4.0),
                xycoords='axes fraction',
                textcoords='offset points',
                color='1.0',
                backgroundcolor='0.3',
                horizontalalignment='left',
                verticalalignment='top')
        axes_arr[1].set_yticks([0.0, 1.0, 2.5, 4.0, 8.0, 16.0])

        axes_arr[2].annotate(
                r'$\mathrm{LWP\ [kg/m^2]}$',
                (0.0, 1.0),
                xytext=(4.0, -4.0),
                xycoords='axes fraction',
                textcoords='offset points',
                color='1.0',
                backgroundcolor='0.3',
                horizontalalignment='left',
                verticalalignment='top')

        axes_arr[3].annotate(
                r'$\mathrm{IWP\ [kg/m^2]}$',
                (0.0, 1.0),
                xytext=(4.0, -4.0),
                xycoords='axes fraction',
                textcoords='offset points',
                color='1.0',
                backgroundcolor='0.3',
                horizontalalignment='left',
                verticalalignment='top')

        axes_arr[4].annotate(
                r'$\mathrm{O_3\ [DU]}$',
                (0.0, 1.0),
                xytext=(4.0, -4.0),
                xycoords='axes fraction',
                textcoords='offset points',
                color='1.0',
                backgroundcolor='0.3',
                horizontalalignment='left',
                verticalalignment='top')

    mask = time_plottime <= xmax
    axes_arr[0].plot(
            time_plottime[mask],
            tau225[mask],
            color=colors[fnum],
            linewidth=widths[fnum])

    axes_arr[1].plot(
            time_plottime[mask],
            pwv[mask],
            color=colors[fnum],
            linewidth=widths[fnum])

    axes_arr[2].plot(
            time_plottime[mask],
            lwp[mask],
            color=colors[fnum],
            linewidth=widths[fnum])

    axes_arr[3].plot(
            time_plottime[mask],
            iwp[mask],
            color=colors[fnum],
            linewidth=widths[fnum])

    axes_arr[4].plot(
            time_plottime[mask],
            o3[mask],
            color=colors[fnum],
            linewidth=widths[fnum])


fig.align_ylabels()
fig.autofmt_xdate()
plt.subplots_adjust(top=0.98, bottom=0.17, left=0.12, right=0.97)

tau_max = axes_arr[0].get_ylim()[1]
if (tau_max < 0.1):
    tau_max = 0.1
axes_arr[0].set_ylim(bottom=0.01, top=tau_max)
pwv_max = axes_arr[1].get_ylim()[1]
axes_arr[1].set_ylim(bottom=-0.05 * pwv_max, top=None)

annotation_str = """
Forecast is for {0} at {1} deg. {2}, {3} deg. {4}, {5} m altitude.  Dates are UT with major ticks at 00:00.  Shading indicates local night.  The current forecast is plotted in black; the prior 48 hours' forecasts are in grey.

Atmospheric state data are from the NOAA/NCEP Global Forecast System (GFS), with data access provided by the NOAA Operational Model Archive and Distribution System (https://nomads.ncep.noaa.gov).  Optical depth is from am v.{6} (https://doi.org/10.5281/zenodo.640645).
""".format(
        args.site,
        abs(args.lat), "S" if args.lat < 0 else "N",
        abs(args.lon), "W" if args.lon < 0 else "E",
        args.alt,
        args.am_vers)

plt.figtext(0.07, 0.0, annotation_str, fontsize=5.5, wrap=True)
fig.savefig('forecast_{0}.png'.format(args.hours), dpi=150)
plt.close(fig)
