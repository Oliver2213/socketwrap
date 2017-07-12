# socketwrap
Wrap a given subprocess so it's stdin, stdout, and stderr streams get received and sent from sockets, allowing remote usage.


This was originally created to wrap a command-line game so that it could be used with a MUD client (for triggers, aliases and timers), but will work just as well for any command-line program (as long as it directs it's output to stdout / stderr, and takes input from stdin).
It can also be used to allow multiple people to interact with a single program remotely (such as a game).

## Features

* Full ssl support: if you use this to wrap an application and you access it remotely, traffic is encrypted. Note that any client you use must of course support ssl. A command like `openssl s_client -h hostname -p port` will work (replacing hostname and port with those that socketwrap is bound to). You will also need a certificate to use (one is provided in this repository for testing purposes).
* Support for generating and using a config file: instead of always typing the same options every time you use the tool, you can generate a config file and just tell socketwrap to use the values stored in it.
* Optional password authentication: You can specify a password that all clients need to provide before they are allowed to send to, or view output from, the wrapped command.
* works on Windows, Mac OS, and Linux.
