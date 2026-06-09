#################################### Part 0: Environment Evaluation ->

# Imports necessary modules
import os
import datetime
import pandas as pd

# ----------------------------------------->

# Define base names
BASE_AUDIT = "Device_USB-Audit-Usage"
BASE_TIME = 3 # Minimum history required to run (in months)

BASE_EXCEPTIONS = "Device-Control-USB-Exceptions"
BASE_USAGE = "Device-Control-Usage"

# Getting current paths
current_date = datetime.datetime.now()
current_dir = os.path.dirname(os.path.realpath(__file__))
entry_dir = os.path.join(current_dir, "../Datas/Entry")
dir_to_save = os.path.join(current_dir, f"../Datas/{current_date.strftime('%Y-%m')}/{BASE_AUDIT}.csv")

os.makedirs(os.path.dirname(dir_to_save), exist_ok=True)



#################################### Part 1: Locating Input Files ->

def find_csv(base):
    for f in os.listdir(entry_dir):
        if f.startswith(base) and f.endswith(".csv"):
            return os.path.join(entry_dir, f)

exceptions_csv = find_csv(BASE_EXCEPTIONS)
usage_csv = find_csv(BASE_USAGE)

if not exceptions_csv or not usage_csv: print("Pending files...")
else:

    try:


        #################################### Part 2: Loading Data ->

        df_exceptions = pd.read_csv(exceptions_csv, encoding="utf-8")
        df_usage = pd.read_csv(usage_csv, encoding="utf-8")

        dates = pd.to_datetime(df_usage["Date"], format="%Y-%m-%d %H:%M:%S", errors="coerce"); history_days = (dates.max() - dates.min()).days

        if history_days < 1: print(f"Not enough usage history to generate the audit ({history_days} days collected, {BASE_TIME * 30} required).")
        else:



            #################################### Part 3: Cross-referencing Exceptions vs Usage ->

            empty = "-"

            # Match Method -> exception columns used to cross-reference against usage
            match_keys = {
                "COMBINED_ID":    ["Device Combined Id"],
                "VID_PID_SERIAL": ["Device Vendor Id", "Device Product Id", "Device Serial Id"],
                "VID_PID":        ["Device Vendor Id", "Device Product Id"],
            }

            # Normalize key columns to string on both sides so merges line up regardless of inferred dtypes
            key_cols = ["Device Combined Id", "Device Vendor Id", "Device Product Id", "Device Serial Id"]
            for df in (df_exceptions, df_usage): df[key_cols] = df[key_cols].astype(str).apply(lambda c: c.str.strip())

            # Exceptions to audit: any supported match method
            df_audit = df_exceptions[df_exceptions["Match Method"].isin(match_keys)].copy()
            df_usage_full = df_usage[df_usage["Policy Action"].str.contains("Full access", na=False)]

            # Summarize Full access usage by a given set of key columns — latest record first
            def summarize_usage(keys): return (df_usage_full.sort_values("Date", ascending=False).groupby(keys, as_index=False).agg(**{"Last Seen": ("Date", "max"), "Last Connected Machines": ("Computer Name", lambda x: ", ".join(sorted(x.dropna().unique()))), "Connection Type": ("Connection Type",  "first"), "Device Name": ("Device Name", "first")}))

            # Cross-reference each match-method group against its matching usage summary, then recombine
            parts = [df_audit[df_audit["Match Method"] == method].merge(summarize_usage(keys), on=keys, how="left") for method, keys in match_keys.items()]; df_output = pd.concat(parts, ignore_index=True)

            # A device is active if it was used with Full access
            df_output["Is Active"] = df_output["Last Seen"].notna()
            df_output["Reference Month"] = current_date.strftime("%m")
            df_output["Reference Year"] = current_date.strftime("%Y")
            df_output["Reference Date"] = current_date.strftime("%Y-%m-%d")
            fill_cols = ["Last Seen", "Last Connected Machines", "Connection Type", "Device Name"]
            df_output[fill_cols] = df_output[fill_cols].fillna(empty)

            df_output = df_output[[
                "Is Active",
                "Exception Id",
                "Exception Action",
                "Connection Type",
                "Match Method",
                "Device Vendor Id",
                "Device Product Id",
                "Device Serial Id",
                "Device Combined Id",
                "Device Name",
                "Description",
                "Created At",
                "Modified At",
                "Last Seen",
                "Last Connected Machines",
                "Policy Id",
                "Policy Name",
                "Policy Platform",
                "Policy Enabled",
                "Enhanced File Metadata",
                "USB Enforcement Mode",
                "USB Device Class",
                "USB Device Class Action",
                "Reference Month",
                "Reference Year",
                "Reference Date"
            ]]



            #################################### Part 4: Data Saving ->

            df_output.to_csv(dir_to_save, index=False, encoding="utf-8")


    except Exception as err: print(err)