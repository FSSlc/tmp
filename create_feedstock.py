#!/usr/bin/env python3
# coding: utf-8
#
"""A tool to create a feedstock directly from a conda-forge package"""

import argparse
import json
import os
import shutil
import urllib.request
import urllib.parse
import re
import tempfile
import tarfile

import ruamel.yaml
import zstandard
from colorama import Fore, Style
from packaging.version import parse as PV

fn_is_simple = re.compile(r"^v?\d+([\-.]\d+)+(\.\w+)+$").match


def load_urls(meta_yaml):
    loader = ruamel.yaml.YAML()
    with open(meta_yaml, encoding="utf8") as f:
        meta = loader.load(f)
    result = {}
    if "source" not in meta:
        return {}
    sources = meta["source"]
    if not isinstance(sources, list):
        sources = [sources]
    for item in sources:
        if "url" not in item:
            continue
        url = item["url"]
        if "md5" in item:
            hash_type = "md5"
        elif "sha256" in item:
            hash_type = "sha256"
        elif "sha1" in item:
            hash_type = "sha1"
        else:
            raise ValueError(f"Unknown hash type in {item}")
        hash = item[hash_type]
        fn = item.get("fn", None)
        result[url] = [hash_type, hash, fn]
    return result


def replace_urls(meta_yaml_tpl, urls, pkgs_dir):
    url_regex = re.compile(r"(^\s*-?\s*url:\s*)([^{]+)\{\{.*\}\}([^}]+)$")
    with open(meta_yaml_tpl) as f:
        content = f.read().split("\n")
    result = []
    for line in content:
        m = url_regex.match(line)
        if not m:
            result.append(line)
            continue
        head = m.group(2)
        tail = m.group(3)
        url_pattern = re.escape(head) + r".*" + re.escape(tail)
        new_url = None
        for u in urls.keys():
            if re.match(url_pattern, u):
                new_url = u
                break
        if new_url is None:
            print(f"!! URL at {line.strip()!r} not found")
            result.append(line)
            continue
        fn = os.path.basename(urllib.parse.urlparse(new_url).path)
        if urls[new_url][2] is not None:
            fn = urls[new_url][2]
        pkg_path = os.path.join(pkgs_dir, fn)
        pkg_path = os.path.relpath(pkg_path, os.path.dirname(meta_yaml_tpl))
        result.append("#" + m.group())
        result.append(m.group(1) + pkg_path)
    with open(meta_yaml_tpl, "w", encoding="utf8") as f:
        f.write("\n".join(result))


def extract_reqs(meta_yaml):
    with open(meta_yaml) as f:
        content = f.read().split("\n")
    keys = ("host:", "run:", "build:", "run_constrained:")
    in_req = False
    result = []
    for line in content:
        line = line.strip()
        if not line:
            continue
        if not in_req:
            if not line.startswith("requirements:"):
                continue
            in_req = True
            result.append(line)
        else:
            if line.startswith("#"):
                continue
            if line.startswith("{"):
                result.append(line)
                continue
            if line.startswith("-"):
                result.append(line)
                continue
            if line.endswith(":") and line not in keys:
                in_req = False
                continue
            result.append(line)
    return "\n".join(result)


def download_file(url, fn):
    # github 代理
    # if "github" in url:
    #     url = os.path.join("https://github.moeyy.xyz/", url)
    CHUNK_SIZE = 64 * 1024
    dest = os.path.dirname(fn)
    basefn = os.path.basename(fn)
    os.makedirs(dest, exist_ok=True)
    url_segs = urllib.parse.urlparse(url)
    netloc = url_segs.netloc
    with open(fn, "wb") as out:
        print(f"{Fore.YELLOW}oo Connecting to {netloc}")
        with urllib.request.urlopen(url) as f:
            print(f"oo Downloading {basefn} from {url}\noo ", end="", flush=True)
            print(f"oo Downloading {basefn} to {dest}\noo ", end="", flush=True)
            blocks = 0
            while True:
                s = f.read(CHUNK_SIZE)
                if len(s) == 0:
                    break
                print(".", end="", flush=True)
                blocks += 1
                if blocks == 77:
                    print("\noo ", flush=True, end="")
                    blocks = 0
                out.write(s)
    print(f"\noo File saved to {fn}{Style.RESET_ALL}")


def url_basename(url):
    return os.path.basename(urllib.parse.urlparse(url).path)


def extract_zst(archive, out_path):
    """extract .zst file"""

    if zstandard is None:
        raise ImportError("pip install zstandard")

    archive = os.path.abspath(archive)
    out_path = os.path.abspath(out_path)
    dctx = zstandard.ZstdDecompressor()

    with tempfile.TemporaryFile(suffix=".tar") as ofh:
        with open(archive, "rb") as ifh:
            dctx.copy_stream(ifh, ofh)
        ofh.seek(0)
        with tarfile.open(fileobj=ofh) as z:
            z.extractall(out_path)


def extract_archive(archive, out_path, format="zip"):
    if format == "zst":
        extract_zst(archive, out_path)
    elif format == "conda":
        shutil.unpack_archive(archive, out_path, format="zip")
    elif format in [
        "zip",
        "tar",
        "tar.gz",
        "tgz",
        "gztar",
        "bztar",
        "tar.bz2",
        "xztar",
        "tar.zx",
    ]:
        shutil.unpack_archive(archive, out_path)
    else:
        raise ValueError(f"Unknown format {format} to extract.")


def get_pkg_spec(pkg, ver, py, pkg_db):
    with open(pkg_db) as f:
        pkg_db = json.load(f)
    if pkg not in pkg_db:
        raise ValueError(f"Requested package {pkg} is not in database")
    pkg_specs = pkg_db[pkg]
    if py:
        filter_pkg_specs = list(filter(lambda x: py in x.get("build"), pkg_specs))
        if len(filter_pkg_specs) > 0:
            pkg_specs = list(filter_pkg_specs)
        else:
            print(
                f"{Fore.YELLOW }>> No packages with {py} build string{Style.RESET_ALL}"
            )
    if ver is None:
        pkg_spec = pkg_specs[-1]  # the newest version
    else:
        pkg_spec = None
        for p in reversed(pkg_specs):
            if PV(p["version"]) <= PV(ver):
                pkg_spec = p
                break
        if pkg_spec is None:
            raise ValueError(f"version {ver} of {pkg} is not found in the db")
    return pkg_spec


def create_feedstock(
    pkg_spec,
    workdir="workdir",
    recipes_dir="recipes",
    pkgs_dir="pkgs",
):
    pkg = pkg_spec.get("name")
    print(
        f"{Fore.GREEN}>> Creating feedstock for "
        + f"{pkg!r} {pkg_spec['version']}{Style.RESET_ALL}"
    )
    nv = pkg_spec["nv"]
    print(f">> Downloading binary package {nv} from conda-forge channel ...")
    out_fn = os.path.join(workdir, url_basename(pkg_spec["url"]))
    download_file(pkg_spec["url"], out_fn)

    extract_dir = os.path.basename(out_fn).replace(".tar.bz2", "").replace(".conda", "")
    extract_dir = os.path.join(workdir, extract_dir)
    print(f">> Unpacking {os.path.basename(out_fn)} to {extract_dir}...")
    shutil.rmtree(extract_dir, ignore_errors=True)
    os.makedirs(extract_dir, exist_ok=True)
    if ".conda" in out_fn:
        extract_archive(out_fn, extract_dir, "conda")
        info_out_fn = "info-" + url_basename(pkg_spec["url"]).replace(
            ".conda", ".tar.zst"
        )
        info_out_path = os.path.join(extract_dir, info_out_fn)
        extract_archive(info_out_path, extract_dir, format="zst")
    else:
        extract_archive(out_fn, extract_dir)

    old_recipe = os.path.join(extract_dir, "info", "recipe")
    new_recipe = os.path.join(recipes_dir, pkg_spec["nv"])
    os.makedirs(recipes_dir, exist_ok=True)
    if os.path.exists(new_recipe):
        shutil.rmtree(new_recipe)
    if os.path.exists(os.path.join(old_recipe, "parent")):
        print(
            f"{Fore.RED}!! {pkg} is a multi-output package, "
            + f"correct its name{Style.RESET_ALL}"
        )
        real_recipe = os.path.join(old_recipe, "parent")
        shutil.copytree(real_recipe, new_recipe)
        meta_yaml = os.path.join(old_recipe, "meta.yaml")
        meta_yaml_tpl = os.path.join(new_recipe, "meta.yaml")
    else:
        print(f">> Copying recipe to {new_recipe} ...")
        shutil.copytree(old_recipe, new_recipe)
        conda_build_cfg = os.path.join(new_recipe, "conda_build_config.yaml")
        meta_yaml = os.path.join(new_recipe, "meta.yaml")
        meta_yaml_tpl = os.path.join(new_recipe, "meta.yaml.template")
        if os.path.exists(conda_build_cfg):
            print(f">> Removing redundant {conda_build_cfg} ...")
            os.remove(conda_build_cfg)
    print(f">> Downloading packages to {pkgs_dir} ...")
    urls = load_urls(meta_yaml)
    for url, v in urls.items():
        fn = v[2] if v[2] is not None else url_basename(url)
        fn = f"{pkg}-{fn}" if fn_is_simple(fn) else fn
        v[2] = fn  # fix the destination filename
        full_fn = os.path.join(pkgs_dir, fn)
        # TODO: validate hash, if exists then skip download
        download_file(url, full_fn)
    print(f">> Replacing urls in {meta_yaml_tpl} ...")
    replace_urls(meta_yaml_tpl, urls, pkgs_dir)
    if os.path.exists(os.path.join(old_recipe, "parent")):
        print(f">> Created feedstock for {pkg!r} at {new_recipe}.")
    else:
        os.remove(meta_yaml)
        shutil.move(meta_yaml_tpl, meta_yaml)
        print(
            f"{Fore.GREEN}>> Created feedstock for {pkg!r} "
            + f"at {new_recipe}.{Style.RESET_ALL}"
        )
    print("!! Please be sure to check the recipe for necessary modifications.")
    print("!! Please check if all the following dependencies are built: ")
    deps = extract_reqs(os.path.join(new_recipe, "meta.yaml"))
    print("-" * 80)
    print(deps)
    print("-" * 80)
    with open(os.path.join(workdir, "deps.txt"), "a") as f:
        f.write("-" * 72)
        f.write(f"\ndependencies for {nv}:\n")
        f.write(deps + "\n\n")


def get_abs_path(path):
    if not os.path.isabs(path):
        script_dir = os.path.dirname(__file__)
        path = os.path.join(script_dir, path)
        path = os.path.abspath(path)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "PKG_NAME", help="Package name without any version and build strings."
    )
    parser.add_argument(
        "-ub",
        "--upper-bound",
        default=None,
        help="Package version upper bound (default: highest)",
    )
    parser.add_argument(
        "--db",
        default="../data/pkgdb.json",
        help="Package database file (default: %(default)s)",
    )
    parser.add_argument(
        "--py",
        default="310",
        help="python version (default: %(default)s)",
    )
    parser.add_argument(
        "--workdir",
        metavar="WORKDIR",
        default="../workdir",
        help="Workdir for downloading (default: %(default)s)",
    )
    parser.add_argument(
        "--recipes-dir",
        metavar="DIR",
        default="../recipes",
        help="Recipes directory (default: %(default)s)",
    )
    parser.add_argument(
        "--pkgs-dir",
        metavar="DIR",
        default="../pkgs",
        help="Source packages directory (default: %(default)s)",
    )
    args = parser.parse_args()

    args.db = get_abs_path(args.db)
    args.workdir = get_abs_path(args.workdir)
    args.pkgs_dir = get_abs_path(args.pkgs_dir)
    args.recipes_dir = get_abs_path(args.recipes_dir)
    pkg_spec = get_pkg_spec(args.PKG_NAME, args.upper_bound, args.py, args.db)

    create_feedstock(
        pkg_spec,
        args.workdir,
        args.recipes_dir,
        args.pkgs_dir,
    )


if __name__ == "__main__":
    main()
