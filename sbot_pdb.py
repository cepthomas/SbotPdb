import sys
import os
import socket
import sublime
import sublime_plugin
import pdb
from . import sbot_common as sc


SBOTPDB_SETTINGS_FILE = "SbotPdb.sublime-settings"

ANSI_RESET = '\033[0m'

# Standard delim.
EOL = '\n'
# EOL = '\r\n'


#-----------------------------------------------------------------------------------
def plugin_loaded():
    '''Called per plugin instance.'''
    sc.info(f'plugin_loaded() {__package__}')


#-----------------------------------------------------------------------------------
def make_readable(s):
    '''So we can see things like LF, CR, ESC in log.'''
    s = s.replace('\n', '_N').replace('\r', '_R').replace('\033', '_E')
    return s


#-----------------------------------------------------------------------------------
class CommIf(object):
    '''Read/write interface to socket. Makes server socket look like a file.
    Also handles encoding, colo, line endings etc.'''
    def __init__(self, conn):
        self.conn = conn
        self.last_cmd = None
        fh = conn.makefile('rw')
        # Return a file object associated with the socket. https://docs.python.org/3.8/library/socket.html
        self.stream = fh
        # readline seems to be the only read function used. Blow up if the others show up.
        # self.read = fh.read
        # self.readlines = fh.readlines
        self.close = fh.close
        self.flush = fh.flush
        self.fileno = fh.fileno
        # Private stuff.
        settings = sublime.load_settings(SBOTPDB_SETTINGS_FILE)
        self.ind = settings.get('internal_message_ind')
        self.use_color = settings.get('use_color')
        self.current_line_color = settings.get('current_line_color')
        self.exception_line_color = settings.get('exception_line_color')
        self.stack_location_color = settings.get('stack_location_color')
        self.prompt_color = settings.get('prompt_color')
        self.error_color = settings.get('error_color')
        # self._nl_rex = re.compile(EOL)  # TODO1? Convert all to standard line ending.
        self.send = lambda data: conn.sendall(data.encode(fh.encoding)) if hasattr(fh, 'encoding') else conn.sendall
        self.send_buff = ''

    def readline(self, size=1):
        '''Capture the last user command.'''
        try:
            s = self.stream.readline()
            self.last_cmd = s
            sc.debug(f'Receive command:{make_readable(s)}')
            return self.last_cmd
        except Exception:
            return ''

    def __iter__(self):
        return self.stream.__iter__()

    @property
    def encoding(self):
        return self.stream.encoding

    def write(self, line):
        '''Core pdb calls this to write to cli/client.'''
        # pdb writes lines piecemeal but we want full proper lines.
        # Easiest is to accumulate in a buffer until we see the prompt then slice and write.

        try:
            if '(Pdb)' in line:
                for s in self.send_buff.splitlines():
                    sc.debug(f'Send response:{s}')
                    color = None

                    if self.use_color:
                        if s.startswith('-> '): color = self.current_line_color
                        elif ' ->' in s: color = self.current_line_color
                        elif s.startswith('>> '): color = self.exception_line_color
                        elif '***' in s: color = self.error_color
                        elif 'Error:' in s: color = self.error_color
                        elif s.startswith('> '): color = self.stack_location_color

                    self.send(f'{s}{EOL}' if color is None else f'\033[{color}m{s}{ANSI_RESET}{EOL}')

                self.writePrompt()

                # Reset buffer.
                self.send_buff = ''
            else:
                # Just collect.
                self.send_buff += line

        except ConnectionError:  # BrokenPipeError, ConnectionAbortedError, ConnectionRefusedError, ConnectionResetError.
            # Ignore and retry later.
            sc.info('Lost connection during write.')
            # Reset buffer.
            self.send_buff = ''

        except Exception as e:
            raise

    def writeInfo(self, line):
        '''Write internal non-pdb info to client.'''
        sc.debug(f'Send info:{line}')
        self.send(f'{self.ind} {line}{EOL}')
        self.writePrompt()

    def writePrompt(self):
        sc.debug('Send prompt')
        s = f'\033[{self.prompt_color}m(Pdb) {ANSI_RESET}' if self.use_color else '(Pdb) '
        self.send(s)


#-----------------------------------------------------------------------------------
class SbotPdb(pdb.Pdb):
    '''Run pdb behind a blocking tcp server.'''

    def __init__(self):
        '''Construction.'''
        try:
            settings = sublime.load_settings(SBOTPDB_SETTINGS_FILE)
            host = settings.get('host')
            port = settings.get('port')
            client_connect_timeout = settings.get('client_connect_timeout')
            self.commif = None
            self.active_instance = None

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TODO does this need close()?
            if client_connect_timeout > 0:
                sock.settimeout(client_connect_timeout)  # Seconds.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
            sock.bind((host, port))
            sc.info(f'Socket open at {sock.getsockname()}, waiting for connection.')
            sock.listen(1)
            # Blocks until client connect or timeout.
            conn, address = sock.accept()

            # Connected.
            sc.info(f'Socket accepted connection from {repr(address)}.')
            self.commif = CommIf(conn)
            super().__init__(completekey='tab', stdin=self.commif, stdout=self.commif)
            SbotPdb.active_instance = self

        except TimeoutError:
            # Timeout waiting for a client to connect.
            sublime.message_dialog('Socket timed out.')
            sc.info('Socket timed out.')

        except Exception as e:
            self.do_error(e)

    def set_trace(self, frame):
        '''Starts the debugger.'''
        if self.commif is not None:
            try:
                # This blocks until client says done.
                super().set_trace(frame)

            except ConnectionError:
                # BrokenPipeError, ConnectionAbortedError, ConnectionRefusedError, ConnectionResetError.
                # Ignore and retry later.
                sc.info('Lost connection during debugging.')

            except Exception as e:
                # App exceptions actually go to sys.excepthook.
                self.do_error(e)

    def do_quit(self, arg=None):
        '''Stopping debugging, exit application.'''
        sc.info('Socket quitting.')
        if self.commif is not None:
            self.commif.close()
            self.commif = None
            SbotPdb.active_instance = None
            try:
                super().do_quit(arg)
            except Exception as e:
                self.do_error(e)

    def do_error(self, e):
        '''Error handler. All do_error() are fatal.'''
        print(f'>>> {type(e)} {e}')
        sc.error(f'{e}', e.__traceback__)
        if self.commif is not None:
            self.commif.writeInfo(f'Exception: {e}')
        self.do_quit()


#-----------------------------------------------------------------------------------
def set_trace():
    '''Opens a remote PDB using familiar syntax.'''
    spdb = SbotPdb()
    spdb.set_trace(sys._getframe().f_back)
