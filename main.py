import os
import time
import configparser
import threading
import subprocess
import sys

from printer import Printer
from GUI import Application
from filemonitor import Watcher
from api import ApiHandler


# Get printer id and API key from INI file
# Format: ID = API_KEY
#
# [PRINTERS]
# 01 = 1234567890ABCDEF
# 02 = 1234567890ABCDEF
#
config = configparser.ConfigParser()
config.read("./Config/config.ini")

printer_conf = config["PRINTERS"]
printer_connection_settings = []
for printer in printer_conf:
    printer_connection_settings.append([printer, printer_conf[printer]])

# Check if code should run with GUI - script needs to run with > python main.py -g
GUI_FLAG = "-g" in sys.argv

printers = [Printer(id=connection_settings[0], api=connection_settings[1]) for connection_settings in printer_connection_settings]
start_str = "Printers online: "
for printer in printers:
    start_str += str(printer.id) + " "
print(start_str)

if GUI_FLAG:
    app = Application(printer_connection_settings, printers)

# Initialize file/job handling
GCODE_INPUT_PATH = config["PATHS"]["input_folder"]
GCODE_OUTPUT_PATH = config["PATHS"]["output_folder"]
if not os.path.exists(GCODE_INPUT_PATH):
    print("No input folder found, creating " + GCODE_INPUT_PATH)
    os.mkdir(GCODE_INPUT_PATH)
if not os.path.exists(GCODE_OUTPUT_PATH):
    print("No output folder found, creating " + GCODE_OUTPUT_PATH)
    os.mkdir(GCODE_OUTPUT_PATH)
watcher = Watcher(printers, GCODE_INPUT_PATH, GCODE_OUTPUT_PATH)

# Initialize Flask API
api_handler = ApiHandler(printers)

# Asynchronous printer update logic
def printer_update_async(printer):
    update_delay = 1 # seconds
    while True:
        start_time = time.time()
        printer.autoConnect()
        if not printer.octopi_status == "Error":
            printer.update()
        # Wait for delay
        while not time.time() >= start_time + update_delay:
            time.sleep(5)

# Create list of threads, one for each printer
# Starts update function as background processes
thread_list = []
for index, printer in enumerate(printers):
        thread_list.append(threading.Thread(target=printer_update_async, args=(printer, ), daemon=True))
        thread_list[index].start()

# Create thread for Flask API
api_thread = threading.Thread(target=api_handler.run, daemon=True)
api_thread.start()

# Start autoslicer
autoslicer_path = config["PATHS"]["autoslicer_path"]
# Find venv python path
if os.name == "nt":
    python_path = os.path.join(autoslicer_path, "venv", "Scripts", "python")
else:
    python_path = os.path.join(autoslicer_path, "venv", "bin", "python")
filemonitor_path = os.path.join(autoslicer_path, "fileMonitor.py")
subprocess.Popen([python_path, filemonitor_path])

while True:
    if GUI_FLAG:
        # replaces app.mainloop()
        app.update_idletasks()
        app.update()

        app.update_printers()

    watcher.update()