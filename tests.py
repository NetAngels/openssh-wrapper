# -*- coding: utf-8 -*-
import os
from openssh_wrapper import *
from nose.tools import *

test_file = os.path.join(os.path.dirname(__file__), 'tests.py')

class TestSSHCommandNames(object):

    def setUp(self):
        self.c = SSHConnection('localhost', login='root',
                               configfile='ssh_config.test')

    def test_ssh_command(self):
        eq_(self.c.ssh_command('/bin/bash', False),
            ['/usr/bin/ssh', '-l', 'root', '-F', 'ssh_config.test', 'localhost', '/bin/bash'])

    def test_scp_command(self):
        eq_(self.c.scp_command(('/tmp/1.txt', ), target='/tmp/2.txt'),
            ['/usr/bin/scp', '-q', '-r', '-F', 'ssh_config.test', '/tmp/1.txt', 'root@localhost:/tmp/2.txt'])

    def test_scp_multiple_files(self):
        eq_(self.c.scp_command(('/tmp/1.txt', '2.txt'), target='/home/username/'),
            ['/usr/bin/scp', '-q', '-r', '-F', 'ssh_config.test', '/tmp/1.txt', '2.txt', 'root@localhost:/home/username/'])

    def test_scp_targets(self):
        targets = self.c.get_scp_targets(['foo.txt', 'bar.txt'], '/etc')
        eq_(targets, ['/etc/foo.txt', '/etc/bar.txt'])
        targets = self.c.get_scp_targets(['foo.txt'], '/etc/passwd')
        eq_(targets, ['/etc/passwd'])

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
        self.c.run('rm -f /tmp/*.py /tmp/test*.txt')

    def test_scp(self):
        self.c.scp((test_file, ), target='/tmp')
        ok_(os.path.isfile('/tmp/tests.py'))

    @raises(SSHError)
    def test_scp_to_nonexistent_dir(self):
        self.c.scp((test_file, ), target='/abc/def/')

    def test_mode(self):
        self.c.scp((test_file, ), target='/tmp', mode='0666')
        mode = os.stat('/tmp/tests.py').st_mode & 0777
        eq_(mode, 0666)

    def test_owner(self):
        import pwd, grp
        uid, gid = os.getuid(), os.getgid()
        user, group = pwd.getpwuid(uid).pw_name, grp.getgrgid(gid).gr_name
        self.c.scp((test_file, ), target='/tmp', owner='%s:%s' % (user, group))
        stat = os.stat('/tmp/tests.py')
        eq_(stat.st_uid, uid)
        eq_(stat.st_gid, gid)

    def test_file_descriptors(self):
        from StringIO import StringIO
        # name is set explicitly as target
        fd1 = StringIO('test')
        self.c.scp((fd1, ), target='/tmp/test1.txt', mode='0644')
        eq_(open('/tmp/test1.txt').read(), 'test')
        # name is set explicitly in the name option
        fd2 = StringIO('test')
        fd2.name = 'test2.txt'
        self.c.scp((fd2, ), target='/tmp', mode='0644')
        eq_(open('/tmp/test2.txt').read(), 'test')
