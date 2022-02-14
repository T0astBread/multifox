# This is a test module so shut up pylint.
# pylint: disable=missing-function-docstring
# pylint: disable=missing-module-docstring

import filecmp
import os
import random
import string
import threading
from concurrent import futures
from http import server

from click.testing import CliRunner

from multifox import multifox


def test_init_profile_firefox():
    runner = CliRunner()
    working_dir = os.getcwd()
    with runner.isolated_filesystem():
        result = runner.invoke(
            multifox,
            [
                "init-profile",
                os.path.join(working_dir, "testdata", "firefox-simple"),
                "firefox-simple-1",
            ],
        )
        assert result.exit_code == 0
        assert os.path.isfile(os.path.join("firefox-simple-1", "profile-config.json"))
        profile_dir = get_firefox_profile_dir("firefox-simple-1")
        assert os.path.isfile(os.path.join(profile_dir, "extensions.json"))
        assert os.path.isfile(os.path.join(profile_dir, "extension-preferences.json"))
        assert os.path.isfile(os.path.join(profile_dir, "prefs.js"))
        assert os.path.isfile(os.path.join(profile_dir, "addonStartup.json.lz4"))


def test_init_profile_tor_browser():
    runner = CliRunner()
    working_dir = os.getcwd()
    with runner.isolated_filesystem():
        result = runner.invoke(
            multifox,
            [
                "init-profile",
                os.path.join(working_dir, "testdata", "tor-browser-simple"),
                "tor-browser-simple-1",
            ],
        )
        assert result.exit_code == 0
        assert os.path.isfile(
            os.path.join("tor-browser-simple-1", "profile-config.json")
        )
        profile_dir = os.path.join(
            "tor-browser-simple-1",
            ".local",
            "share",
            "tor-browser",
            "TorBrowser",
            "Data",
            "Browser",
            "profile.default",
        )
        assert os.path.isdir(profile_dir)
        assert os.path.isfile(os.path.join(profile_dir, "extensions.json"))
        assert os.path.isfile(os.path.join(profile_dir, "extension-preferences.json"))
        assert os.path.isfile(os.path.join(profile_dir, "prefs.js"))
        assert os.path.isfile(os.path.join(profile_dir, "addonStartup.json.lz4"))


def test_launch_browser_firefox():
    runner = CliRunner()
    working_dir = os.getcwd()
    with futures.ThreadPoolExecutor() as executor:
        with runner.isolated_filesystem():
            result = runner.invoke(
                multifox,
                [
                    "init-profile",
                    os.path.join(working_dir, "testdata", "firefox-simple"),
                    "firefox-simple-1",
                ],
            )
            assert result.exit_code == 0
            url_token = random_string(16)
            listen = executor.submit(
                lambda: listen_for_http_connection(executor, url_token)
            )
            browser = executor.submit(
                lambda: runner.invoke(
                    multifox,
                    [
                        "launch-browser",
                        "firefox-simple-1",
                        "--",
                        "--devtools",
                        "--screenshot",
                        f"http://127.0.0.1:8080/{url_token}",
                    ],
                )
            )
            listen.result()
            result = browser.result()
            assert result.exit_code == 0
            assert os.path.isfile("screenshot.png")


def test_userjs_firefox():
    runner = CliRunner()
    working_dir = os.getcwd()
    with runner.isolated_filesystem():
        config_dir = os.path.join(working_dir, "testdata", "firefox-with-userjs")
        result = runner.invoke(
            multifox,
            [
                "init-profile",
                config_dir,
                "firefox-userjs-1",
            ],
        )
        assert result.exit_code == 0
        profile_dir = get_firefox_profile_dir("firefox-userjs-1")
        user_js = os.path.join(profile_dir, "user.js")
        assert os.path.isfile(user_js)
        assert filecmp.cmp(os.path.join(config_dir, "user.js"), user_js)

        config_dir = os.path.join(
            working_dir, "testdata", "firefox-with-different-userjs"
        )
        result = runner.invoke(
            multifox,
            [
                "apply-profile-config",
                config_dir,
                "firefox-userjs-1",
            ],
        )
        assert result.exit_code == 0
        assert os.path.isfile(user_js)
        assert filecmp.cmp(os.path.join(config_dir, "user.js"), user_js)


def get_firefox_profile_dir(profile_home_path):
    firefox_dir = os.path.join(profile_home_path, ".mozilla", "firefox")
    assert os.path.isfile(os.path.join(firefox_dir, "profiles.ini"))
    profile_dirs = [p for p in os.listdir(firefox_dir) if p.endswith(".default")]
    assert len(profile_dirs) == 1
    profile_dir = os.path.join(firefox_dir, profile_dirs[0])
    assert os.path.isdir(profile_dir)
    return profile_dir


def listen_for_http_connection(executor: futures.Executor, url_token: str):
    """
    listen_for_http_connection waits until a GET request is received
    for the given URL token.
    """
    event = threading.Event()

    class ConnectionTestRequestHandler(server.BaseHTTPRequestHandler):
        """
        ConnectionTestRequestHandler handles HTTP requests and
        reports when the expected request for a connection test
        arrives.
        """

        def respond(self, status: int, body: str):
            self.send_response(status)
            self.send_header("Content-type", "text/html;charset=utf-8")
            self.end_headers()
            self.wfile.write(bytes(body, encoding="utf-8"))
            self.wfile.flush()

        def do_GET(
            self,
        ):  # pylint: disable=invalid-name  # That name is required by `http.server`.
            if self.path == f"/{url_token}":
                self.respond(200, "<h1>It works</h1><p>Congrats!</p>")
                event.set()
            else:
                self.respond(404, "<h1>404</h1><p>Not the request I expected</p>")

    srv = server.HTTPServer(("127.0.0.1", 8080), ConnectionTestRequestHandler)
    serve = executor.submit(srv.serve_forever)
    event.wait()
    srv.shutdown()
    serve.result()


def random_string(length: int):
    """
    random_string generates a random string of characters of the
    given length.

    The generated string is NOT suitable for cryptographic purposes.
    """
    letters = string.ascii_lowercase
    # The generated string will not be used for cryptographic purposes.
    return "".join(random.choice(letters) for i in range(length))  # nosec
