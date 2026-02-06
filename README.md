# GeoIP All in One

This downloads the following sources, merges them with a voting algorithm, and outputs a single mmdb file with country, coordinates, and timezone info.

Releases are built weekly.

---

### City sources

Longitude and latitude:

- [IP2Location LITE](https://lite.ip2location.com)
- [GeoLite2](https://www.maxmind.com)
- [DB-IP Lite](https://db-ip.com)

### Country sources

These are additionally used to help vote on which city source to use for a given IP range:

- [ip-location-db GeoFeed + Whois + ASN database](https://github.com/tdulcet/ip-geolocation-dbs?tab=readme-ov-file#geofeed--whois--asn-database) (Created by merging the five [Regional Internet Registries](https://en.wikipedia.org/wiki/Regional_Internet_registry) (RIRs) ([AFRINIC](https://afrinic.net/), [APNIC](https://www.apnic.net/), [ARIN](https://www.arin.net/), [LACNIC](https://www.lacnic.net/), [RIPE NCC](https://www.ripe.net/)) IP-ASN, WHOIS and [OpenGeoFeed](https://opengeofeed.org/) databases)
- [IPinfo\.io](https://ipinfo.io)
- [IPlocate](https://iplocate.io)

### Timezone data

Calculated from the longitude/latitude using [tzfpy](https://github.com/ringsaturn/tzfpy)

---

## Merge algorithm

For each IP range, all 6 sources vote on a country.

The winning country is then used to narrow down city sources which then picks a longitude/latitude in the priority IP2Location > DB-IP > GeoLite2.

If all 3 city sources agree on the same country, the middle-most/most common coordinate pair is used.

---

This was developed for Camoufox's geolocation finder, so I've left out city names and only included country ISO codes, coordinates, and timezone to keep the file size smaller. I may add more later.

---

## Licenses

| Source           | Attribution                                                                                         |
| ---------------- | --------------------------------------------------------------------------------------------------- |
| IP2Location LITE | This project uses the IP2Location LITE database for [IP geolocation](https://lite.ip2location.com). |
| GeoLite2         | This product includes GeoLite2 Data created by MaxMind, available from https://www.maxmind.com/.    |
| DB-IP Lite       | [IP Geolocation by DB-IP](https://db-ip.com)                                                        |

## Sources

- [tdulcet/ip-geolocation-dbs](https://github.com/tdulcet/ip-geolocation-dbs)
- [sapics/ip-location-db](https://github.com/sapics/ip-location-db)
