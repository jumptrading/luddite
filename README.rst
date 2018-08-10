luddite
=======

``luddite`` checks if pinned versions in your ``requirements.txt`` file
have newer versions in the package index. It's great to be near the
cutting edge, but not so close that you get cut! This tool will
help you keep things up to date manually.

There are many ways to specify dependencies in those files, but
luddite's parsing is pretty dumb and simple: we're only looking for
``package==version`` pins. It won't break on lines not fitting this
format, but you'll have to check them manually.

It works on Python 2 and Python 3.


Installation
------------

``pip install luddite``


Usage
-----

``luddite /path/to/requirements.txt``

If you are in the same directory as the ``requirements.txt`` file,
you can just type ``luddite``.

