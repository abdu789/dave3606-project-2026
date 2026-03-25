import json
import html
import psycopg
from flask import Flask, Response, request
from time import perf_counter

app = Flask(__name__)

DB_CONFIG = {
    "host": "localhost",
    "port": 9876,
    "dbname": "lego-db",
    "user": "lego",
    "password": "bricks",
}


@app.route("/")
def index():
    template = open("templates/index.html").read()
    return Response(template)


@app.route("/sets")
def sets():
    encoding = request.args.get("encoding", "utf-8").lower()
    if encoding not in ("utf-8", "utf-16"):
        encoding = "utf-8"

    with open("templates/sets.html", "r", encoding="utf-8") as f:
        template = f.read()

    charset_meta = '<meta charset="UTF-8">' if encoding == "utf-8" else ""
    template = template.replace("{CHARSET_META}", charset_meta)

    rows_list = []

    conn = psycopg.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute("select id, name from lego_set order by id")
            for row in cur.fetchall():
                html_safe_id = html.escape(row[0])
                html_safe_name = html.escape(row[1])
                rows_list.append(f'<tr><td><a href="/set?id={html_safe_id}">{html_safe_id}</a></td><td>{html_safe_name}</td></tr>\n')
    finally:
        conn.close()

    template_content = template.replace("{ROWS}", "".join(rows_list))
    html_bytes = template_content.encode(encoding)
    compressed_bytes = gzip.compress(html_bytes)

    response = Response(compressed_bytes)
    response.headers["Content-Type"] = f"text/html; charset={encoding}"
    response.headers["Content-Encoding"] = "gzip"
    return response


@app.route("/set")
def legoSet():  
    # Use a context manager to safely read the file and avoid handle leaks
    with open("templates/set.html", "r", encoding="utf-8") as f:
        template = f.read()
    return Response(template, content_type="text/html")


@app.route("/api/set")
def apiSet():
    set_id = request.args.get("id")
    conn = psycopg.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            # Fetch set information
            cur.execute("SELECT id, name FROM lego_set WHERE id = %s", (set_id,))
            set_row = cur.fetchone()
            if not set_row:
                return Response(
                    json.dumps({"error": "Set not found"}, indent=4),
                    content_type="application/json",
                    status=404
                )
            
            result = {
                "id": set_row[0],
                "name": set_row[1],
                "inventory": []
            }

            # Fetch inventory for this set
            cur.execute(
                "SELECT brick_type_id, color_id, count FROM lego_inventory WHERE set_id = %s",
                (set_id,)
            )
            for row in cur.fetchall():
                result["inventory"].append({
                    "brick_type_id": row[0],
                    "color_id": row[1],
                    "count": row[2]
                })
    finally:
        conn.close()

    json_result = json.dumps(result, indent=4)
    return Response(json_result, content_type="application/json")


if __name__ == "__main__":
    app.run(port=5000, debug=True)

# Note: If you define new routes, they have to go above the call to `app.run`.
