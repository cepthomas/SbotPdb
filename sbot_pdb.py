import sys
import socket
import pdb
import os
import datetime
import traceback
import sublime


#------------------------------------------------------------------------------
#------------------------- Configuration start --------------------------------
#------------------------------------------------------------------------------

# Where to log. Usually same as the client log. None indicates no logging.
LOG_FN = os.path.join(os.environ['APPDATA'], 'Sublime Text', 'Packages', 'User', '_Test', 'ppdb.log')

# TCP host.
HOST = '127.0.0.1'

# TCP port
PORT = 59120

# Client connect seconds after breakpoint() called 0=forever
CONNECT_TIMEOUT = 5

# Indicate internal message (not pdb)
MSG_IND = '!'

# Server provides ansi color (https://en.wikipedia.org/wiki/ANSI_escape_code)
USE_COLOR = True
CURRENT_LINE_COLOR = 93 # yellow
EXCEPTION_LINE_COLOR = 92 # green
STACK_LOCATION_COLOR = 96 # cyan
PROMPT_COLOR = 94 # blue
ERROR_COLOR = 91 # red

# Delimiter for socket message lines.
MDEL = '\n'

#------------------------------------------------------------------------------
#------------------------- Configuration end ----------------------------------
#------------------------------------------------------------------------------



#------------------------------------------------------------------------------
def plugin_loaded():
    '''Hello.'''
    write_log('DBG', 'sbot_pdb plugin_loaded()')


#------------------------------------------------------------------------------
class CommIf(object):
    '''
    Read/write interface to socket. Makes server socket look like a file.
    Also handles encoding, color, line endings etc.
    Catches exceptions for the purpose of logging only. They are re-raised.
    '''

    def __init__(self, conn):
        self.conn = conn
        self.last_cmd = None
        self.buff = ''

        # Return a file object associated with the socket. https://docs.python.org/3.8/library/socket.html
        fh = conn.makefile('rw')
        self.stream = fh
        # self.read = fh.read
        # self.readlines = fh.readlines
        self.close = fh.close
        self.flush = fh.flush
        self.fileno = fh.fileno

    @property
    def encoding(self):
        return self.stream.encoding

    def send(self, s):
        # self.do_debug(f'send(): {make_readable(s)}')
        self.conn.sendall(s.encode())

    def readline(self, size=1):
        del size
        '''Core pdb calls this to read from cli/client. Captures the last user command.'''
        try:
            s = self.stream.readline()
            self.last_cmd = s
            # self.do_debug(f'Received command: {make_readable(s)}')
            return self.last_cmd

        except (ConnectionError, socket.timeout) as e:
            self.do_debug(f'Disconnected: {type(e)}')
            raise

        except Exception as e:
            self.do_debug(f'CommIf.readline() other exception: {str(e)}')
            self.buff = ''
            raise

    def __iter__(self):
        return self.stream.__iter__()

    def write(self, line):
        '''Core pdb calls this to write to cli/client. This adjusts and sends to socket.'''
        try:
            # pdb writes lines piecemeal but we want full proper lines.
            # Easiest is to accumulate in a buffer until we see the prompt then slice and write.
            if '(Pdb)' in line:
                # settings = sublime.load_settings(sc.get_settings_fn())

                for s in self.buff.splitlines():
                    # sc.debug(f'DBG Send response: {s}')
                    color = None

                    if USE_COLOR:
                        if s.startswith('-> '): color = CURRENT_LINE_COLOR
                        elif ' ->' in s: color = CURRENT_LINE_COLOR
                        elif s.startswith('>> '): color = EXCEPTION_LINE_COLOR
                        elif '***' in s: color = ERROR_COLOR
                        elif 'Error:' in s: color = ERROR_COLOR
                        elif s.startswith('> '): color = STACK_LOCATION_COLOR

                    self.send(f'{s}{MDEL}' if color is None else f'\033[{color}m{s}\033[0m{MDEL}')

                self.writePrompt()

                # Reset buffer.
                self.buff = ''
            else:
                # Just collect.
                self.buff += line

        except (ConnectionError, socket.timeout) as e:
            self.do_debug(f'Disconnected: {type(e)}')
            raise

        except Exception as e:
            self.do_debug(f'CommIf.write() other exception: {str(e)}')
            self.buff = ''
            raise

    def do_debug(self, msg):
        '''Log only.'''
        write_log('DBG', msg)

    def writePrompt(self):
        s = f'\033[{PROMPT_COLOR}m(Pdb)\033[0m ' if USE_COLOR else '(Pdb)'
        self.send(s)


#------------------------------------------------------------------------------
class SbotPdb(pdb.Pdb):
    '''Run pdb behind a blocking tcp server.'''

    def __init__(self):
        '''Construction.'''
        try:
            self.sock = None
            self.commif = None
            self.active_instance = None

            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if CONNECT_TIMEOUT > 0:
                self.sock.settimeout(CONNECT_TIMEOUT)  # Seconds.
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
            self.sock.bind((HOST, PORT))
            self.do_info(f'Server started on {HOST}:{PORT} - waiting for connection.')

            # Blocks until client connect or timeout.
            self.sock.listen(1)
            conn, address = self.sock.accept()

            # Connected.
            self.do_info(f'Server accepted connection from {repr(address)}.')
            self.commif = CommIf(conn)
            super().__init__(completekey='tab', stdin=self.commif, stdout=self.commif)  # pyright: ignore
            SbotPdb.active_instance = self

        except (ConnectionError, socket.timeout) as e:
            self.do_info(f'Server connection timed out: {str(e)}')
            sublime.message_dialog('Server connection timed out, try again')
            self.do_quit()

        except Exception as e:
            # Other error handler.
            self.do_error(e)

    def breakpoint(self, frame):
        '''Starts the debugger.'''
        self.do_debug('breakpoint() entry')
        if self.commif is not None:
            try:
                # This blocks until user says done.
                super().set_trace(frame)

            except Exception as e:
                # TODO Code under test exceptions actually go to sys.excepthook so this doesn't do anything.
                self.do_error(e)

        self.do_debug('breakpoint() exit')
        self.do_quit()

    def do_quit(self, arg=None):
        '''Stopping debugging, clean up resources, exit application.'''
        self.do_info('Server quitting.')

        if self.commif is not None:
            self.commif.close()
            self.commif = None

        if self.sock is not None:
            self.sock.close()
            self.sock = None

        SbotPdb.active_instance = None

        try:
            super().do_quit(arg)
        except:
            pass
            # do_debug('do_quit() exit')

    def do_error(self, e):
        '''Log, tell, exit. All are considered fatal. Exit the application. User needs to restart debugger.'''
        write_log('ERR', str(e), e.__traceback__)
        sys.stdout.write(f'{MSG_IND} Server Error: {e}\n')
        sys.stdout.flush()
        self.do_quit()

    def do_info(self, msg):
        '''Log, tell.'''
        write_log('INF', msg)
        sys.stdout.write(f'{MSG_IND} {msg}\n')
        sys.stdout.flush()

    def do_debug(self, msg):
        '''Log only.'''
        write_log('DBG', msg)

    def make_readable(self, s):
        '''So we can see things like LF, CR, ESC in log.'''
        s = s.replace('\n', '_N').replace('\r', '_R').replace('\033', '_E')
        return s


#------------------------------------------------------------------------------
def write_log(level, msg, tb=None):
    '''Format a standard message with caller info and log it.'''
    if LOG_FN is None:
        return
    frame = sys._getframe(2)
    time_str = f'{str(datetime.datetime.now())}'[0:-3]
    with open(LOG_FN, 'a') as log:
        out_line = f'{time_str} {level} SRV {frame.f_lineno} {msg}'
        log.write(out_line + '\n')
        if tb is not None:
            log.write('\n'.join(traceback.format_tb(tb)) + '\n')
        log.flush()


#------------------------------------------------------------------------------
def breakpoint():
    '''Opens a remote PDB. See test_sbot_pdb.py.'''
    spdb = SbotPdb()
    spdb.breakpoint(sys._getframe().f_back)


write_log('DBG', 'sbot_pdb module loaded')
