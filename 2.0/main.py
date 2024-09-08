import tests
from colorama import Style, Fore
from classes import *
from hood import *
from pyshortcuts import make_shortcut
import os


def loop(f: Spoonfeed):
    in_str = input(Fore.LIGHTCYAN_EX+'> '+Style.RESET_ALL)
    f.act_on_human_input(in_str)
    loop(f)


if __name__ == '__main__':
    tests.test_all()
    path = "/Users/simon/dev/Spoonfeed/2.0/"
    # make_shortcut(path + "/main.py", "Spoonfeed")
    f = Spoonfeed(path+'log_book.txt')
    initialize(f)
    loop(f)

