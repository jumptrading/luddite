# coding: utf-8
from __future__ import unicode_literals

import json
import sys
from subprocess import CalledProcessError

import pytest

import luddite


def test_version_out_of_date(mocker):
    line = luddite.RequirementsLine("crappy==1.2.1")
    worker = mocker.Mock(return_value=("1.2.1", "1.2.3"))
    assert line.process(worker) == "fail"


def test_version_up_to_date(mocker):
    line = luddite.RequirementsLine("happy==1.2.3")
    worker = mocker.Mock(return_value=("1.2.1", "1.2.3"))
    assert line.process(worker) == "pass"


def test_version_nearly_out_of_date(mocker):
    line = luddite.RequirementsLine("prerelease==0.9")
    worker = mocker.Mock(return_value=("0.9", "1.0a1"))
    assert line.process(worker) == "warn"


def test_version_missing_from_index(mocker):
    line = luddite.RequirementsLine("where==1.2")
    worker = mocker.Mock(return_value=("1.1", "1.3"))
    assert line.process(worker) == "gone"


def test_empty_line(mocker):
    line = luddite.RequirementsLine("")
    worker = mocker.Mock(side_effect=Exception)
    assert line.process(worker) == "noop"


def test_comment_line(mocker):
    line = luddite.RequirementsLine("# py==1.2")
    worker = mocker.Mock(side_effect=Exception)
    assert line.process(worker) == "noop"


def test_index_line(mocker):
    line = luddite.RequirementsLine("--index-url https://pypi.org/simple")
    worker = mocker.Mock(side_effect=Exception)
    assert line.process(worker) == "noop"


def test_req_line_with_inline_comment(mocker):
    line = luddite.RequirementsLine("johnnydep==0.3  # what a cool app!")
    worker = mocker.Mock(return_value=("0.3",))
    assert line.process(worker) == "pass"


def test_extra_whitespace_ok(mocker):
    line = luddite.RequirementsLine("  johnnydep ==   0.3 \n")
    worker = mocker.Mock(return_value=("0.3",))
    assert line.process(worker) == "pass"


def test_line_not_proper_req(mocker):
    line = luddite.RequirementsLine("what the fuck")
    worker = mocker.Mock(side_effect=Exception)
    assert line.process(worker) == "skip"


def test_index_lookup_failed(mocker):
    line = luddite.RequirementsLine("notexist==1.0")
    worker = mocker.Mock(side_effect=Exception)
    assert line.process(worker) == "oops"


def test_package_unpinned(mocker):
    line = luddite.RequirementsLine("dist>=1.0")
    worker = mocker.Mock(side_effect=Exception)
    assert line.process(worker) == "free"


def test_multiple_constraints(mocker):
    line = luddite.RequirementsLine("dist>=1.5,<2.0")
    worker = mocker.Mock(side_effect=Exception)
    assert line.process(worker) == "free"


def test_parse_reqs_file(tmpdir):
    reqs = tmpdir.join("reqs.txt")
    reqs.write("abc==1.0\ndef==2.0")
    file = luddite.RequirementsFile(reqs)
    assert file.index is None
    assert [line.text for line in file.lines] == ["abc==1.0\n", "def==2.0"]


def test_parse_reqs_file_with_index(tmpdir):
    reqs = tmpdir.join("reqs.txt")
    reqs.write("--index http://myindex\nabc==1.0\ndef==2.0")
    file = luddite.RequirementsFile(reqs)
    assert file.index == "http://myindex"


def test_parse_reqs_file_with_two_indices(tmpdir):
    reqs = tmpdir.join("reqs.txt")
    reqs.write(
        "-i http://myindex\n"
        "--index-url=http://anotherindexwtf\n"
        "abc==1.0\n"
        "def==2.0"
    )
    file = luddite.RequirementsFile(reqs)
    with pytest.raises(luddite.MultipleIndicesError):
        file.index


def test_cprint(mocker, capsys):
    mocker.patch("luddite.sys.stdout.isatty", return_value=True)
    luddite.cprint("submarine", color="yellow")
    assert capsys.readouterr().out == "\x1b[33msubmarine\x1b[0m\n"


def test_get_charset(mocker):
    headers = mocker.MagicMock()
    headers.get_content_charset.return_value = "test"
    assert luddite.get_charset(headers) == "test"


@pytest.mark.skipif(sys.version_info >= (3,), reason="Python 2 only")
def test_get_charset_in_header_directly(mocker):
    headers = mocker.MagicMock()
    headers.get_content_charset.side_effect = AttributeError
    headers.getparam.return_value = "test"
    assert luddite.get_charset(headers) == "test"


@pytest.mark.skipif(sys.version_info >= (3,), reason="Python 2 only")
def test_get_charset_in_content_type(mocker):
    headers = mocker.MagicMock()
    headers.get_content_charset.side_effect = AttributeError
    headers.getparam.return_value = None
    headers.getheader.return_value = "application/json; charset=test"
    assert luddite.get_charset(headers) == "test"


def test_json_get_fails(mocker):
    mock_response = mocker.MagicMock()
    mock_response.code = 500
    mock_response.read.return_value = b"boom"
    mocker.patch("luddite.urlopen", return_value=mock_response)
    with pytest.raises(luddite.LudditeError, match="Unexpected response code 500") as cm:
        luddite.json_get("http://example.org")
    assert cm.value.response_data == b"boom"


def test_autodetect_index_url(mocker, tmpdir):
    reqs = tmpdir.join("requirements.txt")
    reqs.write("whatever")
    mocker.patch("luddite.subprocess.check_output", return_value=b"https://test-index/")
    mocker.patch("luddite.guess_index_type", return_value="pypi")
    lud = luddite.Luddite(reqs)
    assert lud.index == "https://test-index/"
    assert lud.get_versions is luddite.get_versions_pypi


def test_autodetect_index_url_failed(mocker, tmpdir, monkeypatch):
    monkeypatch.delenv("PIP_INDEX_URL", raising=False)
    monkeypatch.delenv("LUDDITE_DEFAULT_INDEX", raising=False)
    reqs = tmpdir.join("requirements.txt")
    reqs.write("whatever")
    mocker.patch("luddite.subprocess.check_output", side_effect=CalledProcessError(1, "wtf"))
    mocker.patch("luddite.guess_index_type", return_value="devpi")
    lud = luddite.Luddite(reqs)
    assert lud.index == luddite.DEFAULT_INDEX == "https://pypi.org/pypi/"
    assert lud.get_versions is luddite.get_versions_devpi


def test_guess_index_type_pypi(mocker):
    mock_response = mocker.MagicMock()
    mock_response.code = 200
    mock_response.headers = {}
    mocker.patch("luddite.urlopen", return_value=mock_response)
    assert luddite.guess_index_type("http://test-index/") == "pypi"


def test_guess_index_type_devpi(mocker):
    mock_response = mocker.MagicMock()
    mock_response.code = 200
    mock_response.headers = {
        "Content-type": "awesomesauce",
        "X-Devpi-Server-Version": "4.0.0\r\n",
    }
    mocker.patch("luddite.urlopen", return_value=mock_response)
    assert luddite.guess_index_type("http://test-index/") == "devpi"


def test_guess_index_fails(mocker):
    mock_response = mocker.MagicMock()
    mock_response.code = 403
    mocker.patch("luddite.urlopen", return_value=mock_response)
    with pytest.raises(luddite.LudditeError):
        luddite.guess_index_type("http://test-index/")


def test_get_version_devpi(mocker):
    mock_response = mocker.MagicMock()
    mock_response.code = 200
    mock_response.read.return_value = b'{"result": {"0.1": null, "0.2": null}}'
    mocker.patch("luddite.urlopen", return_value=mock_response)
    mocker.patch("luddite.get_charset", return_value="utf-8")
    v = luddite.get_version_devpi("dist", "http://myindex/+simple/")
    assert v == "0.2"


def test_get_version_pypi(mocker):
    mock_response = mocker.MagicMock()
    mock_response.code = 200
    mock_response.read.return_value = b'{"info": {"version": "0.3"}}'
    mocker.patch("luddite.urlopen", return_value=mock_response)
    mocker.patch("luddite.get_charset", return_value="utf-8")
    v = luddite.get_version_pypi("dist", "http://myindex/+simple/")
    assert v == "0.3"


def test_integration(tmpdir, capsys, mocker, monkeypatch):
    mock_response = mocker.MagicMock()
    mock_response.code = 200
    mock_response.headers.get_content_charset.return_value = "utf-8"
    releases = {
        "releases": {
            "1.0": [{"yanked": False}],
            "1.1": [{"yanked": False}],
            "1.4": [{"yanked": False}],
        }
    }
    mock_response.read.return_value = json.dumps(releases).encode()
    mocker.patch("luddite.urlopen", return_value=mock_response)
    mocker.patch("sys.argv", "luddite -i http://index-from-cmdline".split())

    tmpdir.join("requirements.txt").write(
        """
        --index-url http://index-from-file

        # dist0==1.0
        dist1==1.1
        dist2==1.2  # some comment

        dist3

        what the feck

        dist4==1.4
        distextra[x,y]==1.2.3
"""
    )

    monkeypatch.chdir(tmpdir)
    luddite.main()

    out, err = capsys.readouterr()
    assert err == ""
    assert (
        out
        == """   using index: http://index-from-cmdline
---requirements.txt-------------------------------------------------------------

        --index-url http://index-from-file

        # dist0==1.0
        dist1==1.1                           ✖ dist1 1.1 (index has 1.4)
        dist2==1.2  # some comment           ! dist2 1.2 is not in the index (from versions: 1.0, 1.1, 1.4)

        dist3                                ! dist3 appears unpinned?

        what the feck                        ? skipped a line: what the feck

        dist4==1.4                           ✔ dist4 is up to date @ 1.4
        distextra[x,y]==1.2.3                ! distextra 1.2.3 is not in the index (from versions: 1.0, 1.1, 1.4)
"""
    )


def test_yanked_versions_skipped(mocker):
    mock_response = mocker.MagicMock()
    mock_response.code = 200
    releases = {
        "releases": {
            "1.1": [{}],
            "1.4": [{"yanked": False}],
            "1.3": [{"yanked": True}],
            "1.2": [{"yanked": False}],
        }
    }
    mock_response.read.return_value = json.dumps(releases).encode()
    mocker.patch("luddite.urlopen", return_value=mock_response)
    mocker.patch("luddite.get_charset", return_value="utf-8")
    vs = luddite.get_versions_pypi("dist", "http://myindex/+simple/")
    assert vs == ("1.1", "1.2", "1.4")
