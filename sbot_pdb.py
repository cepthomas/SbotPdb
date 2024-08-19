import errno
import os
import re
import socket
import sys
import traceback
import sublime
import sublime_plugin
import pdb
from . import sbot_common as sc


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


# TODO Unhandled exception BdbQuit when using q(uit) not c(ont). Maybe fix/patch. https://stackoverflow.com/a/34936583:


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
        '''Write debug info to client.'''
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
class SbotPdb(pdb.Pdb):
    '''Run pdb behind a blocking telnet server.'''

    def __init__(self):
        try:
            settings = sublime.load_settings(SBOTPDB_SETTINGS_FILE)
            host = settings.get('host')
            port = settings.get('port')
            timeout = settings.get('timeout')
            self.handle = None
            self.active_instance = None

            lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if timeout > 0:
                lsock.settimeout(timeout)  # Seconds.
            lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
            lsock.bind((host, port))
            sc.info(f'SbotPdb session open at {lsock.getsockname()}, waiting for connection.')
            lsock.listen(1)
            # blocks until timeout
            conn, address = lsock.accept()

            # Connected.
            sc.info(f'SbotPdb session accepted connection from {repr(address)}.')
            self.handle = FileWrapper(conn)
            super().__init__(completekey='tab', stdin=self.handle, stdout=self.handle)
            SbotPdb.active_instance = self
        except socket.timeout as e:
            # Timeout waiting for a client to connect.
            sublime.message_dialog('SbotPdb session timed out.')
            sc.info('SbotPdb session timed out.')
        except Exception as e:
            self.do_error(e)

    def set_trace(self, frame):
        # Check good instantiation.
        if self.handle is None:
            return

        try:
            super().set_trace(frame)  # This blocks until user says done.
        except IOError as e:
            if e.errno == errno.ECONNRESET:  # Client closed the connection.
                print(f'--- set_trace() IOError')  # TODO1 reopen/retry?
            else:
                self.do_error(e)
        except Exception as e:
            self.do_error(e)

    def do_error(self, e):
        tb = e.__traceback__
        s = '\n'.join(traceback.format_tb(tb))
        sc.error(f'{e}\n{s}')
        if self.handle is not None:
            self.handle.write_debug(f'Exception! {e}\n{s}')  # TODO1 test
        self.do_quit()

    def do_quit(self, arg=None):
        if self.handle is not None:
            self.handle.close()
            self.handle = None
            SbotPdb.active_instance = None
            try:
                res = super().do_quit(arg)
            except Exception as e:
                self.do_error(e)


#-----------------------------------------------------------------------------------
def set_trace():
    '''Opens a remote PDB using familiar syntax.'''
    spdb = SbotPdb()
    spdb.set_trace(sys._getframe().f_back)
