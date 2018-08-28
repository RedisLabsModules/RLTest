from RLTest import Env
import time


class testExample():
    '''
    run all tests on a single env without taking
    env down between tests
    '''
    def __init__(self):
        self.env = Env()

    def testExample(self):
        con = self.env.getConnection()
        con.set('x', 1)
        self.env.assertEqual(con.get('x'), '1')

    def testExample1(self):
        con = self.env.getConnection()
        con.set('x', 1)
        self.env.assertEqual(con.get('x'), '1')
        self.env.assertFalse(True)

    def testExample2(self):
        con = self.env.getConnection()
        con.set('x', 1)
        self.env.assertEqual(con.get('x'), '1')


# run each test on different env
def test_example():
    env = Env()
    con = env.getConnection()
    con.set('x', 1)
    env.assertEqual(con.get('x'), '1')


def test_example_2():
    env = Env()
    env.assertOk(env.cmd('set', 'x', '1'))
    env.expect('get', 'x').equal('1')

    env.expect('lpush', 'list', '1', '2', '3').equal(3)
    env.expect('lrange', 'list', '0', '-1').debugPrint().contains('1')
    env.debugPrint('this is some debug printing')


def test_example_3():
    env = Env(useSlaves=True, env='oss')
    con = env.getConnection()
    con.set('x', 1)
    con2 = env.getSlaveConnection()
    time.sleep(0.1)
    env.assertEqual(con2.get('x'), '1')
