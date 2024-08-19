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
class MyClass(object):

    def __init__(self, name, tags, arg):
        self._name = name
        self._tags = tags
        self._arg = arg

    def do_something(self, arg):
        res = f'{self._arg}-user-{arg}'
        return res

    def class_boom(self, arg):
        x = 1 / 0  # boom


#----------------------------------------------------------
def function_1(a1: int, a2: float):
    cl1 = MyClass('number 1', [45, 78, 23], a1)
    cl2 = MyClass('number 2', [100, 101, 102], a2)
    ret = f'answer is cl1:{cl1.do_something(a1)}...cl2:{cl2.do_something(a2)}'
    # ret = f'{cl1.class_boom(a2)}'
    return ret


#----------------------------------------------------------
def function_2(a_list, a_dict):
    return len(a_list) + len(a_dict)


#----------------------------------------------------------
def function_boom():
    i = 0
    return 1 / i  # boom


#----------------------------------------------------------
def do_a_suite(alpha, number):

    sbot_pdb.set_trace()

    ret = function_1(5, 9.126)
    # function_boom()
    ret = function_2([33, 'thanks', 3.56], {'aaa': 111, 'bbb': 222, 'ccc': 333})
    return ret
