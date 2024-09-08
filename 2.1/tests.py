import unittest
from classes import *
import random
from hood import *


class Testing(unittest.TestCase):
    def test_feed_init(self):
        f = Spoonfeed()
        self.assertEquals(f.feed, [])
        self.assertEquals(f.count, 0)

    def test_task_init(self):
        t = Task(0, "asdf")
        now = time.time()
        self.assertEquals(t.id, 0)
        self.assertEquals(t.name, "asdf")
        self.assertLess(now - t.reveal_time, 10)
        self.assertEquals(t.interval, -1)

    def test_feed_new_task(self):
        f = Spoonfeed()
        f.new_task('adf')
        self.assertEquals(len(f.feed), 1)
        self.assertEquals(f.feed[0].name, 'adf')
        self.assertLess(time.time() - f.feed[0].reveal_time, 1)
        self.assertEquals(f.feed[0].interval, -1)
        self.assertEquals(f.count, 1)
        f2 = Spoonfeed()
        f2.new_task('d', 2)
        self.assertEquals(f2.feed[0].interval, 2)

    def test_task_set_time(self):
        t = Task(0, 'a', 4)
        t.set_time(8)
        self.assertEquals(t.reveal_time, 8)
        return True

    def test_feed_set_unit(self):
        f = Spoonfeed()
        self.assertEquals(f.unit, 1)
        f.set_unit(3)
        self.assertEquals(f.unit, 3)

    def test_feed_get_task_by_id(self):
        f = Spoonfeed()
        self.assertIsNone(f.get_task_by_id(0))
        f.new_task('a')
        self.assertEquals(f.get_task_by_id(0).name, 'a')

    def test_feed_set_time(self):
        f = Spoonfeed()
        f.new_task('a', 0)
        f.set_time(0, 100)
        self.assertEquals(f.get_task_by_id(0).reveal_time, 100)

    def test_feed_get_task_by_name_timeframe(self):
        f = Spoonfeed()
        f.new_task('a')
        self.assertIsNone(f.get_task_by_name_timeframe_or_id('b', time.time() + 1000))
        self.assertIsNone(f.get_task_by_name_timeframe_or_id('b', 0))
        self.assertIsNone(f.get_task_by_name_timeframe_or_id('a', 0))
        self.assertEquals(f.get_task_by_name_timeframe_or_id('a', time.time() + 1000), f.get_task_by_id(0))

    def test_task_pretty(self):
        t = Task(0, 'a')
        self.assertEquals(t.pretty(), '- a')

    def test_feed_remove(self):
        f = Spoonfeed()
        f.new_task('a')
        f.remove(1)
        self.assertEquals(f.count, 1)
        self.assertEquals(f.get_task_by_id(0).name, 'a')
        self.assertEquals(f.get_task_by_name_timeframe_or_id('a', 100000000000000000).name, 'a')
        f.remove(0)
        self.assertEquals(f.count, 1)
        self.assertIsNone(f.get_task_by_id(0))
        self.assertIsNone(f.get_task_by_name_timeframe_or_id('a', 100000000000000000))

    # def test_feed_check_off(self):
    #     f = Spoonfeed()
    #     f.new_task('0')
    #     f.get_task_by_id(0).set_time(0)
    #     f.check_off(0)
    #     self.assertEquals(f.count, 1)
    #     self.assertIsNone(f.get_task_by_id(0))
    #     self.assertIsNone(f.get_task_by_name_timeframe('0', 0))
    #     f.new_task('1', 1)
    #     f.get_task_by_id(1).set_time(0)
    #     f.check_off(1)
    #     self.assertEquals(f.count, 2)
    #     self.assertEquals(f.get_task_by_id(1).reveal_time, 1)

    def test_feed_push_from_today(self):
        f = Spoonfeed()
        f.new_task('0', 0)
        f.push_from_today(0, 100)
        self.assertLessEqual(99, f.get_task_by_id(0).reveal_time - time.time())
        self.assertGreaterEqual(100, f.get_task_by_id(0).reveal_time - time.time())
        f.new_task('1', 0)
        f.set_unit(100)
        f.push_from_today(1, 1)
        self.assertLessEqual(99, f.get_task_by_id(1).reveal_time - time.time())
        self.assertGreaterEqual(100, f.get_task_by_id(1).reveal_time - time.time())

    def test_feed_act_on_computer_input(self):
        f = Spoonfeed()
        f.act_on_computer_input("new_task my task,-1,3")
        t = f.get_task_by_id(0)
        self.assertEquals(t.name, "my task")
        self.assertEquals(t.interval, -1)
        self.assertEquals(t.reveal_time, 3)

        f.act_on_computer_input("set_time 0,2")
        self.assertEquals(t.reveal_time, 2)

        f.act_on_computer_input("remove 0")
        self.assertIsNone(f.get_task_by_id(0))

        f.act_on_computer_input("set_unit 4")
        self.assertEquals(f.unit, 4)

    def remove_time(self, in_str):
        time_len = len(in_str.split(' ')[0])
        return in_str[time_len+1:]

    def test_feed_process_human_input(self):
        f = Spoonfeed()
        self.assertEquals(self.remove_time(f.process_human_input("nt my task"))[:20], "new_task my task,-1,")
        f.new_task("my_task")
        self.assertEquals(self.remove_time(f.process_human_input("remove my_task")), "remove2 0")
        f.new_task("my other task")
        self.assertEquals(self.remove_time(f.process_human_input("check_off my other task")), "check_off 1")
        f.new_task("my third task")
        self.assertEquals(self.remove_time(f.process_human_input("pft my third task,3"))[:11], "set_time 2,")
        self.assertEquals(self.remove_time(f.process_human_input("su 3")), "set_unit 3")

    def test_hood_log(self):
        log("new_task my task", "test_logs.txt")
        with open("test_logs.txt", 'r') as test_logs:
            self.assertEquals(test_logs.readline(), "new_task my task\n")
        open("test_logs.txt", 'w').close()

    def test_hood_initialize(self):
        f = Spoonfeed('test_logs.txt')
        f.act_on_human_input("new_task zero,0,0")
        f.act_on_human_input("new_task one,1,1")
        f.act_on_human_input("new_task two,2,2")
        f.act_on_human_input("remove one")
        f1 = Spoonfeed('test_logs.txt')
        initialize(f1)
        open('test_logs.txt', 'w').close()
