import errno
import os
import re
import socket
import sys
import sublime
import sublime_plugin
from pdb import Pdb
# ?? from .SbotCommon import logger as log

# print(f'>>> (re)load {__name__}')

SBOTPDB_SETTINGS_FILE = "SbotPdb.sublime-settings"

COLOR_GRAY   = '\033[90m'
COLOR_RED    = '\033[91m'
COLOR_BLUE   = '\033[94m'
COLOR_YELLOW = '\033[33m'
COLOR_GREEN  = '\033[92m'
COLOR_RESET  = '\033[0m'


# TODO1 PRODUCTION flag disables all tracing, sets log level to >= info, disable allstpdb set_trace().

# run: "C:\Program Files\PuTTY\kitty-0.76.1.13.exe" -load "sbot_dev"
# TODO1 make it easier to run and Close+restart.
# https://the.earth.li/~sgtatham/putty/0.81/htmldoc/Chapter3.html#using-cmdline
# https://www.9bis.net/kitty/#!pages/CommandLine.md

# TODO1 Unhandled exception BdbQuit when q(uit) not c(ont). https://stackoverflow.com/a/34936583


# TODO1 Do not bind to a specific port. Instead, bind to port 0:
# The OS will then pick an available port for you. You can get the port that was chosen 
# using sock.getsockname()[1], and pass it on to the slaves so that they can connect back.

# Well-known ports—Ports in the range 0 to 1023 are assigned and controlled.
# Registered ports—Ports in the range 1024 to 49151 are not assigned or controlled,
#   but can be registered to prevent duplication.
# Dynamic ports—Ports in the range 49152 to 65535 are not assigned, controlled, or registered.
#   They are used for temporary or private ports. They are also known as private or non-reserved ports.
#   Clients should choose ephemeral port numbers from this range, but many systems do not.
#   ??? the regular ephemeral port range to use ports 32768 through 49151, and the alternate ephemeral port range to 49152 through 65535.



#-----------------------------------------------------------------------------------
class FileWrapper(object):
    '''Make socket look like a file. Also handles encoding and line endings.'''
    def __init__(self, conn):
        self.conn = conn
        fh = conn.makefile('rw')
        # Return a file object associated with the socket.
        # https://docs.python.org/3.8/library/socket.html
        self.stream = fh
        self.read = fh.read
        self.readline = fh.readline
        self.readlines = fh.readlines
        self.close = fh.close
        self.flush = fh.flush
        self.fileno = fh.fileno
        self._nl_rex=re.compile('\r?\n')  # Convert all to windows style.
        if hasattr(fh, 'encoding'):
            self._send = lambda data: conn.sendall(data.encode(fh.encoding))
        else:
            self._send = conn.sendall

    def __iter__(self):
        return self.stream.__iter__()

    @property
    def encoding(self):
        return self.stream.encoding

    def write(self, line):
        '''Write line to client. Fix any line endings.'''

        print('---1', line.replace('\r', 'CR').replace('\n', 'NL'))
        
        line = self._nl_rex.sub('\r\n', line)

        print('---2', line.replace('\r', 'CR').replace('\n', 'NL'))


        # Colorize?
        settings = sublime.load_settings(SBOTPDB_SETTINGS_FILE)
        if settings.get('use_ansi_color'):
            if '->' in line:
                line = f'{COLOR_YELLOW}{line}{COLOR_RESET}'
            elif '>>' in line:
                line = f'{COLOR_GREEN}{line}{COLOR_RESET}'
            elif '***' in line:
                line = f'{COLOR_RED}{line}{COLOR_RESET}'
            elif 'Error:' in line:
                line = f'{COLOR_RED}{line}{COLOR_RESET}'
            elif '>' in line:
                line = f'{COLOR_BLUE}{line}{COLOR_RESET}'
        self._send(line)

    def writelines(self, lines):
        '''Write all to client.'''
        for line in lines:
            self.write(line)


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
        # log.info(f'StPdb session open at {listen_socket.getsockname()}, waiting for connection.')
        listen_socket.listen(1)  # TODO1 need a timeout/retry mechanism.
        conn, address = listen_socket.accept()
        # log.info(f'StPdb accepted connection from {repr(address)}.')
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
        except IOError as exc:
            if exc.errno != errno.ECONNRESET:
                raise

    def do_quit(self, arg):
        self.__restore()
        return Pdb.do_quit(self, arg)

    # do_q = do_exit = do_quit  # TODO what?


#-----------------------------------------------------------------------------------
def set_trace():
    '''Opens a remote PDB using import stpdb; stpdb.set_trace() syntax.'''
    # print('--- 10')
    rdb = StPdb()
    # print('--- 20')
    rdb.set_trace(frame=sys._getframe().f_back)
    # print('--- 30')
