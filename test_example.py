from RLTest import Env
import time


def test_example():
    env = Env()
    con = env.GetConnection()
    con.set('x', 1)
    env.AssertEqual(con.get('x'), '1')


def test_example_2():
    env = Env()
    con = env.GetConnection()
    con.set('x', 1)
    env.AssertEqual(con.get('x'), '2')


def test_example_3():
    env = Env(useSlaves=True, env='oss')
    con = env.GetConnection()
    con.set('x', 1)
    con2 = env.GetSlaveConnection()
    time.sleep(0.1)
    env.AssertEqual(con2.get('x'), '1')
