#!/usr/bin/env python
# plot_forecast.py - generate tau forecast plot for specified
# number of hours into the future, showing the current and past
# 48 hours' forecasts.
#
# Note that this script has to make use of, and interconvert
# between, three different kinds of time objects, namely Python
# datetime, matplotlib plot time, and skyfield timescale.
#
# Updated 6/17/2019 for new GFS output with 3-hour resolution
# all the way out to 384 hours.

import argparse
import datetime
import dateutil
import matplotlib
matplotlib.use('Cairo')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.dates import DAILY, MO, TU, WE, TH, FR, SA, SU
import numpy as np
import skyfield.api as sf
ts = sf.load.timescale()
e  = sf.load('de421.bsp') # skyfield ephemeris data, cached locally
from skyfield import almanac

#
# The list of files to be plotted.  These are symbolic links to
# the most recent two days' forecast files.  The forecast files
# themselves are named by date and archived permanently.
#
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
#
# Plot line widths and colors corresponding to the forecast
# files tabulated above, e.g. thick black line for the latest
# forecast and thin grey lines for the previous two days'
# forecasts.
#
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

#
# Color and transparancy for the shading on the plots indicating
# local night.
#
nightcolor = '0.7'
nightalpha = 0.2

#
# Parse command line arguments.
#
parser = argparse.ArgumentParser()
parser.add_argument("site",    help="site name",                  type=str  )
parser.add_argument("lat",     help="site latitude  [deg]",       type=float)
parser.add_argument("lon",     help="site longitude [deg]",       type=float)
parser.add_argument("alt",     help="site altitude  [m]",         type=float)
parser.add_argument("tz",      help="site time zone (IANA name)", type=str  )
parser.add_argument("am_vers", help="am version string",          type=str  )
parser.add_argument("datadir", help="data directory",             type=str  )
parser.add_argument("hours",   help="hours forward  (0 to 384)",  type=int  )
args=parser.parse_args()

#
# Command line argument checks
#
if (args.lat   <  -90. or args.lat   >  90.):
    parser.error("invalid latitude")
if (args.lon   < -180. or args.lon   > 180.):
    parser.error("invalid longitude")
if (args.alt   < -100. or args.alt   > 1e5 ):
    parser.error("invalid altitude")
if (args.hours <    0  or args.hours > 384 ):
    parser.error("invalid number of hours")

#
# Here, 'site' is an object used by the Skyfield package to define
# the topocentric location of the site.
#
site = sf.Topos(latitude_degrees=args.lat, longitude_degrees=args.lon,
        elevation_m=args.alt)

#
# We need two time zones.  The data files use UTC, and the bottom
# x-axis and x grid are UTC.  For convenience, weekdays in the
# observatory site's local time zone are indicated across the
# top x-axis.
#
tz_UTC  = dateutil.tz.gettz("UTC")
tz_site = dateutil.tz.gettz(args.tz) 

#
# Set up an array of 5 plots arranged vertically, sharing a
# common x (time) axis, and take care of the axes setups that
# don't depend on the data.
#
fig, axes_arr = plt.subplots(nrows=5,
        gridspec_kw={'height_ratios':[2,1,1,1,1]}, sharex=True,
        figsize=(6, 8))
#
# tau225 - 225 GHz optical depth
#
axes_arr[0].grid(
        which="minor",
        axis="y",
        dashes=(1.0, 1.0),
        color="0.9")
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
#
# PWV - Precipitable water vapor [mm]
#
axes_arr[1].set_yticks([0.0, 1.0, 2.5, 4.0, 8.0, 16.0])
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
#
# LWP - Cloud liquid water path [kg / m^2]
#
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
#
# LWP - Cloud ice water path [kg / m^2]
#
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
#
# O3 - ozone column density [Dobson units]
#
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
#
# Plot the forecast files, looping over the list of symbolic
# links defined at the top of this script.
#
for fnum, fname in enumerate(filenames): 
    #
    # The full path to the file includes the data directory path
    # from the command line.
    #
    fpath = args.datadir + '/' + fname
    #
    # The forecast files contain a one-line header, which must
    # be skipped.  The first data column in each file is a text
    # date string:
    #
    time_str = np.loadtxt(
            fpath,
            dtype=str,
            usecols=(0,),
            skiprows=1,
            unpack=True)
    #
    # .. and the remaining columns are all straight numeric data.
    #
    tau225, Tb, pwv, lwp, iwp, o3 = np.loadtxt(
            fpath,
            usecols=(1, 2, 3, 4, 5, 6),
            skiprows=1,
            unpack=True)
    #
    # The date strings need to be converted to Python datetimes
    # as well as matplotlib plottimes for different purposes below
    #
    time_datetime = []
    time_plottime = []
    for s in time_str.tolist():
        dtime = datetime.datetime.strptime(s,
                "%Y%m%d_%H:%M:%S").replace(tzinfo=tz_UTC)
        time_datetime.append(dtime)
        time_plottime.append(mdates.date2num(dtime))
    time_plottime = np.asarray(time_plottime)
    #
    # Computation of the x axis range and day/night shading
    # are done once when the first data file is processed.
    #
    if (fnum == 0):
        for axes in axes_arr:
            axes.grid(
                    b=True,
                    which="major",
                    dashes=(1.0, 1.0),
                    color="0.8")
        xmin = time_plottime[0]
        xmax = time_plottime[0] + 2. + args.hours / 24.
        #
        # Compute sunrise, sunset times across x axis with
        # Skyfield.  Here, tsun is a sequence of rise/set times.
        # The corresponding values of rise are True for rising,
        # False for setting.
        #
        tmin = ts.utc(time_datetime[0])
        tmax = ts.utc(time_datetime[0] +
                datetime.timedelta(hours=(48. + args.hours)))
        tsun, rise = almanac.find_discrete(tmin, tmax,
                almanac.sunrise_sunset(e, site))
        tsun_datetime = tsun.utc_datetime()
        tsun_plottime = mdates.date2num(tsun_datetime)
        #
        # Set x limits and plot vspan rectangles from sunset to
        # sunrise.
        #
        for axes in axes_arr:
            axes.set_xlim(xmin, xmax)
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

    #
    # Plot all the data columns from the current file, setting
    # a mask to restrict to the x-axis range.
    #
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

#
# UTC tics along shared bottom x-axis
#
major_locator = mdates.DayLocator(interval=1, tz=tz_UTC)
if (args.hours <= 120):
    minor_locator = mdates.HourLocator(byhour=(0, 6, 12, 18), tz=tz_UTC)
elif (args.hours <= 240):
    minor_locator = mdates.HourLocator(byhour=(0, 12), tz=tz_UTC)
else:
    minor_locator = mdates.HourLocator(byhour=(0), tz=tz_UTC)
axes_arr[-1].xaxis.set_major_locator(major_locator)
axes_arr[-1].xaxis.set_minor_locator(minor_locator)
axes_arr[-1].xaxis.set_major_formatter(
        mdates.ConciseDateFormatter(major_locator, tz=tz_UTC))
axes_arr[-1].xaxis.set_tick_params(which='major', labelsize=10)
axes_arr[-1].annotate(
        "UTC",
        xy=(0,-26),
        xycoords='axes points',
        fontsize=10)
#
# Create a twin of the top axes to carry weekday labels in
# local observatory time.  Major ticks are placed at the day
# boundaries.  Labels for selected days are placed on invisible
# minor ticks located at 12:00 noon local time.
#
axes_top = axes_arr[0].twiny()
axes_top.set_xlim(xmin, xmax)
axes_top.annotate(args.tz, xy=(5,12), xycoords='axes points', fontsize=8)
axes_top.xaxis.set_tick_params(which='both', direction='in',
        top=False, bottom=True, labeltop=False, labelbottom=True)

axes_top.xaxis.set_major_locator(mdates.DayLocator(tz=tz_site))
axes_top.xaxis.set_major_formatter(matplotlib.ticker.NullFormatter()) 
axes_top.xaxis.set_tick_params(which='major', length=8)

if (args.hours <= 120):
    labeled_days=(MO, TU, WE, TH, FR, SA, SU)
else:
    labeled_days=(SA, SU)
rule = mdates.rrulewrapper(DAILY, byweekday=labeled_days, byhour=12)
loc  = mdates.RRuleLocator(rule, tz=tz_site)
axes_top.xaxis.set_minor_locator(loc)
axes_top.xaxis.set_minor_formatter(mdates.DateFormatter("%a", tz=tz_site)) 
axes_top.xaxis.set_tick_params(which='minor', length=0, labelsize=8, pad=-8)

#
# Tweak to tau225 y-axis to ensure we always get at least one
# full log decade
#
tau_max = axes_arr[0].get_ylim()[1]
if (tau_max < 0.1):
    tau_max = 0.1
axes_arr[0].set_ylim(bottom=0.01, top=tau_max)
#
# Tweak to PWV y axis to always start from pwv = 0, with a
# small offset.
pwv_max = axes_arr[1].get_ylim()[1]
axes_arr[1].set_ylim(bottom=-0.05 * pwv_max, top=None)
#
# Tweaks to adjust plot and label positions
#
fig.align_ylabels()
plt.subplots_adjust(top=0.96, bottom=0.17, left=0.12, right=0.97)

#
# Write a header with the update time right at the top.  This will
# make a stale forecast more easily noticed.
#
update_time = datetime.datetime.now(tz=tz_site)
update_str  = update_time.strftime("%A, %B %d, %Y at %I:%M %p")
header   = "Updated {0} {1}".format(update_str, args.tz)
plt.figtext(0.05, 0.98, header, fontsize=9)

footnote = (
        "Forecast is for " +
        "{0} at {1} deg. {2}, {3} deg. {4}, {5} m altitude.  ".format(
                args.site,
                abs(args.lat), "S" if args.lat < 0 else "N",
                abs(args.lon), "W" if args.lon < 0 else "E",
                args.alt) +
        "The current forecast is plotted in black and the prior 48 " +
        "hours' forecasts in grey.  Shading indicates local night, " +
        "and weekdays in the top panel are indicated in local " +
        "({0}) time.\n".format(args.tz) +
        "\n" +
        "All quantities are referred to zenith.  Definitions are: " +
        r"$\mathrm{\tau_{225}}$" +
        " - 225 GHz optical depth; PWV - precipitable water vapor; " +
        "LWP - cloud liquid water path; IWP - cloud ice water path; " +
        r"$\mathrm{O_3\ [DU]}$" +
        " - ozone column density in Dobson Units.\n" +
        "\n" +
        "Atmospheric state data are from the NOAA/NCEP Global " +
        "Forecast System (GFS), with data access provided by the " +
        "NOAA Operational Model Archive and Distribution System " +
        "(https://nomads.ncep.noaa.gov).  Optical depth is from " +
        "am v.{0} ".format(args.am_vers) + 
        "(https://doi.org/10.5281/zenodo.640645).\n"
        )

plt.figtext(0.07, 0.0, footnote, fontsize=5.5, wrap=True)
fig.savefig('forecast_{0}.png'.format(args.hours), dpi=150)
plt.close(fig)
