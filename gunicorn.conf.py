import os

bind = "0.0.0.0:8000"
workers = 2
threads = 2
timeout = 30
accesslog = "-"
errorlog = "-"
# The read-only runtime has no writable home directory for a control socket.
control_socket_disable = True
worker_tmp_dir = "/tmp"

# No forwarded-header trust unless the operator names the proxy's source IPs.
forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "")
secure_scheme_headers = {"X-FORWARDED-PROTO": "https"}
