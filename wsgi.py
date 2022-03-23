"""
WSGI config for project

"""

#import sys
#import site

#site.addsitedir('/var/www/hitme/lib/python3.6/site-packages')

#sys.path.insert(0, '/var/www/hitme')

import os
from app import app as application

if __name__ == "__main__":
    #application.run()
    from wsgiref.simple_server import make_server
    httpd = make_server('localhost', 8051, application)
    httpd.serve_forever()