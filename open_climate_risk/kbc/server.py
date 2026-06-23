import os, sys
os.chdir('/Users/alexandre/Documents/Geospatial/open_climate_risk/kbc')
sys.argv = ['server']
import http.server
http.server.test(HandlerClass=http.server.SimpleHTTPRequestHandler, port=8788, bind='127.0.0.1')
