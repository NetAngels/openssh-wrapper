# -*- coding: utf-8 -*-
import io
import os
import pytest
from openssh_wrapper import *


test_file = os.path.join(os.path.dirname(__file__), 'tests.py')


def eq_(arg1, arg2):
    assert arg1 == arg2


class TestSSHCommandNames(object):

    def setup_method(self, meth):
        self.c = SSHConnection('localhost', login='root',
                               configfile='ssh_config.test')

    def test_ssh_command(self):
        eq_(self.c.ssh_command('/bin/bash', False),
            b_list(['/usr/bin/ssh', '-l', 'root', '-F', 'ssh_config.test', 'localhost', '/bin/bash']))

    def test_scp_command(self):
        eq_(self.c.scp_command(('/tmp/1.txt', ), target='/tmp/2.txt'),
            b_list(['/usr/bin/scp', '-q', '-r', '-F', 'ssh_config.test', '/tmp/1.txt', 'root@localhost:/tmp/2.txt']))

    def test_scp_multiple_files(self):
        eq_(self.c.scp_command(('/tmp/1.txt', '2.txt'), target='/home/username/'),
            b_list(['/usr/bin/scp', '-q', '-r', '-F', 'ssh_config.test', '/tmp/1.txt', '2.txt',
                    'root@localhost:/home/username/']))

    def test_scp_targets(self):
        targets = self.c.get_scp_targets(['foo.txt', 'bar.txt'], '/etc')
        eq_(targets, ['/etc/foo.txt', '/etc/bar.txt'])
        targets = self.c.get_scp_targets(['foo.txt'], '/etc/passwd')
        eq_(targets, ['/etc/passwd'])

    def test_simple_command(self):
        result = self.c.run('whoami')
        eq_(result.stdout, b('root'))
        eq_(result.stderr, b(''))
        eq_(result.returncode, 0)

    def test_python_command(self):
        result = self.c.run('print "Hello world"', interpreter='/usr/bin/python')
        eq_(result.stdout, b('Hello world'))
        eq_(result.stderr, b(''))
        eq_(result.returncode, 0)

def test_timeout():
    c = SSHConnection('example.com', login='root', timeout=1)
    with pytest.raises(SSHError):  # ssh connect timeout
        c.run('whoami')


def test_permission_denied():
    c = SSHConnection('localhost', login='www-data', configfile='ssh_config.test')
    with pytest.raises(SSHError):  # Permission denied (publickey)
        c.run('whoami')


class TestSCP(object):

    def setup_method(self, meth):
        self.c = SSHConnection('localhost', login='root')
        self.c.run('rm -f /tmp/*.py /tmp/test*.txt')

    def test_scp(self):
        self.c.scp((test_file, ), target='/tmp')
        assert os.path.isfile('/tmp/tests.py')

    def test_scp_to_nonexistent_dir(self):
        with pytest.raises(SSHError):
            self.c.scp((test_file, ), target='/abc/def/')

    def test_mode(self):
        self.c.scp((test_file, ), target='/tmp', mode='0666')
        mode = os.stat('/tmp/tests.py').st_mode & 0o777
        eq_(mode, 0o666)

    def test_owner(self):
        import pwd, grp
        uid, gid = os.getuid(), os.getgid()
        user, group = pwd.getpwuid(uid).pw_name, grp.getgrgid(gid).gr_name
        self.c.scp((test_file, ), target='/tmp', owner='%s:%s' % (user, group))
        stat = os.stat('/tmp/tests.py')
        eq_(stat.st_uid, uid)
        eq_(stat.st_gid, gid)

    def test_file_descriptors(self):
        # name is set explicitly as target
        fd1 = io.BytesIO(b('test'))
        self.c.scp((fd1, ), target='/tmp/test1.txt', mode='0644')
        assert io.open('/tmp/test1.txt', 'rt').read() == 'test'

        # name is set explicitly in the name option
        fd2 = io.BytesIO(b('test'))
        fd2.name = 'test2.txt'
        self.c.scp((fd2, ), target='/tmp', mode='0644')
        assert io.open('/tmp/test2.txt', 'rt').read() == 'test'
