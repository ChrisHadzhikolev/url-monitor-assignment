import time
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST
import logging
import threading
import os
from dotenv import load_dotenv

load_dotenv()

# Console Logger Config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Hardcoded URLs for monitoring
URLS = [
    "https://httpstat.us/503",
    "https://httpstat.us/200"
]

# Parsing the environment variables
INTERVAL = int(os.getenv('INTERVAL', '30'))
HTTP_PORT = int(os.getenv('HTTP_PORT', '8080'))
print(INTERVAL, HTTP_PORT)


# Prometheus metrics
is_up_metric = Gauge('sample_external_url_up', 'URL availability (1=up, 0=down)', ['url'])
response_ms_metric = Gauge('sample_external_url_response_ms', 'URL response time in milliseconds', ['url'])

class URLMonitoring:
    def __init__(self, urls, interval=30):
        self.urls = urls
        self.interval = interval
        self.running = False
        self.thread = None
    
    # Gather Monitoring metrics
    def monitor_url(self, url):
        try:
            start_time = time.time()
            response = requests.get(url, timeout=10)
            end_time = time.time()
            
            response_time_ms = (end_time - start_time) * 1000
            is_up = 1 if response.status_code == 200 else 0
            
            logger.info(f"URL: {url}, Status: {response.status_code}, Response Time: {response_time_ms:.2f}ms, Up: {is_up}")
            
            return is_up, response_time_ms
            
        except requests.RequestException as e:
            logger.error(f"Error checking URL {url}: {e}")
            return 0, 0

    # Gather Metrics for all URLs based on interval    
    def monitor_loop(self):
        while self.running:
            for url in self.urls:
                is_up, response_time = self.monitor_url(url)
                
                is_up_metric.labels(url=url).set(is_up)
                response_ms_metric.labels(url=url).set(response_time)
            
            time.sleep(self.interval)

    # Start monitoring loop and ensure only one process is running
    def start_monitoring(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.thread.start()
            logger.info("URL monitoring started")

    # Stop monitoring loop
    def stop_monitoring(self):
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("URL monitoring stopped")

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics':
            metrics_output = generate_latest()
            
            self.send_response(200)
            self.send_header('Content-Type', CONTENT_TYPE_LATEST)
            self.end_headers()
            self.wfile.write(metrics_output)
            
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
            
        else:
            self.send_response(404)
            self.end_headers()

    # Logger Custom Format
    def log_message(self, format, *args):
        logger.info(f"{self.address_string()} - {format % args}")

def main():
    # Initialize URL monitor, interval defaulting to 30 seconds if missing
    monitor = URLMonitoring(URLS, INTERVAL)

    monitor.start_monitoring()
    
    # First check of the metrics before startup
    for url in URLS:
        is_up, response_time = monitor.monitor_url(url)
        is_up_metric.labels(url=url).set(is_up)
        response_ms_metric.labels(url=url).set(response_time)
    
    # Start the HTTP server, port defaults to 8080 if missing
    server = HTTPServer(('0.0.0.0', HTTP_PORT), MetricsHandler)
    
    logger.info(f"Starting HTTP server on port {HTTP_PORT}")
    logger.info(f"Metrics available at http://localhost:{HTTP_PORT}/metrics")
    logger.info(f"Health check available at http://localhost:{HTTP_PORT}/health")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()

if __name__ == '__main__':
    main()
