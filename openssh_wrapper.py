# -*- coding: utf-8 -*-
"""
This is a wrapper around the openssh binaries ssh and scp.
"""
import re
import os
import subprocess
import signal
import pipes
import tempfile
import shutil

__all__ = 'SSHConnection SSHResult SSHError'.split()


class SSHConnection(object):
    """
    This class holds all values needed to connect to a host via ssh.
    It provides methods for command execution and file transfer via scp.
    """

    def __init__(self, server, login=None, port=None, configfile=None,
            identity_file=None, ssh_agent_socket=None, timeout=60):
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
        self.port = port
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
            self.identity_file = os.path.expanduser(identity_file)
            if not os.path.isfile(self.identity_file):
                raise SSHError('Key file %s is not found' % self.identity_file)
        else:
            self.identity_file = None
        self.ssh_agent_socket = ssh_agent_socket

    def check_server(self, server):
        """
        Check the server string for illegal characters.
        Returns:
            Nothing
        Raises:
            SSHError
        """
        if not re.compile(r'^[a-zA-Z0-9.\-_]+$').match(server):
            raise SSHError('Server name contains illegal symbols')

    def check_login(self, login):
        """
        Check the login string for illegal characters.
        Returns:
            Nothing
        Raises:
            SSHError
        """
        if not re.compile(r'^[a-zA-Z0-9.\-_]+$').match(login):
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
        except ValueError:  # signal only works in main thread
            pass
        signal.alarm(self.timeout)
        out = err = ""
        try:
            out, err = pipe.communicate(command)
        except IOError, exc:
            # pipe.terminate() # only in python 2.6 allowed
            os.kill(pipe.pid, signal.SIGTERM)
            signal.alarm(0)  # disable alarm
            raise SSHError(str(exc))

        signal.alarm(0)  # disable alarm
        returncode = pipe.returncode
        if returncode == 255:  # ssh client error
            raise SSHError(err.strip())
        return SSHResult(command, out.strip(), err.strip(), returncode)

    def scp(self, files, target, mode=None, owner=None):
        """ Copy files identified by their names to remote location

        :param files: files or file-like objects to copy
        :param target: target file or directory to copy data to. Target file
                       makes sense only if the number of files to copy equals
                       to one.
        :param mode: optional parameter to define mode for every uploaded file
                     (must be a string in the form understandable by chmod)
        :param owner: optional parameter to define user and group for every
                      uploaded file (must be a string in the form
                      understandable by chown). Makes sence only if you open
                      your connection as root.
        """
        filenames, tmpdir = self.convert_files_to_filenames(files)

        def cleanup_tmp_dir():
            if tmpdir:
                shutil.rmtree(tmpdir, ignore_errors=True)

        scp_command = self.scp_command(filenames, target)
        pipe = subprocess.Popen(scp_command,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, env=self.get_env())
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(self.timeout)
        err = ""
        try:
            _, err = pipe.communicate()
        except IOError, exc:
            # pipe.terminate() # only in python 2.6 allowed
            os.kill(pipe.pid, signal.SIGTERM)
            signal.alarm(0)  # disable alarm
            cleanup_tmp_dir()
            raise SSHError(stderr=str(exc))
        signal.alarm(0)  # disable alarm
        returncode = pipe.returncode
        if returncode != 0:  # ssh client error
            cleanup_tmp_dir()
            raise SSHError(err.strip())

        if mode or owner:
            targets = self.get_scp_targets(filenames, target)
            if mode:
                cmd_chunks = ['chmod', mode] + targets
                cmd = ' '.join([pipes.quote(chunk) for chunk in cmd_chunks])
                result = self.run(cmd)
                if result.returncode:
                    cleanup_tmp_dir()
                    raise SSHError(result.stderr.strip())
            if owner:
                cmd_chunks = ['chown', owner] + targets
                cmd = ' '.join([pipes.quote(chunk) for chunk in cmd_chunks])
                result = self.run(cmd)
                if result.returncode:
                    cleanup_tmp_dir()
                    raise SSHError(result.stderr.strip())
        cleanup_tmp_dir()

    def convert_files_to_filenames(self, files):
        """
        Check for every file in list and save it locally to send to remote side, if needed
        """
        filenames = []
        tmpdir = None
        for file_obj in files:
            if isinstance(file_obj, basestring):
                filenames.append(file_obj)
            else:
                if not tmpdir:
                    tmpdir = tempfile.mkdtemp()
                if hasattr(file_obj, 'name'):
                    basename = os.path.basename(file_obj.name)
                    tmpname = os.path.join(tmpdir, basename)
                    fd = open(tmpname, 'w')
                    fd.write(file_obj.read())
                    fd.close()
                else:
                    tmpfd, tmpname = tempfile.mkstemp(dir=tmpdir)
                    os.write(tmpfd, file_obj.read())
                    os.close(tmpfd)
                filenames.append(tmpname)
        return filenames, tmpdir

    def get_scp_targets(self, filenames, target):
        """
        Given a list of filenames and a target name return the full list of targets

        Internal command which is used to perform chmod and chown.

        For example, get_scp_targets(['foo.txt', 'bar.txt'], '/etc') returns ['/etc/foo.txt', '/etc/bar.txt'],
        whereas get_scp_targets(['foo.txt', ], '/etc/passwd') returns ['/etc/passwd', ]
        """
        result = self.run('test -d %s' % pipes.quote(target))
        is_directory = result.returncode == 0
        if is_directory:
            ret = []
            for filename in filenames:
                ret.append(os.path.join(target, os.path.basename(filename)))
            return ret
        else:
            return [target, ]

    def ssh_command(self, interpreter, forward_ssh_agent):
        """ Build the command string to connect to the server
        and start the given interpreter. """
        interpreter = str(interpreter)
        cmd = ['/usr/bin/ssh', ]
        if self.login:
            cmd += ['-l', self.login]
        if self.configfile:
            cmd += ['-F', self.configfile]
        if self.identity_file:
            cmd += ['-i', self.identity_file]
        if forward_ssh_agent:
            cmd.append('-A')
        if self.port:
            cmd += ['-p', str(self.port)]
        cmd.append(self.server)
        cmd.append(interpreter)
        return cmd

    def scp_command(self, files, target):
        """ Build the command string to transfer the files
        identifiend by the given filenames.
        Include target(s) if specified. """
        cmd = ['/usr/bin/scp', '-q', '-r']
        files = map(str, files)
        if self.login:
            remotename = '%s@%s' % (self.login, self.server)
        else:
            remotename = self.server
        if self.configfile:
            cmd += ['-F', self.configfile]
        if self.identity_file:
            cmd += ['-i', self.identity_file]
        if self.port:
            cmd += ['-P', self.port]

        if isinstance(files, basestring):
            raise ValueError('"files" argument have to be iterable (list or tuple)')
        if len(files) < 1:
            raise ValueError('You should name at least one file to copy')

        cmd += files
        cmd.append('%s:%s' % (remotename, target))
        return cmd

    def get_env(self):
        """ Retrieve environment variables and replace SSH_AUTH_SOCK
        if ssh_agent_socket was specified on object creation. """
        env = os.environ.copy()
        if self.ssh_agent_socket:
            env['SSH_AUTH_SOCK'] = self.ssh_agent_socket
        return env


def _timeout_handler(signum, frame):
    """ This function is called when ssh takes too long to connect. """
    raise IOError('SSH connect timeout')


class SSHResult(object):
    """ Command execution status. Has ``command``, ``stdout``, ``stderr`` and
    ``returncode`` fields """

    def __init__(self, command, stdout, stderr, returncode):
        """ Create a new object to hold output and a return code
        to the given command. """
        self.command = command
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

    def __str__(self):
        """ Get acscii representation from unicode representation. """
        return unicode(self).decode('utf-8', 'ignore')

    def __unicode__(self):
        """ Build simple unicode representation from all member values. """
        ret = []
        ret.append(u'command: %s' % unicode(self.command))
        ret.append(u'stdout: %s' % unicode(self.stdout))
        ret.append(u'stderr: %s' % unicode(self.stderr))
        ret.append(u'returncode: %s' % unicode(self.returncode))
        return u'\n'.join(ret)


class SSHError(Exception):
    """
    This exception is used for all errors raised by this module.
    """
    pass
