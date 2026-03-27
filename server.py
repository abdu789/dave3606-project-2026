import json
import html
import gzip
from flask import Flask, Response, request
from time import perf_counter
from collections import OrderedDict
import psycopg

app = Flask(__name__)

# -------------------------------
# Database configuration
# -------------------------------
DB_CONFIG = {
    "host": "localhost",
    "port": 9876,
    "dbname": "lego-db",
    "user": "lego",
    "password": "bricks",
}

# -------------------------------
# Server-side LRU cache (100 sets)
# -------------------------------
SET_CACHE = OrderedDict()
CACHE_SIZE = 100

def get_set_from_cache(set_id):
    if set_id in SET_CACHE:
        SET_CACHE.move_to_end(set_id)
        return SET_CACHE[set_id], True
    return None, False

def update_cache(set_id, data):
    if set_id in SET_CACHE:
        SET_CACHE.move_to_end(set_id)
        SET_CACHE[set_id] = data
    else:
        if len(SET_CACHE) >= CACHE_SIZE:
            SET_CACHE.popitem(last=False)
        SET_CACHE[set_id] = data

# -------------------------------
# Database wrapper
# -------------------------------
class Database:
    def __init__(self, host, port, dbname, user, password):
        self.db_config = dict(host=host, port=port, dbname=dbname, user=user, password=password)
        self.conn = None
        self.cur = None

    def execute_and_fetch_all(self, query, params=None):
        self.conn = psycopg.connect(**self.db_config)
        self.cur = self.conn.cursor()
        self.cur.execute(query, params)
        return self.cur.fetchall()

    def close(self):
        if self.cur: self.cur.close()
        if self.conn: self.conn.close()

# -------------------------------
# Helper functions (separated from endpoints)
# -------------------------------

def fetch_all_sets_html(db, encoding="utf-8"):
    """Return gzipped HTML string of all sets."""
    rows_list = []
    for row in db.execute_and_fetch_all("SELECT id, name FROM lego_set ORDER BY id"):
        html_safe_id = html.escape(row[0])
        html_safe_name = html.escape(row[1])
        rows_list.append(f'<tr><td><a href="/set?id={html_safe_id}">{html_safe_id}</a></td><td>{html_safe_name}</td></tr>\n')

    with open("templates/sets.html", "r", encoding="utf-8") as f:
        template = f.read()

    charset_meta = '<meta charset="UTF-8">' if encoding == "utf-8" else ""
    template = template.replace("{CHARSET_META}", charset_meta)
    template_content = template.replace("{ROWS}", "".join(rows_list))
    html_bytes = template_content.encode(encoding)
    return gzip.compress(html_bytes)

def fetch_set_data(db, set_id):
    """Return JSON string of a single set + inventory."""
    row = db.execute_and_fetch_all("SELECT id, name FROM lego_set WHERE id = %s", (set_id,))
    if not row:
        return json.dumps({"error": "Set not found"}, indent=4), 404

    data = {"id": row[0][0], "name": row[0][1], "inventory": []}

    for r in db.execute_and_fetch_all("SELECT brick_type_id, color_id, count FROM lego_inventory WHERE set_id = %s", (set_id,)):
        data["inventory"].append({"brick_type_id": r[0], "color_id": r[1], "count": r[2]})
    
    return json.dumps(data, indent=4), 200

def fetch_set_binary(db, set_id):
    """Return custom binary format for a set + inventory."""
    json_data, status = fetch_set_data(db, set_id)
    if status != 200:
        return None, status
    data = json.loads(json_data)

    binary = bytearray()
    set_id_bytes = data["id"].encode("utf-8")
    name_bytes = data["name"].encode("utf-8")
    binary.append(len(set_id_bytes))
    binary.extend(set_id_bytes)
    binary.append(len(name_bytes))
    binary.extend(name_bytes)

    num_items = len(data["inventory"])
    binary.extend(num_items.to_bytes(2, byteorder="big"))

    for item in data["inventory"]:
        bt_bytes = str(item["brick_type_id"]).encode("utf-8")
        color_bytes = str(item["color_id"]).encode("utf-8")
        binary.append(len(bt_bytes))
        binary.extend(bt_bytes)
        binary.append(len(color_bytes))
        binary.extend(color_bytes)
        binary.extend(item["count"].to_bytes(4, byteorder="big"))

    return bytes(binary), 200

# -------------------------------
# Routes
# -------------------------------

@app.route("/")
def index():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        template = f.read()
    return Response(template, content_type="text/html")

@app.route("/sets")
def sets():
    encoding = request.args.get("encoding", "utf-8").lower()
    if encoding not in ("utf-8", "utf-16"):
        encoding = "utf-8"

    db = Database(**DB_CONFIG)
    try:
        html_bytes = fetch_all_sets_html(db, encoding)
    finally:
        db.close()

    response = Response(html_bytes)
    response.headers["Content-Type"] = f"text/html; charset={encoding}"
    response.headers["Content-Encoding"] = "gzip"
    response.headers["Cache-Control"] = "public, max-age=60"
    return response

@app.route("/set")
def set_page():
    with open("templates/set.html", "r", encoding="utf-8") as f:
        template = f.read()
    return Response(template, content_type="text/html")

@app.route("/api/set")
def api_set():
    set_id = request.args.get("id")
    start_time = perf_counter()

    data, cached = get_set_from_cache(set_id)
    if not cached:
        db = Database(**DB_CONFIG)
        try:
            data_json, status = fetch_set_data(db, set_id)
            if status != 200:
                return Response(data_json, content_type="application/json", status=status)
            data = json.loads(data_json)
            update_cache(set_id, data)
        finally:
            db.close()
    
    elapsed = perf_counter() - start_time
    print(f"Set {set_id} response time: {elapsed:.4f} sec (cached={cached})")
    return Response(json.dumps(data, indent=4), content_type="application/json")

@app.route("/api/set/binary")
def api_set_binary():
    set_id = request.args.get("id")
    data, cached = get_set_from_cache(set_id)
    if not cached:
        db = Database(**DB_CONFIG)
        try:
            binary_data, status = fetch_set_binary(db, set_id)
            if status != 200:
                return Response(status=status)
            data = {"binary": "stored"}  # placeholder to update cache
            update_cache(set_id, data)
        finally:
            db.close()
    else:
        binary_data, _ = fetch_set_binary(Database(**DB_CONFIG), set_id)  # regenerate for response
    
    return Response(binary_data, content_type="application/octet-stream")

# -------------------------------
# Run app
# -------------------------------
if __name__ == "__main__":
    app.run(port=5000, debug=True)