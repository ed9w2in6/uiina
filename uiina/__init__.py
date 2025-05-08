"""
uiina
=====

Provides
--------
  1. A script that helps using a single instance of IINA using CLI, based on umpv.
     Run `uiina --help` for details.
  2. Exposes functions used by main() to interact with a single instance of IINA.

Details
-------
The script (uiina.py) allows the use of a single instance of IINA when launching through
the command line.  When starting playback with this script, it will try to reuse
an already running instance of IINA (but only if that was started with uiina).
Other IINA instances (not started by `uiina`) are ignored, and the script
doesn't know about them.

This only takes filenames, and URLs as arguments, or read from stdin.
The script will fail on custom options. If IINA is already running, the files passed to
`uiina` are appended to IINA's internal playlist. If a file does not exist or is
otherwise not playable, IINA will exit on error.

If IINA isn't running yet, this script will start IINA and let it control the
current terminal. It will not write output to stdout/stderr, unless `--verbose`
option is given.

Note: you can supply custom IINA path and options with the IINA environment
      variable. The environment variable will be split on whitespace, and the
      first item is used as path to IINA binary and the rest is passed as options
      _if_ the script starts IINA. If IINA is not started by the script (i.e. IINA
      is already running), this will be ignored.

Recent Changes
--------------
Edit (welkinSL):  [2025-05-04] - fix unhappy path (Invalid Options.) never do print_quick_help
                                 fix type signature mismatch warnings from pyright
                                 merge all upstream changes up to:
                                 https://github.com/mpv-player/mpv/commit/48f944d21b42b682bd12e522f5b24fd1a0e15058
Edit (welkinSL):  [2023-10-14] - rewrite
Edit (welkinSL):  I simply replaced all mentions of 'mpv' with 'IINA' in the instruction
                  below, and removed irrelavent sections since the mechanism and behaviour
                  should be almost identical.  The only differences should be that IINA
                  won't quit automatically after all files are played, and that mpv options
                  needs to be passed differently, see: `iina --help`.
"""

from importlib.metadata import version

from .uiina import create_new_iina_with  # pyright: ignore[reportUsend_targets_to_iina_with
from .uiina import get_socket_path  # pyright: ignore[reportUnusedImport]
from .uiina import is_url  # pyright: ignore[reportUnusedImport]
from .uiina import send_targets_to_iina_with  # pyright: ignore[reportUnusedImport]

__version__ = version("uiina")

# __metadata__ = metadata("uiina")
# __metadata_content_default__ = "Unknown"
# __version__ = __metadata__.get("Version", __metadata_content_default__)
