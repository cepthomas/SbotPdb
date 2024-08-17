import sys
import datetime
import importlib
import sublime
import sublime_plugin

from . import sbot_pdb
# import .sbot_pdb

# print(f'>>> (re)load {__name__}')

importlib.reload(sbot_pdb)


#-----------------------------------------------------------------------------------
class SbotPdbTestCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        from . import sbot_pdb
        try:
            # sbot_pdb.StPdb()  # shorter
            # sbot_pdb.set_trace()
            # print('+++ 0')
            ret = do_a_suite(number=911, alpha='abcd')
            print(ret)
        except Exception as e:
            dir(e)
            print(f'StPdb exception: {e}')
            # log.error(f'StPdb exception: {e}')


#----------------------------------------------------------
class TestClass(object):
    ''' Dummy for testing class function tracing.'''

    def __init__(self, name, tags, arg):
        '''Construct.'''
        self._name = name
        self._tags = tags
        self._arg = arg

    def do_something(self, arg):
        '''Entry/exit is traced with args and return value.'''
        res = f'{self._arg}-user-{arg}'
        return res

    def do_class_exception(self, arg):
        '''Entry/exit is traced with args and return value.'''
        x = 1 / 0


#----------------------------------------------------------
def a_test_function(a1: int, a2: float):
    '''Entry/exit is traced with args and return value.'''
    cl1 = TestClass('number 1', [45, 78, 23], a1)
    cl2 = TestClass('number 2', [100, 101, 102], a2)
    ret = f'answer is cl1:{cl1.do_something(a1)}...cl2:{cl2.do_something(a2)}'

    # ret = f'{cl1.do_class_exception(a2)}'
    
    return ret


#----------------------------------------------------------
def another_test_function(a_list, a_dict):
    '''Entry/exit is traced with args and return value.'''
    return len(a_list) + len(a_dict)


#----------------------------------------------------------
def test_exception_function():
    '''Cause exception and handling.'''
    i = 0
    return 1 / i


#----------------------------------------------------------
def do_a_suite(alpha, number):
    '''Make a nice suite with entry/exit and return value.'''

    # print('+++ 10')

    dir(sbot_pdb)

    sbot_pdb.set_trace()

    ret = a_test_function(5, 9.126)
    # print('+++ 20')

    # test_exception_function()
    # print('+++ 30')

    ret = another_test_function([33, 'tyu', 3.56], {'aaa': 111, 'bbb': 222, 'ccc': 333})
    # print('+++ 40')

    return ret
