import sys
import datetime
import importlib
import sublime
import sublime_plugin
from . import sbot_pdb



#-----------------------------------------------------------------------------------
class SbotPdbTestCommand(sublime_plugin.TextCommand):
    '''Run the plugin from a menu item:
    { "caption": "Run sbot pdb test", "command": "sbot_pdb_test" },
    '''

    def run(self, edit):
        # Benign reload in case of being edited.
        importlib.reload(sbot_pdb)
        # Run the code under debug.
        ret = do_a_suite(number=911, alpha='abcd')


#----------------------------------------------------------
class MyClass(object):
    '''A simple object.'''

    def __init__(self, name, tags, arg):
        self._name = name
        self._tags = tags
        self._arg = arg

    def do_something(self, arg):
        res = f'{self._arg}-user-{arg}'
        return res

    def class_boom(self, arg):
        # Cause unhandled exception.
        return 1 / 0


#----------------------------------------------------------
def function_1(a1: int, a2: float):
    '''A simple function.'''
    cl1 = MyClass('number 1', [45, 78, 23], a1)
    cl2 = MyClass('number 2', [100, 101, 102], a2)
    ret = f'answer is cl1:{cl1.do_something(a1)}...cl2:{cl2.do_something(a2)}'

    # Play with exception handling.
    # ret = f'{cl1.class_boom(a2)}'

    return ret


#----------------------------------------------------------
def function_2(a_list, a_dict):
    '''A simple function.'''
    return len(a_list) + len(a_dict)


#----------------------------------------------------------
def function_boom():
    '''A function that causes an unhandled exception.'''
    return 1 / 0


#----------------------------------------------------------
def do_a_suite(alpha, number):
    '''Main test code.'''

    # Set a breakpoint here then step through and examine the code.
    sbot_pdb.breakpoint()

    ret = function_1(5, 9.126)

    # Unhandled exception actually goes to sys.__excepthook__.
    # function_boom()

    ret = function_2([33, 'thanks', 3.56], {'aaa': 111, 'bbb': 222, 'ccc': 333})

    return ret
