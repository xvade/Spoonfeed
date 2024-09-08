import threading
from multiprocessing import Process
import tests
import unittest
from colorama import Style, Fore
from classes import *
from hood import *
# from pyshortcuts import make_shortcut
import os


def loop(feed: Spoonfeed):
    in_str = input(Fore.LIGHTCYAN_EX+'> '+Style.RESET_ALL)
    feed.act_on_human_input(in_str)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromModule(tests)
    unittest.TextTestRunner(verbosity=0).run(suite)
    path = "/Users/xvade/dev/Spoonfeed/2.1/"
    homework = "homework"
    # make_shortcut(path + "/main.py", "Spoonfeed")

    f = Spoonfeed(path+'log_book.txt', homework, path+'chance.txt')
    initialize(f)
    while True:
        loop(f)

