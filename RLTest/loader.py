import os
import sys
import imp
import inspect


class TestFunction(object):
    is_class = False

    def __init__(self, target, name=None, is_method=False):
        self.target = target
        if not name:
            name = target.__name__

        self.name = '{}:{}'.format(target.__module__, name)
        self.is_method = is_method

    def shortname(self):
        return self.target.__name__


class TestClass(object):
    is_class = True

    def __init__(self, cls, names):
        self.methnames = names
        self.clsname = cls.__name__
        self.cls = cls
        self.name = '{}:{}'.format(cls.__module__, self.clsname)

    def create_instance(self, *args, **kwargs):
        return self.cls(*args, **kwargs)

    def get_functions(self, instance):
        fns = []
        for mname in self.methnames:
            bound = getattr(instance, mname)
            if not callable(bound):
                continue
            fns.append(TestFunction(bound,
                                    name='{}.{}'.format(self.clsname, mname),
                                    is_method=True))
        return fns


class TestLoader(object):
    def __init__(self, filter=None):
        self.tests = []
        self.toplevel_filter = filter
        self.subfilter = None

    def load_spec(self, arg):
        # See what kind of spec this is!
        """
        Load tests from single argument form, e.g. foo.py:BarBaz
        """
        if ':' in arg:
            filename, varname = arg.split(':')
        else:
            filename = arg
            varname = None
            if os.path.isdir(filename):
                sys.path.append(filename)
                self.scan_dir(filename)
                return

        # Ensure the path is in sys.path
        dirname = os.path.abspath(os.path.dirname(filename))
        if dirname not in sys.path:
            sys.path.append(dirname)

        module_name, _ = os.path.splitext(os.path.basename(filename))
        if varname:
            if '.' in varname:
                self.toplevel_filter, self.subfilter = varname.split('.')
            else:
                self.toplevel_filter = varname

        self.load_files(dirname, module_name)

    def load_files(self, module_dir, module_name):
        filename = '%s/%s.py' % (module_dir, module_name)
        module_file = open(filename, 'r')
        module = imp.load_module(module_name, module_file, filename,
                                 ('.py', 'r', imp.PY_SOURCE))
        for symbol in dir(module):
            if not self.filter_modulevar(symbol):
                continue

            obj = getattr(module, symbol)
            if inspect.isclass(obj):
                methnames = [mname for mname in dir(obj)
                             if self.filter_method(mname)]
                self.tests.append(TestClass(obj, methnames))
            elif inspect.isfunction(obj):
                self.tests.append(TestFunction(obj))

    def scan_dir(self, testdir):
        for filename in os.listdir(testdir):
            if filename.startswith('test') and filename.endswith('.py'):
                module_name, ext = os.path.splitext(filename)
                self.load_files(testdir, module_name)

    def filter_modulevar(self, candidate):
        if not candidate.lower().startswith('test'):
            return False
        if self.toplevel_filter and candidate != self.toplevel_filter:
            return False
        return True

    def filter_method(self, candidate):
        if not candidate.lower().startswith('test'):
            return False
        if self.subfilter and candidate != self.subfilter:
            return False

        return True

    def __iter__(self):
        return iter(self.tests)

    def print_tests(self):
        for t in self.tests:
            print "Test: ", t.name
            if t.is_class:
                print "\tClass"
                print "\tFunctions"
                for m in t.methnames:
                    print "\t\t", m
            else:
                print "\tFunction"