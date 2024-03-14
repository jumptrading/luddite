#!/usr/bin/env python
# coding: utf-8
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from packaging.requirements import InvalidRequirement
from packaging.requirements import Requirement
from packaging.version import InvalidVersion
from packaging.version import Version

try:
    from urllib2 import Request, urlopen
except ImportError:
    from urllib.request import Request, urlopen
else:
    import cgi
    import codecs

    sys.stdout = codecs.getwriter("utf8")(sys.stdout)


__version__ = "1.0.4"


DEFAULT_FNAME = "requirements.txt"
DEFAULT_PIP_INDEX = os.environ.get("PIP_INDEX_URL", "https://pypi.org/pypi/")
DEFAULT_INDEX = os.environ.get("LUDDITE_DEFAULT_INDEX", DEFAULT_PIP_INDEX)

ANSI_COLORS = {
    None: "\x1b[0m",  # actually black but whatevs
    "red": "\x1b[31m",
    "green": "\x1b[32m",
    "yellow": "\x1b[33m",
    "magenta": "\x1b[35m",
}
if sys.platform == "win32":
    import colorama
    colorama.init(autoreset=True)


class LudditeError(Exception):
    """base for exceptions explicitly raised by this module"""


class MultipleIndicesError(LudditeError):
    """could not parse index url from the requirements.txt"""


def cprint(value, **kwargs):
    color = ANSI_COLORS[kwargs.pop("color", None)]
    reset = ANSI_COLORS[None]
    if sys.stdout.isatty():
        print("{}{}{}".format(color, value, reset), **kwargs)
    else:
        print(value, **kwargs)


def get_charset(headers, default="utf-8"):
    # this is annoying.
    try:
        charset = headers.get_content_charset(default)
    except AttributeError:
        # Python 2
        charset = headers.getparam("charset")
        if charset is None:
            ct_header = headers.getheader("Content-Type")
            content_type, params = cgi.parse_header(ct_header)
            charset = params.get("charset", default)
    return charset


def json_get(url, headers=(("Accept", "application/json"),)):
    request = Request(url=url, headers=dict(headers))
    response = urlopen(request)
    code = response.code
    if code != 200:
        err = LudditeError("Unexpected response code {}".format(code))
        err.response_data = response.read()
        raise err
    raw_data = response.read()
    response_encoding = get_charset(response.headers)
    decoded_data = raw_data.decode(response_encoding)
    data = json.loads(decoded_data)
    return data


def get_data_pypi(name, index=DEFAULT_INDEX):
    uri = "{}/{}/json".format(index.rstrip("/"), name.split("[")[0])
    data = json_get(uri)
    return data


def _safe_version(v):
    try:
        return Version(v)
    except InvalidVersion:
        pass


def get_versions_pypi(name, index=DEFAULT_INDEX):
    data = get_data_pypi(name, index)
    versions = []
    for raw_version, details in data["releases"].items():
        version = _safe_version(raw_version)
        if version is not None:
            if any(not d.get("yanked", False) for d in details):
                versions.append((version, raw_version))
    versions.sort()
    return tuple(v for (_, v) in versions)


def get_version_pypi(name, index=DEFAULT_INDEX):
    latest = get_data_pypi(name, index)["info"]["version"]
    return latest


def strip_suffixes(s, *suffixes):
    """Removes the suffix, if it's there, otherwise returns input string unchanged"""
    for suffix in suffixes:
        if s.endswith(suffix):
            s = s[: len(s) - len(suffix)]
    return s


def get_data_devpi(name, index):
    index = strip_suffixes(index, "+simple/", "+simple")
    uri = "{}/{}".format(index.rstrip("/"), name.split("[")[0])
    data = json_get(uri)
    return data


def get_versions_devpi(name, index):
    data = get_data_devpi(name, index)
    versions = []
    for raw_version, details in data["result"].items():
        version = _safe_version(raw_version)
        if version is not None:
            versions.append((version, raw_version))
    versions.sort()
    return tuple(v for (_, v) in versions)


def get_version_devpi(name, index):
    latest = get_versions_devpi(name, index)[-1]
    return latest


def get_index_url(default=DEFAULT_INDEX):
    args = [sys.executable] + "-m pip config get global.index-url".split()
    with open(os.devnull, "w") as shh:
        try:
            output = subprocess.check_output(args, stderr=shh)
        except subprocess.CalledProcessError:
            # this is not working for older versions pip < 10.0.0
            return default
        else:
            return output.decode().strip() or default


def guess_index_type(index_url):
    index_url = strip_suffixes(index_url, "+simple/", "+simple")
    try:
        request = Request(index_url, method="HEAD")
    except TypeError:
        # Python 2
        request = Request(index_url)
        request.get_method = lambda: "HEAD"
    response = urlopen(request)
    if response.code != 200:
        err = LudditeError("Unexpected response code {}".format(response.code))
        err.response_data = response.read()
        raise err
    for header_name in response.headers:
        if header_name.lower().startswith("x-devpi"):
            return "devpi"
    return "pypi"


def choose_worker(index_url):
    choices = {"pypi": get_versions_pypi, "devpi": get_versions_devpi}
    index_type = guess_index_type(index_url)
    func = choices.get(index_type, get_versions_pypi)
    return func


result_map = {
    # string template: color
    "noop": ("", None),
    "skip": ("? skipped a line: {stripped}", "magenta"),
    "pass": ("✔ {req.name} is up to date @ {latest}", "green"),
    "warn": ("! {req.name} {version} will be outdated soon (index has {latest})", "yellow"),
    "gone": ("! {req.name} {version} is not in the index {from_versions}", "yellow"),
    "free": ("! {req.name} appears unpinned?", "yellow"),
    "fail": ("✖ {req.name} {version} (index has {latest_non_pre})", "red"),
    "oops": ("💩 couldn't get {req.name}, sorry ({error})", "magenta"),
}


class RequirementsLine(object):
    def __init__(self, text, line_number=None):
        self.text = text
        self.line_number = line_number
        line, _sep, _comment = text.partition(" #")
        line = line.strip()
        self.stripped = "" if line.startswith("#") else line
        self.req = None
        self.version = None
        self.from_versions = ""
        if self.stripped:
            try:
                self.req = Requirement(self.stripped)
            except (InvalidRequirement, ValueError):
                pass
            else:
                if len(self.req.specifier) == 1:
                    spec = str(self.req.specifier)
                    if spec.startswith("=="):
                        _, self.version = spec.split("==", 1)
        self.error = None
        self.latest = None
        self.latest_non_pre = None

    def is_index(self):
        parts = self.stripped.split()
        for pre in "-i", "--index", "--index-url":
            if pre in parts:
                return parts[parts.index(pre) + 1]
        for pre in "--index=", "--index-url=":
            for part in parts:
                if part.startswith(pre):
                    return part[len(pre):]

    def process(self, worker, index=None):
        if not self.stripped or self.is_index():
            return "noop"
        if self.req is None:
            return "skip"
        if self.version is None:
            return "free"
        try:
            index_versions = worker(self.req.name, index=index)
        except Exception as e:
            self.error = e
            return "oops"
        else:
            versions_str = ", ".join(index_versions)
            self.from_versions = "(from versions: {})".format(versions_str)
        if self.version not in index_versions:
            return "gone"
        self.latest = index_versions[-1]
        self.latest_non_pre = max(
            index_versions, key=lambda v: (not Version(v).is_prerelease, Version(v))
        )
        if self.version == self.latest:
            return "pass"
        elif self.version == self.latest_non_pre:
            return "warn"
        else:
            return "fail"


class RequirementsFile(object):
    def __init__(self, fname):
        self.fname = fname
        self.lines = self.parse()
        self.width = max(len(line.text) for line in self.lines)

    def parse(self):
        with open(str(self.fname)) as f:
            return [RequirementsLine(text=t, line_number=n) for n, t in enumerate(f, 1)]

    @property
    def index(self):
        index_url = None
        index_urls = list(filter(None, [x.is_index() for x in self.lines]))
        if len(index_urls) > 1:
            raise MultipleIndicesError
        elif index_urls:
            [index_url] = index_urls
        return index_url


class Luddite(object):
    def __init__(self, fname=DEFAULT_FNAME, index=None):
        self.req_file = RequirementsFile(fname)
        self.index = index or self.req_file.index or get_index_url()
        self.get_versions = choose_worker(self.index)

    def run(self, n_threads=4):
        print("   using index: {}".format(self.index))
        print("---" + "{:-<77}".format(self.req_file.fname))
        with ThreadPoolExecutor(max_workers=n_threads) as executor:
            futures = [
                executor.submit(line.process, worker=self.get_versions, index=self.index)
                for line in self.req_file.lines
            ]
            for line, future in zip(self.req_file.lines, futures):
                result = future.result()
                template, color = result_map[result]
                line_out = line.text.rstrip("\r\n")
                if result == "noop":
                    print(line_out)
                    continue
                pad = self.req_file.width - len(line_out) + 2
                print(line_out, end=" " * pad)
                cprint(template.format(**vars(line)), color=color)


def main():
    version_str = "%(prog)s v{}".format(__version__)
    parser = argparse.ArgumentParser(description="Luddite checks for out-of-date package versions")
    parser.add_argument("fname", nargs="?", default=DEFAULT_FNAME, metavar="<requirements.txt>")
    parser.add_argument("-i", "--index-url", metavar="<url>")
    parser.add_argument("-n", "--n-threads", type=int, default=4, metavar="<N>")
    parser.add_argument("-v", "--version", action="version", version=version_str)
    args = parser.parse_args()
    luddite = Luddite(fname=args.fname, index=args.index_url)
    luddite.run(n_threads=args.n_threads)


if __name__ == "__main__":
    main()
