"""
Merge geoip sources into a single tsv
"""

import os
import sys
from collections import Counter
from typing import Optional

import yaml

"""
ip conversion helpers
"""


def hex_to_int(h: str) -> int:
    return int(h, 16)


def ip_to_int(ip: str) -> int:
    parts = ip.split('.')
    return (int(parts[0]) << 24) + (int(parts[1]) << 16) + (int(parts[2]) << 8) + int(parts[3])


def ipv6_to_int(ip: str) -> int:
    import ipaddress

    return int(ipaddress.ip_address(ip))


def int_to_hex(n: int) -> str:
    return f"{n:x}"


"""
range table
"""


class RangeTable:
    """
    sorted IP range table with sweep-line cursor for sequential lookup.
    """

    __slots__ = ('starts', 'ends', 'data', '_cursor')

    def __init__(self) -> None:
        self.starts: list[int] = []
        self.ends: list[int] = []
        self.data: list = []
        self._cursor: int = 0

    def add(self, start: int, end: int, value) -> None:
        self.starts.append(start)
        self.ends.append(end)
        self.data.append(value)

    def finalize(self, name: str = '') -> None:
        """
        sort ranges and check for overlaps.
        """
        if not self.starts:
            return
        combined = sorted(zip(self.starts, self.ends, self.data))
        self.starts = [c[0] for c in combined]
        self.ends = [c[1] for c in combined]
        self.data = [c[2] for c in combined]
        overlaps = 0
        for i in range(1, len(self.starts)):
            if self.starts[i] < self.ends[i - 1]:
                overlaps += 1
        if overlaps:
            print(f"  Warning: {name} has {overlaps} overlapping ranges", file=sys.stderr)

    def sweep(self, point: int):
        """
        lookup point; points must be non-decreasing between calls.
        """
        c = self._cursor
        n = len(self.starts)
        while c < n and self.ends[c] <= point:
            c += 1
        if c < n and self.starts[c] <= point:
            self._cursor = c
            return self.data[c]
        self._cursor = c
        return None

    def __len__(self) -> int:
        return len(self.starts)

    def boundaries(self) -> set[int]:
        """
        returns set of all start/end IPs.
        """
        b = set()
        for i in range(len(self.starts)):
            b.add(self.starts[i])
            b.add(self.ends[i])
        return b


"""
file loaders
latlong loaders return (country, lat, lon) tuples, country loaders return country strings
"""


def load_latlong_tsv(filename: str, lat_col: int, long_col: int, ipv6: bool = False) -> RangeTable:
    table = RangeTable()
    if not os.path.exists(filename):
        return table
    with open(filename) as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) > max(lat_col, long_col):
                try:
                    start = hex_to_int(parts[0])
                    end = hex_to_int(parts[1]) + 1
                    table.add(start, end, (parts[2], parts[lat_col], parts[long_col]))
                except Exception as e:
                    print(f"Error processing line in {filename}: {e}", file=sys.stderr)
                    pass
    table.finalize(os.path.basename(filename))
    return table


def load_country_tsv(filename: str) -> RangeTable:
    table = RangeTable()
    if not os.path.exists(filename):
        return table
    with open(filename) as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 3:
                try:
                    start = hex_to_int(parts[0])
                    end = hex_to_int(parts[1]) + 1
                    table.add(start, end, parts[2])
                except Exception as e:
                    print(f"Error processing line in {filename}: {e}", file=sys.stderr)
                    pass
    table.finalize(os.path.basename(filename))
    return table


def load_country_csv(filename: str, ipv6: bool = False) -> RangeTable:
    """
    handles both decimal ipv4 and ipv6 notation.
    """
    table = RangeTable()
    if not os.path.exists(filename):
        return table
    with open(filename) as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) >= 3:
                try:
                    if ipv6:
                        start = ipv6_to_int(parts[0])
                        end = ipv6_to_int(parts[1]) + 1
                    else:
                        start = ip_to_int(parts[0])
                        end = ip_to_int(parts[1]) + 1
                    table.add(start, end, parts[2])
                except Exception as e:
                    print(f"Error processing line in {filename}: {e}", file=sys.stderr)
                    pass
    table.finalize(os.path.basename(filename))
    return table


"""
merge logic
"""


def distance(lat1, lon1, lat2, lon2) -> float:
    # euclidean distance (good enough for comparing relative positions)
    return ((float(lat1) - float(lat2)) ** 2 + (float(lon1) - float(lon2)) ** 2) ** 0.5


def pick_center_coords(
    named_ll: list[tuple[str, tuple]], threshold: int = 2
) -> tuple[str, str, str]:
    """
    when all coord sources agree on country, pick the point closest to the others.
    if spread is small (< threshold degrees), just use highest-priority source instead.
    named_ll: [(name, (country, lat, lon))] in coord priority order.
    """
    if len(named_ll) < 3:
        name, data = named_ll[0]
        return (data[1], data[2], name)

    coords = [(float(d[1]), float(d[2])) for _, d in named_ll]

    # max spread between any pair
    max_dist = 0
    for a in range(len(coords)):
        for b in range(a + 1, len(coords)):
            dist = distance(coords[a][0], coords[a][1], coords[b][0], coords[b][1])
            max_dist = max(max_dist, dist)

    # close enough, use highest priority for better merging
    if max_dist <= threshold:
        name, data = named_ll[0]
        return (data[1], data[2], name)

    # pick source with smallest total distance to the others
    min_total = float('inf')
    best = 0
    for idx in range(len(coords)):
        total = sum(
            distance(coords[idx][0], coords[idx][1], coords[j][0], coords[j][1])
            for j in range(len(coords))
            if j != idx
        )
        if total < min_total:
            min_total = total
            best = idx

    name, data = named_ll[best]
    return (data[1], data[2], name)


def pick_winner(
    all_data: dict, latlong_names: set[str], merge_config: dict
) -> Optional[tuple[str, str, str, str]]:
    """
    main merge decision for a single IP point.
    all_data maps source name -> (country, lat, lon) for latlong or country string for country-only.
    returns (country, lat, lon, debug_label) or None.
    """
    # collect countries from all sources that have data
    countries = {}
    for name, data in all_data.items():
        if data is None:
            continue
        countries[name] = data[0] if isinstance(data, tuple) else data

    if not countries:
        return None

    all_country_list = list(countries.values())
    votes = Counter(all_country_list)

    # coord sources in priority order, with their reported country
    coord_priority = merge_config.get('coord_priority', list(latlong_names))
    coord_sources = []
    for name in coord_priority:
        data = all_data.get(name)
        if data and isinstance(data, tuple):
            coord_sources.append((data[0], data[1], data[2], name))

    # find best coords for a country by walking coord priority
    def find_coords(country: str) -> Optional[tuple[str, str, str]]:
        for cc, lat, lon, src in coord_sources:
            if cc == country:
                return (lat, lon, src)
        return None

    # all available lat/long sources agree on country
    # so try to find the most center coordinate
    threshold = merge_config.get('coord_spread_threshold', 2)
    available_ll = [
        (name, all_data[name])
        for name in coord_priority
        if name in latlong_names and all_data.get(name)
    ]
    ll_country_list = [data[0] for _, data in available_ll]

    if len(available_ll) >= 2 and len(set(ll_country_list)) == 1:
        lat, lon, src = pick_center_coords(available_ll, threshold)
        return (ll_country_list[0], lat, lon, f'unanimous->{src}')

    # override rules (preconfigured pairs that force a country win)
    for rule in merge_config.get('overrides', []):
        match_names = rule['match']
        match_countries = []
        all_present = True
        for src_name in match_names:
            if src_name not in countries:
                all_present = False
                break
            match_countries.append(countries[src_name])

        if not all_present or len(set(match_countries)) != 1:
            continue

        matched_country = match_countries[0]
        coords = find_coords(matched_country)
        if coords:
            lat, lon, src = coords
            return (matched_country, lat, lon, '+'.join(match_names) + f'->{src}')

    # vote (rank countries by count, break ties using vote_priority)
    if not coord_sources:
        return (votes.most_common(1)[0][0], '0', '0', 'no_coords')

    vote_priority = merge_config.get('vote_priority', [])
    top = votes.most_common()

    # resolve ties: among tied countries, prefer one from vote_priority that has coords
    if len(top) >= 2 and top[0][1] == top[1][1]:
        tied = {c for c, n in top if n == top[0][1]}
        for prio_name in vote_priority:
            if prio_name in countries and countries[prio_name] in tied:
                coords = find_coords(countries[prio_name])
                if coords:
                    lat, lon, src = coords
                    return (countries[prio_name], lat, lon, f'vote->{src}')

    # walk voted countries, use the first one that has matching coords
    for country, _ in top:
        coords = find_coords(country)
        if coords:
            lat, lon, src = coords
            return (country, lat, lon, f'vote->{src}')

    # no coord source matches any voted country
    return (top[0][0], '0', '0', 'no_match')


def main() -> None:
    if len(sys.argv) != 5:
        print("Usage: merge.py <sources.yaml> <ipv4|ipv6> <data_dir> <output_file>")
        sys.exit(1)

    sources_file = sys.argv[1]
    ip_version = sys.argv[2]
    data_dir = sys.argv[3]
    output_file = sys.argv[4]

    ipv6 = ip_version == 'ipv6'

    with open(sources_file) as f:
        sources = yaml.safe_load(f)

    merge_config = sources.get('merge', {})

    # load latlong sources (return (country, lat, lon) tuples)
    print(f"Loading {ip_version} lat/long sources...", file=sys.stderr)
    latlong_sources: dict[str, RangeTable] = {}
    for name, info in sources.get('latlong', {}).items():
        ext = 'csv' if info.get('format') == 'decimal_csv' else 'tsv'
        filepath = os.path.join(data_dir, f"{name}.{ext}")
        lat_col = info.get('lat_col', 5)
        long_col = info.get('long_col', 6)
        latlong_sources[name] = load_latlong_tsv(filepath, lat_col, long_col, ipv6)
        print(f"  {name}: {len(latlong_sources[name])} ranges", file=sys.stderr)

    # load country-only sources (return country code strings)
    print(f"Loading {ip_version} country-only sources...", file=sys.stderr)
    country_sources: dict[str, RangeTable] = {}
    for name, info in sources.get('country', {}).items():
        fmt = info.get('format', 'hex_tsv')
        ext = 'csv' if fmt == 'decimal_csv' else 'tsv'
        filepath = os.path.join(data_dir, f"{name}.{ext}")
        if fmt == 'decimal_csv':
            country_sources[name] = load_country_csv(filepath, ipv6)
        else:
            country_sources[name] = load_country_tsv(filepath)
        print(f"  {name}: {len(country_sources[name])} ranges", file=sys.stderr)

    # collect all range start/end points across every source
    print("Finding boundary points...", file=sys.stderr)
    all_tables = list(latlong_sources.values()) + list(country_sources.values())
    boundary_set: set[int] = set()
    for table in all_tables:
        boundary_set.update(table.boundaries())
    boundaries = sorted(boundary_set)
    print(f"  {len(boundaries)} boundaries", file=sys.stderr)

    # sweep-line merge: walk boundaries in order, query each source, pick winner
    print("Processing segments...", file=sys.stderr)
    output: list[tuple] = []
    latlong_name_set = set(latlong_sources.keys())
    all_tables_named = [(name, table) for name, table in latlong_sources.items()] + [
        (name, table) for name, table in country_sources.items()
    ]

    total = len(boundaries) - 1
    for idx in range(total):
        start = boundaries[idx]
        end = boundaries[idx + 1] - 1

        # query all sources at this point
        all_data: dict = {}
        any_data = False
        for name, table in all_tables_named:
            val = table.sweep(start)
            all_data[name] = val
            if val is not None:
                any_data = True

        if not any_data:
            continue

        result = pick_winner(all_data, latlong_name_set, merge_config)
        if result:
            country, lat, lon, _ = result
            output.append((start, end, country, lat, lon))

        if idx % 500000 == 0 and idx > 0:
            print(f"  {idx}/{total} segments...", file=sys.stderr)

    # merge adjacent segments with identical country/coords
    print("Merging consecutive entries...", file=sys.stderr)
    merged: list[tuple] = []
    for entry in output:
        if merged and merged[-1][2:] == entry[2:] and merged[-1][1] + 1 == entry[0]:
            merged[-1] = (merged[-1][0], entry[1], *entry[2:])
        else:
            merged.append(entry)

    print(f"  {len(output)} -> {len(merged)} entries", file=sys.stderr)

    # write final tsv
    print(f"Writing {output_file}...", file=sys.stderr)
    with open(output_file, 'w') as f:
        for start, end, country, lat, lon in merged:
            f.write(f"{int_to_hex(start)}\t{int_to_hex(end)}\t{country}\t{lat}\t{lon}\n")

    print(f"Done! {len(merged)} entries written.", file=sys.stderr)


if __name__ == '__main__':
    main()
