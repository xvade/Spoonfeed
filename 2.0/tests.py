from tqdm import tqdm
from colorama import Fore, Style
from classes import *
import random
from hood import *


def test_all():
    tests = [feed_init, task_init, feed_new_task, task_set_time, feed_set_unit, feed_get_task_by_id, feed_set_time,
             feed_get_task_by_name_timeframe, task_pretty, feed_remove, feed_check_off, feed_push_from_today,
             feed_act_on_computer_input, feed_process_human_input, hood_log, hood_initialize
             ]
    fails = []
    for test in tests:
        print(test.__qualname__)
        if not test():
            fails.append(test)
    if len(fails) > 0:
        if len(fails) == 1:
            fail_message = "One test failed (" + fails[0].__qualname__ + "). Exiting."
        else:
            fail_message = "Some tests failed ("
            for i in range(len(fails)-1):
                fail_message += fails[i].__qualname__ + ", "
            fail_message += fails[len(fails)-1].__qualname__
        exit(fail_message)
    else:
        print(Fore.GREEN + "All tests passed." + Style.RESET_ALL)


def feed_init():
    try:
        f = Spoonfeed()
        assert f.feed == []
        assert f.count == 0
        return True
    except:
        return False


def task_init():
    try:
        t = Task(0, "asdf")
        assert t.id == 0
        assert t.name == "asdf"
        assert time.time() - t.reveal_time < 0.1
        assert t.interval == -1
        return True
    except:
        return False


def feed_act_on_str():
    try:
        return True
    except:
        return False


def feed_new_task():
    try:
        f = Spoonfeed()
        f.new_task('adf')
        assert len(f.feed) == 1
        assert f.feed[0].name == 'adf'
        assert time.time() - f.feed[0].reveal_time < 0.1
        assert f.feed[0].interval == -1
        assert f.count == 1
        f2 = Spoonfeed()
        f2.new_task('d', 2)
        assert f2.feed[0].interval == 2
        return True
    except:
        return False


def task_set_time():
    try:
        t = Task(0, 'a', 4)
        t.set_time(8)
        assert t.reveal_time == 8
        return True
    except:
        return False


def feed_set_unit():
    try:
        f = Spoonfeed()
        assert f.unit == 1
        f.set_unit(3)
        assert f.unit == 3
        return True
    except:
        return False


def feed_get_task_by_id():
    try:
        f = Spoonfeed()
        assert f.get_task_by_id(0) is None
        f.new_task('a')
        assert f.get_task_by_id(0).name == 'a'
        return True
    except:
        return False


def feed_set_time():
    try:
        f = Spoonfeed()
        f.new_task('a', 0)
        f.set_time(0, 100)
        assert f.get_task_by_id(0).reveal_time == 100
        return True
    except:
        return False


def feed_get_task_by_name_timeframe():
    try:
        f = Spoonfeed()
        f.new_task('a')
        assert f.get_task_by_name_timeframe('b', time.time()+1000) is None
        assert f.get_task_by_name_timeframe('b', 0) is None
        assert f.get_task_by_name_timeframe('a', 0) is None
        assert f.get_task_by_name_timeframe('a', time.time()+1000) == f.get_task_by_id(0)

        return True
    except:
        return False


def task_pretty():
    try:
        t = Task(0, 'a')
        assert t.pretty() == '- a'
        return True
    except:
        return False


def feed_remove():
    try:
        f = Spoonfeed()
        f.new_task('a')
        f.remove(1)
        assert f.count == 1
        assert f.get_task_by_id(0).name == 'a'
        assert f.get_task_by_name_timeframe('a', 100000000000000000).name == 'a'
        f.remove(0)
        assert f.count == 1
        assert f.get_task_by_id(0) is None
        assert f.get_task_by_name_timeframe('a', 100000000000000000) is None
        return True
    except:
        return False


def feed_check_off():
    try:
        f = Spoonfeed()
        f.new_task('0')
        f.get_task_by_id(0).set_time(0)
        f.check_off(0)
        assert f.count == 1
        assert f.get_task_by_id(0) is None
        assert f.get_task_by_name_timeframe('0', 0) is None
        f.new_task('1', 1)
        f.get_task_by_id(1).set_time(0)
        f.check_off(1)
        assert f.count == 2
        assert f.get_task_by_id(1).reveal_time == 1
        return True
    except:
        return False


def feed_push_from_today():
    try:
        f = Spoonfeed()
        f.new_task('0', 0)
        f.push_from_today(0, 100)
        assert 99 <= f.get_task_by_id(0).reveal_time - time.time() <= 100
        f.new_task('1', 0)
        f.set_unit(100)
        f.push_from_today(1, 1)
        assert 99 <= f.get_task_by_id(1).reveal_time - time.time() <= 100
        return True
    except:
        return False


def feed_act_on_computer_input():
    try:
        f = Spoonfeed()
        f.act_on_computer_input("new_task my task,-1,3")
        t = f.get_task_by_id(0)
        assert t.name == "my task"
        assert t.interval == -1
        assert t.reveal_time == 3

        f.act_on_computer_input("set_time 0,2")
        assert t.reveal_time == 2

        f.act_on_computer_input("remove 0")
        assert f.get_task_by_id(0) is None

        f.act_on_computer_input("set_unit 4")
        assert f.unit == 4
        return True
    except:
        return False


def feed_process_human_input():
    # try:
        f = Spoonfeed()
        assert f.process_human_input("nt my task")[:20] == "new_task my task,-1,"
        f.new_task("my_task")
        assert f.process_human_input("remove  my_task") == "remove 0"
        f.new_task("my other task")
        assert f.process_human_input("check_off my other task") == "remove 1"
        f.new_task("my third task")
        assert f.process_human_input("pft my third task,3")[:11] == "set_time 2,"
        assert f.process_human_input("su 3") == "set_unit 3"
        return True
    # except:
    #     return False


def hood_log():
    try:
        log("new_task my task", "test_logs.txt")
        with open("test_logs.txt", 'r') as test_logs:
            assert test_logs.readline() == "new_task my task\n"
        open("test_logs.txt", 'w').close()
        return True
    except:
        open("test_logs.txt", 'w').close()
        return False


def hood_initialize():
    try:
        f = Spoonfeed('test_logs.txt')
        f.act_on_human_input("new_task 0,0,0")
        f.act_on_human_input("new_task 1,1,1")
        f.act_on_human_input("new_task 2,2,2")
        f.act_on_human_input("remove 1")
        f.act_on_human_input("set_time 2,3")
        f1 = Spoonfeed('test_logs.txt')
        initialize(f1)
        open('test_logs.txt', 'w').close()
        return True
    except:
        open('test_logs.txt', 'w').close()
        return False

