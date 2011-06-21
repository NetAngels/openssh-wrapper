OpenSSH Python wrapper
=======================

Under some circumstances simple wrapper around OpenSSH ``ssh`` command-line
utility seems more preferable than paramiko machinery.

This project proposes yet another hopefully thin wrapper around ``ssh`` to
execute commands on remote servers. All you need thereis to make sure that
OpenSSH client and Python interpreter are installed, and then install
`openssh-wrapper` package.

Usage sample
-------------

Simple command execution ::

    >>> from openssh_wrapper import SSHConnection
    >>> conn = SSHConnection('localhost', 'root')
    >>> ret = conn.run('whoami')
    >>> print ret
    command: whoami
    stdout: root
    stderr: 
    returncode: 0
    >>> ret.command
    'whoami'
    >>> ret.stdout
    'root'
    >>> ret.stderr
    ''
    >>> ret.returncode
    0

If python interpreter is installed on a remote machine, you can also run pieces
of python code remotely. The same is true for any other interpreter which can
execute code from stdin ::

    >>> ret = conn.run('whoami')
    >>> print conn.run('print "Hello world"', interpreter='/usr/bin/python').stdout
    Hello world

Yet another userful `run` method option is `forward_ssh_agent` (the feature
which paramiko doesn't yet have). Suppose you have access as support to foobar
server while root@localhost does not, so you can take advantage of SSH agent
forwarding ::

    $ eval `ssh-agent`
    Agent pid 5272
    $ ssh-add 
    Identity added: /home/me/.ssh/id_rsa (/home/,e/.ssh/id_rsa)
    $ python
    >>> conn = SSHConnection('localhost', 'root')
    >>> print conn.run('ssh support@foobar "whoami"', forward_ssh_agent=True).stdout
    support


And finally there is a sample which shows how to copy a file from local to
remote machine ::

    >>> fd = open('test.txt', 'w')
    >>> fd.write('Hello world')
    >>> fd.close()
    >>> from openssh_wrapper import SSHConnection
    >>> conn = SSHConnection('localhost', 'root')
    >>> conn.scp('test.txt', target='/tmp')
    >>> print conn.run('cat /tmp/test.txt').stdout
    Hello world
