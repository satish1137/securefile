import pandas as pd

def detect_anomaly(logs):
    if len(logs) > 5:
        return "Suspicious Activity Detected"
    return "Normal"