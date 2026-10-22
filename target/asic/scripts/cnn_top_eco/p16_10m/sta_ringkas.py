import json, sys
d = sys.argv[1]
m = json.load(open(d + "/53-openroad-stapostpnr/state_out.json"))["metrics"]
for c in ("nom_tt_025C_1v80", "nom_ss_100C_1v60", "max_ss_100C_1v60", "min_ss_100C_1v60",
          "nom_ff_n40C_1v95", "max_ff_n40C_1v95", "min_ff_n40C_1v95"):
    g = lambda k: m.get(k + "__corner:" + c)
    print("%-18s setup %8.3f  hold %7.3f  hold_vio %s  kap %s  slew %s" % (
        c, g("timing__setup__ws"), g("timing__hold__ws"), g("timing__hold_vio__count"),
        g("design__max_cap_violation__count"), g("design__max_slew_violation__count")))
for k in ("design__max_cap_violation__count", "design__max_slew_violation__count", "design__max_fanout_violation__count",
          "route__drc_errors", "timing__hold_vio__count", "timing__setup_vio__count"):
    print(k, m.get(k))
a = json.load(open(d + "/44-openroad-checkantennas-1/state_out.json"))["metrics"]
print("antena pasca-DRT:", a.get("route__antenna_violation__count"), "net")
