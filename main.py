import time
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST
import logging

# Console Logger Config
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Hardcoded URLs for monitoring
URLS = [
    "https://httpstat.us/503",
    "https://httpstat.us/200"
]


# Prometheus metrics
is_up_metric = Gauge('sample_external_url_up', 'URL availability (1=up, 0=down)', ['url'])
response_ms_metric = Gauge('sample_external_url_response_ms', 'URL response time in milliseconds', ['url'])

class URLMonitoring:
    def __init__(self, urls, interval=30):
        self.urls = urls
        self.interval = interval
    
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
    # Initialize URL monitor
    monitor = URLMonitoring(URLS, interval=30)
    
    # First check of the metrics before startup
    for url in URLS:
        is_up, response_time = monitor.monitor_url(url)
        is_up_metric.labels(url=url).set(is_up)
        response_ms_metric.labels(url=url).set(response_time)
    
    # Start the HTTP server
    server_port = 8080
    server = HTTPServer(('0.0.0.0', server_port), MetricsHandler)
    
    logger.info(f"Starting HTTP server on port {server_port}")
    logger.info(f"Metrics available at http://localhost:{server_port}/metrics")
    logger.info(f"Health check available at http://localhost:{server_port}/health")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()

if __name__ == '__main__':
    main()
