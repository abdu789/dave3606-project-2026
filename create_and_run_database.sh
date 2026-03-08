#!/bin/sh

# Note: Do not use the `shared_buffers` configuration with such a small value in real life!
# It severely restricts the internal caching in PostgreSQL,to highlight the effects
# of the indexes even though the database isn't huge.
docker run \
    -d \
    --name lego-postgres \
    -e POSTGRES_USER=lego \
    -e POSTGRES_PASSWORD=bricks \
    -e POSTGRES_DB=lego-db \
    -p 9876:5432 \
    postgres:18 \
    -c shared_buffers=128kB
