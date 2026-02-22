#!/usr/bin/env python3
import pandas as pd, os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DATESTAMP = datetime.now().strftime("%Y-%m-%d")

def filter_no_website(service, town):
    src=os.path.join(DATA_DIR,f"leads_{town}_{service}_{DATESTAMP}.csv")
    if not os.path.exists(src):
        print(f"[ERROR] {src} not found."); return None
    df=pd.read_csv(src)
    mask=df["website"].isna() | (df["website"].astype(str).str.strip()=="")
    df=df[mask]
    out=os.path.join(DATA_DIR,f"leads_{town}_{service}_NO_WEBSITE_{DATESTAMP}.csv")
    df.to_csv(out,index=False)
    print(f"[✅] {len(df)} no‑website leads → {out}")
    return out

if __name__=="__main__":
    import sys
    if len(sys.argv)<3:
        print("Usage: python3 filter_no_website.py <service> <city>")
    else:
        filter_no_website(sys.argv[1], sys.argv[2])