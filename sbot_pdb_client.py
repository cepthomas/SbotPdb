import sys
import os
import time
import socket
import threading
import queue
import datetime
import traceback
import json


# Human polling time in msec.
_loop_time = 50

# Server must reply to client in msec or it's considered dead.
_server_response_time = 200  # 100?

# Delimiter for socket message lines.
_comm_delim = '\n'

# Where to log.
_log_fn = '???'


#-----------------------------------------------------------------------------------
class PdbClient(object):

    def __init__(self):
        '''Construction.'''

        self.sock = None
        self.commif = None

        # User command read queue.
        self.cmdQ = queue.Queue()

        # Last command time. Non zero implies waiting for a response.
        self.sendts = 0

        # Server config. TODO1 get from cmd line too.
        self.host = '127.0.0.1'
        self.port = 59120
        self.ind = '!'

        self.log_debug(f'Constructing client')

    def go(self):
        '''Run the main loop.'''

        try:
            self.log_info(f'Starting client on {self.host}:{self.port}')
            run = True

            ##### Run user cli input in a thread.
            def worker():
                while run:
                    self.cmdQ.put_nowait(sys.stdin.readline().replace(_comm_delim, ''))
            threading.Thread(target=worker, daemon=True).start()

            ##### Forever loop #####
            while run:
                timed_out = False

                ##### Try (re)connecting? #####
                if self.commif is None:
                    # TCP socket client
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                    # Block with timeout.
                    self.sock.settimeout(float(_server_response_time) / 1000.0)

                    try:
                        self.sock.connect((self.host, self.port))

                        # Didn't fault so must be success.
                        self.commif = self.sock.makefile('rw')
                        self.log_info('Connected to server')

                    except TimeoutError:
                        # Server is not running or not listening right now. Normal operation.
                        timed_out = True
                        self.reset()

                    except ConnectionError as e:
                        # BrokenPipeError, ConnectionAbortedError, ConnectionRefusedError, ConnectionResetError.
                        # Ignore and retry later.
                        self.log_debug(f'ConnectionError: {type(e)}')
                        self.reset()

                    except Exception as e:
                        # Other unexpected error.
                        self.log_error(e)

                ##### Check for server not responding but still connected. #####
                if self.commif is not None and self.sendts > 0:
                    dur = self.get_msec() - self.sendts
                    if dur > _server_response_time:
                        self.log_info('Server not listening')
                        self.reset()

                ##### Anything to send? Check for user input. #####
                while not self.cmdQ.empty():
                    s = self.cmdQ.get()

                    if self.commif is not None:
                        # self.log_debug(f'Send command: {self.make_readable(s)}')
                        self.commif.write(s + _comm_delim)
                        self.commif.flush()
                        # Measure round trip for timeout.
                        self.sendts = self.get_msec()
                    else:
                        self.log_info('Execute command failed - not connected')

                ##### Get any server responses. #####
                if self.commif is not None:
                    try:
                        # Don't block.
                        self.sock.settimeout(0)  # pyright: ignore

                        done = False
                        while not done:
                            s = self.commif.read(100)

                            if s == '':
                                done = True
                            else:
                                sys.stdout.write(s)
                                sys.stdout.flush()
                                # self.log_debug(self.make_readable(s))
                                # Reset watchdog.
                                self.sendts = 0

                    except TimeoutError:
                        # Nothing to read.
                        timed_out = True
                        self.reset()

                    except ConnectionError:
                        # Server disconnected.
                        self.reset()

                    except Exception as e:
                        self.log_error(e)

                ##### If there was no timeout, delay a bit. #####
                slp = (float(_loop_time) / 1000.0) if timed_out else 0
                time.sleep(slp)

            self.log_debug('go() run ended')

        except KeyboardInterrupt:
            # Hard shutdown, ignore and quit.
            pass

        except Exception as e:
            # Other unexpected errors.
            self.log_error(e)

        self.quit(0)

    def get_msec(self):
        '''Get current msec.'''
        return time.perf_counter_ns() / 1000000

    def reset(self):
        '''Reset comms, resource management.'''

        if self.commif is not None:
            self.commif.close()
            self.commif = None

        if self.sock is not None:
            self.sock.close()
        #     self.sock = None

        # Reset watchdog.
        self.sendts = 0
        # Clear queue.
        while not self.cmdQ.empty():
            self.cmdQ.get()

    def log_error(self, e):
        '''Log function. All error() are considered fatal.'''
        self.write_log('ERR', str(e), e.__traceback__)
        sys.stdout.write(f'{self.ind} Error: {e}\n')
        sys.stdout.flush()
        self.quit(1)

    def log_info(self, msg):
        '''Log function.'''
        self.write_log('INF', msg)
        sys.stdout.write(f'{self.ind} {msg}\n')
        sys.stdout.flush()

    def log_debug(self, msg):
        '''Log function.'''
        self.write_log('DBG', msg)

    def write_log(self, level, msg, tb=None):
        '''Format a standard message with caller info and log it.'''

        frame = sys._getframe(2)
        fn = os.path.basename(frame.f_code.co_filename)
        line = frame.f_lineno
        time_str = f'{str(datetime.datetime.now())}'[0:-3]
        # with open(_log_fn, 'a') as log:
        #     out_line = f'{time_str} {level} {fn}:{line} {msg}'
        #     log.write(out_line + '\n')
        #     if tb is not None:
        #         # The traceback formatter is a bit ugly - clean it up.
        #         tblines = []
        #         for s in traceback.format_tb(tb):
        #             if len(s) > 0:
        #                 tblines.append(s[:-1])
        #         stb = '\n'.join(tblines)
        #         log.write(stb + '\n')
        #     log.flush()

    def quit(self, code):
        '''Clean up and go home.'''
        self.reset()
        if self.sock is not None:
            self.sock.close()
            self.sock = None
        sys.exit(code)

    def make_readable(self, s):
        '''So we can see things like LF, CR, ESC in log.'''
        return s.replace('\n', '_N').replace('\r', '_R').replace('\033', '_E')


#-----------------------------------------------------------------------------------
if __name__ == '__main__':

    client = PdbClient()
    client.go()
