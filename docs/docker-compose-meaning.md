# `docker-compose.yml` meaning

```yml
services:
  floci:
    image: floci/floci:latest
    container_name: floci
    ports:
      - "4566:4566"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./data:/app/data
    environment:
      FLOCI_STORAGE_MODE: hybrid
    restart: unless-stopped
```

- `4566:4566` makes Floci available at `http://localhost:4566`.
- `/var/run/docker.sock:/var/run/docker.sock` allows Floci to use Docker.
- `./data:/app/data` stores Floci data in a local `data` folder, so your buckets, queues, and other resources are not immediately lost when the container restarts.
- `FLOCI_STORAGE_MODE: hybrid` means Floci uses both memory and disk storage.
- `memory` is fast, but data is lost when Floci stops.
- `persistent` writes directly to disk.
- `hybrid` uses fast memory storage plus periodic disk saving.
