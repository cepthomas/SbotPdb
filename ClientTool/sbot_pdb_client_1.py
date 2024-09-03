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

# TODO Partially completed port of VS tool. This is the version most like VS.

# Server config.
_host = "???"
_port = 0

# Client socket.
_client = None

# Inter-thread queue.
_cmdQ = queue.Queue



# Use telnet standard.
EOL = "\r\n"

# Human polling time in msec.
LOOP_TIME = 100

# Server must reply to commands in msec.
SERVER_LOSS_TIME = 100

# readonly Stopwatch _watch = new()
# Last command time.
_sendts = 0
# _trace_start_time = time.perf_counter_ns()

def get_msec():
    return time.perf_counter_ns() / 1000000




#-----------------------------------------------------------------------------------
class FileWrapper(object):
    '''Make client socket look like a file. Also handles encoding and line endings.'''
    def __init__(self, conn):
        self.conn = conn
        fh = conn.makefile('rw')
        # Return a file object associated with the socket. https://docs.python.org/3.8/library/socket.html
        self.stream = fh
        # self.read = fh.read
        self.readline = fh.readline
        # self.readlines = fh.readlines
        self.write = fh.write
        self.close = fh.close
        self.flush = fh.flush
        self.fileno = fh.fileno
        # Private stuff.
        self._nl_rex=re.compile(EOL)  # Convert all to standard line ending.
        self._send = lambda data: conn.sendall(data.encode(fh.encoding)) if hasattr(fh, 'encoding') else conn.sendall
        self._send_buff = ''

    # def readline(self, size=1):
    #     '''Capture the last user command.'''
    #     try:
    #         s = self.stream.readline()
    #         slog = s.replace('\n', '_N').replace('\r', '_R')
    #         sc.debug(f'Command:{slog}')
    #         self.last_cmd = s
    #         return self.last_cmd
    #     except Exception as e:
    #         return ''

    # readline seems to be the only read function used. Blow up if the others show up.
    # def read(self, size=1):
    #     s = self.stream.read(size)
    #     return s
    # def readlines(self, hint=1):
    #     s = self.stream.readlines(hint)
    #     return s

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
    try:
        # Console.Title = "Plugin Pdb Client"
        # Console.BufferHeight = 300
        # Console.BufferWidth = 120


        _get_config()

        sys.stdout.write(f"! Plugin Pdb Client started on {_host}:{_port}")
        sys.stdout.write(f"! Run your plugin code to debug")

        run = true

        # Run user cli input in a thread.
        def worker():
            while run:
                _cmdQ.put_nowait(sys.stdin.readline())
        threading.Thread(target=worker, daemon=True).start()






        # Main/forever loop.
        while (run):
            # Try re/connecting?
            if (_client is None):
                _reset()


                # Basic TCP socket client
                _client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                try:
                    _client.connect((_host, _port))
                except OSError as e:
                    # Ignore and retry later.
                    # Maybe should check code. https://learn.microsoft.com/en-us/windows/win32/winsock/windows-sockets-error-codes-2
                    _reset()
                except Exception as e:
                    # Other errors are considered fatal.
                    sys.stdout.write(f"! Fatal error:{e}")
                    _reset()
                    run = false

# _trace_start_time = time.perf_counter_ns()

            # Check for loss of server.
            if (_client is not None and _sendts > 0):
                dur = _get_msec() - _sendts
                if (dur - LOOP_TIME > SERVER_LOSS_TIME):
                    sys.stdout.write("! Server stopped")
                    _reset()


            #     sock.sendall(bytes(data + "\n", "utf-8")) # Send data
            #     received = str(sock.recv(1024), "utf-8") # Receive data synchronically

            # Echo anything from server to user.
            if (_client is not None and _client.Available > 0):
                var data = new byte[_client.Available]
                _client.GetStream().Read(data, 0, data.Length)
                string s = Encoding.ASCII.GetString(data, 0, data.Length)
                _trace(f"INN:{s}")
                _sendts = 0 # reset watchdog
                var rtdur = _get_msec() - _sendts
                Console.Write(f"{s}")

            # Check for user input.
            if (_cmdQ.TryDequeue(out var cliInput)):
                switch (cliInput):
                    case None: # should never happen
                        pass
                    case "x": # internal - exit client
                        run = false
                    case "hh": # internal - short usage
                        _short_usage()
                    default: # Send any other user input to server.
                        if (_client is not None):
                            _trace(f"OUT:{cliInput}")
                            # Measure round trip.
                            _sendts = _get_msec()
                            byte[] data = Encoding.ASCII.GetBytes(cliInput + EOL)
                            _client.GetStream().Write(data, 0, data.Length)
                            _client.GetStream().Flush()
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
    pkgspath = os.path.join(sc.expand_vars("$APPDATA%"), "Sublime Text", "Packages")

            if not os.path.isfile(sc.expand_vars(p)):
                sc.info(f'Invalid project file {p} - edit your settings')

     Path.Join(Environment.ExpandEnvironmentVariables("%APPDATA%"), "Sublime Text", "Packages")
    parse(Path.Join(pkgspath, "SbotPdb", "SbotPdb.sublime-settings"), true)
    parse(Path.Join(pkgspath, "User", "SbotPdb.sublime-settings"), false)

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

# Diagnostics.
def _trace(string msg):
    msg = msg.replace("\n", "_N").replace("\r", "_R")
    # File.AppendAllText(@"C:\Users\cepth\AppData\Roaming\Sublime Text\Packages\SbotPdb\Client\_trace.txt", msg + Environment.NewLine)

# Reset comms, resource management.
def _reset():
    global _client, _sendts
    _client.close()
    _client = None
    # Reset watchdog.
    _sendts = 0



if __name__ == "__main__":
    go()