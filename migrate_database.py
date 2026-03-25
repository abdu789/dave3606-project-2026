import psycopg

conn = psycopg.connect(
    host="localhost",
    port=9876,
    dbname="lego-db",
    user="lego",
    password="bricks",
)

cur = conn.cursor()
cur.execute(
    """
    create table lego_set(
        id TEXT NOT NULL PRIMARY KEY,
        name text not null,
        year int null,
        category text null,
        preview_image_url text null
    );
    """
)
cur.execute(
    """
    create table lego_brick(
        brick_type_id text not null,
        color_id int not null,
        name text not null,
        preview_image_url text null,
        PRIMARY KEY (brick_type_id, color_id)
    );
    """
)
cur.execute(
    """
    create table lego_inventory(
        set_id text not null,
        brick_type_id text not null,
        color_id int not null,
        count int not null,
        PRIMARY KEY (set_id, brick_type_id, color_id),
        FOREIGN KEY (set_id) REFERENCES lego_set(id),
        FOREIGN KEY (brick_type_id, color_id) REFERENCES lego_brick(brick_type_id, color_id)
    );
    """
)
cur.close()
conn.commit()
conn.close()