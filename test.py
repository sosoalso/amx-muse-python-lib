import logging
import time

import PyATEMMax

switcher = PyATEMMax.ATEMMax()
switcher.setLogLevel(logging.INFO)  # Initially silent
# Connect
switcher.connect("10.20.0.88")
switcher.waitForConnection()
# Have fun!
switcher.setPreviewInputVideoSource(0, 5)  # Set PVW on input 5 for m/e 0
