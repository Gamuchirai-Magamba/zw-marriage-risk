"""Copy this to paths.py and edit ROOT for your machine.

paths.py is gitignored because it holds a machine-specific path.
"""
from pathlib import Path

ROOT = Path(r"C:\Users\YOURNAME\zwgirls")   # <-- edit this line only
DATA = ROOT / "data"

DHS_WOMEN     = DATA / "dhs2015"  / "ir"     / "ZWIR72FL.DTA"
DHS_GPS       = DATA / "dhs2015"  / "gps"    / "ZWGE72FL.shp"
DHS_GEOCOV    = DATA / "dhs2015"  / "geocov" / "ZWGC72FL.csv"

MICS_WOMEN    = DATA / "mics2019" / "spss"   / "wm.sav"
MICS_CHILDREN = DATA / "mics2019" / "spss"   / "fs.sav"
MICS_GPS      = DATA / "mics2019" / "gps"    / "ZimbabweMICS2019GPS.shp"

DISTRICTS     = DATA / "mics2019" / "gps" / "mics_boundaries_nr shp" / "mics_boundaries_nr.shp"
