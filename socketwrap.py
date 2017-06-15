# socketwrap
# Author: Blake Oliver <oliver22213@me.com>

from collections import deque
import click
import socket
import select
import subprocess
import time
import threading

# define the command and it's options and args

@click.command()
@click.option('--host', '--hostname', '-hn', default='127.0.0.1', show_default=True, help="""Interface the server should listen on.""")
@click.option('--port', '-p', default=3000, show_default=True, help="""Port the server should bind to.""")
@click.option('--enable-multiple-connections/--disable-multiple-connections', '-e/-E', help="""Allow multiple connections. Each one will be able to send to the subprocess as well as receive.""")
@click.argument('command', nargs=-1, required=True)
def socket_wrap(hostname, port, enable_multiple_connections, command):
	"""Capture a given command's standard input, standard output, and standard error (stdin, stdout, and stderr) streams and let clients send and receive data to it by connecting to this program.
Args:
command: The command this program should wrap (including any arguments).
	Any data received from it's stdout and stderr streams is buffered until the first client connects.
	If the command exits with a non-zero returncode before the server is initialized, it's stderr is printed to the console.
"""
	subproc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
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
		t = threading.Thread(target=poll_command_for_output, args=([subproc.stdout, subproc.stderr], command_output_queue, 0.1, stop_flag))
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
		while subproc.poll()==None:
			r, w, e = select.select(read, write, error, 3)
			for sock in r: # for each socket that has something to be read
				if sock == server_sock: # this is the server socket, accept the new connection
					con, addr = sock.accept()
					print("""{} has connected.""".format(addr))
					read.append(con)
					write.append(con)
					error.append(con)
					all_clients.append(con)
				else: # socket with something to read is not the server
					# large amounts of data might cause a lockup; it's unlikely though
					print("Using makefile")
					f = sock.makefile('r') # use makefile because data should be split by lines
					data = f.readline()
					f.close()
					print("File closed and data retrieved.")
					if data:
						try:
							subproc.stdin.write(data)
							subproc.stdin.flush()
						except IOError as e: # the subprocess has closed
							raise KeyboardInterrupt # trigger an exit
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
			if command_output_queue and w: # if there is at least one item in the queue and there is at least one socket to send it to
				print("Something in the queue to send.")
				i = command_output_queue.popleft()
				print("Sending {}.".format(i))
				for sock in w: # for every socket who's buffer is free for writing
					print("Sent.")
					sock.sendall(bytes(i))
				print("Finished sending")
			# handle sockets with errors
			print("Handling errors...")
			for sock in e:
				print("Socket {} has an error!".format(sock.getpeername()))
				if sock in rread:
					r.remove(sock)
				if sock in write:
					write.remove(sock)
				error.remove(sock)
				all_clients.remove(sock)
				sock.close()
		# main loop has exited
		for sock in all_clients:
			sock.send("Process has exited.")
		raise KeyboardInterrupt
	except Exception as e:
		if e is KeyboardInterrupt:
			print("Shutting down.")
		else:
			print("""Shutting down do to error: {}""".format(e))
		stop_flag.set()
		for sock in all_clients:
			sock.send("Shutting down. Goodbye.")
			sock.close()
		server_sock.close()
		subproc.kill()


def poll_command_for_output(handles, output_queue, poll_time, stop_flag):
	"""For every file-like object in the 'handles' list, check every poll_time to see if it has new output. If it does, add it as a string to output_queue."""
	while not stop_flag.is_set():
		for h in handles:
			buff = h.read(8192)
			if buff:
				output_queue.append(buff)
				print("Something added to output queue")
		time.sleep(poll_time)


if __name__ == '__main__':
	socket_wrap()