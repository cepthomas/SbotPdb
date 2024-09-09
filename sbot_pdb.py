import sys
import os
import socket
import subprocess as sp
import pdb
import sublime
import sublime_plugin
from . import sbot_common as sc


SBOTPDB_SETTINGS_FILE = "SbotPdb.sublime-settings"

# Delimiter for socket message lines.
COMM_DELIM = '\n'

# Delimiter for log lines.
LOG_EOL = '\n'


#-----------------------------------------------------------------------------------
def plugin_loaded():
    '''Called per plugin instance.'''
    sc.info(f'plugin_loaded() {__package__}')


#-----------------------------------------------------------------------------------
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
        # sc.debug(f'send(): {make_readable(s)}')
        self.conn.sendall(s.encode())

    def readline(self, size=1):
        '''Core pdb calls this to read from cli/client. Captures the last user command.'''
        try:
            s = self.stream.readline()
            self.last_cmd = s
            # sc.debug(f'Received command: {make_readable(s)}')
            return self.last_cmd

        except ConnectionError as e:
            sc.debug(f'Disconnected: {type(e)}')
            raise

        except Exception as e:
            sc.debug(f'CommIf.readline() other exception: {str(e)}')
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
                settings = sublime.load_settings(SBOTPDB_SETTINGS_FILE)

                for s in self.buff.splitlines():
                    # sc.debug(f'Send response: {s}')
                    color = None

                    if settings.get('use_color'):
                        if s.startswith('-> '): color = settings.get('current_line_color')
                        elif ' ->' in s: color = settings.get('current_line_color')
                        elif s.startswith('>> '): color = settings.get('exception_line_color')
                        elif '***' in s: color = settings.get('error_color')
                        elif 'Error:' in s: color = settings.get('error_color')
                        elif s.startswith('> '): color = settings.get('stack_location_color')

                    self.send(f'{s}{COMM_DELIM}' if color is None else f'\033[{color}m{s}\033[0m{COMM_DELIM}')

                self.writePrompt()

                # Reset buffer.
                self.buff = ''
            else:
                # Just collect.
                self.buff += line

        except ConnectionError as e:
            sc.debug(f'Disconnected: {type(e)}')
            raise

        except Exception as e:
            sc.debug(f'CommIf.write() other exception: {str(e)}')
            self.buff = ''
            raise

    def writeInfo(self, line):
        '''Write internal non-pdb info to client.'''
        settings = sublime.load_settings(SBOTPDB_SETTINGS_FILE)
        ind = settings.get('internal_message_ind')
        self.send(f'{ind} {line}{COMM_DELIM}')
        self.writePrompt()

    def writePrompt(self):
        settings = sublime.load_settings(SBOTPDB_SETTINGS_FILE)
        pc = settings.get('prompt_color')
        s = f'\033[{pc}m(Pdb)\033[0m ' if settings.get('use_color') else '(Pdb) '
        self.send(s)


#-----------------------------------------------------------------------------------
class SbotPdb(pdb.Pdb):
    '''Run pdb behind a blocking tcp server.'''

    def __init__(self):
        '''Construction.'''
        try:
            self.sock = None
            self.commif = None
            self.active_instance = None

            settings = sublime.load_settings(SBOTPDB_SETTINGS_FILE)
            host = settings.get('host')
            port = settings.get('port')
            client_connect_timeout = settings.get('client_connect_timeout')

            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if client_connect_timeout > 0:
                self.sock.settimeout(client_connect_timeout)  # Seconds.
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
            self.sock.bind((host, port))
            sc.info(f'Server started on {host}:{port} - waiting for connection.')

            # Blocks until client connect or timeout.
            self.sock.listen(1)
            conn, address = self.sock.accept()

            # Connected.
            sc.info(f'Server accepted connection from {repr(address)}.')
            self.commif = CommIf(conn)
            super().__init__(completekey='tab', stdin=self.commif, stdout=self.commif)
            SbotPdb.active_instance = self

        except Exception as e:
            self.do_error(e)

    def set_trace(self, frame):
        '''Starts the debugger.'''
        sc.debug('set_trace() entry')
        if self.commif is not None:
            try:
                # This blocks until user says done.
                super().set_trace(frame)

            except Exception as e:
                # App exceptions actually go to sys.excepthook so this doesn't really do anything.
                self.do_error(e)

        sc.debug('set_trace() exit')
        self.do_quit()

    def do_quit(self, arg=None):
        '''Stopping debugging, clean up resources, exit application.'''
        sc.info('Quitting.')

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
        sc.debug('do_quit() exit')

    def do_error(self, e):
        '''Error handler. All are considered fatal. Exit the application. User needs to restart debugger.'''
        # except ConnectionError: BrokenPipeError, ConnectionAbortedError, ConnectionRefusedError, ConnectionResetError.
        sc.error(f'{str(e)}', e.__traceback__)
        if self.commif is not None:
            self.commif.writeInfo(f'Server exception: {e}')
        self.do_quit()


#-----------------------------------------------------------------------------------
def make_readable(s):
    '''So we can see things like LF, CR, ESC in log.'''
    s = s.replace('\n', '_N').replace('\r', '_R').replace('\033', '_E')
    return s


#-----------------------------------------------------------------------------------
def set_trace():
    '''Opens a remote PDB using standard syntax. See test_sbot_pdb.py.'''
    spdb = SbotPdb()
    spdb.set_trace(sys._getframe().f_back)
