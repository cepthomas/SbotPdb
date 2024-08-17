import sys
import datetime
import importlib

from .sbot_pdb import StPdb

# print(f'>>> (re)load {__name__}')


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

    ret = f'{cl1.do_class_assert(a1)}'

    ret = f'{cl1.do_class_exception(a2)}'
    
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

    ret = a_test_function(5, 9.126)

    test_exception_function()

    ret = another_test_function([33, 'tyu', 3.56], {'aaa': 111, 'bbb': 222, 'ccc': 333})

    return ret


#----------------------------------------------------------
def do_trace_test():
    '''Test starts here.'''

    do_a_suite(number=911, alpha='abcd')  # named args
