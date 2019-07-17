# make_forecast_table.sh - writes a forecast summary table with
# one line for each forecast hour starting from the analysis
# epoch.  For each hour, gfs_to_am10.py is called to generate am
# model layers.  These are appended to a header and am is run to
# compute total column densities and the 225 GHz opacity, which
# are then summarized in a single data line.
#
# This script depends on the following environment variables:
#   GFS_CYCLE - forecast cycle (YYYYMMDD HH) for this table
#   LAT       - site latitude
#   LON       - site longitude
#   APPDIR    - directory containing this and related scripts
#   AM        - path to am executable

#
# Limit the maximum download rate on the GFS server by sleeping
# for RATE_LIMIT_DELAY seconds after each access.
#
RATE_LIMIT_DELAY=1

#
# Print table column headers.
#
printf "#%16s %12s %12s %12s %12s %12s %12s\n" \
        "date" \
        "tau225" \
        "Tb[K]" \
        "pwv[mm]" \
        "lwp[kg*m^-2]" \
        "iwp[kg*m^-2]" \
        "o3[DU]"

#
# Hourly GFS forecast for the first 5 days
#
for (( H = 0   ; H <= 120 ; H += 1 )); do
    FORECAST_HOUR=$(printf "f%03d" $H)
    if gfs15_to_am10.py $LAT $LON $ALT $GFS_CYCLE $FORECAST_HOUR \
            > layers.amc 2>layers.err; then
        make_gfs_timestamp.py $GFS_CYCLE $H
        cat $APPDIR/header.amc layers.amc | $AM - 2>&1 |
            awk -f $APPDIR/summarize.awk
    else
        date >> errors.log
        cat layers.err >> errors.log
    fi
    sleep $RATE_LIMIT_DELAY
done

#
# 3-hourly forecasts after 5 days
#
for (( H = 123 ; H <= 384 ; H += 3 )); do
    FORECAST_HOUR=$(printf "f%03d" $H)
    if gfs15_to_am10.py $LAT $LON $ALT $GFS_CYCLE $FORECAST_HOUR \
            > layers.amc 2>layers.err; then
        make_gfs_timestamp.py $GFS_CYCLE $H
        cat $APPDIR/header.amc layers.amc | $AM - 2>&1 |
            awk -f $APPDIR/summarize.awk
    else
        date >> errors.log
        cat layers.err >> errors.log
    fi
    sleep $RATE_LIMIT_DELAY
done
