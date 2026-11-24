import os
import re
import sys
import shutil
import zipfile
import subprocess
import ctypes

MANIFEST_FILE_NAME = "manifest.ini"

def q(value):
    return f'"{value}"'

def read_manifest(script_dir):
    manifest_path = os.path.join(script_dir, MANIFEST_FILE_NAME)
    data = {}
    if not os.path.exists(manifest_path):
        return data
    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            data[key.strip().lower()] = val.strip()
    return data

def write_manifest_value(script_dir, key_name, key_value):
    manifest_path = os.path.join(script_dir, MANIFEST_FILE_NAME)
    lines = []
    found = False
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
    for i, line in enumerate(lines):
        clean_line = line.strip()
        if clean_line and not clean_line.startswith("#") and "=" in clean_line:
            k, _ = clean_line.split("=", 1)
            if k.strip().lower() == key_name.lower():
                lines[i] = f"{key_name}={key_value}\n"
                found = True
                break
    if not found:
        lines.append(f"{key_name}={key_value}\n")
        
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

def get_latest_package_version(network_dir, prefix):
    if not network_dir or not os.path.isdir(network_dir):
        return -1, ""
    highest = -1
    latest_zip = ""
    pattern = re.compile(f"^{re.escape(prefix)}([0-9]+)\\.zip$", re.IGNORECASE)
    
    try:
        for filename in os.listdir(network_dir):
            match = pattern.match(filename)
            if match:
                version = int(match.group(1))
                if version > highest:
                    highest = version
                    latest_zip = os.path.join(network_dir, filename)
    except Exception:
        pass
    return highest, latest_zip

def safely_kill_process_by_script(script_name):
    """Uses native Windows taskkill to close the python process running the specific main script."""
    try:
        # Filter down to the exact commandline usage using taskkill's window title check or command string matching
        # Because pythonw doesn't have a console window, we match by the script execution argument via WMIC or taskkill
        query_cmd = f'taskkill /f /fi "IMAGENAME eq pythonw.exe" /fi "WINDOWTITLE eq {script_name}*"'
        subprocess.call(query_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Fallback check targeting all running pythonw environments just in case window titles match loosely
        fallback_cmd = f'wmic process where "name=\'pythonw.exe\' and commandline like \'%{script_name}%\'" call terminate'
        subprocess.call(fallback_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config = read_manifest(script_dir)
    
    main_script_name = config.get("main_script_name", "app.py")
    package_prefix = config.get("package_prefix", "binary_texture_annotation_")
    network_update_dir = config.get("network_update_dir", "")
    python_subdir = config.get("python_subdir", "python")
    python_command = config.get("python_command", "pythonw.exe")
    
    try:
        current_release = int(config.get("release_number", "1"))
    except ValueError:
        current_release = 1

    latest_version, latest_zip_path = get_latest_package_version(network_update_dir, package_prefix)
    
    if latest_version <= current_release:
        sys.exit(0)

    # Prompt User to apply update
    msg = f"Current Release: {current_release}\nNew Release Available: {latest_version}\n\nWould you like to download and install this update in the background?"
    response = ctypes.windll.user32.MessageBoxW(0, msg, "Update Available", 4 + 32 + 4096)
    
    if response != 6:  # 6 = User clicked 'Yes'
        sys.exit(0)

    # Extraction Flow 
    temp_extract_dir = os.path.join(os.environ.get("TEMP", ""), f"_update_py_{latest_version}")
    if os.path.exists(temp_extract_dir):
        shutil.rmtree(temp_extract_dir, ignore_errors=True)
    os.makedirs(temp_extract_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(latest_zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_extract_dir)
    except Exception:
        shutil.rmtree(temp_extract_dir, ignore_errors=True)
        ctypes.windll.user32.MessageBoxW(0, "Update package extraction failed.", "Update Error", 16)
        sys.exit(1)

    # Overwrite assets using Robocopy
    robocopy_cmd = f'robocopy "{temp_extract_dir}" "{script_dir}" /E /NFL /NDL /NJH /NJS /NC /NS'
    rc = subprocess.call(robocopy_cmd, shell=True)
    
    shutil.rmtree(temp_extract_dir, ignore_errors=True)

    if rc >= 8:
        ctypes.windll.user32.MessageBoxW(0, "File copy migration failed. Check file access rights.", "Update Error", 16)
        sys.exit(1)

    # Update manifest file metadata
    write_manifest_value(script_dir, "release_number", str(latest_version))

    # Install pip requirements if found
    requirements_path = os.path.join(script_dir, "requirements.txt")
    if os.path.exists(requirements_path):
        python_exe = os.path.join(script_dir, python_subdir, "python.exe")
        if os.path.exists(python_exe):
            install_cmd = f'"{python_exe}" -m pip install -r "{requirements_path}"'
            subprocess.call(install_cmd, shell=True)

    # Prompt user for an immediate application restart
    restart_msg = "The update has been applied successfully!\n\nWould you like to restart the application now to apply the changes?"
    restart_response = ctypes.windll.user32.MessageBoxW(0, restart_msg, "Update Complete", 4 + 64 + 4096)

    if restart_response == 6:  # User clicked 'Yes'
        # Close the running instance
        safely_kill_process_by_script(main_script_name)
        
        # Spawn a brand new decoupled instance of your app matching your VBS configuration
        python_bin_path = os.path.join(script_dir, python_subdir, python_command)
        app_path = os.path.join(script_dir, main_script_name)
        
        if os.path.exists(python_bin_path) and os.path.exists(app_path):
            # Launch completely decoupled from this background execution thread
            subprocess.Popen([python_bin_path, app_path], creationflags=subprocess.CREATE_NO_WINDOW)

if __name__ == "__main__":
    main()