#!/usr/bin/env python3

"""
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

import sys
import os
import getopt
import socket
import subprocess
import string
import textwrap
import errno
import signal
import atexit

def print_quick_help():
    print('Usage: uiina [-vh] [file ...]')

def print_help():
    print( textwrap.dedent("""\
        Usage: uiina [option] [file ...]

            option:
                -h(elp)           Show this help.
                -v(erbose)        Be verbose.

            file ...:
               The file(s) to be opened by uiina.

            Inspect the python script for a more detailed explaination."""))
    
is_quiet = True
try:
    opts, args = getopt.getopt(sys.argv[1:], "hv", ["help", "verbose"])
except getopt.GetoptError:
    print('ERROR: Invalid options.')
    print_quick_help()
    sys.exit(2)

for opt, arg in opts:
    if opt in ['-h', '--help']:
        print_help()
        sys.exit(0)
    elif opt in ['-v', '--verbose']:
        is_quiet = False
    else:
        assert False, "Invalid Options."
        print_quick_help()
    
files = args 

# this is the same method mpv uses to decide this
def is_url(filename):
    parts = filename.split("://", 1)
    if len(parts) < 2:
        return False
    # protocol prefix has no special characters => it's an URL
    allowed_symbols = string.ascii_letters + string.digits + '_'
    prefix = parts[0]
    return all(map(lambda c: c in allowed_symbols, prefix))

# make them absolute; also makes them safe against interpretation as options
def make_abs(filename):
    if not is_url(filename):
        return os.path.abspath(filename)
    return filename
files = (make_abs(f) for f in files)

def sigint_handler(signo, frame):
    is_quiet or print(f'\nReceived signal number { signo }, from frame { frame }.')
    is_quiet or print('Exiting normally.')
    sys.exit(0)

SOCK = os.path.join(os.getenv("HOME"), ".uiina_socket")

def remove_uiina_socket_artefacts():
    is_quiet or print(f'Exiting uiina.\nRemoving file at "{SOCK}".')
    os.unlink( SOCK )
    is_quiet or print('Socket file removed.\nExit now.')
    
sock = None
try:
    sock = socket.socket(socket.AF_UNIX)
    sock.connect(SOCK)
    is_quiet or print(f'Using socket: {sock}')
except socket.error as e:
    if e.errno == errno.ECONNREFUSED:
        sock = None
        pass  # abandoned socket
    elif e.errno == errno.ENOENT:
        sock = None
        pass # doesn't exist
    else:
        raise e

if sock:
    # Unhandled race condition: what if mpv is terminating right now?
    for f in files:
        # escape: \ \n "
        f = f.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")
        f = "\"" + f + "\""
        sock.send(("raw loadfile " + f + " append\n").encode("utf-8"))
else:
    # Let mpv recreate socket if it doesn't already exist.

    # Add handlers to clean artefacts ( the file at `SOCK` ) on exit and interrupted.
    # Note that adding them here means they are only added if we need to launch an IINA instance.
    atexit.register( remove_uiina_socket_artefacts )
    signal.signal(signal.SIGINT, sigint_handler)
    
    opts = (os.getenv("IINA") or "iina").split()
    
    # append replaced `--` with `--mpv-` as per instructions of iina-cli.  See: `iina --help`.
    opts.extend(["--mpv-no-terminal", "--mpv-force-window", "--mpv-input-ipc-server=" + SOCK,
                 "--no-stdin", "--keep-running", # Need this to allow artefacts cleaning. See `iina --help`.
                 "--"]) # <- Didn't change this one.
    opts.extend(files)

    subprocess.check_call(opts)
