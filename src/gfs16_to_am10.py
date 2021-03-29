#!/usr/bin/env python
#
# gfs16_to_am10.py - For a given site latitude, longitude, and altitude, this
# script will download an appropriately-subsetted GFS forecast file in
# grib2 format from the NOAA Operational Model Archive Distribution
# System (NOMADS), then generate a corresponding set of am layers
# interpolated to the site position.
#
# This version is for GFSv.16 grib2 data, and writes layer data for am-10.0+

import argparse
import datetime
import dateutil.parser as dparser
import math
import pygrib
import requests
import sys
import time

# Timeouts and retries
CONN_TIMEOUT        = 15       # Initial server response timeout in seconds
READ_TIMEOUT        = 15       # Stalled download timeout in seconds
RETRY_DELAY         = 60       # Delay before retry (NOAA requests 60 s)
MAX_DOWNLOAD_TRIES  = 4

# Numerical and physical constants
BADVAL              = -99999.  # placeholder for missing or undefined data
BADVAL_TEST         = -99998.
G_STD               = 9.80665  # standard gravity [m / s^2]
M_AIR               = 28.964   # average dry air mass [g / mole]
M_O3                = 47.997   # O3 mass [g / mole]
H2O_SUPERCOOL_LIMIT = 238.     # Assume ice below this temperature [K]
PASCAL_ON_MBAR      = 100.     # conversion from mbar (hPa) to Pa

# Above the level defined here, use a fixed stratospheric mixing
# ratio instead of RH from GFS.
RH_TOP_PLEVEL = 29.
STRAT_H2O_VMR = 5e-6

#
# Below are constants and format strings for constructing the data
# request URL.  These include the base URL for the NOMADS CGI, and
# various strings for formatting the arguments given to it.  Note
# that some information (e.g. grid, forecast production cycle) gets
# used more than once to construct the CGI request.
#

# URL for the CGI interface.  Field {0} is the grid spacing string
# defined below.
CGI_URL = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_{0}_1hr.pl?"

# Format string for requesting the kind of data product.
# Fields are:
#   {0} - forecast production cycle (00, 06, 12, 18)
#   {1} - grid spacing string
#   {2} - forecast product, either  "anl" for analysis at production
#         time, or "fxxx" for forecast xxx hours in the future, where
#         xxx ranges from 000 to 384 by 1-hour steps, by 1-hour steps up
#         to 120 hours, and by 3-hour steps thereafter.
PRODUCT_REQUEST_FORMAT = "&file=gfs.t{0:02d}z.pgrb2.{1}.{2}"

# Format string for requesting the specific data and production cycle
# within that date.  Fields are:
#   {0} - date in the form YYYYMMDD
#   {1} - forecast production cycle (00, 06, 12, 18)
CYCLE_REQUEST_FORMAT = "&dir=%2Fgfs.{0}%2F{1:02d}%2Fatmos"

# The available GFS lat,lon grid spacings are 0.25, 0.50, or 1.00
# degrees.  In the GFS file names and CGI interface, this is
# coded as "0p25" for 0.25 deg, etc.
LATLON_GRID_STR = "0p25"

# Format string for the grid subset request.
SUBREGION_REQUEST_FORMAT = (
    "&subregion=&leftlon={0}&rightlon={1}&toplat={2}&bottomlat={3}")

# GFS grid levels [mbar], and the format string used to add each level
# to the CGI request URL.
LEVELS = (1, 2, 3, 5, 7, 10, 20, 30, 50, 70, 100, 150, 200, 250, 300, 350, 400,
        450, 500, 550, 600, 650, 700, 750, 800, 850, 900, 925, 950, 975, 1000)
LEVEL_REQUEST_FORMAT = "&lev_{0:d}_mb=on"

# GFS variables to be requested, and the format string for adding them
# to the CGI request URL.  The variables are
#   CLWMR - Cloud liquid water mass mixing ratio [kg liquid / kg air]
#   ICMR  - Cloud ice mass mixing ratio [kg liquid / kg air]
#   HGT   - Geopotential height [m]
#   O3MR  - Ozone mass mixing ratio [kg O3 / kg air]
#   RH    - Relative Humidity [%]
#   TMP   - Temperature [K]
VARIABLES = ("CLWMR", "ICMR", "HGT", "O3MR", "RH", "TMP")
VARIABLE_REQUEST_FORMAT = "&var_{0}=on"

#
# Comment string to be printed above model layers:
#
LAYER_HEADER = """
#
# Layer data below were derived from NCEP GFS model data obtained
# from the NOAA Operational Model Archive Distribution System
# (NOMADS).  See http://nomads.ncep.noaa.gov for more information.
#
#         Production date: {0}
#                   Cycle: {1:02d} UT
#                 Product: {2}
#
# Interpolated to
#
#                latitude: {3} deg. N
#               longitude: {4} deg. E
#   Geopotential altitude: {5} m
#
"""

#
# Function for bilinear grid interpolation.  a[i_lat][i_lon] is a
# 2x2 array of adjacent points on the lon,lat grid.  u,v are the
# fractional distances in grid spacing in grid spacing units from
# the "bottom left" grid point to the interpolation point.
#
def grid_interp(a, u, v):
    return ( a[0][0] * (1.0 - u) * (1.0 - v) + a[1][0] * u * (1.0 - v)
           + a[0][1] * (1.0 - u) * v         + a[1][1] * u * v        )


#
# Parse the command line and validate arguments.
#
parser = argparse.ArgumentParser()
parser.add_argument("lat",      help="site latitude [deg], (-90 to 90)",
    type=float)
parser.add_argument("lon",      help="site longitude [deg], (-180 to 180)",
    type=float)
parser.add_argument("altitude", help="site altitude [m]",
    type=float)
parser.add_argument("gfsdate",  help="GFS production date (YYYYMMDD)",
    type=str)
parser.add_argument("gfscycle", help="GFS production cycle (0, 6, 12, 18)",
    type=int)
parser.add_argument("gfsprod",  help="GFS product: anl or f000 - f384",
    type=str)
args = parser.parse_args()

if (args.lat < -90. or args.lat > 90.):
    parser.error("invalid latitude")
if (args.lon < -180. or args.lon > 180.):
    parser.error("invalid longitude")
if (args.altitude < -500.):
    parser.error("invalid altitude")
try:
    gfsdatetime = dparser.parse(args.gfsdate)
except:
    parser.error("bad GFS production date")
if (gfsdatetime < datetime.datetime(2017, 1, 1)):
    parser.error("GFS production date too early")
if (args.gfscycle not in (0, 6, 12, 18)):
    parser.error("invalid GFS production cycle")
if (args.gfsprod != "anl"):
    if (args.gfsprod[0:1] == "f"):
        forecast_hour = int(args.gfsprod[1:])
        #
        # These checks pertain to the 0.25 degree product
        #
        if (forecast_hour < 0 or forecast_hour > 384):
            parser.error("invalid forecast hour (out of range)")
        if (forecast_hour > 120 and forecast_hour % 3 != 0):
            parser.error("invalid forecast hour (3-hourly only after 120 h)")
    else:
        parser.error("invalid GFS product name")

#
# Args OK.  Build the request URL to retrieve the GFS data.
#
request_url = CGI_URL.format(LATLON_GRID_STR)
request_url += PRODUCT_REQUEST_FORMAT.format(
    args.gfscycle,
    LATLON_GRID_STR,
    args.gfsprod)
for lev in LEVELS:
    request_url += LEVEL_REQUEST_FORMAT.format(int(lev))
for var in VARIABLES:
    request_url += VARIABLE_REQUEST_FORMAT.format(var)

#
# The requested regional subset will be the four points nearest the
# user-requested lat, lon.
#
latlon_delta = float(LATLON_GRID_STR[0:1]) + 0.01 * float(LATLON_GRID_STR[2:])
leftlon = math.floor(args.lon / latlon_delta) * latlon_delta
rightlon = leftlon + latlon_delta
bottomlat = math.floor(args.lat / latlon_delta) * latlon_delta
toplat = bottomlat + latlon_delta

request_url += SUBREGION_REQUEST_FORMAT.format(
        leftlon,
        rightlon,
        toplat,
        bottomlat)
request_url += CYCLE_REQUEST_FORMAT.format(
        args.gfsdate,
        args.gfscycle)

#
# Download the requested data in grib2 format, and build an index
# for efficient lookups by variable name and level.  Allow a
# limited number of retries for connection errors and timeouts.
#
retry = MAX_DOWNLOAD_TRIES
while retry > 0:
    try:
        r = requests.get(request_url, timeout=(CONN_TIMEOUT, READ_TIMEOUT))
        if r.status_code == requests.codes.ok:
            errflag = 0
        else:
            errflag = 1
            print("Download failed with status code {0}".format(r.status_code),
                    file=sys.stderr, end='')
    except requests.exceptions.ConnectTimeout:
        print("Connection timed out.", file=sys.stderr, end='')
        errflag = 1
    except requests.exceptions.ReadTimeout:
        print("Data download timed out.", file=sys.stderr, end='')
        errflag = 1
    if (errflag):
        retry = retry - 1
        if (retry):
            print("  Retrying...", file=sys.stderr)
            time.sleep(RETRY_DELAY)
        else:
            print("  Giving up.", file=sys.stderr)
            print("Failed URL was: ", file=sys.stderr)
            print(request_url, file=sys.stderr)
            exit(1)
    else:
        break
f = open("temp.grb", 'wb')
f.write(r.content)
f.flush()
grbindx = pygrib.index("temp.grb", "name", "level")

#
# Turn the grib2 data into am layers.  In a first pass, interpolate
# at each pressure level to lat,lon. For height and temperature,
# insert BADVAL if the variable is missing or not defined on the level.
# For other variables, set missing values to zero.
#
u = (args.lat - bottomlat) / latlon_delta 
v = (args.lon - leftlon) / latlon_delta
Pbase     = []
z         = []
T         = []
o3_vmr    = []
RH        = []
cloud_lmr = []
cloud_imr = []
for i,lev in enumerate(LEVELS):
    Pbase.append(lev)
    try:
        x = (grid_interp(grbindx.select(
            name="Geopotential Height", level=lev)[0].values, u, v))
        z.append(x)
    except:
        z.append(BADVAL)
    try:
        x = (grid_interp(grbindx.select(
            name="Temperature", level=lev)[0].values, u, v))
        T.append(x)
    except:
        T.append(BADVAL)
    try:
        x = (grid_interp(grbindx.select(
            name="Ozone mixing ratio", level=lev)[0].values, u, v))
        x *= M_AIR / M_O3 # convert mass mixing ratio to volume mixing ratio
        o3_vmr.append(x)
    except:
        o3_vmr.append(0.0)
    try:
        x = (grid_interp(grbindx.select(
            name="Relative humidity", level=lev)[0].values, u, v))
        RH.append(x)
    except:
        RH.append(0.0)
    try:
        x = (grid_interp(grbindx.select(
            name="Cloud mixing ratio", level=lev)[0].values, u, v))
        cloud_lmr.append(x)
    except:
        cloud_lmr.append(0.0)
    try:
        x = (grid_interp(grbindx.select(
            name="Ice water mixing ratio", level=lev)[0].values, u, v))
        cloud_imr.append(x)
    except:
        cloud_imr.append(0.0)


#
# Print a header comment over the layer descriptions
#
if (args.gfsprod == "anl"):
    product_str = "analysis"
else:
    product_str = args.gfsprod[1:] + " hour forecast"
print(LAYER_HEADER.format(
        args.gfsdate,
        args.gfscycle,
        product_str,
        args.lat,
        args.lon,
        args.altitude))
#
# Print out the layer descriptions.  On a layer, mixing ratios and
# RH are set to their averages over the two levels bounding the layer.
#
for i,lev in enumerate(LEVELS):
    if (z[i] < args.altitude):
        break
    print("layer")
    print("Pbase {0:.1f} mbar  # {1:.1f} m".format(Pbase[i], z[i]))
    print("Tbase {0:.1f} K".format(T[i]))
    print("column dry_air vmr")
    if (i > 0):
        o3_vmr_mid    = 0.5 * (   o3_vmr[i-1] +    o3_vmr[i])
        RH_mid        = 0.5 * (       RH[i-1] +        RH[i])
        cloud_lmr_mid = 0.5 * (cloud_lmr[i-1] + cloud_lmr[i])
        cloud_imr_mid = 0.5 * (cloud_imr[i-1] + cloud_imr[i])
        T_mid         = 0.5 * (        T[i-1] +         T[i])
    else:
        o3_vmr_mid    = o3_vmr[i]
        RH_mid        = RH[i]
        cloud_lmr_mid = cloud_lmr[i]
        cloud_imr_mid = cloud_imr[i]
        T_mid         = T[i]
    if (o3_vmr_mid > 0.0):
        print("column o3 vmr {0:.3e}".format(o3_vmr_mid))
    if (Pbase[i] > RH_TOP_PLEVEL):
        if (T_mid < H2O_SUPERCOOL_LIMIT):
            print("column h2o RHi {0:.2f}%".format(RH_mid))
        else:
            print("column h2o RH {0:.2f}%".format(RH_mid))
    else:
        print("column h2o vmr {0:.3e}".format(STRAT_H2O_VMR))
    if (cloud_lmr_mid > 0.0):
        #
        # Convert cloud liquid water mixing ratio [kg / kg] to
        # cloud total liquid water across the layer [kg / m^2].
        # Below the supercooling limit, assume any liquid water
        # is really ice.  (GFS 15 occasionally had numerically
        # negligible amounts of liquid water at unphysically
        # low temperature.)
        #
        dP = PASCAL_ON_MBAR * (Pbase[0] if i == 0 else Pbase[i] - Pbase[i-1])
        m = dP / G_STD 
        ctw = m * cloud_lmr_mid
        if (T_mid < H2O_SUPERCOOL_LIMIT):
            print("column iwp_abs_Rayleigh {0:.3e} kg*m^-2".format(ctw))
        else:
            print("column lwp_abs_Rayleigh {0:.3e} kg*m^-2".format(ctw))
    if (cloud_imr_mid > 0.0):
        #
        # Convert cloud ice mixing ratio [kg / kg] to cloud total
        # ice across the layer [kg / m^2].
        #
        dP = PASCAL_ON_MBAR * (Pbase[0] if i == 0 else Pbase[i] - Pbase[i-1])
        m = dP / G_STD 
        cti = m * cloud_imr_mid
        print("column iwp_abs_Rayleigh {0:.3e} kg*m^-2".format(cti))
    print("")

#
# The base layer and base level of the model are special cases.  First,
# we find the pressure and temperature of the base level by linearly
# interpolating (or extrapolating) log P and T in z.
#
if (i == 0):
    print("User-specified altitude exceeds top GFS level", file=sys.stderr)
    exit(1)

#
# If the base level coincides exactly with a model level, we're done.
#
if (z[i] == args.altitude):
    exit(0)

u      = (args.altitude - z[i-1]) / (z[i] - z[i-1])
logP_s = u * math.log(Pbase[i]) + (1.0 - u) * math.log(Pbase[i-1]) 
P_s    = math.exp(logP_s)
T_s    = u * T[i] + (1.0 - u) * T[i-1]
T_mid  = 0.5 * (T_s + T[i-1])

#
# Other variables are interpolated or extrapolated linearly in P
# to the base level and clamped at zero.
#
u = (P_s - Pbase[i-1]) / (Pbase[i] - Pbase[i-1])
o3_vmr_s    = u *    o3_vmr[i] + (1.0 - u) *    o3_vmr[i-1]
RH_s        = u *        RH[i] + (1.0 - u) *        RH[i-1]
cloud_lmr_s = u * cloud_lmr[i] + (1.0 - u) * cloud_lmr[i-1]
cloud_imr_s = u * cloud_imr[i] + (1.0 - u) * cloud_imr[i-1]
if (o3_vmr_s < 0.0):
    o3_vmr_s = 0.0
if (RH_s < 0.0):
    RH_s = 0.0
if (cloud_lmr_s < 0.0):
    cloud_lmr_s = 0.0
if (cloud_imr_s < 0.0):
    cloud_imr_s = 0.0
o3_vmr_mid    = 0.5 * (   o3_vmr[i-1] +    o3_vmr_s)
RH_mid        = 0.5 * (       RH[i-1] +        RH_s)
cloud_lmr_mid = 0.5 * (cloud_lmr[i-1] + cloud_lmr_s)
cloud_imr_mid = 0.5 * (cloud_imr[i-1] + cloud_imr_s)
print("layer")
print("Pbase {0:.1f} mbar  # {1:.1f} m".format(P_s, args.altitude))
print("Tbase {0:.1f} K".format(T_s))
print("column dry_air vmr")
if (o3_vmr_mid > 0.0):
    print("column o3 vmr {0:.3e}".format(o3_vmr_mid))
if (P_s > RH_TOP_PLEVEL):
    if (T_mid < H2O_SUPERCOOL_LIMIT):
        print("column h2o RHi {0:.2f}%".format(RH_mid))
    else:
        print("column h2o RH {0:.2f}%".format(RH_mid))
else:
    print("column h2o vmr {0:.3e}".format(STRAT_H2O_VMR))
if (cloud_lmr_mid > 0.0):
    dP = PASCAL_ON_MBAR * (Pbase[0] if i == 0 else Pbase[i] - Pbase[i-1])
    m = dP / G_STD 
    ctw = m * cloud_lmr_mid
    if (T_mid < H2O_SUPERCOOL_LIMIT):
        print("column iwp_abs_Rayleigh {0:.3e} kg*m^-2".format(ctw))
    else:
        print("column lwp_abs_Rayleigh {0:.3e} kg*m^-2".format(ctw))
if (cloud_imr_mid > 0.0):
    dP = PASCAL_ON_MBAR * (Pbase[0] if i == 0 else Pbase[i] - Pbase[i-1])
    m = dP / G_STD 
    cti = m * cloud_imr_mid
    print("column iwp_abs_Rayleigh {0:.3e} kg*m^-2".format(cti))
exit(0)
