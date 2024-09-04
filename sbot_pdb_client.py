import sys
import os
import time
import socket
import threading
import queue
from . import sbot_common as sc


# Standard delim.
EOL = '\r\n'

# Human polling time in msec.
LOOP_TIME = 50

# Server must reply to client in msec.
SERVER_RESPONSE_TIME = 100


#-----------------------------------------------------------------------------------
class PdbClient(object):

    def __init__(self):
        '''Construction.'''

        # Client adapter.
        self.commif = None

        # CLI read queue.
        self.cmdQ = queue.Queue

        # Last command time. Non zero implies waiting for a response.
        self.sendts = 0

        # Server config.
        self.host = '???'
        self.port = 0
        self.get_config()

    def go(self):
        '''Run the loop.'''

        try:
            sys.stdout.writeline(f'! Plugin Pdb Client started on {self.host}:{self.port}')
            sys.stdout.writeline('! Run your plugin code to debug')

            ##### Run user cli input in a thread.
            def worker():
                while run:
                    self.cmdQ.put_nowait(sys.stdin.readline())
            threading.Thread(target=worker, daemon=True).start()

            ##### Main/forever loop.
            run = True
            while run:
                timedout = False

                ##### Try (re)connecting?
                if self.commif is None:

                    # TCP socket client
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    # Don't block.
                    sock.settimeout(float(SERVER_RESPONSE_TIME) / 1000.0)

                    try:
                        sock.connect((self.host, self.port))

                        # Success.
                        sc.info('Connected to server.')
                        self.commif = sock.makefile('rw', buffering=0)

                    except TimeoutError:
                        # Server is not listening right now. Normal operation.
                        timedout = True
                        self.reset()

                    except ConnectionError:
                        # BrokenPipeError, ConnectionAbortedError, ConnectionRefusedError, ConnectionResetError.
                        # Ignore and retry later.
                        self.reset()

                    except Exception as e:
                        # Other errors are considered fatal.
                        sys.stdout.writeline(f'! Fatal error:{e}')
                        self.reset()
                        run = False

                ##### Do main work.

                # Check for server stopped but still connected.
                if self.commif is not None and self.sendts > 0:
                    dur = self._get_msec() - self.sendts
                    if dur > SERVER_RESPONSE_TIME:
                        sys.stdout.writeline('! Server stopped')
                        self.reset()

                # Anything to send? Check for user input.
                while not self.cmdQ.empty():
                    s = self.cmdQ.get()
                    if s == 'x':
                        # internal - exit client
                        run = False
                    elif s == 'hh':
                        # internal - short usage
                        self.succinct_usage()
                    else:
                        if self.commif is not None:
                            # Send any other user input to server.
                            self.commif.writeline(s)
                            # Measure round trip.
                            self.sendts = self._get_msec()
                        else:
                            sys.stdout.writeline('! Not connected')

                # Get any server responses.
                if self.commif is not None:

                    try:
                        while True:
                            s = self.commif.readline()
                            sys.stdout.writeline(s)

                    except TimeoutError:
                        timedout = True
                        self.reset()

                    except ConnectionError:
                        self.reset()

                    except Exception as e:
                        sys.stdout.writeline(f'! Fatal error:{e}')
                        self.reset()
                        run = False

                # If there was no timeout, delay a bit.
                if not timedout:
                    time.sleep(float(LOOP_TIME) / 1000.0)

        except Exception as e:
            # An error escaped the controls in the main loop.
            sys.stdout.writeline(f'! Fatal error:{e}')
            sc.error()
            self.reset()
            run = False

    def get_config(self):
        '''Hand parse config files. Json parser is too heavy for this app.'''

        # Overlay default and user options.
        pkgspath = os.path.join(sc.expand_vars('$APPDATA'), 'Sublime Text', 'Packages')

        self.parse(os.path.join(pkgspath, 'SbotPdb', 'SbotPdb.sublime-settings'), True)
        self.parse(os.path.join(pkgspath, 'User', 'SbotPdb.sublime-settings'), False)

    def parse(self, fn, required):
        if (not required and not os.path.isfile(fn)):
            return

        for s in list(fn):
            s = s.trim()
            if s.startswith('\"'):
                s = s.replace('\"', '').replace(',', '')

                parts = s.split(':')
                name = parts[0]
                val = parts[1].trim()

                if name == 'host':
                    self.host = val
                elif name == 'port':
                    self.port = int.parse(val)
                else:
                    pass

    def succinct_usage(self):
        sys.stdout.writeline('! Succinct help')
        lines = [
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
            sys.stdout.writeline(line)

    def get_msec(self):
        return time.perf_counter_ns() / 1000000

    def reset(self):
        '''Reset comms, resource management.'''
        if self.commif is not None:
            self.commif.close()
            self.commif = None
        # Reset watchdog.
        self.sendts = 0
        self.cmdQ.clear()


#-----------------------------------------------------------------------------------
if __name__ == '__main__':
    client = PdbClient
    client.go()
