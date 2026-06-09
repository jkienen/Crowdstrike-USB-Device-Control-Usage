#################################### Part 0: Environment Evaluation ->

# Imports necessary modules
import os
import datetime
import pandas as pd
from falconpy import DeviceControlPolicies

# ----------------------------------------->

# Define base name
BASE = "Device-Control-USB-Exceptions"

# Getting current date
current_date = datetime.datetime.now()

# Getting current path for file saving
current_dir = os.path.dirname(os.path.realpath(__file__))
env_path = os.path.join(current_dir, f"./.env")

# Define saving directories
file_name = f"{BASE}.csv"
datas_dir = os.path.join(current_dir, "../../Datas/Entry")
csv_path = os.path.join(datas_dir, file_name)

# Define auto create DIR
if not os.path.exists(datas_dir):
    os.makedirs(datas_dir)



#################################### Part 1: Obtaining Authorization ->

from dotenv import load_dotenv
if os.path.exists(env_path):

    load_dotenv(env_path)

    CLIENT_ID = os.getenv("CLIENT_ID")
    CLIENT_SECRET = os.getenv("SECRET_ID")

    if CLIENT_ID and CLIENT_SECRET:

        falcon = DeviceControlPolicies(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)



        #################################### Part 2: Querying Device Control Policies ->
        
        try:

            response = falcon.query_policies()

            if response["status_code"] != 200:
                print(f"API returned status code {response['status_code']}. Please validate your token (CLIENT_ID / SECRET_ID).")
                raise SystemExit(1)

            response_details = falcon.get_policies_v2(ids=response["body"]["resources"])
            policies = response_details["body"]["resources"]



            #################################### Part 3: Data Processing ->

            records = []
            empty = "-"

            def format_date(ts): return ts[:10] if ts else empty

            for policy in policies:
                policy_id = policy.get("id", empty)
                policy_name = policy.get("name", empty)
                platform = policy.get("platform_name", empty)
                enabled = policy.get("enabled", empty)
                usb_settings = policy.get("usb_settings", {})
                usb_mode = usb_settings.get("enforcement_mode", empty)
                enhanced_meta = usb_settings.get("enhanced_file_metadata", empty)

                for cls in usb_settings.get("classes", []):
                    class_name = cls.get("class", empty)
                    class_default_action = cls.get("action", empty)
                    exceptions = cls.get("exceptions", []) or [{}]

                    for exc in exceptions:
                        record = {
                            "Policy Id":               policy_id,
                            "Policy Name":             policy_name,
                            "Policy Platform":         platform,
                            "Policy Enabled":          enabled,
                            "Enhanced File Metadata":  enhanced_meta,
                            "USB Enforcement Mode":    usb_mode,
                            "USB Device Class":        class_name,
                            "USB Device Class Action": class_default_action,
                            "Exception Id":            exc.get("id", empty),
                            "Exception Action":        exc.get("action", empty),
                            "Match Method":            exc.get("match_method", empty),
                            "Device Vendor Id":        exc.get("vendor_id", empty),
                            "Device Product Id":       exc.get("product_id", empty),
                            "Device Serial Id":        exc.get("serial_number") or "NA",
                            "Device Combined Id":      exc.get("combined_id") or empty,
                            "Description":             exc.get("description", empty),
                            "Created At":              format_date(exc.get("created_timestamp")),
                            "Modified At":             format_date(exc.get("modified_timestamp")),
                            "Reference Month":         current_date.strftime("%m"),
                            "Reference Year":          current_date.strftime("%Y"),
                            "Reference Date":          current_date.strftime("%Y-%m-%d"),
                        }

                        records.append(record)



            #################################### Part 4: Data Saving ->

            df = pd.DataFrame(records)
            df.to_csv(csv_path, index=False, encoding="utf-8")


        except Exception as err: print(err)

    else: print(".env file exists but is missing some variables!")
else: print(".env file does not exist!")