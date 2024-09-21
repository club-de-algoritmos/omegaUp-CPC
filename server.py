from http.server import BaseHTTPRequestHandler, HTTPServer


class Server(BaseHTTPRequestHandler):
    file: str

    def do_GET(self) -> None:
        self.send_response(2000)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(self.file.encode())


def start_server(file_to_serve: str) -> None:
    Server.file = file_to_serve
    hostname = "localhost"
    port = 8080
    server = HTTPServer((hostname, port), Server)

    print("Results: http://{}:{}".format(hostname, port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Server stopped")
        server.server_close()
