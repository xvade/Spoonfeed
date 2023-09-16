import time
from hood import *


class Spoonfeed:
    def __init__(self, path="test_logs.txt"):
        self.feed = []
        self.count = 0
        self.unit = 1
        self.path = path

    def __eq__(self, other):
        return self.feed == other.feed and self.count == other.count and self.unit == other.unit and self.path == other.path

    def str_to_command(self, in_str):
        command = in_str.split(' ')[0]
        args = [arg.strip() for arg in in_str[len(command):].split(',') if arg.strip() != '']
        return command, args

    def process_human_input(self, in_str):
        comp_str = ''
        command, args = self.str_to_command(in_str)

        if command == "new_task" or command == 'nt':
            comp_str = 'new_task ' + args[0] + ','
            if len(args) == 2:
                comp_str += args[1]
            else:
                comp_str += '-1'
            comp_str += ',' + str(time.time())

        elif command == "remove" or command == 'r':
            comp_str = "remove " + str(self.get_task_by_name_timeframe(args[0], time.time()).id)

        elif command == "check_off" or command == 'co':
            t = self.get_task_by_name_timeframe(args[0], time.time())
            if t.interval == -1:
                comp_str = "remove " + str(t.id)
            else:
                comp_str = "set_time " + str(t.id) + "," + str(t.reveal_time + t.interval)

        elif command == "push_from_today" or command == 'pft':
            t = self.get_task_by_name_timeframe(args[0], time.time())
            comp_str = "set_time " + str(t.id) + ',' + str(time.time() + float(args[1])*self.unit)

        elif command == "exit" or command == 'e':
            exit()

        elif command == "show" or command == 's':
            self.show()

        elif command == "set_unit" or command == 'su':
            comp_str = "set_unit " + args[0]

        elif command == "unit" or command == 'u':
            print(str(self.unit)+" seconds")

        return comp_str

    def act_on_human_input(self, in_str):
        comp_str = self.process_human_input(in_str)
        if comp_str != '':
            self.act_on_computer_input(comp_str)
            log(comp_str, self.path)

    def act_on_computer_input(self, in_str):
        command, args = self.str_to_command(in_str)

        if command == "new_task":
            self.new_task(name=args[0], interval=int(args[1]), reveal_time=float(args[2]))
        elif command == "set_time":
            self.set_time(id=int(args[0]), new_time=float(args[1]))
        elif command == "remove":
            self.remove(id=int(args[0]))
        elif command == "set_unit":
            self.set_unit(unit=int(args[0]))

    def new_task(self, name, interval=-1, reveal_time=time.time()):
        self.feed.append(Task(self.count, name, reveal_time, interval))
        self.count += 1

    def set_unit(self, unit: int):
        self.unit = unit

    def get_task_by_id(self, id:int):
        for task in self.feed:
            if task.id == id:
                return task
        return None

    def set_time(self, id:int, new_time: float):
        self.get_task_by_id(id).set_time(new_time)

    def get_task_by_name_timeframe(self, name: str, after: float):
        for task in self.feed:
            if task.name == name and task.reveal_time < after:
                return task
        return None

    def show(self) -> None:
        for task in self.feed:
            if task.reveal_time < time.time():
                print(task.pretty())

    def remove(self, id: int):
        for i in range(len(self.feed)):
            if self.feed[i].id == id:
                return self.feed.pop(i)
        return None

    def check_off(self, id):
        task = self.get_task_by_id(id)
        if task.interval == -1:
            self.remove(id)
        else:
            task.set_time(task.reveal_time + task.interval)

    def push_from_today(self, id, amount):
        self.get_task_by_id(id).set_time(time.time() + amount * self.unit)


class Task:
    def __init__(self, id, name, reveal_time=time.time(), interval=-1):
        self.id = id
        self.name = name
        self.reveal_time = reveal_time
        self.interval = interval

    def __eq__(self, other):
        return self.id == other.id and self.name == other.name and self.reveal_time == other.reveal_time and self.interval == other.interval

    def set_time(self, new: float) -> None:
        self.reveal_time = new

    def pretty(self) -> str:
        return "- " + self.name
