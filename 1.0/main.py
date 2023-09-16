import re
from classes import *
from tests import test_all
from hood import *
from colorama import Fore, Style
from pyshortcuts import make_shortcut
import os


def main():
    feed = SpoonFeed()
    if os.getcwd() == "/Users/simon/dev/The_List":
        path = ''
    else:
        path = 'dev/The_List/'

    with open(path+'list.txt', 'r') as the_list:
        lines = the_list.readlines()
        for line in lines:
            data = re.findall('^-{(.*)}$', line)[0].split(',')
            feed.new_item(int(data[0]), data[1], int(data[2]), int(data[3]))
    with open(path+'edit_log.txt', 'r') as edit_log:
        edits = edit_log.readlines()
        for edit in edits:
            feed.eval(edit)
    id_count = feed.the_list[len(feed.the_list)-1].id+1
    loop(feed, id_count, path)


def loop(feed, id_count, path):
    prompt = input('> ').lower()
    command, inputs = process_input(prompt)
    feed, id_count = execute_command(command, inputs, feed, id_count, path)

    loop(feed, id_count, path)


def test():
    test_all()


if __name__ == "__main__":
    print(os.getcwd())
    # os.system('afplay /System/Library/Sounds/Hero.aiff')
    # make_shortcut('main.py', name='Spoon Feed')
    test()
    main()
