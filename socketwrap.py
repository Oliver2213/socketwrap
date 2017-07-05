# -*- coding: utf-8 -*-
# socketwrap
# Author: Blake Oliver <oliver22213@me.com>

from collections import deque, OrderedDict
import click
import socket
import select
from subprocess import PIPE
import sys, time, threading, subprocess_nonblocking, ssl, subprocess, pytoml
import pytoml
context = None

# generate config callback
def generate_config(ctx, param, val):
	if not val or ctx.resilient_parsing:
		return
	config = OrderedDict()
	click.echo("You are about to be asked to provide values for socketwrap's config options. Pressing enter will leave the default.")
	click.echo("If you are unsure what an option does, you can use the '--help' option to show the full help for each.")
	config["hostname"] = click.prompt ("""Specify the hostname or IP address socketwrap should listen on.""", default="127.0.0.1", show_default=True, type=click.STRING)
	config["port"] = click.prompt ("""Specify the port socketwrap should listen on.""", default=3000, show_default=True, type=click.INT)
	config["append_newline"] = click.confirm ("""Should socketwrap automatically append a newline to each buffer of data received from the subprocess's streams if it doesn't already have one?""", default=False, show_default=True)
	config["enable_multiple_connections"] = click.confirm ("""Allow multiple connections?""", default=False, show_default=True)
	config["loop_delay"] = click.prompt ("""Specify the loop delay.""", default=0.025, show_default=True, type=click.FLOAT)
	config["thread_sleep_time"] = click.prompt ("""Specify the thread sleep time.""", default=0.1, show_default=True, type=click.FLOAT)
	config["enable_ssl"] = click.confirm ("""Should socketwrap encrypt connections to clients with SSL?""", default=False, show_default=True)
	if config['enable_ssl'] == True:
		config["cert_file"] = click.prompt ("""Specify the public key certificate file.""", default=None, type=click.STRING, show_default=True, confirmation_prompt=True)
		config["key_file"] = click.prompt ("Specify the certificate key file.", default=None, show_default=True, type=click.STRING, confirmation_prompt=True)
	click.echo ("Please review your below configuration to ensure it is correct. Answering yes will save the configuration (and you can load it later with the '-c' option); answering no will exit.")
	for key, value in config.items():
		click.echo ("{}: {}".format (key, value))
	correct = click.confirm ("Is this configuration correct?", default=True, show_default=True)
	if correct == True:
		file = click.prompt ("Specify the configuration filename.", default="socketwrap.conf", show_default=True, type=click.STRING)
		with open (file, "w") as f:
			pytoml.dump (config, f)
			f.close()
		click.echo ("Configuration written to {}.".format (file))
	ctx.exit()

# define the command and it's options and args

@click.command()
@click.option('--host', '--hostname', '-hn', default='127.0.0.1', show_default=True, help="""Interface the server should listen on.""")
@click.option('--port', '-p', default=3000, show_default=True, help="""Port the server should bind to.""")
@click.option('--password', '--pass', '-pw', 'password', prompt=True, hide_input=True, confirmation_prompt=True, default=None, help="""Specify a password that clients must provide before they are allowed to view or send data to the wrapped subprocess.""")
@click.option ('--config-file', '--config', '-c', type=click.Path (exists=True, file_okay=True, dir_okay=False, writable=False, readable=True, resolve_path=True), multiple=False, default="socketwrap.conf", show_default=True, help="""Reads a configuration file and overrides all options specified on the command line with the values in the configuration file if the values are specified within that file. This file must be in TOML format (use the '-g' option to generate one).""")
@click.option('--generate-config', '-g', is_flag=True, callback=generate_config, expose_value=False, is_eager=True, help="""Generates a config file with values you provide. This can be used with the '-c' option so you don't need to specify specific options each time you want to run the program.""")
@click.option('--append-newline/--no-append-newline', '-a/-A', default=False, show_default=True, help="""Automatically append a newline to each buffer of data received from the subprocess's streams if it doesn't already have one.\nThis isn't normally useful, but for some programs such as shells which write the prompt and don't follow it with a newline character (which shows the command you type on the same line), you won't see that prompt when using them with socketwrap.\nThis option flag fixes such problems, though if the amount of output is extremely large in a rare case newlines could be mistakenly added where they aren't supposed to go by this option.""")
@click.option('--enable-multiple-connections/--disable-multiple-connections', '-e/-E', help="""Allow multiple connections. Each one will be able to send to the subprocess as well as receive.""")
@click.option('--loop-delay', '-l', default=0.025, show_default=True, help="""How long to sleep for at the end of each main loop iteration. This is meant to reduce CPU spiking of the main (socket-handling) thread. Setting this value too high introduces unnecessary lag when handling new data from clients or the wrapped command; setting it too low defeats the purpose. If it's set to 0, the delay is disabled.""")
@click.option('--thread-sleep-time', '-t', default=0.1, show_default=True, help="""How long the thread that reads output from the given command will sleep. Setting this to a lower value will make socketwrap notice and send output quicker, but will raise it's CPU usage""")
@click.option ('--enable-ssl/--disable-ssl', '-s/-S', default=False, show_default=True, help="""Specifies whether to use SSL to encrypt remote connections or not. If true, SSL will be used; if false, SSL will not be used and the connection will be unencrypted.""")
@click.option ('--cert-file', '-c', type=click.Path (exists=True, file_okay=True, dir_okay=False, writable=False, readable=True, resolve_path=True), default=None, show_default=True, help="""specifies a file which contains a certificate to be used to identify the local side of the ssl connection.""")
@click.option('--key-file', '-k', type=click.Path (exists=True, file_okay=True, dir_okay=False, writable=False, readable=True, resolve_path=True), default=None, show_default=True, help="""The ssl certificate key file to be used with the '--cert-file' option.""")
@click.version_option ("0.1.1", "-v", prog_name="socketwrap", message="""%(prog)s, version %(version)s\nOriginal copyright Copyright (c) 2017 Blake Oliver.\nUsing {}\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\nof this software and associated documentation files (the "Software"), to deal\nin the Software without restriction, including without limitation the rights\nto use, copy, modify, merge, publish, distribute, sublicense, and/or sell\ncopies of the Software, and to permit persons to whom the Software is\nfurnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all\ncopies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\nIMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\nFITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\nAUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\nLIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\nOUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\nSOFTWARE.""".format (ssl.OPENSSL_VERSION))
@click.argument('command', nargs=-1, required=True)
def socket_wrap(config_file, hostname, port, append_newline,  enable_multiple_connections, loop_delay, password, thread_sleep_time, enable_ssl, key_file, cert_file, command):
	"""Capture a given command's standard input, standard output, and standard error (stdin, stdout, and stderr) streams and let clients send and receive data to it by connecting to this program.

Args:

command: The command this program should wrap (including any arguments).

Any data received from it's stdout and stderr streams is buffered until the first client connects.

If the command exits with a non-zero returncode before the server is initialized, it's stderr is printed to the console.

"""
	if not len(config_file) == 0:
		try:
			with open (config_file, mode="rb") as f:
				config = pytoml.load (f)
			if "hostname" in config: hostname = config["hostname"]
			if "port" in config: port = config["port"]
			if "append_newline" in config: append_newline = config["append_newline"]
			if "enable_multiple_connections" in config: enable_multiple_connections = config["enable_multiple_connections"]
			if "loop_delay" in config: loop_delay = config["loop_delay"]
			if "thread_sleep_time" in config: thread_sleep_time = config["thread_sleep_time"]
			if "enable_ssl" in config: enable_ssl = config["enable_ssl"]
			if "key_file" in config: key_file = config["key_file"]
			if "cert_file" in config: cert_file = config["cert_file"]
		except BaseException as ex:
			click.echo ("TOML configuration parsing error: {}".format (ex), err=True)
			return
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
			print((subproc.stderr.read()))
			return
	# the returncode was none, so the process is running
	# set up the server
	if enable_ssl:
		context = ssl.create_default_context (ssl.Purpose.CLIENT_AUTH)
		context.load_default_certs(ssl.Purpose.SERVER_AUTH)
		if cert_file != None and key_file == None: # cert given, no key
			context.load_cert_chain (certfile=cert_file)
		elif cert_file!= None and key_file != None:
			context.load_cert_chain (certfile=cert_file, keyfile=key_file)
		else:
			print ("Warning: not loading certificate or keyfile; may cause security check errors.")
	else:
		context = None

	try:
		command_output_queue = deque() # queue of strings sent by the command we're wrapping
		stop_flag = threading.Event()
		t = threading.Thread(target=nonblocking_poll_command_for_output, args=(subproc, command_output_queue, thread_sleep_time, append_newline, stop_flag))
		t.start()
		server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		server_sock.bind((hostname, port))
		server_sock.listen(2)
		print("Command started and server listening on {}:{}".format(hostname, port))
		read = [] # sockets that might have something we can read
		write = [] # sockets that might have free space in their buffer
		error = [] # sockets we need to handle errors for
		all_clients = {}
		read.append(server_sock) # add the server socket so we can accept new connections
		running = True
		while running:
			r, w, e = select.select(read, write, error, 3)
			for sock in r: # for each socket that has something to be read
				if sock == server_sock: # this is the server socket, accept the new connection
					if context != None:
						con1, addr = sock.accept()
						# wrap the socket using the established SSL context
						con = context.wrap_socket (con1, server_side=True)
					else:
						con, addr = sock.accept()

					print("""{} has connected.""".format(addr))
					if enable_multiple_connections or len(all_clients)==0:
						read.append(con)
						write.append(con)
						error.append(con)
						all_clients[con] = {}
						con.sendall("Welcome!\n".encode())
						all_clients[con]['fd'] = con.makefile('r')
						if password != None:
							all_clients[con]['logged_in'] = False
							con.sendall("Password:\n".encode())
						else:
							con.sendall(info_message(command).encode())
					else: # there is already one client connected and enable_multiple_connections is false
						con.sendall("Sorry, allowing multiple connections is disabled.\nGoodbye.".encode())
						remove_socket(con, read, write, error, all_clients)
						print("{} has been disconnected because allowing multiple connections is disabled.".format(addr))
				else: # socket with something to read is not the server
					# large amounts of data might cause a lockup; it's unlikely though
					data = all_clients[sock]['fd'].readline()
					if data:
						if all_clients[sock].get('logged_in', None) == False: # passwored required and this client hasn't provided it yet
							candidate = data.strip()
							if candidate == password:
								sock.sendall("""Logged in to socketwrap.\n{}""".format(info_message(command)).encode())
								all_clients[sock]['logged_in'] = True
							else:
								sock.sendall("Incorrect password.\nGoodbye.\n".encode())
								remove_socket(sock, read, write, error, all_clients)
							continue # don't process the password as subprocess input
						try:
							subproc.stdin.write(data)
							subproc.stdin.flush()
						except IOError as e: # the subprocess has closed
							running = False
					else: # a client sending an empty string indicates a disconnect
						print(("{} has disconnected.".format(sock.getpeername())))
						remove_socket(sock, read, write, error, all_clients)
			# now check if the command has any output that needs to be sent to clients
			# make a list of sockets we can send to (ones for clients that are logged in and that are writable)
			sendable_clients = [c for c, d in all_clients.items() if d.get('logged_in', True) and c in w]
			if len(command_output_queue)>0 and len(sendable_clients)>0: # if there is at least one item in the queue and there is at least one socket to send it to
				i = command_output_queue.popleft()
				if i == False: # the reader thread has noticed the process has exited or closed it's pipes
					running = False
					raise KeyboardInterrupt # directly raise it to stop the boolean from being sent instead of waiting for the loop to complete
				for sock in sendable_clients: # for every socket who's buffer is free for writing
					sock.sendall(i.encode())
			# handle sockets with errors
			for sock in e:
				print(("Socket {} has an error!".format(sock.getpeername())))
				remove_socket(sock, read, write, error, all_clients)
				print(("{} has been disconnected.".format(sock.getpeername())))
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
		for sock in all_clients.keys():
			sock.sendall(reason.encode())
			remove_socket(sock, read, write, error, all_clients, remove_from_all=False) # prevent size changed durring iteration errors
		del(read)
		del(write)
		del(error)
		del(all_clients)
		del(server_sock)
		subproc.kill()


def nonblocking_poll_command_for_output(subproc, output_queue, poll_time, append_newline, stop_flag):
	"""Check stdout and stderr every poll_time to see if it has new output. If it does, add it as a string to output_queue."""
	while not stop_flag.is_set():
		try:
			stdout_buff = subprocess_nonblocking.recv_some(subproc, timeout=poll_time, tries=1)
			stderr_buff = subprocess_nonblocking.recv_some(subproc, timeout=poll_time, tries=1, stderr=True)
			if stdout_buff:
				if append_newline and not stdout_buff.endswith('\n'):
					stdout_buff += "\n"
				output_queue.append(stdout_buff)
			if stderr_buff:
				if append_newline and not stderr_buff.endswith('\n'):
					stderr_buff += "\n"
				output_queue.append(stderr_buff)
		except subprocess_nonblocking.PipeClosedError as e:
			output_queue.append(False)
		time.sleep(poll_time)


def info_message(command):
	w = """This is socketwrap, running command {}\n""".format(" ".join(command))
	return w

def remove_socket(sock, read, write, error, all_clients, remove_from_all=True):
	sock.close()
	if sock in read:
		read.remove(sock)
	if sock in write:
		write.remove(sock)
	if sock in error:
		error.remove(sock)
	if sock in list(all_clients.keys()):
		if all_clients[sock].get('fd', None) != None:
			all_clients[sock]['fd'].close()
		if remove_from_all:
			del(all_clients[sock])


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
