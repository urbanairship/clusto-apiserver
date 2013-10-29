#!/usr/bin/env python
#
# -*- mode:python; sh-basic-offset:4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim:set tabstop=4 softtabstop=4 expandtab shiftwidth=4 fileencoding=utf-8:
#

import doctest
import functools
import inspect
import os
import port_for
import sys
import shelldoctest
import string
import unittest
import util


# Select a random port to spin up this testing server
PORT = port_for.select_random()


def setUpModule():

    util.start_testing_web_server(PORT)
    util.ping(PORT)


class TemplatedShellDocTestParser(shelldoctest.ShellDocTestParser):

    """
    A Regular ShellDocTestParser that passes the test through a string.Template
    object before passing it to the parser. This because I am using a variable
    in the docstrings around here so they look "correct" no matter where they
    are or how they are being served.
    """

    def __init__(self, substitutions={}):
        """
        This constructor can optionally receive a dictionary with substitution
        strings to parse via string.Template down below.
        """
        self.substitutions = substitutions

    def parse(self, svalue, name='<string>'):
        """
        Get the example, pass it through the string.Template object and then
        parse it as usual.
        """
        tpl = string.Template(svalue)
        text = tpl.safe_substitute(**self.substitutions)
        output = shelldoctest.ShellDocTestParser.parse(self, text, name)
        return output


class ShellDocComplete(unittest.TestCase):

    def __init__(self, functionname, function):
        f = functools.partial(self.shelldoc, function)
        f.__doc__ = 'At least one ShellDoc example for %s (in %s)' % (function, functionname,)
        methodname = 'test_shell_example_%s' % (functionname.replace('.', '_'),)
        self.__setattr__(methodname, f)
        unittest.TestCase.__init__(self, methodname)

    def shelldoc(self, function):
        "ShellDoc completeness partial check"
        # we don't care about strings here, just that there is at least 1 example
        finder = doctest.DocTestFinder(
            parser=shelldoctest.ShellDocTestParser(),
            exclude_empty=False,
        )
        shelldocs = finder.find(function)
        for sd in shelldocs:
            self.assertGreater(
                len(sd.examples), 0,
                msg='All public functions must have at least 1 shell example'
            )


def test_cases():
    shell_docsuite = unittest.TestSuite()

    # Test for at least one example in all public methods on each mounted app
    shelldoc_complete = unittest.TestSuite()
    for mount_point, cls in util.get_mount_apps().items():
        module = __import__(cls, fromlist=[cls])
        for fname in dir(module):
            function = getattr(module, fname)
            if not fname.startswith('_') and inspect.isfunction(function):
                shelldoc_complete.addTest(ShellDocComplete(cls, function))
            else:
                pass

    shell_docsuite.addTest(shelldoc_complete)

    # Now, for those that *do* have shell examples, test that they are actually correct
    filenames = [os.path.join(util.SRC_DIR, 'clustoapi', 'server.py')]
    for walkable in ('apps',):
        for root, dirs, files in os.walk(
            os.path.join(util.SRC_DIR, 'clustoapi', walkable)
        ):
            for f in files:
                filename = os.path.join(root, f)
                if f.endswith('.py') and os.path.getsize(filename) > 0:
                    filenames.append(filename)
    for filename in filenames:
        suite = doctest.DocFileSuite(
            filename,
            module_relative=False,
            parser=TemplatedShellDocTestParser(
                substitutions={'server_url': 'http://127.0.0.1:%s' % (PORT,)},
            ),
            globs={
                'system_command': shelldoctest.system_command,
            },
            optionflags=doctest.ELLIPSIS,
        )
        shell_docsuite.addTest(suite)
    return shell_docsuite


def main():
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(test_cases())


if __name__ == '__main__':
    sys.exit(main())