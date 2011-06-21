# -*- coding: utf-8 -*-
import os
from openssh_wrapper import *
from nose.tools import *


class TestSSHCommandNames(object):

    def setUp(self):
        self.c = SSHConnection('localhost', login='root',
                               configfile='ssh_config.test')

    def test_ssh_command(self):
        eq_(self.c.ssh_command('/bin/bash', False),
            ['/usr/bin/ssh', '-l', 'root', '-F', 'ssh_config.test', 'localhost', '/bin/bash'])

    def test_scp_command(self):
        eq_(self.c.scp_command('/tmp/1.txt', target='/tmp/2.txt'),
            ['/usr/bin/scp', '-q', '-r', '-F', 'ssh_config.test', '/tmp/1.txt', 'root@localhost:/tmp/2.txt'])

    def test_scp_multiple_files(self):
        eq_(self.c.scp_command('/tmp/1.txt', '2.txt', target='/home/username/'),
            ['/usr/bin/scp', '-q', '-r', '-F', 'ssh_config.test', '/tmp/1.txt', '2.txt', 'root@localhost:/home/username/'])

    def test_simple_command(self):
        result = self.c.run('whoami')
        eq_(result.stdout, 'root')
        eq_(result.stderr, '')
        eq_(result.returncode, 0)

    def test_python_command(self):
        result = self.c.run('print "Hello world"', interpreter='/usr/bin/python')
        eq_(result.stdout, 'Hello world')
        eq_(result.stderr, '')
        eq_(result.returncode, 0)

@raises(SSHError) # ssh connect timeout
def test_timeout():
    c = SSHConnection('example.com', login='root', timeout=1)
    c.run('whoami')


@raises(SSHError) # Permission denied (publickey)
def test_permission_denied():
    c = SSHConnection('localhost', login='www-data', configfile='ssh_config.test')
    c.run('whoami')


class TestSCP(object):

    def setUp(self):
        self.c = SSHConnection('localhost', login='root')

    def test_scp(self):
        self.c.scp(__file__, target='/tmp')
        ok_(os.path.isfile('/tmp/tests.py'))

    @raises(SSHError)
    def test_scp_to_nonexistent_dir(self):
        self.c.scp(__file__, target='/abc/def/')
