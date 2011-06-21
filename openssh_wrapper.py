# -*- coding: utf-8 -*-
import re, os, subprocess, signal

__all__ = 'SSHConnection SSHResult SSHError'.split()

class SSHConnection(object):

    def __init__(self, server, login=None, configfile=None, identity_file=None,
                 ssh_agent_socket=None, timeout=60):
        """
        Create new object to establish SSH connection to remote
        servers.

        Arguments:

        - `server`: server name or IP address to send commands to (required).
        - `login`: user login (by default, current login)
        - `confgfile`: local configuration file (by default ~/.ssh/config is used)
        - `identity_file`: identity file (by default ~/.ssh/id_rsa)
        - `ssh_agent_socket`: address of the socket to connect to ssh agent,
           if you want to use one. ``SSH_AUTH_SOCK`` environment variable is
           used if None is supplied.
        - `timeout`: connect timeout. If you plan to execute long lasting
          commands, adjust this variable accordingly.  Default value of 60
          seconds is usually a good choice.

        By the way, `man ssh_config` is highly recommended amendment to this
        command.
        """
        self.server = str(server)
        self.timeout = timeout
        self.check_server(server)
        if login:
            self.check_login(login)
            self.login = str(login)
        else:
            self.login = None
        if configfile:
            self.configfile = os.path.expanduser(configfile)
            if not os.path.isfile(self.configfile):
                raise SSHError('Config file %s is not found' % self.configfile )
        else:
            self.configfile = None
        if identity_file:
            self.identity_file = os.path.expanduser(configfile)
            if not os.path.isfile(self.identity_file):
                raise SSHError('Key file %s is not found' % self.identity_file)
        else:
            self.identity_file = None
        self.ssh_agent_socket = ssh_agent_socket

    def check_server(self, server):
        if not re.compile(r'^[a-zA-Z0-9.\-]+$').match(server):
            raise SSHError('Server name contains illegal symbols')

    def check_login(self, login):
        if not re.compile(r'^[a-zA-Z0-9.\-]+$').match(login):
            raise SSHError('User login contains illegal symbols')

    def run(self, command, interpreter='/bin/bash', forward_ssh_agent=False):
        """
        Execute ``command`` using ``interpreter``

        Consider this roughly as::

            echo "command" | ssh root@server "/bin/interpreter"

        Raise SSHError if server is unreachable

        Hint: Try interpreter='/usr/bin/python'
        """
        ssh_command = self.ssh_command(interpreter, forward_ssh_agent)
        pipe = subprocess.Popen(ssh_command,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, env=self.get_env())
        try:
            signal.signal(signal.SIGALRM, _timeout_handler)
        except ValueError, e: #signal only works in main thread
            pass
        signal.alarm(self.timeout)
        try:
            out, err = pipe.communicate(command)
        except IOError, e:
            # pipe.terminate() # only in python 2.6 allowed
            os.kill(pipe.pid, signal.SIGTERM)
            signal.alarm(0) # disable alarm
            raise SSHError(str(e))

        signal.alarm(0) # disable alarm
        returncode = pipe.returncode
        if returncode == 255: # ssh client error
            raise SSHError(err.strip())
        return SSHResult(command, out.strip(), err.strip(), returncode)

    def scp(self, *filenames, **kwargs):
        """ Copy files identified by their names to remote location

        Optional ``target`` parameter can be used to define target directory
        """
        scp_command = self.scp_command(*filenames, **kwargs)
        pipe = subprocess.Popen(scp_command,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, env=self.get_env())
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(self.timeout)
        try:
            out, err = pipe.communicate()
        except IOError, e:
            # pipe.terminate() # only in python 2.6 allowed
            os.kill(pipe.pid, signal.SIGTERM)
            signal.alarm(0) # disable alarm
            raise SSHError(stderr=str(e))
        signal.alarm(0) # disable alarm
        returncode = pipe.returncode
        if returncode != 0: # ssh client error
            raise SSHError(err.strip())

    def ssh_command(self, interpreter, forward_ssh_agent):
        interpreter = str(interpreter)
        cmd = ['/usr/bin/ssh', ]
        if self.login:
            cmd += [ '-l', self.login ]
        if self.configfile:
            cmd += [ '-F', self.configfile ]
        if self.identity_file:
            cmd += [ '-i', self.identity_file ]
        if forward_ssh_agent:
            cmd.append('-A')
        cmd.append(self.server)
        cmd.append(interpreter)
        return cmd

    def scp_command(self, *filenames, **kwargs):
        cmd = ['/usr/bin/scp', '-q', '-r']
        filenames = map(str, filenames)
        if self.login:
            remotename = '%s@%s' % (self.login, self.server)
        else:
            remotename = self.server
        if self.configfile:
            cmd += [ '-F', self.configfile ]
        if self.identity_file:
            cmd += [ '-i', self.identity_file ]

        if len(filenames) < 1:
            raise ValueError('You should name at least one file to copy')

        if 'target' in kwargs:
            cmd += filenames
            target = kwargs['target']
        else:
            if len(filenames) > 1:
                cmd += filenames[:-1]
                target = filenames[-1]
            else:
                cmd.append = filenames[0]
                target = filenames[0]
        cmd.append('%s:%s' % (remotename, target))
        return cmd

    def get_env(self):
        env = os.environ.copy()
        if self.ssh_agent_socket:
            env['SSH_AUTH_SOCK'] = self.ssh_agent_socket
        return env


def _timeout_handler(signum, frame):
    raise IOError, 'SSH connect timeout'


class SSHResult(object):
    """ Command execution status. Has ``command``, ``stdout``, ``stderr`` and
    ``returncode`` fields """

    def __init__(self, command, stdout, stderr, returncode):
        self.command = command
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

    def __str__(self):
        return unicode(self).decode('utf-8', 'ignore')

    def __unicode__(self):
        ret = []
        ret.append(u'command: %s' % unicode(self.command))
        ret.append(u'stdout: %s' % unicode(self.stdout))
        ret.append(u'stderr: %s' % unicode(self.stderr))
        ret.append(u'returncode: %s' % unicode(self.returncode))
        return u'\n'.join(ret)

class SSHError(Exception):  pass
