import errno
import os
import re
import socket
import sys
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


# run: "C:\Program Files\PuTTY\kitty-0.76.1.13.exe" -load "sbot_dev"
# TODO1 make it easier to run and Close+restart.
# https://the.earth.li/~sgtatham/putty/0.81/htmldoc/Chapter3.html#using-cmdline
# https://www.9bis.net/kitty/#!pages/CommandLine.md

# TODO1 Unhandled exception BdbQuit when q(uit) not c(ont). https://stackoverflow.com/a/34936583

# TODO? Do not bind to a specific port. Instead, bind to port 0.



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


#-----------------------------------------------------------------------------------
class StPdb(Pdb):
    '''Run pdb behind a blocking telnet server.'''
    active_instance = None

    def __init__(self):
        settings = sublime.load_settings(SBOTPDB_SETTINGS_FILE)
        host = settings.get('host')
        port = settings.get('port')
        listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        listen_socket.bind((host, port))
        # print(f'StPdb session open at {listen_socket.getsockname()}, waiting for connection.')
        listen_socket.listen(1)  # TODO1 need a timeout/retry mechanism.
        conn, address = listen_socket.accept()
        # print(f'StPdb session accepted connection from {repr(address)}.')
        self.handle = FileWrapper(conn)
        Pdb.__init__(self, completekey='tab', stdin=self.handle, stdout=self.handle)
        StPdb.active_instance = self

    def __restore(self):
        self.handle.close()
        StPdb.active_instance = None

    def set_trace(self, frame=None):
        if frame is None:
            frame = sys._getframe().f_back
        try:
            Pdb.set_trace(self, frame)
        except IOError as e:
            if e.errno == errno.ECONNRESET:  # TODO1 retry?
                pass
            else:
                self.do_error(e.__traceback__)
        except Exception as e:
            self.do_error(e.__traceback__)

    def do_error(self, tb):
        self.handle.write_debug(f'Exception! {traceback.format_tb(tb)}')
        # frame = traceback.extract_tb(tb)[-1]
        # sublime.error_message(f'Exception at {frame.name}({frame.lineno})')
        self.do_quit()

    def do_quit(self, arg=None):
        self.__restore()
        return Pdb.do_quit(self, arg)

    # do_q = do_exit = do_quit  # TODO what?


#-----------------------------------------------------------------------------------
def set_trace():
    '''Opens a remote PDB using import stpdb; stpdb.set_trace() syntax.'''
    rdb = StPdb()
    rdb.set_trace(frame=sys._getframe().f_back)
