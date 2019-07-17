# summarize.awk - take concatenated stderr and stdout streams from am
# run on GFS-based model, and produce a single line containing
#
#  tau  Tb[K]  pwv[mm]  lwp[kg*m^-2]  iwp[kg*m^-2]  o3[DU]
#
BEGIN {
    # column density units (cm^-2 equivalents)
    MM_PWV   = 3.3427e21
    KG_ON_M2 = 3.3427e21
    DU       = 2.6868e16
}

/^#.*h2o/ {
    pwv = $3 / MM_PWV
}

/^#.*lwp_abs_Rayleigh/ {
    lwp = $3 / KG_ON_M2
}

/^#.*iwp_abs_Rayleigh/ {
    iwp = $3 / KG_ON_M2
}

/^#.*o3/ {
    o3 = $3 / DU
}

/^[0-9]/ {
    tau = $2
    Tb  = $3
}
END {
    # last line read was single-point output spectrum
    printf(" %12.4e %12.4e %12.4e %12.4e %12.4e %12.4e\n", tau, Tb, pwv, lwp, iwp, o3)
}
