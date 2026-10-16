# GeoIP database (offline location for the admin activity monitor)

The activity monitor resolves visitor IPs to a **city / country** entirely
**offline** — no user IP ever leaves the server. It uses MaxMind's free
**GeoLite2-City** database, which is not redistributable, so you drop the file
in here yourself. Until you do, the monitor still works — the *Location* column
just shows “Không rõ”.

## How to enable

1. Create a free account at https://www.maxmind.com/en/geolite2/signup
2. On the download page pick **GeoLite2-City** → format **GeoIP2 Binary (.mmdb)**
   → **Download GZIP**. (Not the CSV, and not ASN/Country — City is worldwide and
   includes city + coordinates.)
3. Extract the downloaded `GeoLite2-City_YYYYMMDD.tar.gz`. Inside a dated folder is
   the file `GeoLite2-City.mmdb`. Copy just that file here so the path is exactly:

   ```
   <repo>/geoip/GeoLite2-City.mmdb
   ```

   (Drop the date suffix — the filename must be exactly `GeoLite2-City.mmdb`.)

   The backend/worker containers mount the repo at `/workspace`, so it resolves
   to `/workspace/geoip/GeoLite2-City.mmdb` (the default `GEOIP_DB_PATH`).

4. **(Optional) ISP / network operator** — also download **GeoLite2-ASN** →
   **GeoIP2 Binary (.mmdb) → Download GZIP**, extract, and place `GeoLite2-ASN.mmdb`
   next to the City file:

   ```
   <repo>/geoip/GeoLite2-ASN.mmdb
   ```

   This adds the ISP (e.g. “Viettel Group”, “FPT Telecom”) under each session's
   location. Without it, location still works — just no ISP line.

5. Restart the backend: `docker compose -f docker-compose.prod.yml restart backend`

No image rebuild is needed — the files are read from the mounted volume at runtime.
Override paths with `GEOIP_DB_PATH` (city) and `GEOIP_ASN_DB_PATH` (ASN).

> Tip: keep the database fresh (MaxMind updates it weekly). `.mmdb` files are
> git-ignored below so the large binary never lands in the repo history.
