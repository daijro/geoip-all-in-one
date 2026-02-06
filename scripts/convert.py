"""
Convert merged tsv to mmdb (and adds timezone)
"""

import sys

import netaddr
from mmdb_writer import MMDBWriter
from tzfpy import get_tz


def hex_to_ip(hex_str, ipv6=False):
    num = int(hex_str, 16)
    if ipv6:
        return netaddr.IPAddress(num, version=6)
    return netaddr.IPAddress(num, version=4)


def process_file(input_file, writer, ipv6=False):
    count = 0

    with open(input_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            parts = line.split('\t')
            if len(parts) < 5:
                continue

            start_hex = parts[0]
            end_hex = parts[1]
            country_code = parts[2]
            latitude = parts[3]
            longitude = parts[4]

            try:
                start_ip = hex_to_ip(start_hex, ipv6)
                end_ip = hex_to_ip(end_hex, ipv6)

                lat = float(latitude)
                lon = float(longitude)
                tz = get_tz(lon, lat)

                data = {
                    'country': {'iso_code': country_code},
                    'location': {'latitude': lat, 'longitude': lon, 'time_zone': tz},
                }

                for cidr in netaddr.iprange_to_cidrs(start_ip, end_ip):
                    writer.insert_network(cidr, data)
                count += 1

            except Exception as e:
                print(f"Error on line {line_num}: {e}", file=sys.stderr)
                continue

            if line_num % 100000 == 0:
                print(f"  Processed {line_num} lines...", file=sys.stderr)

    return count


def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("  convert.py <input.tsv> <output.mmdb> <4|6>")
        print("  convert.py <ipv4.tsv> <ipv6.tsv> <output.mmdb>")
        sys.exit(1)

    if len(sys.argv) == 4 and sys.argv[3] in ('4', '6'):
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        ip_version = int(sys.argv[3])

        writer = MMDBWriter(ip_version=ip_version, database_type='GeoIP2-City')

        print(f"Processing {input_file}...", file=sys.stderr)
        count = process_file(input_file, writer, ipv6=(ip_version == 6))

        print(f"Writing {count} entries to {output_file}...", file=sys.stderr)
        writer.to_db_file(output_file)
        print(f"Done! Created {output_file}", file=sys.stderr)

    elif len(sys.argv) == 4:
        # combined ipv4+ipv6
        ipv4_file = sys.argv[1]
        ipv6_file = sys.argv[2]
        output_file = sys.argv[3]

        writer = MMDBWriter(ip_version=6, ipv4_compatible=True, database_type='GeoIP2-City')

        print(f"Processing {ipv4_file} (IPv4)...", file=sys.stderr)
        count4 = process_file(ipv4_file, writer, ipv6=False)

        print(f"Processing {ipv6_file} (IPv6)...", file=sys.stderr)
        count6 = process_file(ipv6_file, writer, ipv6=True)

        total = count4 + count6
        print(
            f"Writing {total} entries ({count4} IPv4, {count6} IPv6) to {output_file}...",
            file=sys.stderr,
        )
        writer.to_db_file(output_file)
        print(f"Done! Created {output_file}", file=sys.stderr)

    else:
        print("Invalid arguments", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
