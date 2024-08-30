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


SBOTPDB_SETTINGS_FILE = "SbotPdb.sublime-settings"

ANSI_GRAY   = '\033[90m'
ANSI_RED    = '\033[91m'
ANSI_GREEN  = '\033[92m'
ANSI_YELLOW = '\033[93m'
ANSI_BLUE   = '\033[94m'
ANSI_PURPLE = '\033[95m'
ANSI_CYAN   = '\033[96m'
ANSI_RESET  = '\033[0m'

# Handshake delim.
EOL = '\r\n'


#-----------------------------------------------------------------------------------
def plugin_loaded():
    '''Called per plugin instance.'''
    sc.info(f'plugin_loaded() {__package__}')


#-----------------------------------------------------------------------------------
def plugin_unloaded():
    '''Ditto.'''
    pass


#-----------------------------------------------------------------------------------
class FileWrapper(object):
    '''Make socket look like a file. Also handles encoding and line endings.'''
    def __init__(self, conn):
        self.conn = conn
        self.last_cmd = None
        fh = conn.makefile('rw')
        # Return a file object associated with the socket. https://docs.python.org/3.8/library/socket.html
        self.stream = fh
        # self.read = fh.read
        # self.readline = fh.readline
        # self.readlines = fh.readlines
        self.close = fh.close
        self.flush = fh.flush
        self.fileno = fh.fileno
        # Private stuff.
        settings = sublime.load_settings(SBOTPDB_SETTINGS_FILE)
        self._col = settings.get('use_ansi_color')
        self._nl_rex=re.compile(EOL)  # Convert all to standard line ending.
        self._send = lambda data: conn.sendall(data.encode(fh.encoding)) if hasattr(fh, 'encoding') else conn.sendall
        self._send_buff = ''

    def read(self, size=1):
        s = self.stream.read(size)
        return s

    def readline(self, size=1):
        '''Seems to be the only read function used. Capture the last user command.'''
        try:
            s = self.stream.readline()
            slog = s.replace('\n', '_N').replace('\r', '_R')
            sc.debug(f'Command:{slog}')
            self.last_cmd = s
            return self.last_cmd
        except Exception as e:
            return ''

    def readlines(self, hint=1):
        s = self.stream.readlines(hint)
        return s

    def __iter__(self):
        return self.stream.__iter__()

    @property
    def encoding(self):
        return self.stream.encoding

    def write(self, line):
        '''Write pdb output line to client.'''
        # pdb writes lines piecemeal but we want full proper lines.
        # Easiest is to accumulate in a buffer until we see the prompt then slice and write.
        if '(Pdb)' in line:
            for l in self._send_buff.splitlines():
                sc.debug(f'Response:{l}')
                if self._col:  # TODO user configurable colors.
                    if l.startswith('-> '):
                        self._send(f'{ANSI_YELLOW}{l}{ANSI_RESET}{EOL}')
                    # elif '->\t' in l:
                    elif ' ->' in l:
                        self._send(f'{ANSI_YELLOW}{l}{ANSI_RESET}{EOL}')
                    elif l.startswith('>> '):
                        self._send(f'{ANSI_GREEN}{l}{ANSI_RESET}{EOL}')
                    elif '***' in l:
                        self._send(f'{ANSI_RED}{l}{ANSI_RESET}{EOL}')
                    elif 'Error:' in l:
                        self._send(f'{ANSI_RED}{l}{ANSI_RESET}{EOL}')
                    elif l.startswith('> '):
                        self._send(f'{ANSI_CYAN}{l}{ANSI_RESET}{EOL}')
                    else: # default
                        self._send(f'{l}{EOL}')
                else:  # As is
                    self._send(f'{l}{EOL}')

            self.writePrompt()
            # Reset.
            self._send_buff = ''
        else:
            # Just collect.
            self._send_buff += line

    def writelines(self, lines):
        '''Write all lines to client. Seems to be unused.'''
        for line in lines:
            self.write(line)

    def writeInfo(self, line):
        '''Write internal non-pdb info to client.'''
        sc.debug(f'Info:{line}')
        self._send(f'! {line}{EOL}')
        self.writePrompt()

    def writePrompt(self):
        sc.debug(f'Prompt')
        if self._col:
            self._send(f'{ANSI_BLUE}(Pdb) {ANSI_RESET}')
        else:  # As is
            self._send(f'(Pdb) ')


#-----------------------------------------------------------------------------------
class SbotPdb(pdb.Pdb):
    '''Run pdb behind a blocking tcp server.'''

    def __init__(self):
        '''Construction.'''
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
            sc.info(f'Session open at {lsock.getsockname()}, waiting for connection.')
            lsock.listen(1)
            # blocks until timeout
            conn, address = lsock.accept()

            # Connected.
            sc.info(f'Session accepted connection from {repr(address)}.')
            self.handle = FileWrapper(conn)
            super().__init__(completekey='tab', stdin=self.handle, stdout=self.handle)
            SbotPdb.active_instance = self
        except socket.timeout as e:
            # Timeout waiting for a client to connect.
            sublime.message_dialog('Session timed out.')
            sc.info('Session timed out.')
        except Exception as e:
            self.do_error(e)

    def set_trace(self, frame):
        '''Starts the debugger.'''
        if self.handle is not None:
            try:
                # This blocks until client says done.
                super().set_trace(frame)
            except IOError as e:
                if e.errno == errno.ECONNRESET:
                    sc.info('Client closed connection.')
                    self.do_quit()
                else:
                    self.do_error(e)
            except Exception as e:  # App exceptions actually go to sys.excepthook.
                self.do_error(e)

    def do_quit(self, arg=None):
        '''Stopping debugging.'''
        sc.info('Session quitting.')
        if self.handle is not None:
            self.handle.close()
            self.handle = None
            SbotPdb.active_instance = None
            try:
                res = super().do_quit(arg)
            except Exception as e:
                self.do_error(e)

    def do_error(self, e):
        '''Bad error handler.'''
        sc.error(f'{e}', e.__traceback__)
        if self.handle is not None:
            self.handle.writeInfo(f'Exception: {e}')
        self.do_quit()


#-----------------------------------------------------------------------------------
def set_trace():
    '''Opens a remote PDB using familiar syntax.'''
    spdb = SbotPdb()
    spdb.set_trace(sys._getframe().f_back)
