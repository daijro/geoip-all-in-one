.PHONY: all clean download download-ipv4 download-ipv6 merge convert ipv4 ipv6 deps

PYTHON := python3
SOURCES := sources.yaml

IPV4_MERGED := merged_ipv4.tsv
IPV6_MERGED := merged_ipv6.tsv
IPV4_MMDB := geoip_ipv4.mmdb
IPV6_MMDB := geoip_ipv6.mmdb
COMBINED_MMDB := geoip.mmdb

DATA_DIR := data
IPV4_DIR := $(DATA_DIR)/ipv4
IPV6_DIR := $(DATA_DIR)/ipv6
IPV4_DONE := $(IPV4_DIR)/.downloaded
IPV6_DONE := $(IPV6_DIR)/.downloaded

all: $(COMBINED_MMDB)

download: download-ipv4 download-ipv6
download-ipv4: $(IPV4_DONE)
download-ipv6: $(IPV6_DONE)

$(IPV4_DONE): $(SOURCES)
	@mkdir -p $(IPV4_DIR)
	$(PYTHON) scripts/download.py $(SOURCES) ipv4 $(IPV4_DIR)
	@touch $@

$(IPV6_DONE): $(SOURCES)
	@mkdir -p $(IPV6_DIR)
	$(PYTHON) scripts/download.py $(SOURCES) ipv6 $(IPV6_DIR)
	@touch $@

merge: $(IPV4_MERGED) $(IPV6_MERGED)

$(IPV4_MERGED): $(IPV4_DONE) scripts/merge.py
	$(PYTHON) scripts/merge.py $(SOURCES) ipv4 $(IPV4_DIR) $@

$(IPV6_MERGED): $(IPV6_DONE) scripts/merge.py
	$(PYTHON) scripts/merge.py $(SOURCES) ipv6 $(IPV6_DIR) $@

convert: $(COMBINED_MMDB)

$(IPV4_MMDB): $(IPV4_MERGED)
	$(PYTHON) scripts/convert.py $< $@ 4

$(IPV6_MMDB): $(IPV6_MERGED)
	$(PYTHON) scripts/convert.py $< $@ 6

$(COMBINED_MMDB): $(IPV4_MERGED) $(IPV6_MERGED) scripts/convert.py
	$(PYTHON) scripts/convert.py $(IPV4_MERGED) $(IPV6_MERGED) $@

ipv4: $(IPV4_MMDB)
ipv6: $(IPV6_MMDB)

clean:
	rm -rf $(DATA_DIR)
	rm -f $(IPV4_MERGED) $(IPV6_MERGED)
	rm -f $(IPV4_MMDB) $(IPV6_MMDB) $(COMBINED_MMDB)

deps:
	pip install pyyaml mmdb_writer netaddr tzfpy requests
