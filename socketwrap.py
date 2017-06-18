# socketwrap
# Author: Blake Oliver <oliver22213@me.com>

from collections import deque
import click
import socket
import select
from subprocess import PIPE
import sys
import time
import threading
import subprocess_nonblocking

# define the command and it's options and args

@click.command()
@click.option('--host', '--hostname', '-hn', default='127.0.0.1', show_default=True, help="""Interface the server should listen on.""")
@click.option('--port', '-p', default=3000, show_default=True, help="""Port the server should bind to.""")
@click.option('--enable-multiple-connections/--disable-multiple-connections', '-e/-E', help="""Allow multiple connections. Each one will be able to send to the subprocess as well as receive.""")
@click.option('--loop-delay', '-l', default=0.025, show_default=True, help="""How long to sleep for at the end of each main loop iteration. This is meant to reduce CPU spiking of the main (socket-handling) thread. Setting this value too high introduces unnecessary lag when handling new data from clients or the wrapped command; setting it too low defeats the purpose. If it's set to 0, the delay is disabled.""")
@click.option('--thread-sleep-time', '-t', default=0.2, show_default=True, help="""How long the thread that reads output from the given command will sleep. Setting this to a lower value will make socketwrap notice and send output quicker, but will raise it's CPU usage""")
@click.argument('command', nargs=-1, required=True)
def socket_wrap(hostname, port, enable_multiple_connections, loop_delay, thread_sleep_time, command):
	"""Capture a given command's standard input, standard output, and standard error (stdin, stdout, and stderr) streams and let clients send and receive data to it by connecting to this program.
Args:
command: The command this program should wrap (including any arguments).
	Any data received from it's stdout and stderr streams is buffered until the first client connects.
	If the command exits with a non-zero returncode before the server is initialized, it's stderr is printed to the console.
"""
	command = list(command)
	subproc = subprocess_nonblocking.Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE, universal_newlines=True)
	time.sleep(0.2) # wait a bit before checking it's returncode
	r = subproc.poll()
	if r != None:
		if r == 0:
			print("The specified command has exited; not starting server.")
			return
		else: # non-zero returncode
			print("Subcommand exited with a non-zero returncode. It's standard error is:")
			print(subproc.stderr.read())
			return
	# the returncode was none, so the process is running
	# set up the server
	try:
		command_output_queue = deque() # queue of strings sent by the command we're wrapping
		stop_flag = threading.Event()
		t = threading.Thread(target=nonblocking_poll_command_for_output, args=(subproc, command_output_queue, thread_sleep_time, stop_flag))
		t.start()
		server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		server_sock.bind((hostname, port))
		server_sock.listen(2)
		print("Command started and server listening on {}:{}".format(hostname, port))
		read = [] # sockets that might have something we can read
		write = [] # sockets that might have free space in their buffer
		error = [] # sockets we need to handle errors for
		all_clients = []
		read.append(server_sock) # add the server socket so we can accept new connections
		running = True
		while running:
			r, w, e = select.select(read, write, error, 3)
			for sock in r: # for each socket that has something to be read
				if sock == server_sock: # this is the server socket, accept the new connection
					con, addr = sock.accept()
					print("""{} has connected.""".format(addr))
					if enable_multiple_connections or len(all_clients)==0:
						read.append(con)
						write.append(con)
						error.append(con)
						all_clients.append(con)
						con.sendall("Welcome!\nThis is socketwrap, running command {}\n".format(" ".join(command)))
					else: # there is already one client connected and enable_multiple_connections is false
						con.sendall("Sorry, allowing multiple connections is disabled.\nGoodbye.")
						con.close()
						print("{} has been disconnected because allowing multiple connections is disabled.".format(addr))
				else: # socket with something to read is not the server
					# large amounts of data might cause a lockup; it's unlikely though
					f = sock.makefile('r') # use makefile because data should be split by lines
					data = f.readline()
					f.close()
					if data:
						try:
							subproc.stdin.write(data)
							subproc.stdin.flush()
						except IOError as e: # the subprocess has closed
							running = False
					else: # a client sending an empty string indicates a disconnect
						read.remove(sock)
						print("{} has disconnected.".format(sock.getpeername()))
						if sock in write:
							write.remove(sock)
						if sock in error:
							error.remove(sock)
						all_clients.remove(sock)
						sock.close()
			# now check if the command has any output that needs to be sent to clients
			if len(command_output_queue)>0 and len(w)>0: # if there is at least one item in the queue and there is at least one socket to send it to
				i = command_output_queue.popleft()
				if i == False: # the reader thread has noticed the process has exited or closed it's pipes
					running = False
					raise KeyboardInterrupt # directly raise it to stop the boolean from being sent instead of waiting for the loop to complete
				for sock in w: # for every socket who's buffer is free for writing
					sock.sendall(i)
			# handle sockets with errors
			for sock in e:
				print("Socket {} has an error!".format(sock.getpeername()))
				if sock in rread:
					read.remove(sock)
				if sock in write:
					write.remove(sock)
				error.remove(sock)
				all_clients.remove(sock)
				sock.close()
				print("{} has been disconnected.".format(sock.getpeername()))
			if loop_delay>0:
				time.sleep(loop_delay)

		# main loop has exited
		raise KeyboardInterrupt
	except BaseException as e:
		if isinstance(e, KeyboardInterrupt):
			if subproc.poll() != None:
				reason = "Shutting down because command has exited.\n"
			else: # subprocess is still running
				reason = "Shutting down.\n"
			print(reason)
		else:
			reason = """Shutting down do to error:\n{}\n""".format(e)
		stop_flag.set()
		for sock in all_clients:
			sock.sendall(reason)
			sock.close()
		server_sock.close()
		del(read)
		del(write)
		del(error)
		del(server_sock)
		subproc.kill()


def nonblocking_poll_command_for_output(subproc, output_queue, poll_time, stop_flag):
	"""Check stdout and stderr every poll_time to see if it has new output. If it does, add it as a string to output_queue."""
	while not stop_flag.is_set():
		try:
			stdout_buff = subprocess_nonblocking.recv_some(subproc, timeout=poll_time, tries=1)
			stderr_buff = subprocess_nonblocking.recv_some(subproc, timeout=poll_time, tries=1, stderr=True)
			if stdout_buff:
				output_queue.append(stdout_buff)
			if stderr_buff:
				output_queue.append(stderr_buff)
		except subprocess_nonblocking.PipeClosedError as e:
			output_queue.append(False)
		time.sleep(poll_time)

def blocking_poll_command_for_output(handles, output_queue, poll_time, stop_flag):
	"""For every file-like object in the 'handles' list, check every poll_time to see if it has new output. If it does, add it as a string to output_queue."""
	while not stop_flag.is_set():
		for h in handles:
			try:
				# buff = h.read(8192)
				buff = h.readline()
				if buff:
					output_queue.append(buff)
			except IOError as e:
				pass
		time.sleep(poll_time)


if __name__ == '__main__':
	# socket_wrap()
	# handle click exceptions
	try:
		# return_code = socket_wrap.main(standalone_mode=False)
		context = socket_wrap.make_context(sys.argv[0], sys.argv[1:])
		with context:
			return_code = socket_wrap.invoke(context)
	except click.ClickException as e:
		return_code = getattr("e", "return_code", None) or 1
		e.show()
	sys.exit(return_code)
