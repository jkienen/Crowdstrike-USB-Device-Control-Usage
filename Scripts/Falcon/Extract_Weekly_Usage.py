#################################### Part 0: Environment Evaluation ->

# Imports necessary modules
import os
import time
import datetime
import pandas as pd
from falconpy import NGSIEM

# ----------------------------------------->

# Define retention in months
BASE = "Device-Control-Usage"

# Getting current date
current_date = datetime.datetime.now()

# Getting current path for file saving
current_dir = os.path.dirname(os.path.realpath(__file__))
env_path = os.path.join(current_dir, f"./.env")

# Define time filter to events from last 7 days
end_ms = int((end_time := datetime.datetime.now(datetime.timezone.utc)).timestamp() * 1000)
start_ms = int((start_time := end_time - datetime.timedelta(days=7)).timestamp() * 1000)

# Define saving directories
start_date_str = start_time.strftime("%Y-%m-%d")
end_date_str = end_time.strftime("%Y-%m-%d")
file_name = f"{BASE}_{start_date_str}-to-{end_date_str}"
dir_to_save_csv = os.path.join(current_dir, f"../../Datas/Entry/{file_name}.csv")

# Define auto create DIR
parent_directory = os.path.dirname(dir_to_save_csv)
if not os.path.exists(parent_directory):
    os.makedirs(parent_directory)

# NGSIEM query (Device Control - USB & Removable Storage events)
NGSIEM_QUERY = """
#repo=base_sensor | in(#event_simpleName, values=[DcUsbDeviceConnected, DcUsbDevicePolicyViolation, DcUsbDeviceBlocked, DcRemovableStorageDeviceConnected, DcRemovableStorageDevicePolicyViolation, DcRemovableStorageDeviceBlocked]) | default(field=[DeviceManufacturer, DeviceProduct, DeviceSerialNumber], value="--", replaceEmpty=true) | case { #event_simpleName=DcUsb* | ConnectionType := "USB"; #event_simpleName=DcRemovableStorage* AND event_platform="Mac" | ConnectionType := "PCIe" | DeviceClass := "Mass Storage"; #event_simpleName=DcRemovableStorage* AND event_platform="Win" | ConnectionType := "Storage spaces" | DeviceClass := "Mass Storage"; } | join({ #repo=sensor_metadata #data_source_name=dcusbinterfacedescriptor-ds | groupBy(DeviceDescriptorSetHash, function=collect(DeviceUsbClass, separator=" | "), limit=max) }, field=DeviceDescriptorSetHash, include=[DeviceUsbClass], mode=left) | $falcon/devicecontrol:DCFriendlyPolicyAction() | DeviceId := format(format="%s_%s_%s", field=[DeviceVendorId, DeviceProductId, DeviceSerialNumber]) | case { ConnectionType = "PCIe" | case { event_platform=Mac | Device := format(format="%s %s (S/N: %s)", field=[DeviceManufacturer, DeviceProduct, DeviceSerialNumber]); event_platform=Win | Device := "SD card reader"; *; }; ConnectionType = "USB" | Device := format(format="%s %s (S/N: %s)", field=[DeviceManufacturer, DeviceProduct, DeviceSerialNumber]); *; } | case { ConnectionType = "USB" | default(field=DeviceUsbClass, value="No class", replaceEmpty=true) | DeviceClass := rename(DeviceUsbClass); *; } | groupBy([aid, DeviceInstanceId], function=[session(maxpause=10s, [collect([Device, ConnectionType, DeviceVendorId, DeviceProductId, DeviceSerialNumber, DeviceId, DeviceClass, ComputerName, event_platform]), selectLast([@timestamp, DcPolicyAction])])], limit=max) | default(field=[ComputerName], value="--", replaceEmpty=true) | DeviceClass=/Mass Storage|No class|Mobile|Printer/i | Date := formatTime("%Y-%m-%d %H:%M:%S", field=@timestamp, locale="pt_BR", timezone="America/Sao_Paulo") | table([Date, Device, DeviceVendorId, DeviceProductId, DeviceSerialNumber, DeviceId, ConnectionType, DcPolicyAction, DeviceClass, ComputerName, event_platform], sortby=@timestamp, order=desc, limit=max)
""".strip()



#################################### Part 1: Obtaining Authorization ->

# Data obtained from project file
from dotenv import load_dotenv
if os.path.exists(env_path):

    load_dotenv(env_path)

    # Get .env variables
    CLIENT_ID = os.getenv("CLIENT_ID")
    SECRET_ID = os.getenv("SECRET_ID")

    # If valid items
    if CLIENT_ID and SECRET_ID:

        falcon = NGSIEM(client_id=CLIENT_ID, client_secret=SECRET_ID)



        #################################### Part 2: Executing NGSIEM Query ->

        try:

            # Start the search job
            response_start = falcon.start_search(repository="search-all", query_string=NGSIEM_QUERY, start=start_ms, end=end_ms)

            if response_start["status_code"] != 200:
                print(f"API returned status code {response_start['status_code']}. Please validate your token (CLIENT_ID / SECRET_ID).")
                raise SystemExit(1)
  
            # Poll until the job is complete
            while True:
                response_status = falcon.get_search_status(repository="search-all", id=response_start["resources"]["id"])
                body = response_status["body"]
                if body.get("cancelled"): raise RuntimeError(f"NGSIEM search cancelled: {body}")
                if body.get("done"): raw_events = body.get("events", []); break
                time.sleep(3)



            #################################### Part 3: Data Processing ->

            records = []
            empty = "-"

            # Normalize each event returned by NGSIEM
            for event in raw_events:

                record = {
                    "Date":               event.get("Date", empty),
                    "Platform":           event.get("event_platform", empty),
                    "Computer Name":      event.get("ComputerName", empty),
                    "Device Name":        event.get("Device", empty),
                    "Device Vendor Id":   event.get("DeviceVendorId", empty),
                    "Device Product Id":  event.get("DeviceProductId", empty),
                    "Device Serial Id":   event.get("DeviceSerialNumber", empty),          
                    "Device Combined Id": event.get("DeviceId", empty),
                    "Policy Action":      event.get("DcPolicyAction", empty),
                    "Device Class":       event.get("DeviceClass", empty),
                    "Connection Type":    event.get("ConnectionType", empty),
                    "Reference Month":    current_date.strftime("%m"),
                    "Reference Year":     current_date.strftime("%Y"),
                    "Reference Date":     current_date.strftime("%Y-%m-%d")
                }

                records.append(record)



            #################################### Part 4: Data Saving ->

            df_new = pd.DataFrame(records)
            datas_dir = os.path.join(current_dir, "../../Datas/Entry")

            # Find existing accumulated file (any Device-Control-Usage_*.csv)
            existing_file = None
            if os.path.exists(datas_dir):
                for f in os.listdir(datas_dir):
                    if f.startswith(BASE) and f.endswith(".csv"):
                        existing_file = os.path.join(datas_dir, f)
                        break

            if existing_file:
                df_existing = pd.read_csv(existing_file, encoding="utf-8")
                df = pd.concat([df_existing, df_new], ignore_index=True)
                df = df.drop_duplicates(subset=["Date", "Device Id", "Computer Name"], keep="first")
            else: df = df_new

            # Apply retention: drop records older than 6 months
            cutoff = end_time - datetime.timedelta(days=6 * 30)
            df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
            df = df[df["Date"] >= cutoff.replace(tzinfo=None)]
            df["Date"] = df["Date"].dt.strftime("%Y-%m-%d %H:%M:%S")

            # Filename covers actual retained date range
            actual_start = df["Date"].min()[:10] if not df.empty else start_date_str
            new_file_name = f"{BASE}_{actual_start}-to-{end_date_str}"

            new_csv = os.path.join(datas_dir, f"{new_file_name}.csv")
            df.to_csv(new_csv, index=False, encoding="utf-8")

            # Remove old file if filename changed
            if existing_file and existing_file != new_csv: os.remove(existing_file)


        except Exception as err: print(err)

    else: print(".env file exists but is missing some variables!")
else: print(".env file does not exist!")