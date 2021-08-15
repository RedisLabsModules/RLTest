import random
import socket
import struct
import fcntl
import os
import errno
import json

def _check_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError as e:
        if e.errno == errno.EPERM:
            return True
        return False


def register_port(port):
    fp = open('/tmp/rltest_portfile.lock', 'a+')
    fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
    fp.seek(0, 2)  # seek from end
    if fp.tell() == 0:
        entries = {}
    else:
        fp.seek(0, 0)
        entries = json.load(fp)
    # remove not responsive processes
    entries = { p:pid for p, pid in entries.items() if _check_alive(pid) }

    if str(port) in entries:
        ret = False
    else:
        entries[str(port)] = os.getpid()
        ret = True

    fp.seek(0, 0)
    fp.truncate()
    json.dump(entries, fp)
    fp.close()
    return ret


def get_random_port():
    for _ in range(10000):
        p = random.randint(10000, 20000)
        # Try to open and bind the socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
        try:
            s.bind(('', p))
            s.close()
            if not register_port(p):
                continue
            return p
        except Exception as e:
            if hasattr(e, 'errno') and e.errno in (errno.EADDRINUSE, errno.EADDRNOTAVAIL):
                pass
            else:
                raise e

    raise Exception('Could not find open port to listen on!')
