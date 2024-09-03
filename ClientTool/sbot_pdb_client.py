import errno
import os
import re
import time
import socket
import sys
import traceback
import threading
import queue
from . import sbot_common as sc

# TODO Partially completed port of VS tool.

# // Lint this view
# { "keys": ["ctrl+k", "l"], "command": "sublime_linter_lint" },
# // Show all errors
# { "keys": ["ctrl+k", "a"], "command": "sublime_linter_panel_toggle" },
# // You can also trigger the line report with a keybinding:
# // { "keys": ["ctrl+k", "r"], "command": "sublime_linter_line_report" }
# // Goto next/previous errors from your position, in the current file:
# { "keys": ["ctrl+k", "n"], "command": "sublime_linter_goto_error",
#   "args": { "direction": "next" }
# },
# { "keys": ["ctrl+k", "p"], "command": "sublime_linter_goto_error",
#   "args": { "direction": "previous" }
# }


# Server config.
_host = "???"
_port = 0

# Client socket.
# sock = None

# Client adapter.
_commif = None

# Inter-thread queue.
_cmdQ = queue.Queue



# Use telnet standard.
EOL = "\r\n"

# Human polling time in msec.
LOOP_TIME = 100

# Server must reply to commands in msec.
SERVER_LOSS_TIME = 100

# Last command time. Implies waiting for a response.
_sendts = 0


def get_msec():
    return time.perf_counter_ns() / 1000000

# Example - Client:
# # Example Python program that reads from
# # a TCP/IP server socket through the associated file object retrieved # using socket.makefile() method
# import socket
# # Create a socket and connect to the server
# sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# sock.connect(("127.0.0.1",1236))
# # Obtain the file object associated with the socket
# fileObject = sock.makefile("rbw", buffering=0)
# # Read all that the server has sent
# while(True):
#     data = fileObject.readline()
#     if data == b'':
#         break
#     print(data.decode())


# socket.settimeout(value)
# Set a timeout on blocking socket operations. The value argument can be a nonnegative floating-point number expressing seconds, or None. If a non-zero value is given, subsequent socket operations will raise a timeout exception if the timeout period value has elapsed before the operation has completed. If zero is given, the socket is put in non-blocking mode. If None is given, the socket is put in blocking mode.
# A socket object can be in one of three modes: blocking, non-blocking, or timeout. Sockets are by default always created in blocking mode, but this can be changed by calling setdefaulttimeout().
# In blocking mode, operations block until complete or the system returns an error (such as connection timed out).
# In non-blocking mode, operations fail (with an error that is unfortunately system-dependent) if they cannot be completed immediately: functions from the select module can be used to know when and whether a socket is available for reading or writing.
# In timeout mode, operations fail if they cannot be completed within the timeout specified for the socket (they raise a timeout exception) or if the system returns an error.
# The connect() operation is also subject to the timeout setting, and in general it is recommended to call settimeout() before calling connect() or pass a timeout parameter to create_connection(). However, the system network stack may also return a connection timeout error of its own regardless of any Python socket timeout setting.





#-----------------------------------------------------------------------------------
class CommIf(object):
    '''Read/write interface to socket. Makes client socket look like a file.
    Also handles encoding and line endings.'''
    def __init__(self, conn):
        self.conn = conn
        fh = conn.makefile('rw')
        # Return a file object associated with the socket. https://docs.python.org/3.8/library/socket.html
        self.stream = fh
        # self.read = fh.read
        self.readline = fh.readline
        self.readlines = fh.readlines
        self.write = fh.write
        self.close = fh.close
        self.flush = fh.flush
        self.fileno = fh.fileno
        # Private stuff.
        self._nl_rex = re.compile(EOL)  # Convert all to standard line ending.
        self._send = lambda data: conn.sendall(data.encode(fh.encoding)) if hasattr(fh, 'encoding') else conn.sendall
        self._receive_buff = []

    def readline(self, size=1):
        '''Capture the last server response.'''
        try:
            s = self.stream.readline()
            self._receive_buff.append(s)            
            slog = s.replace('\n', '_N').replace('\r', '_R')
            sc.debug(f'Receive response:{slog}')
            return s
        except Exception as e:
            return ''

    # readline seems to be the only read function used. Blow up if the others show up.
    # def read(self, size=1):
    #     s = self.stream.read(size)
    #     return s
    def readlines(self, hint=1):
        sbuff = self._receive_buff
        self._receive_buff.clear()
        return sbuff

    def __iter__(self):
        return self.stream.__iter__()

    @property
    def encoding(self):
        return self.stream.encoding

    # def write(self, line):
    #     '''Write command to server.'''

    # def writelines(self, lines):
    #     '''Write all lines to client. Seems to be unused.'''
    #     for line in lines:
    #         self.write(line)

    # def writeInfo(self, line):
    #     '''Write internal non-pdb info to client.'''
    #     sc.debug(f'Info:{line}')
    #     self._send(f'! {line}{EOL}')
    #     self.writePrompt()

    # def writePrompt(self):
    #     sc.debug(f'Prompt')
    #     if self._col:
    #         self._send(f'{ANSI_BLUE}(Pdb) {ANSI_RESET}')
    #     else:  # As is
    #         self._send(f'(Pdb) ')






# Run the loop.
def go():
    global _commif, _sendts

    try:
        # Console.Title = "Plugin Pdb Client"
        # Console.BufferHeight = 300
        # Console.BufferWidth = 120


        _get_config()

        sys.stdout.write(f"! Plugin Pdb Client started on {_host}:{_port}")
        sys.stdout.write(f"! Run your plugin code to debug")

        run = True

        # Run user cli input in a thread.
        def worker():
            while run:
                _cmdQ.put_nowait(sys.stdin.readline())
        threading.Thread(target=worker, daemon=True).start()






        # Main/forever loop.
        while run:
            # Try re/connecting?
            if (_commif is None):
                _reset()


                # Basic TCP socket client
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                try:
                    sock.connect((_host, _port))

                    sc.info(f'Connected to server.')
                    self.commif = CommIf(sock)

                except OSError as e:
                    # Ignore and retry later. This is probably timeout.
                    # Maybe should check code. https://learn.microsoft.com/en-us/windows/win32/winsock/windows-sockets-error-codes-2
                    _reset()
                except Exception as e:
                    # Other errors are considered fatal.
                    sys.stdout.write(f"! Fatal error:{e}")
                    _reset()
                    run = False

            # Check for loss of server response.
            if (_commif is not None and _sendts > 0):
                dur = _get_msec() - _sendts
                if (dur - LOOP_TIME > SERVER_LOSS_TIME):
                    sys.stdout.write("! Server stopped")
                    _reset()


            # Echo anything from server to user.
            if _commif is not None and _commif._ _client.Available > 0):
                while not _cmdQ.empty():
                    _sendts = 0 # reset watchdog
                    s = _cmdQ.get()
                    stdout.write(s)
                    # s = s.replace('\n', '_N').replace('\r', '_R')
                    # sc.debug(f'Receive response:{s}')


            # Check for user input.
            if not _cmdQ.empty():
                if 



                switch (cliInput):
                    case None: # should never happen
                        pass
                    case "x": # internal - exit client
                        run = False
                    case "hh": # internal - short usage
                        _short_usage()
                    default: # Send any other user input to server.
                        if (_commif is not None):
                            _trace(f"OUT:{cliInput}")
                            # Measure round trip.
                            _sendts = _get_msec()
                            byte[] data = Encoding.ASCII.GetBytes(cliInput + EOL)
                            _commif.GetStream().Write(data, 0, data.Length)
                            _commif.GetStream().Flush()
                        else:
                            sys.stdout.write("! Can't execute - not connected")
                            _sendts = 0

            # Human time.
            System.Threading.Thread.Sleep(LOOP_TIME)
    catch (Exception e):
        # Errors are considered fatal.
        sys.stdout.write(f"1 Fatal error:{e}")
    finally:
        _watch.Stop()
        _reset()

# Hand parse config files. Json parser is too heavy for this app.
def _get_config():
    # Overlay default and user options.
    pkgspath = os.path.join(sc.expand_vars("$APPDATA"), "Sublime Text", "Packages")

    if not os.path.isfile(sc.expand_vars(p)):
        sc.info(f'Invalid project file {p} - edit your settings')

     os.path.join(Environment.ExpandEnvironmentVariables("%APPDATA%"), "Sublime Text", "Packages")
    parse(os.path.join(pkgspath, "SbotPdb", "SbotPdb.sublime-settings"), True)
    parse(os.path.join(pkgspath, "User", "SbotPdb.sublime-settings"), False)

    def parse(string fn, bool required):
        if (not required and not os.path.isfile(fn)):
            return

        for l in file.readlines(fn):
            s = l.trim()
            if s.startswith('\"'):
                s = s.replace("\"", "").replace(",", "")

                parts = s.split(':')
                name = parts[0]
                val = parts[1].trim()

                switch (name):
                    case "host":
                        _host = val
                    case "port":
                        _port = int.parse(val)
                    default:
                        //throw new ArgumentException(s)
                        pass

# Succinct usage.
def _short_usage():
    sys.stdout.write("! Succinct help")

    lines =
    [
        "h(elp)         [command]",
        "hh                                           What you see now.",
        "q(uit)                                       Don't do this.",
        "x(it)                                        Do this.",
        "run or restart [args ...]                    Restart the program with 'args'.",
        "s(tep)                                       Step into function.",
        "n(ext)                                       Step over function.",
        "r(eturn)                                     Step out of function.",
        "c(ont(inue))                                 Continue execution until breakpoint.",
        "unt(il)        [lineno]                      Continue until 'lineno' or next.",
        "j(ump)         lineno                        Jump to 'lineno'.",
        "w(here)                                      Print a stack trace. '>' is current frame.",
        "d(own)         [count]                       Move the current frame 'count' or 1 levels down/newer.",
        "u(p)           [count]                       Move the current frame 'count' or 1 levels up/older.",
        "b(reak)        [([fn:]line or func) [,cond]] Set break point with optional bool condition. If no args, display all breakpoints.",
        "tbreak         same as b                     Temporary breakpoint.",
        "cl(ear)        [filename:lineno or bpnumber] Clear breakpoint. Def is all with conf.",
        "l(ist)         [first[, last]]               Source code for the current file. Current is '->'. Exception line is '>>'.",
        "ll or longlist                               List all source code for the current function or frame.",
        "a(rgs)                                       Print the args of the current function.",
        "retval                                       Print the return value for the current function.",
        "p              expression                    Evaluate 'expression' in the current context.",
        "pp             expression                    Like p except pretty-printed.",
        "!              statement                     Execute one-line statement in the context of the current stack frame. Also handles 'global varname'.",
        "display        [expression]                  When exec stops, display the value of 'expression' or all if it changed. Note mutables may fool you.",
        "undisplay      [expression]                  Do not display 'expression' or all anymore.",
    ]

    for line in lines:
        sys.stdout.write(line)

# # Diagnostics.
# def _trace(string msg):
#     msg = msg.replace("\n", "_N").replace("\r", "_R")
#     # File.AppendAllText(@"C:\Users\cepth\AppData\Roaming\Sublime Text\Packages\SbotPdb\Client\_trace.txt", msg + Environment.NewLine)

# Reset comms, resource management.
def _reset():
    global _commif, _sendts
    _commif.close()
    _commif = None
    # Reset watchdog.
    _sendts = 0



if __name__ == "__main__":
    go()