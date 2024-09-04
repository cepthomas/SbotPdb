import sys
import os
import time
import socket
import threading
import queue
import datetime
import traceback


# Standard delim.
EOL = '\r\n'

# Human polling time in msec.
LOOP_TIME = 50

# Server must reply to client in msec.
SERVER_RESPONSE_TIME = 100

# Some paths.
pkgspath = os.path.join(os.environ['APPDATA'], 'Sublime Text', 'Packages')
log_fn = os.path.join(pkgspath, 'User', '.SbotStore', 'sbot.log')


#-----------------------------------------------------------------------------------
class PdbClient(object):

    def __init__(self):
        '''Construction.'''

        # Client adapter.
        self.commif = None

        # CLI read queue.
        self.cmdQ = queue.Queue()

        # Last command time. Non zero implies waiting for a response.
        self.sendts = 0

        # Server config.
        self.host = None
        self.port = None
        self.get_config()

        if self.host is None or self.port is None:
            self.error('Invalid host or port')

    def go(self):
        '''Run the main loop.'''

        try:
            run = True
            self.tell(f'! Plugin Pdb Client started on {self.host}:{self.port}')
            self.tell(f'! Run your plugin code to debug')

            ##### Run user cli input in a thread.
            def worker():
                while run:
                    self.cmdQ.put_nowait(sys.stdin.readline())
            threading.Thread(target=worker, daemon=True).start()

            ##### Main/forever loop.
            while run:
                timed_out = False

                ##### Try (re)connecting?
                if self.commif is None:

                    # TCP socket client
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    # Don't block.
                    sock.settimeout(float(SERVER_RESPONSE_TIME) / 1000.0)

                    try:
                        sock.connect((self.host, self.port))

                        # Didn't fault so success.
                        self.info('Connected to server')
                        self.commif = sock.makefile('rw')  #, buffering=0)

                    except TimeoutError:
                        # Server is not listening right now. Normal operation.
                        timed_out = True
                        self.reset()

                    except ConnectionError:
                        # BrokenPipeError, ConnectionAbortedError, ConnectionRefusedError, ConnectionResetError.
                        # Ignore and retry later.
                        self.reset()

                    except Exception as e:
                        # Other errors are considered fatal.
                        self.error('Fatal error', e.__traceback__)
                        self.reset()
                        run = False

                ##### Do main work.

                # Check for server stopped but still connected.
                if self.commif is not None and self.sendts > 0:
                    dur = self._get_msec() - self.sendts
                    if dur > SERVER_RESPONSE_TIME:
                        self.tell('! Server stopped')
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
                            self.commif.write(s + '\n')
                            # Measure round trip.
                            self.sendts = self._get_msec()
                        else:
                            self.tell('! Not connected')

                # Get any server responses.
                if self.commif is not None:

                    try:
                        while True:
                            s = self.commif.readline()
                            self.tell(s)

                    except TimeoutError:
                        timed_out = True
                        self.reset()

                    except ConnectionError:
                        self.reset()

                    except Exception as e:
                        self.error('Fatal error', e.__traceback__)
                        self.reset()
                        run = False

                # If there was no timeout, delay a bit.
                if not timed_out:
                    time.sleep(float(LOOP_TIME) / 1000.0)

        except Exception as e:
            # An error escaped the controls in the main loop.
            self.error('Fatal error', e.__traceback__)
            self.reset()
            run = False

    def get_config(self):
        '''Hand parse config files. Json parser is too heavy for this app.'''
        # Overlay default and user options.
        self.parse_record(os.path.join(pkgspath, 'SbotPdb', 'SbotPdb.sublime-settings'), True)
        self.parse_record(os.path.join(pkgspath, 'User', 'SbotPdb.sublime-settings'), False)

    def parse_record(self, fn, required):
        '''Parse one config line.'''
        if (not required and not os.path.isfile(fn)):
            return

        with open(fn) as f:
            for s in f.readlines():
                s = s.strip()
                if s.startswith('\"'):
                    s = s.replace('\"', '').replace(',', '')
                    parts = s.split(':')
                    name = parts[0]
                    val = parts[1].strip()

                    if name == 'host':
                        self.host = val
                    elif name == 'port':
                        self.port = int(val)
                    else:
                        pass

    def succinct_usage(self):
        '''Simple help.'''
        self.tell('! Succinct help')
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
            self.tell(line)

    def get_msec(self):
        '''Get elapsed msec.'''
        return time.perf_counter_ns() / 1000000

    def reset(self):
        '''Reset comms, resource management.'''
        if self.commif is not None:
            self.commif.close()
            self.commif = None
        # Reset watchdog.
        self.sendts = 0
        # Clear queue.
        while not self.cmdQ.empty():
            self.cmdQ.get()

    def error(self, message, tb=None):
        '''Log function.'''
        self.write_log('ERR', message, tb)
        self.tell(f'! Error: {message} - see the log')

    def info(self, message):
        '''Log function.'''
        self.write_log('INF', message)
        # self.tell(f'! {message}')

    def debug(self, message):
        '''Log function.'''
        self.write_log('DBG', message)

    def write_log(self, level, message, tb=None):
        '''Format a standard message with caller info and log it.'''
        frame = sys._getframe(2)
        fn = os.path.basename(frame.f_code.co_filename)
        line = frame.f_lineno

        time_str = f'{str(datetime.datetime.now())}'[0:-3]

        with open(log_fn, 'a') as log:
            out_line = f'{time_str} {level} {fn}:{line} {message}'
            log.write(out_line + '\n')
            if tb is not None:
                # The traceback formatter is a bit ugly - clean it up.
                tblines = []
                for s in traceback.format_tb(tb):
                    if len(s) > 0:
                        tblines.append(s[:-1])
                stb = '\n'.join(tblines)
                log.write(stb + '\n')
            log.flush()

    def tell(self, msg):
        '''Tell the user.'''
        sys.stdout.write(msg + '\n')


#-----------------------------------------------------------------------------------
if __name__ == '__main__':
    client = PdbClient()
    client.go()
