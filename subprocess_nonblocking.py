# recipe-440554-1
# This is from http://code.activestate.com/recipes/440554/

# With modifications from Blake Oliver <oliver22213@me.com>

import os
import subprocess
import errno
import time
import sys

PIPE = subprocess.PIPE

if subprocess.mswindows:
    from win32file import ReadFile, WriteFile
    from win32pipe import PeekNamedPipe
    import msvcrt
else: # unix-like OS
    import select
    import fcntl

class Popen(subprocess.Popen):
    def recv(self, maxsize=None):
        return self._recv('stdout', maxsize)
    
    def recv_err(self, maxsize=None):
        """Return up to maxsize characters from stderr."""
        return self._recv('stderr', maxsize)

    def send_recv(self, input='', maxsize=None):
        """Send input, and receive up to maxsize chars from stdout and stderr. Return a tuple of the form (sent_chars, stdout_output, stderr_output)."""
        return self.send(input), self.recv(maxsize), self.recv_err(maxsize)

    def get_conn_maxsize(self, which, maxsize):
        """Return a sane number for the maxsize parameter."""
        if maxsize is None:
            maxsize = 1024
        elif maxsize < 1:
            maxsize = 1
        return getattr(self, which), maxsize
    
    def _close(self, which):
        getattr(self, which).close()
        setattr(self, which, None)
    
    if subprocess.mswindows:
        # define the send method for windows
        def send(self, input):
            """Send the given string to the subprocess's stdin stream. Return None if stdin was not directed to a pipe."""
            if not self.stdin:
                return None

            try:
                x = msvcrt.get_osfhandle(self.stdin.fileno())
                (errCode, written) = WriteFile(x, input)
            except ValueError:
                return self._close('stdin')
            except (subprocess.pywintypes.error, Exception), why:
                if why[0] in (109, errno.ESHUTDOWN):
                    return self._close('stdin')
                raise

            return written

        def _recv(self, which, maxsize):
            """Return up to maxsize chars from eithe r'stdin' or 'stderr'."""
            conn, maxsize = self.get_conn_maxsize(which, maxsize)
            if conn is None:
                return None
            
            try:
                x = msvcrt.get_osfhandle(conn.fileno())
                (read, nAvail, nMessage) = PeekNamedPipe(x, 0)
                if maxsize < nAvail:
                    nAvail = maxsize
                if nAvail > 0:
                    (errCode, read) = ReadFile(x, nAvail, None)
            except ValueError:
                return self._close(which)
            except (subprocess.pywintypes.error, Exception), why:
                if why[0] in (109, errno.ESHUTDOWN):
                    return self._close(which)
                raise
            
            if self.universal_newlines:
                read = self._translate_newlines(read)
            return read

    else: # define for unix-like OSs
        def send(self, input):
            if not self.stdin:
                return None

            if not select.select([], [self.stdin], [], 0)[1]:
                return 0

            try:
                written = os.write(self.stdin.fileno(), input)
            except OSError, why:
                if why[0] == errno.EPIPE: #broken pipe
                    return self._close('stdin')
                raise

            return written

        def _recv(self, which, maxsize):
            conn, maxsize = self.get_conn_maxsize(which, maxsize)
            if conn is None:
                return None
            
            flags = fcntl.fcntl(conn, fcntl.F_GETFL)
            if not conn.closed:
                fcntl.fcntl(conn, fcntl.F_SETFL, flags| os.O_NONBLOCK)
            
            try:
                if not select.select([conn], [], [], 0)[0]:
                    return ''
                
                r = conn.read(maxsize)
                if not r:
                    return self._close(which)
    
                if self.universal_newlines:
                    r = self._translate_newlines(r)
                return r
            finally:
                if not conn.closed:
                    fcntl.fcntl(conn, fcntl.F_SETFL, flags)


def recv_some(subproc, timeout=0.1, throw_exception=True, tries=5, stderr=False):
    if tries < 1:
        tries = 1
    x = time.time()+timeout
    data = [] # a list of chunks of data we've received from the pipe
    received = '' # string of characters we've received from the pipe
    pipe_receive = subproc.recv
    if stderr:
        pipe_receive = subproc.recv_err
    while time.time() < x or received:
        received = pipe_receive()
        if received == None: # if we didn't get any output
            if throw_exception:
                raise PipeClosedError
            else: # do not raise an exception
                break
        elif received: # we did get some data
            data.append(received)
        else: # we probably got an empty string, so the pipe is open but there's nothing new
            time.sleep(max((x-time.time())/tries, 0))
    # return all of the data concatenated 
    return ''.join(data)
    
def send_all(subproc, data):
    while len(data):
        sent = subproc.send(data)
        if sent is None:
            raise PipeClosedError
        data = buffer(data, sent)

if __name__ == '__main__':
    if sys.platform == 'win32':
        shell, commands, tail = ('cmd', ('dir /w', 'echo HELLO WORLD'), '\r\n')
    else:
        shell, commands, tail = ('sh', ('ls', 'echo HELLO WORLD'), '\n')
    
    a = Popen(shell, stdin=PIPE, stdout=PIPE)
    print recv_some(a),
    for cmd in commands:
        send_all(a, cmd + tail)
        print recv_some(a),
    send_all(a, 'exit' + tail)
    print recv_some(a, throw_exception=False)
    a.wait()
