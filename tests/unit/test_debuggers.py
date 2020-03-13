from unittest import TestCase

from RLTest.debuggers import Valgrind


class TestValgrind(TestCase):
    def test_generate_command_default(self):
        default_valgrind = Valgrind(options="")
        cmd_args = default_valgrind.generate_command()
        assert ['valgrind', '--error-exitcode=1', '--leak-check=full', '--errors-for-leak-kinds=definite',
                ] == cmd_args

    def test_generate_command_supression(self):
        default_valgrind = Valgrind(options="",suppressions="file")
        cmd_args = default_valgrind.generate_command()
        assert ['valgrind', '--error-exitcode=1', '--leak-check=full', '--errors-for-leak-kinds=definite',
                '--suppressions=file' ] == cmd_args

    def test_generate_command_logfile(self):
        default_valgrind = Valgrind(options="")
        cmd_args = default_valgrind.generate_command('logfile')
        assert ['valgrind', '--error-exitcode=1', '--leak-check=full', '--errors-for-leak-kinds=definite',
                '--log-file=logfile' ] == cmd_args
