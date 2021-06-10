"""An example of a simple HTTP server."""
import json
import mimetypes
import pickle
import socket
from os.path import isdir
from urllib.parse import unquote_plus

# Pickle file for storing data
PICKLE_DB = "db.pkl"

# Directory containing www data
WWW_DATA = "www-data"

# Header template for a successful HTTP request
HEADER_RESPONSE_200 = """HTTP/1.1 200 OK\r
content-type: %s\r
content-length: %d\r
connection: Close\r
\r
"""

# Represents a table row that holds user data
TABLE_ROW = """
<tr>
    <td>%d</td>
    <td>%s</td>
    <td>%s</td>
</tr>
"""

# Template for a 404 (Not found) error
RESPONSE_404 = """HTTP/1.1 404 Not found\r
content-type: text/html\r
connection: Close\r
\r
<!doctype html>
<h1>404 Page not found</h1>
<p>Page cannot be found.</p>
"""

RESPONSE_301 = """HTTP/1.1 301 Moved Permanently\r
location: %s\r
"""

RESPONSE_405 = """HTTP/1.1 405 Method Not Allowed\r
content-type: text/html\r
connection: Close\r
\r
<!doctype html>
<h1>405 Page Not Allowed</h1>
<hr>
<p>Method Not Allowed.</p>
"""

RESPONSE_400 = """HTTP/1.1 400 Bad Request\r
"""


def save_to_db(first, last):
    """Create a new user with given first and last name and store it into
    file-based database.

    For instance, save_to_db("Mick", "Jagger"), will create a new user
    "Mick Jagger" and also assign him a unique number.

    Do not modify this method."""

    existing = read_from_db()
    existing.append({
        "number": 1 if len(existing) == 0 else existing[-1]["number"] + 1,
        "first": first,
        "last": last
    })
    with open(PICKLE_DB, "wb") as handle:
        pickle.dump(existing, handle)


def read_from_db(criteria=None):
    """Read entries from the file-based DB subject to provided criteria

    Use this method to get users from the DB. The criteria parameters should
    either be omitted (returns all users) or be a dict that represents a query
    filter. For instance:
    - read_from_db({"number": 1}) will return a list of users with number 1
    - read_from_db({"first": "bob"}) will return a list of users whose first
    name is "bob".

    Do not modify this method."""
    if criteria is None:
        criteria = {}
    else:
        # remove empty criteria values
        for key in ("number", "first", "last"):
            if key in criteria and criteria[key] == "":
                del criteria[key]

        # cast number to int
        if "number" in criteria:
            criteria["number"] = int(criteria["number"])

    try:
        with open(PICKLE_DB, "rb") as handle:
            data = pickle.load(handle)

        filtered = []
        for entry in data:
            predicate = True

            for key, val in criteria.items():
                if val != entry[key]:
                    predicate = False

            if predicate:
                filtered.append(entry)

        return filtered
    except (IOError, EOFError):
        return []


def parse_headers(client):
    headers = dict()
    while True:
        line = client.readline().decode("utf-8").strip()
        if not line:
            return headers
        key, value = line.split(":", 1)
        headers[key.strip()] = value.strip()


def handle_post(client, headers, connection, address):
    if "Content-Length" not in headers.keys():
        print("ERROR 400")
        client.write(RESPONSE_400.encode("utf-8"))
        connection.close()
        print("[%s:%d] DISCONNECTED" % address)

    length = headers["Content-Length"]
    arguments = client.read(int(length)).strip()
    arguments = unquote_plus(arguments.decode("utf-8"), "utf-8")

    # make a dict of arguments
    raw_args = arguments.split("&")
    args = dict()
    for arg in raw_args:
        key, val = arg.split("=")
        args[key] = val

    if len(args.keys()) != 2 or args.keys() != {"first", "last"}:
        print("ERROR 400")
        client.write(RESPONSE_400.encode("utf-8"))
        connection.close()
        print("[%s:%d] DISCONNECTED" % address)
    save_to_db(args["first"], args["last"])


def display_table(criteria):
    if len(read_from_db()) == 0:
        return

    with open("./www-data/app_list.html") as file:
        code = file.read()

    table = ""
    if len(criteria) == 0:
        items = read_from_db()
    else:
        items = read_from_db(criteria)

    for item in items:
        table += (TABLE_ROW % (item["number"], item["first"], item["last"]))
    code = code.replace("{{students}}", table)
    return code.encode()


def display_json(criteria):
    if len(read_from_db()) == 0:
        return

    if len(criteria) == 0:
        items = read_from_db()
    else:
        items = read_from_db(criteria)

    json_list = json.dumps(items)
    return json_list.encode()


def process_request(connection, address):
    """Process an incoming socket request.

    :param connection is a socket of the client
    :param address is a 2-tuple (address(str), port(int)) of the client
    """
    client = connection.makefile("wrb")

    line = client.readline().decode("utf-8").strip()
    try:
        method, uri, version = line.split()
        headers = parse_headers(client)
        dynamic_uri = {"/www-data/app-add", "/www-data/app-index", "/www-data/app-json", "/app-add",
                       "/app-index", "/app-json"}
        criteria = dict()
        app_list = ""

        if uri in dynamic_uri or "/app-index" in uri:
            if "/app-index" in uri:
                app_list = "i"
                if "?" in uri and len(uri.split("?")) == 2:
                    raw_args = uri.split("?")[1]
                    raw_args = raw_args.split("&")
                    for arg in raw_args:
                        criteria[arg.split("=")[0]] = arg.split("=")[1]

                uri = "/www-data/app_list.html"
                if method != "GET":
                    print("ERROR 405")
                    client.write(RESPONSE_405.encode("utf-8"))
                    connection.close()
            elif uri == "/www-data/app-add" or uri == "/app-add":
                uri = "/www-data/app_add.html"
                if method != "POST":
                    print("ERROR 405")
                    client.write(RESPONSE_405.encode("utf-8"))
                    connection.close()
                    print("[%s:%d] DISCONNECTED" % address)
                else:
                    handle_post(client, headers, connection, address)
            elif "/app-json" in uri:
                app_list = "j"
                if "?" in uri and len(uri.split("?")) == 2:
                    raw_args = uri.split("?")[1]
                    raw_args = raw_args.split("&")
                    for arg in raw_args:
                        criteria[arg.split("=")[0]] = arg.split("=")[1]

                uri = "/www-data/app_list.html"

        assert len(uri) > 0 and uri[0] == "/", "Invalid Request URI"
        assert version == "HTTP/1.1", "Invalid Request Version"
        assert "Host" in headers.keys(), "Host not in headers"

        if "/www-data" not in uri:
            uri = "/www-data" + uri

        if not (method == "GET" or method == "POST"):
            print("ERROR 405")
            client.write(RESPONSE_405.encode("utf-8"))
            connection.close()
            print("[%s:%d] DISCONNECTED" % address)

        file_type = mimetypes.guess_type(uri)

        if isdir("." + uri) and uri[-1] == "/":
            if uri == "/":
                uri += "/index.html"
            else:
                uri += "index.html"
            uri = uri.replace("/www-data", "")
            head = RESPONSE_301 % ("http://localhost:" + str(connection.getsockname()[1]) + uri)
            client.write(head.encode("utf-8"))

        if file_type is None:
            file_type = "application/octet-stream"
        if app_list == "j":
            file_type = "application/json"

        with open(uri[1:], "rb") as handle:
            body = handle.read()
        if app_list == "i":
            body = display_table(criteria)
        elif app_list == "j":
            body = display_json(criteria)

        print(method, uri, version, headers)
        head = HEADER_RESPONSE_200 % (file_type[0], len(body))
        client.write(head.encode("utf-8"))
        client.write(body)
    except (ValueError, AssertionError):
        print("ERROR 400")
        client.write(RESPONSE_400.encode("utf-8"))
        connection.close()
        print("[%s:%d] DISCONNECTED" % address)
    except IOError:
        print("ERROR 404")
        client.write(RESPONSE_404.encode("utf-8"))
        connection.close()
        print("[%s:%d] DISCONNECTED" % address)
    finally:
        client.close()


def main(port):
    """Starts the server and waits for connections."""

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("", port))
    server.listen(1)

    print("Listening on %d" % port)

    while True:
        connection, address = server.accept()
        print("[%s:%d] CONNECTED" % address)
        process_request(connection, address)
        connection.close()
        print("[%s:%d] DISCONNECTED" % address)


if __name__ == "__main__":
    main(8080)
