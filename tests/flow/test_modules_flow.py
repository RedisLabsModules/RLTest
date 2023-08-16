import os

from RLTest import Env


def checkSampleModules(env):
    redis_conn = env.getConnection()
    modules_list = redis_conn.execute_command("info modules").decode().split('\r\n')
    modules_list = modules_list[1:]
    for module_info in modules_list:
        if "module:name=" in module_info:
            module_name = module_info.split(",")[0].split("=")[1]
            if module_name == "module1":
                env.assertEqual(b'OK', redis_conn.execute_command("module1.cmd1"))
            if module_name == "module2":
                env.assertEqual(b'OK', redis_conn.execute_command("module2.cmd2"))


def test_modulesSimpleFlow(env):
    """
    This simple test ensures that we can load two modules on RLTest and their commands are properly accessible
    @param env:
    """
    checkSampleModules(env)



