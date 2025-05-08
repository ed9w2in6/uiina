#!/usr/bin/env python3
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
from collections.abc import Iterable
from functools import partial
from importlib.metadata import version
from pathlib import Path
from platform import platform
from types import FrameType
from typing import BinaryIO


def __print_quick_help() -> None:
    print("Usage: uiina [-vh] [target ...]")


def __print_help() -> None:
    print(
        textwrap.dedent(
            """\
        Usage: uiina [option] [target ...]

            options:
                -h | --help           Show this help.
                -v | --verbose        Be verbose.
                -V | --version        Print version info then exit.

            target ...:
               The target(s) to be opened by uiina.
               They can be paths, or URLs.
               To read from stdin, give a single parameter "-" and nothing else.

            Inspect the python script for a more detailed explaination."""
        )
    )


def is_url(arg: str):
    "Returns True if ARG is an URL following mpv's logic, else False."
    parts = arg.split("://", 1)
    if len(parts) < 2:
        return False
    # protocol prefix has no special characters => it's an URL
    allowed_symbols = string.ascii_letters + string.digits + "_"
    prefix = parts[0]
    return all(map(lambda c: c in allowed_symbols, prefix))


def get_socket_path() -> Path:
    if os.name == "nt":
        return Path(
            r"\\.\pipe\uiina"
        )  # pyright: ignore[reportUnreachable] # unreachable on non-Windows only
    HOME = os.getenv(
        "HOME"
    )  # pyright: ignore[reportUnreachable] # unreachable on Windows only
    TMPDIR = os.getenv("TMPDIR")
    UIINA_SOCKET_DIR = os.getenv("UIINA_SOCKET_DIR")
    XDG_RUNTIME_DIR = os.getenv("XDG_RUNTIME_DIR")
    base_path = None
    for cand_dir in [
        UIINA_SOCKET_DIR,
        XDG_RUNTIME_DIR,
        (
            Path.home() if HOME is None else HOME
        ),  # uiina: our fork defaults HOME to Path.home(), which expands from `~`
        TMPDIR,
    ]:  # uiina: in this specific order, same as umpv
        if cand_dir is None:
            continue
        base_path = Path(cand_dir)
        break  # uiina: take the first match
    if base_path is None:
        raise Exception(
            """
            Could not determine a base directory for the socket.
            Ensure that one of the following environment variables is set:
            UIINA_SOCKET_DIR, XDG_RUNTIME_DIR, HOME or TMPDIR.
        """
        )
    return base_path / ".uiina"


def __print_signal_and_frame_then_exit_normally(
    signo: int, frame: FrameType | None, is_quiet: bool = False
):
    "Handler for signal.signal, private API, do not use this externally."
    if not is_quiet:
        print(f"\nReceived signal number {signo}, from frame {frame}.")
        print("Exiting normally.")
    sys.exit(0)


def __remove_socket_artefacts_at(socket_path: Path, is_quiet: bool = False):
    "Handler for atexit.register, private API, do not use this externally."
    if not is_quiet:
        print(f'Exiting uiina.\nRemoving file at "{socket_path}".')
    socket_path.unlink()
    if not is_quiet:
        print("Socket file removed.\nExit now.")


def create_new_iina_with(targets: Iterable[Path | str], socket_path: Path) -> None:
    iina = "iina" if os.name != "nt" else "iina.exe"
    iina_command = shlex.split(os.getenv("IINA", default=iina))
    stdin_opt = "--stdin" if len(list(targets)) == 0 else "--no-stdin"
    # append replaced `--` with `--mpv-` as per instructions of IINA.  See: `iina --help`.
    iina_command.extend(
        [
            "--mpv-profile=builtin-pseudo-gui",  # ref: https://github.com/mpv-player/mpv/blob/master/etc/builtin.conf
            f"--mpv-input-ipc-server={socket_path}",
            stdin_opt,
            "--keep-running",  # Need this to allow artefacts cleaning. See `iina --help`.
            "--",
        ]
    )  # <- uiina: Didn't change this one.
    iina_command.extend(
        (str(target) if isinstance(target, Path) else target) for target in targets
    )
    # subprocess.Popen(iina_command, start_new_session=True) # uiina: UPSTREAM umpv uses this
    _ = subprocess.check_call(
        iina_command
    )  # uuina: we DO want to wait for our clean up logic.


def send_targets_to_iina_with(
    targets: Iterable[Path | str], conn: socket.socket | BinaryIO
) -> None:
    try:
        send = conn.send if isinstance(conn, socket.socket) else conn.write
        for target in targets:
            # escape: \ \n "
            fname = (
                str(target)
                .replace("\\", r"\\")
                .replace('"', r"\"")
                .replace("\n", r"\n")
                if isinstance(target, Path)
                else target  # else target is an URL
            )
            _ = send((f'raw loadfile "{fname}" append-play\n').encode("utf-8"))
    except Exception:
        print("iina is terminating or the connection was lost.", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hvV", ["help", "verbose", "version"])
    except getopt.GetoptError as err:
        __print_quick_help()
        raise ValueError(f"Invalid options: {err}")

    is_quiet_option = True
    is_print_version_and_quit = False
    for opt, _ in opts:
        match opt:
            case "-h" | "--help":
                __print_help()
                return
            case "-v" | "--verbose":
                is_quiet_option = False
            case "-V" | "--version":
                is_print_version_and_quit = True
            case _:
                __print_quick_help()
                raise ValueError(f"Invalid Options: {opt}, SHOULD NOT REACH HERE")
    if is_print_version_and_quit:
        package_version = version("uiina")
        print(
            f"uiina {package_version}"
            + ("" if is_quiet_option else f"\nPython {sys.version}\n{platform()}")
        )
        return
    # make them absolute; also makes them safe against interpretation as options
    targets = (
        []
        if (len(args) == 1) and (args[0] == "-")
        else [arg if is_url(arg) else Path(arg).expanduser().absolute() for arg in args]
    )
    socket_path = get_socket_path()

    try:
        if os.name == "nt":
            with open(
                socket_path, "r+b", buffering=0
            ) as pipe:  # pyright: ignore[reportUnreachable] # unreachable on non-Windows only
                if not is_quiet_option:
                    print(f"Using existing pipe: {pipe}")
                send_targets_to_iina_with(targets, pipe)
        else:
            with socket.socket(
                socket.AF_UNIX
            ) as sock:  # pyright: ignore[reportUnreachable] # unreachable on Windows only
                sock.connect(
                    str(socket_path)
                )  # we rely on exception for new session creation.
                if not is_quiet_option:
                    print(f"Using existing socket: {sock}")
                send_targets_to_iina_with(targets, sock)
    except (
        FileNotFoundError,  # uiina: old logic uses (socket.error.errno == errno.ENOENT)
        ConnectionRefusedError,  # abandoned socket
    ):
        # create socket if we do NOT have one
        if not is_quiet_option:
            print("Creating new uiina session.")

        # Add handlers to clean artefacts ( the file at `SOCK_PATH` ) on exit and interrupted.
        # Note that adding them here means they are only added if we need to launch an IINA instance.
        sigint_handler = partial(
            __print_signal_and_frame_then_exit_normally, is_quiet=is_quiet_option
        )
        _ = signal.signal(signal.SIGINT, sigint_handler)
        remove_uiina_socket_artefacts = partial(
            __remove_socket_artefacts_at,
            socket_path=socket_path,
            is_quiet=is_quiet_option,
        )
        _ = atexit.register(remove_uiina_socket_artefacts)

        # actually launching an IINA instance
        create_new_iina_with(targets, socket_path)


if __name__ == "__main__":
    main()
