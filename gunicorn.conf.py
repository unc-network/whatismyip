# gunicorn.conf.py
loglevel = "info"
errorlog = "-"  # Logs errors to stdout
accesslog = "-"  # Logs access requests to stdout
capture_output = True  # Redirects stdout/stderr of application to error log
