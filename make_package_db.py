#!/usr/bin/env python3
# coding: utf-8
#
"""Create a package database for newest packages from conda-forge channel"""

import argparse
import json
import os
import urllib.request
import bz2
from packaging.version import parse as PV
from collections import defaultdict

DEFAULT_CONDA_FORGE_URL = "https://mirrors.nju.edu.cn/anaconda/cloud/conda-forge/"
# DEFAULT_CONDA_FORGE_URL = "https://conda.anaconda.org/conda-forge"
DEFAULT_ARCHES = ["linux-64", "noarch"]
#  "linux-aarch64"


def load_repodata(arches, forge_url):
    data = {}
    for arch in arches:
        url = os.path.join(forge_url, f"{arch}/repodata.json.bz2")
        print(f"Connecting to {url} ...")
        with urllib.request.urlopen(url) as f:
            print(f"Loading {url} ...")
            repodata = bz2.decompress(f.read())
            print(f"Parsing {url} ...")
            repodata = json.loads(repodata)
            data.update(repodata["packages"])
            data.update(repodata["packages.conda"])
    with open("../data/data.json", "w", encoding="utf8", newline="\n") as f:
        json.dump(data, f)
    return data


def parse_repodata(data, out, forge_url):
    print("Extracting package database ...")
    pkg_db = defaultdict(list)
    for pn, p in data.items():
        n = p["name"]
        v = p["version"]
        d = p["subdir"]
        b = p["build"]
        tt = p.get("timestamp", 0)
        pkg_db[n].append(
            {
                "name": n,
                "version": v,
                "url": f"{forge_url}/{d}/{pn}",
                "depends": p["depends"],
                "nv": f"{n}-{v}",
                "timestamp": tt,
                "build": b,
            }
        )
    for k, v in pkg_db.items():
        try:
            pkg_db[k] = sorted(v, key=lambda x: PV(x["version"]))
        except Exception:
            pkg_db[k] = sorted(
                v, key=lambda x: (x["version"], x["timestamp"], x["build"])
            )
    print(f"Writing package database to {out}")
    with open(out, "w", encoding="utf8", newline="\n") as f:
        json.dump(pkg_db, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        default="../data/pkgdb.json",
        help="Output package databse file (default: '%(default)s')",
    )
    parser.add_argument(
        "--arch",
        nargs=argparse.ONE_OR_MORE,
        dest="ARCHES",
        default=DEFAULT_ARCHES,
        help="Conda arch (default: %(default)s",
    )
    parser.add_argument(
        "--url",
        dest="CONDA_FORGE_URL",
        default=DEFAULT_CONDA_FORGE_URL,
        help="Conda forge url (default: %(default)s",
    )
    args = parser.parse_args()

    exist_data_fn = "../data/data.json"
    if os.path.exists(exist_data_fn):
        with open(exist_data_fn, "r", encoding="utf8") as fin:
            data = json.load(fin)
    else:
        data = load_repodata(args.ARCHES, args.CONDA_FORGE_URL)
    parse_repodata(data, args.output, args.CONDA_FORGE_URL)


if __name__ == "__main__":
    main()
