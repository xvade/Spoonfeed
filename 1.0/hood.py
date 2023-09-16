import time
from classes import *
import re
import tests


def process_input(prompt: str):
    command = prompt.split(' ')[0]
    start = len(command)
    inputs = [i.strip() for i in prompt[start:].split(',')]
    return command, inputs


def execute_command(command: str, inputs: [str], feed, id_count, path=''):
    if command == "close" or command == 'c':
        exit()

    elif command == "show" or command == 's':
        if len(inputs) == 1 and inputs[0] != '':
            feed.show(int(inputs[0])*feed.unit)
        else:
            feed.show()

    elif command == "showall" or command == 'sa':
        feed.show_all()

    elif command == "debug" or command == 'd':
        feed.debug()

    elif command == "checkoff" or command == 'co':
        feed.check_off_log(inputs[0], time.time(), path)

    elif command == "push" or command == 'p':
        feed.push_log(inputs[0], time.time(), int(inputs[1]) * feed.unit, path)

    elif command == "advance" or command == 'a':
        feed.advance_log(inputs[0], time.time(), int(inputs[1]) * feed.unit, path)

    elif command == "newtask" or command == 'nt':
        if len(inputs) == 1:
            feed.new_item_log(id_count, inputs[0], 1000000000000, time.time(), path)
        if len(inputs) == 2:
            feed.new_item_log(id_count, inputs[0], int(inputs[1]) * feed.unit, time.time(), path)
        if len(inputs) == 3:
            feed.new_item_log(id_count, inputs[0], int(inputs[1]) * feed.unit, time.time() + int(inputs[2]) * feed.unit, path)
        id_count += 1

    elif command == "now":
        print(time.time())
    elif command == "test":
        tests.test_all()
    elif command == "unit":
        if len(inputs) == 1 and inputs[0].strip() != '':
            feed.change_unit_log(int(inputs[0]))
        else:
            print(str(feed.unit) + " seconds")

    return feed, id_count


def item_from_str(s: str):
    i = re.findall('^-{(.*)}$', s)[0].split(',')
    return Item(int(i[0]), i[1], int(i[2]), int(i[3]))
