import sys
import datetime
import importlib
import sublime
import sublime_plugin
from . import sbot_pdb

# print(f'>>> (re)load {__name__}')

# For reload scenario.
importlib.reload(sbot_pdb)


#-----------------------------------------------------------------------------------
class SbotPdbTestCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        ret = do_a_suite(number=911, alpha='abcd')


#----------------------------------------------------------
class TestClass(object):

    def __init__(self, name, tags, arg):
        self._name = name
        self._tags = tags
        self._arg = arg

    def do_something(self, arg):
        res = f'{self._arg}-user-{arg}'
        return res

    def do_class_exception(self, arg):
        x = 1 / 0  # boom


#----------------------------------------------------------
def a_test_function(a1: int, a2: float):
    cl1 = TestClass('number 1', [45, 78, 23], a1)
    cl2 = TestClass('number 2', [100, 101, 102], a2)
    ret = f'answer is cl1:{cl1.do_something(a1)}...cl2:{cl2.do_something(a2)}'
    # ret = f'{cl1.do_class_exception(a2)}'
    return ret


#----------------------------------------------------------
def another_test_function(a_list, a_dict):
    return len(a_list) + len(a_dict)


#----------------------------------------------------------
def test_exception_function():
    i = 0
    return 1 / i  # boom


#----------------------------------------------------------
def do_a_suite(alpha, number):
    sbot_pdb.set_trace()
    ret = a_test_function(5, 9.126)
    # test_exception_function()
    ret = another_test_function([33, 'thanks', 3.56], {'aaa': 111, 'bbb': 222, 'ccc': 333})
    return ret
