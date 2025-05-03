#!/usr/bin/env python3

"""
Edit (welkinSL):  [2025-05-04] - fix unhappy path (Invalid Options.) never do print_quick_help
                                 fix type signature mismatch warnings from pyright
Edit (welkinSL):  [2023-10-14] - rewrite
Edit (welkinSL):  I simply replaced all mentions of 'mpv' with 'IINA' in the instruction
                  below, and removed irrelavent sections since the mechanism and behaviour
                  should be almost identical.  The only differences should be that IINA
                  won't quit automatically after all files are played, and that mpv options
                  needs to be passed differently, see: `iina --help`.

This script allows the use of a single instance of IINA when launching through
the command line.  When starting playback with this script, it will try to reuse
an already running instance of IINA (but only if that was started with uiina).
Other IINA instances (not started by `uiina`) are ignored, and the script
doesn't know about them.

This only takes filenames as arguments. Custom options can't be used; the script
interprets them as filenames. If IINA is already running, the files passed to
`uiina` are appended to IINA's internal playlist. If a file does not exist or is
otherwise not playable, IINA will skip the playlist entry when attempting to
play it (from the GUI perspective, it's silently ignored).

If IINA isn't running yet, this script will start IINA and let it control the
current terminal. It will not write output to stdout/stderr, because this
will typically just fill ~/.xsession-errors with garbage.  (Edit: Not sure if the
same reasoning applies in MacOS, but indeed NOTHING will be written to stdout/stderr.)

Note: you can supply custom IINA path and options with the IINA environment
      variable. The environment variable will be split on whitespace, and the
      first item is used as path to IINA binary and the rest is passed as options
      _if_ the script starts IINA. If IINA is not started by the script (i.e. IINA
      is already running), this will be ignored.
"""

import atexit
import errno
import getopt
import os
import signal
import socket
import string
import subprocess
import sys
import textwrap
from pathlib import Path


def print_quick_help():
    print("Usage: uiina [-vh] [file ...]")


def print_help():
    print(
        textwrap.dedent(
            """\
        Usage: uiina [option] [file ...]

            option:
                -h(elp)           Show this help.
                -v(erbose)        Be verbose.

            file ...:
               The file(s) to be opened by uiina.

            Inspect the python script for a more detailed explaination."""
        )
    )


# this is the same method mpv uses to decide this
def is_url(filename):
    parts = filename.split("://", 1)
    if len(parts) < 2:
        return False
    # protocol prefix has no special characters => it's an URL
    allowed_symbols = string.ascii_letters + string.digits + "_"
    prefix = parts[0]
    return all(map(lambda c: c in allowed_symbols, prefix))


try:
    opts, args = getopt.getopt(sys.argv[1:], "hv", ["help", "verbose"])
except getopt.GetoptError:
    print("ERROR: Invalid options.")
    print_quick_help()
    sys.exit(2)

IS_QUIET = True
for opt, arg in opts:
    if opt in ["-h", "--help"]:
        print_help()
        sys.exit(0)
    elif opt in ["-v", "--verbose"]:
        IS_QUIET = False
    else:
        print_quick_help()
        raise ValueError("Invalid Options.")

# make them absolute; also makes them safe against interpretation as options
files = (
    []
    if (len(args) == 1) and (args[0] == "-")
    else [
        filename if is_url(filename) else Path(filename).expanduser().absolute()
        for filename in args
    ]
)

XDG_RUNTIME_DIR = os.getenv("XDG_RUNTIME_DIR")
BASE_PATH = Path(XDG_RUNTIME_DIR) if XDG_RUNTIME_DIR is not None else Path.home()
SOCK_PATH = BASE_PATH / ".uiina_socket"
sock = None
try:
    sock = socket.socket(socket.AF_UNIX)
    sock.connect(SOCK_PATH.as_posix())
    if not IS_QUIET:
        print(f"Using socket: {sock}")
except socket.error as e:
    if e.errno == errno.ECONNREFUSED:
        sock = None
        pass  # abandoned socket
    elif e.errno == errno.ENOENT:
        sock = None
        pass  # doesn't exist
    else:
        raise e


def sigint_handler(signo, frame):
    if not IS_QUIET:
        print(f"\nReceived signal number { signo }, from frame { frame }.")
        print("Exiting normally.")
    sys.exit(0)


def remove_uiina_socket_artefacts():
    if not IS_QUIET:
        print(f'Exiting uiina.\nRemoving file at "{SOCK_PATH}".')
    SOCK_PATH.unlink()
    if not IS_QUIET:
        print("Socket file removed.\nExit now.")


if sock is None:
    # Let mpv recreate socket if it doesn't already exist.

    # Add handlers to clean artefacts ( the file at `SOCK_PATH` ) on exit and interrupted.
    # Note that adding them here means they are only added if we need to launch an IINA instance.
    atexit.register(remove_uiina_socket_artefacts)
    signal.signal(signal.SIGINT, sigint_handler)

    opts = (os.getenv("IINA") or "iina").split()

    stdin_opt = "--stdin" if len(files) == 0 else "--no-stdin"
    # append replaced `--` with `--mpv-` as per instructions of iina-cli.  See: `iina --help`.
    opts.extend(
        [
            "--mpv-no-terminal",
            "--mpv-force-window",
            "--mpv-input-ipc-server=" + SOCK_PATH.as_posix(),
            stdin_opt,
            "--keep-running",  # Need this to allow artefacts cleaning. See `iina --help`.
            "--",
        ]
    )  # <- Didn't change this one.
    opts.extend((f.as_posix() if isinstance(f, Path) else f) for f in files)

    subprocess.check_call(opts)
else:
    # Unhandled race condition: what if mpv is terminating right now?
    for f in files:
        # escape: \ \n "
        fname = (
            f.as_posix().replace("\\", r"\\").replace('"', r"\"").replace("\n", r"\n")
            if isinstance(f, Path)
            else f
        )
        sock.send((f'raw loadfile "{fname}" append\n').encode("utf-8"))
