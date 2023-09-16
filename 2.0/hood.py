from classes import *


def log(log_str, path):
    with open(path, 'a') as log_book:
        log_book.write(log_str + '\n')


def initialize(sf):
    with open(sf.path) as logs:
        for line in logs.readlines():
            sf.act_on_computer_input(line)
