import sys
import socket
import pdb
import json
import os
import datetime
import sublime


# Delimiter for socket message lines.
_comm_delim = '\n'

# Configuration.
_config = None

# Where to log.
_log_fn = '???'


#-----------------------------------------------------------------------------------
def plugin_loaded():
    '''Read the config.'''
    global _config, _log_fn
    dir, _ = os.path.split(__file__)
    fn = os.path.join(dir, 'config.json')

    try:
        with open(fn, 'r') as fp:
            _config = json.load(fp)
            # print(_config)
            _log_fn = os.path.join(dir, 'sbot_pdb.log')
    except Exception as e:
        # No logging yet.
        sublime.message_dialog(f'Error reading config file {fn}: {e}')


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
        # log(f'DBG send(): {make_readable(s)}')
        self.conn.sendall(s.encode())

    def readline(self, size=1):
        del size
        '''Core pdb calls this to read from cli/client. Captures the last user command.'''
        try:
            s = self.stream.readline()
            self.last_cmd = s
            # log(f'DBG Received command: {make_readable(s)}')
            return self.last_cmd

        except (ConnectionError, socket.timeout) as e:
            log(f'DBG Disconnected: {type(e)}')
            raise

        except Exception as e:
            log(f'DBG CommIf.readline() other exception: {str(e)}')
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

                    if _config['use_color']:
                        if s.startswith('-> '): color = _config['current_line_color']
                        elif ' ->' in s: color = _config['current_line_color']
                        elif s.startswith('>> '): color = _config['exception_line_color']
                        elif '***' in s: color = _config['error_color']
                        elif 'Error:' in s: color = _config['error_color']
                        elif s.startswith('> '): color = _config['stack_location_color']

                    self.send(f'{s}{_comm_delim}' if color is None else f'\033[{color}m{s}\033[0m{_comm_delim}')

                self.writePrompt()

                # Reset buffer.
                self.buff = ''
            else:
                # Just collect.
                self.buff += line

        except (ConnectionError, socket.timeout) as e:
            log(f'Disconnected: {type(e)}')
            # sc.debug(f'Disconnected: {type(e)}')
            raise

        except Exception as e:
            log(f'CommIf.write() other exception: {str(e)}')
            # sc.debug(f'CommIf.write() other exception: {str(e)}')
            self.buff = ''
            raise

    def writeInfo(self, line):
        '''Write internal non-pdb info to client.'''
        # settings = sublime.load_settings(sc.get_settings_fn())
        ind = _config['internal_message_ind']
        self.send(f'{ind} {line}{_comm_delim}')
        self.writePrompt()

    def writePrompt(self):
        # settings = sublime.load_settings(sc.get_settings_fn())
        pc = _config['prompt_color']
        s = f'\033[{pc}m(Pdb)\033[0m ' if _config['use_color'] else '(Pdb)'
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

            # settings = sublime.load_settings(sc.get_settings_fn())
            host = _config['host']
            port = _config['port']
            client_connect_timeout = _config['client_connect_timeout']

            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if client_connect_timeout > 0:
                self.sock.settimeout(client_connect_timeout)  # Seconds.
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
            self.sock.bind((host, port))
            log(f'Server started on {host}:{port} - waiting for connection.')
            # sc.info(f'Server started on {host}:{port} - waiting for connection.')

            # Blocks until client connect or timeout.
            self.sock.listen(1)
            conn, address = self.sock.accept()

            # Connected.
            log(f'Server accepted connection from {repr(address)}.')
            # sc.info(f'Server accepted connection from {repr(address)}.')
            self.commif = CommIf(conn)
            super().__init__(completekey='tab', stdin=self.commif, stdout=self.commif)  # pyright: ignore
            SbotPdb.active_instance = self

        except (ConnectionError, socket.timeout) as e:
            log(f'Connection timed out: {str(e)}')
            # sc.info(f'Connection timed out: {str(e)}')
            sublime.message_dialog('Connection timed out, try again')
            self.do_quit()

        except Exception as e:
            # Other error handler. All are considered fatal. Exit the application. User needs to restart debugger.
            log(f'{type(e)} {str(e)}')
            # sc.error(f'{type(e)} {str(e)}', e.__traceback__)
            if self.commif is not None:
                self.commif.writeInfo(f'Server exception: {e}')
            self.do_quit()

    def breakpoint(self, frame):
        '''Starts the debugger.'''
        log('breakpoint() entry')
        # sc.debug('breakpoint() entry')
        if self.commif is not None:
            try:
                # This blocks until user says done.
                super().set_trace(frame)

            except Exception as e:
                # App exceptions actually go to sys.excepthook so this doesn't really do anything.
                log(f'{str(e)}')
                # sc.error(f'{str(e)}', e.__traceback__)

        log('breakpoint() exit')
        # sc.debug('breakpoint() exit')
        self.do_quit()

    def do_quit(self, arg=None):
        '''Stopping debugging, clean up resources, exit application.'''
        log('Quitting.')
        # sc.info('Quitting.')

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
        # log('DBG do_quit() exit')


#-----------------------------------------------------------------------------------
def log(msg, tell=True):
    with open(_log_fn, 'a') as log:
        time_str = f'{str(datetime.datetime.now())}'[0:-3]
        out_line = f'{time_str} {msg}'
        log.write(out_line + '\n')
        if tell:
            print(msg)


#-----------------------------------------------------------------------------------
def make_readable(s):
    '''So we can see things like LF, CR, ESC in log.'''
    s = s.replace('\n', '_N').replace('\r', '_R').replace('\033', '_E')
    return s


#-----------------------------------------------------------------------------------
def breakpoint():
    '''Opens a remote PDB. See test_sbot_pdb.py.'''
    spdb = SbotPdb()
    spdb.breakpoint(sys._getframe().f_back)
