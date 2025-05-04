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
from collections.abc import Iterable
from functools import partial
from pathlib import Path
from types import FrameType

import atexit
import getopt
import os
import shlex
import signal
import socket
import string
import subprocess
import sys
import textwrap


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


def get_socket_path() -> Path:
    HOME = os.getenv("HOME")
    # uiina: our fork defaults HOME to Path.home(), which expands from `~`
    if HOME is None:
        HOME = Path.home()
    TMPDIR = os.getenv("TMPDIR")
    UIINA_SOCKET_DIR = os.getenv("UIINA_SOCKET_DIR")
    XDG_RUNTIME_DIR = os.getenv("XDG_RUNTIME_DIR")
    base_path = None
    for cand_dir in [
        UIINA_SOCKET_DIR,
        XDG_RUNTIME_DIR,
        HOME,
        TMPDIR,
    ]:  # in this specific order
        if cand_dir is None:
            continue
        base_path = Path(cand_dir)
        break  # uiina: take the first match
    if base_path is None:
        raise Exception(
            "Could not determine a base directory for the socket. "
            "Ensure that one of the following environment variables is set: "
            "UIINA_SOCKET_DIR, XDG_RUNTIME_DIR, HOME or TMPDIR."
        )
    return base_path / ".uiina_socket"


def print_signal_and_frame_then_exit_normally(
    signo: int, frame: FrameType | None, is_quiet: bool = False
):
    if not is_quiet:
        print(f"\nReceived signal number { signo }, from frame { frame }.")
        print("Exiting normally.")
    sys.exit(0)


def remove_uiina_socket_artefacts_at(socket_path: Path, is_quiet: bool = False):
    if not is_quiet:
        print(f'Exiting uiina.\nRemoving file at "{socket_path}".')
    socket_path.unlink()
    if not is_quiet:
        print("Socket file removed.\nExit now.")


def start_mpv(files: Iterable[Path | str], socket_path: Path) -> None:
    iina_command = shlex.split(os.getenv("IINA", "iina"))
    stdin_opt = "--stdin" if len(list(files)) == 0 else "--no-stdin"
    # append replaced `--` with `--mpv-` as per instructions of iina-cli.  See: `iina --help`.
    iina_command.extend(
        [
            "--mpv-no-terminal",
            "--mpv-force-window",
            f"--mpv-input-ipc-server={socket_path.as_posix()}",
            stdin_opt,
            "--keep-running",  # Need this to allow artefacts cleaning. See `iina --help`.
            "--",
        ]
    )  # <- uiina: Didn't change this one.
    iina_command.extend((f.as_posix() if isinstance(f, Path) else f) for f in files)
    subprocess.check_call(iina_command)


def send_files_to_mpv(sock: socket.socket, files: Iterable[Path | str]) -> None:
    try:
        for f in files:
            # escape: \ \n "
            fname = (
                f.as_posix()
                .replace("\\", r"\\")
                .replace('"', r"\"")
                .replace("\n", r"\n")
                if isinstance(f, Path)
                else f  # else f is an URL
            )
            sock.send((f'raw loadfile "{fname}" append\n').encode("utf-8"))
    except Exception:
        print("mpv is terminating or the connection was lost.", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hv", ["help", "verbose"])
    except getopt.GetoptError as err:
        print_quick_help()
        raise ValueError(f"Invalid options: {err}")

    IS_QUIET = True
    for opt, _ in opts:
        match opt:
            case "-h" | "--help":
                print_help()
                return
                # sys.exit(0)
            case "-v" | "--verbose":
                IS_QUIET = False
            case _:
                print_quick_help()
                raise ValueError(f"Invalid Options: {opt}, SHOULD NOT REACH HERE")

    # make them absolute; also makes them safe against interpretation as options
    files = (
        []
        if (len(args) == 1) and (args[0] == "-")
        else [
            filename if is_url(filename) else Path(filename).expanduser().absolute()
            for filename in args
        ]
    )
    socket_path = get_socket_path()

    try:
        with socket.socket(socket.AF_UNIX) as sock:
            sock.connect(socket_path.as_posix())
            if not IS_QUIET:
                print(f"Using socket: {sock}")
            send_files_to_mpv(sock, files)
    except (
        FileNotFoundError,  # uiina: old logic uses (socket.error.errno == errno.ENOENT)
        ConnectionRefusedError,  # abandoned socket
    ):
        # Let mpv recreate socket if it doesn't already exist.

        # Add handlers to clean artefacts ( the file at `SOCK_PATH` ) on exit and interrupted.
        # Note that adding them here means they are only added if we need to launch an IINA instance.
        sigint_handler = partial(
            print_signal_and_frame_then_exit_normally, is_quiet=IS_QUIET
        )
        signal.signal(signal.SIGINT, sigint_handler)
        remove_uiina_socket_artefacts = partial(
            remove_uiina_socket_artefacts_at, socket_path=socket_path, is_quiet=IS_QUIET
        )
        atexit.register(remove_uiina_socket_artefacts)

        # actually launching an IINA instance
        start_mpv(files, socket_path)


if __name__ == "__main__":
    main()
