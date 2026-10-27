# gunicorn.conf.py
loglevel = "info"
errorlog = "-"  # Logs errors to stdout
accesslog = "-"  # Logs access requests to stdout
capture_output = True  # Redirects stdout/stderr of application to error log

# Concurrency comes from threads in ONE process, not from multiple processes.
#
# Gunicorn's default is a single sync worker, which serializes every request behind
# whichever one is in flight — including /hostinfo, which blocks on Infoblox, Meraki,
# Extreme NAC and ip-api — and kills the worker outright if a request overruns the
# 30 s default timeout. That is what made /metrics time out: the dashboard build was
# killed before it could populate its cache, so the next request started cold again.
#
# Adding processes would fix the serialization but silently multiply in-process
# safeguards that the app relies on being global:
#   * utils geolocation cache and circuit breaker, which protect ip-api.com
#   * api hostinfo and DNS rate limits / concurrency controls
#   * db._metrics_cache, which would rebuild the dashboard once per process
# Threads keep all of that shared and correct. The code is already written for this
# model — _dns_rate_lock is a threading.Lock and dns_lookup uses a ThreadPoolExecutor.
workers = 1
worker_class = "gthread"
threads = 8
timeout = 120
graceful_timeout = 30
