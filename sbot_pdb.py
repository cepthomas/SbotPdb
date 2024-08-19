import errno
import os
import re
import socket
import sys
import traceback
import sublime
import sublime_plugin
from pdb import Pdb

# print(f'>>> (re)load {__name__}')

SBOTPDB_SETTINGS_FILE = "SbotPdb.sublime-settings"

ANSI_GRAY   = '\033[90m'
ANSI_RED    = '\033[91m'
ANSI_GREEN  = '\033[92m'
ANSI_YELLOW = '\033[93m'
ANSI_BLUE   = '\033[94m'
ANSI_PURPLE = '\033[95m'
ANSI_CYAN   = '\033[96m'
ANSI_RESET  = '\033[0m'

# Standard telnet.
EOL = '\r\n'


# TODO Unhandled exception BdbQuit when using q(uit) not c(ont). Maybe fix/patch.
# https://stackoverflow.com/a/34936583:
# If you continue from the (pdb) prompt and allow your code to finish normally, I wouldn't expect
# output like the traceback you indicated, but if you quit pdb, with the quit command or ^D (EOF),
# a traceback like that occurs because there is nothing to catch the BdbQuit exception raised when
# the debugger quits. In bdb.py self.quitting gets set to True by the set_quit method (and by finally
# clauses in the various run methods). Dispatch methods called by trace_dispatch raise BdbQuit when
# self.quitting is True, and the typical except: clause for BdbQuit is a simple pass statement; pdb
# inherits all of that from gdb. In short, exception handling is used to disable the system trace function
# used by the debugger, when the debugger interaction finishes early.


#-----------------------------------------------------------------------------------
class FileWrapper(object):
    '''Make socket look like a file. Also handles encoding and line endings.'''
    def __init__(self, conn):
        self.conn = conn
        fh = conn.makefile('rw')
        # Return a file object associated with the socket. https://docs.python.org/3.8/library/socket.html
        self.stream = fh
        self.read = fh.read
        self.readline = fh.readline
        self.readlines = fh.readlines
        self.close = fh.close
        self.flush = fh.flush
        self.fileno = fh.fileno
        # Data.
        self._nl_rex=re.compile('\r\n')  # Convert all to telnet standard line ending.
        self._send = lambda data: conn.sendall(data.encode(fh.encoding)) if hasattr(fh, 'encoding') else conn.sendall
        self._buff = ''

    def __iter__(self):
        return self.stream.__iter__()

    @property
    def encoding(self):
        return self.stream.encoding

    def write(self, line):
        '''Write line to client.'''
        # pdb writes lines piecemeal but we want proper lines.
        # Easiest is to accumulate in a buffer until we see the prompt then slice and write.
        if '(Pdb)' in line:
            settings = sublime.load_settings(SBOTPDB_SETTINGS_FILE)
            col = settings.get('use_ansi_color')
#            self._send(f'=== 24 {self._buff}{EOL}')
            for l in self._buff.splitlines():
                if col:  # Colorize?
                    if '->' in l:
                        self._send(f'{ANSI_YELLOW}{l}{ANSI_RESET}{EOL}')
                    elif '>>' in l:
                        self._send(f'{ANSI_GREEN}{l}{ANSI_RESET}{EOL}')
                    elif '***' in l:
                        self._send(f'{ANSI_RED}{l}{ANSI_RESET}{EOL}')
                    elif 'Error:' in l:
                        self._send(f'{ANSI_RED}{l}{ANSI_RESET}{EOL}')
                    elif '>' in l:
                        self._send(f'{ANSI_CYAN}{l}{ANSI_RESET}{EOL}')
                    else:
                        self._send(f'{l}{EOL}')
                else:  # As is
                    self._send(f'{l}{EOL}')

            # Send prompt.
            if col:  # Colorize?
                self._send(f'{ANSI_BLUE}(Pdb) {ANSI_RESET}')
            else:  # As is
                self._send(f'(Pdb) ')
            # Reset.
            self._buff = ''
        else:
            # Just collect.
            self._buff += line

    def writelines(self, lines):
        '''Write all to client.'''
        for line in lines:
            self.write(line)

    def write_debug(self, line):
        '''Write internal debug info to client.'''
        settings = sublime.load_settings(SBOTPDB_SETTINGS_FILE)
        self._send(settings.get('debug'))
        if settings.get('debug'):
            self._send(f'DBG {line}{EOL}')
            # Send prompt.
            if settings.get('use_ansi_color'):  # Colorize?
                self._send(f'{ANSI_BLUE}(Pdb) {ANSI_RESET}')
            else:  # As is
                self._send(f'(Pdb) ')





# TODO1 harmonize print(), log(), write_debug(), ...

#-----------------------------------------------------------------------------------
class SbotPdb(Pdb):
    '''Run pdb behind a blocking telnet server.'''
    active_instance = None

    def __init__(self):
        settings = sublime.load_settings(SBOTPDB_SETTINGS_FILE)

        try:
            host = settings.get('host')
            port = settings.get('port')
            self.handle = None
            lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            lsock.settimeout(1)  # Seconds.
            lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
            lsock.bind((host, port))
            # print(f'SbotPdb session open at {lsock.getsockname()}, waiting for connection.')
            lsock.listen(1)
            conn, address = lsock.accept()
            # print(f'SbotPdb session accepted connection from {repr(address)}.')
            self.handle = FileWrapper(conn)
            Pdb.__init__(self, completekey='tab', stdin=self.handle, stdout=self.handle)
            SbotPdb.active_instance = self
        except socket.timeout as e:
            # Timeout waiting for a client to connect. TODO1 retry etc.
            pass
        except Exception as e:
            print('444', type(e))
            self.do_error(e)

    def set_trace(self, frame):
        # if frame is None:
        #     frame = sys._getframe().f_back

        try:
            # print('777', type(frame), dir(frame)) #777 <class 'frame'> ['__class__', '__delattr__', '__dir__', '__doc__', '__eq__', '__format__', '__ge__', '__getattribute__', '__gt__', '__hash__', '__init__', '__init_subclass__', '__le__', '__lt__', '__ne__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__sizeof__', '__str__', '__subclasshook__', 'clear', 'f_back', 'f_builtins', 'f_code', 'f_globals', 'f_lasti', 'f_lineno', 'f_locals', 'f_trace', 'f_trace_lines', 'f_trace_opcodes']
            # Pdb.set_trace(frame)  # This blocks until user says done.
            Pdb.set_trace(self, frame)  # This blocks until user says done.
            # super().set_trace(frame)  # This blocks until user says done.      # calls base class method

        except IOError as e:
            if e.errno == errno.ECONNRESET:  # Client closed the connection.
                print(f'111')
                pass  # TODO1 reopen/retry?
            else:
                print(f'122')
                self.do_error(e)
        except Exception as e:
            print(f'133', type(e))  # here AttributeError
            self.do_error(e)

    def do_error(self, e):
        tb = e.__traceback__
        s = '\n'.join(traceback.format_tb(tb))
        if self.handle is not None:
            self.handle.write_debug(f'222 Exception! {e}\n{s}')
        else:
            print(f'333 Exception! {e}\n{s}') #333 Exception! 'frame' object has no attribute 'reset'

        # frame = traceback.extract_tb(tb)[-1]
        # sublime.error_message(f'Exception at {frame.name}({frame.lineno})')
        self.do_quit()

    def do_quit(self, arg=None):
        if self.handle is not None:
            self.handle.close()

        SbotPdb.active_instance = None

        try:
            res = Pdb.do_quit(self, arg) # <<< exc
        except Exception as e:
            print('111', '\n'.join(traceback.format_tb(e.__traceback__)))


#-----------------------------------------------------------------------------------
def set_trace():
    '''Opens a remote PDB using familiar syntax.'''
    rdb = SbotPdb()
    rdb.set_trace(sys._getframe().f_back)
