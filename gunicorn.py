#! -*- coding: utf-8 -*-
bind = "0.0.0.0:5000"
reload = True
capture_output = True
loglevel = "info"
timeout = 1000
#errorlog = "/logs/gunicorn-error.log"
#accesslog = "/logs/gunicorn-access.log"
workers = 5
threads = 5
keepalive = 5
