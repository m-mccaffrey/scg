import os
import ctypes

MANIFEST_FILE_NAME = "manifest.ini"

script_dir = os.path.dirname(os.path.abspath(__file__))
manifest_path = os.path.join(os.getcwd(), MANIFEST_FILE_NAME)
manifest_data: dict[str, str] = {}

with open(manifest_path, "r", encoding="utf-8") as f:
    for raw_line in f:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        manifest_data[key.strip()] = value.strip()

APP_VERSION = manifest_data.get("app_version", "")

APP_BUILD = manifest_data.get("release_number", "")

APP_USER_MODEL_ID = manifest_data.get("app_user_model_id", "")

try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
except Exception:
    print('app user model id fail')

ICON_FILE_NAME = manifest_data.get("icon_location", "")

APP_TITLE = manifest_data.get("app_title", "")