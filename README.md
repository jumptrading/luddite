# luddite

[![actions](https://github.com/jumptrading/luddite/actions/workflows/tests.yml/badge.svg)](https://github.com/jumptrading/luddite/actions/workflows/tests.yml/)
[![codecov](https://codecov.io/gh/jumptrading/luddite/branch/master/graph/badge.svg)](https://codecov.io/gh/jumptrading/luddite)
[![pypi](https://img.shields.io/pypi/v/luddite.svg)](https://pypi.org/project/luddite/)
![pyversions](https://img.shields.io/pypi/pyversions/luddite.svg)

`luddite` checks if pinned versions in your `requirements.txt` file have
newer versions in the package index. It's great to be near the cutting
edge, but not so close that you get cut! This tool will help you keep
things up to date manually.

There are [many ways to specify requirements][1], but luddite's only
interested in one: we're looking for `package==version` pins. Parsing
won't break on lines that aren't fitting this format, but you'll have
to check them manually.

`luddite` works on both Python 2 and Python 3.

### Installation

```bash
pip install luddite
```

### Usage

```bash
luddite /path/to/requirements.txt
```

If you are in the same directory as the `requirements.txt` file, you can
just type `luddite`.

### Example output

![image](https://user-images.githubusercontent.com/6615374/43939075-feec4530-9c2c-11e8-9770-6f7f762c72e4.png)

[1]: https://pip.pypa.io/en/stable/reference/requirements-file-format/
