import os
import time
import random
from hood import *


class Spoonfeed:
    def __init__(self, path="test_logs.txt",
                 homework="homework",
                 chance_path='/Users/xvade/dev/Spoonfeed/2.1/chance.txt'):
        self.feed = []
        self.count = 0
        self.unit = 1
        self.path = path
        self.homework = homework
        self.last_check_off = 0
        self.screen_height = 900
        self.chance_path = chance_path
        self.chance = self.get_chance()
        self.clear_before_printing = True;

    def __eq__(self, other):
        return self.feed == other.feed and self.count == other.count and self.unit == other.unit and self.path == other.path

    def get_chance(self):
        with open(self.chance_path, "r") as f:
            return float(f.read())

    def decrease_chance(self, n):
        self.chance -= n
        with open(self.chance_path, "w") as f:
            f.write(str(self.chance))

    def str_to_command(self, in_str):
        command = in_str.split(' ')[0] if not in_str[0].isdigit() else in_str.split(' ')[1]
        prefix_length = len(command) + (0 if not in_str[0].isdigit() else len(in_str.split(' ')[0]) + 1)
        args = [arg.strip() for arg in in_str[prefix_length:].split(',') if arg.strip() != '']
        return command, args

    def process_human_input(self, in_str):
        comp_str = ''
        command, args = self.str_to_command(in_str)

        if command == "new_task" or command == 'nt':
            if args[0].isnumeric():
                print("Tsk tsk, no number-only names.")
            else:
                comp_str = 'new_task ' + args[0] + ','
                if len(args) == 2:
                    comp_str += str(int(args[1])*self.unit)
                else:
                    comp_str += '-1'
                comp_str += ',' + str(time.time())

        elif command == "remove":
            t = self.get_task_by_name_timeframe_or_id(args[0], time.time())
            if t is not None:
                comp_str = "remove2 " + str(t.id)
            else:
                self.get_task_by_name_timeframe_or_id(args[0], time.time())

        elif command == "check_off" or command == 'co':
            t = self.get_task_by_name_timeframe_or_id(args[0], time.time())
            if t is not None:
                self.last_check_off = time.time()
                # if t.interval == -1:
                comp_str = "check_off " + str(t.id)
                # else:
                #     comp_str = "check " + str(t.id) + "," + str(t.reveal_time + t.interval)
                os.system("afplay hero.m4a")
            else:
                print("No tasks have that name or id... did you make a typo?")

        elif command == "push_by_interval" or command == 'pbi':
            t = self.get_task_by_name_timeframe_or_id(args[0], time.time())
            if t is not None:
                if t.interval == -1:
                    print("That task has an interval of -1, did you mean to remove it?")
                else:
                    comp_str = "set_time " + str(t.id) + "," + str(t.reveal_time + t.interval)
            else:
                print("No tasks have that name or id... did you make a typo?")

        elif command == "push_from_today" or command == 'pft':
            t = self.get_task_by_name_timeframe_or_id(args[0], time.time())
            if t is not None:
                comp_str = "set_time " + str(t.id) + ',' + str(time.time() + float(args[1])*self.unit)
            else:
                print("No tasks have that name or id... did you make a typo?")

        elif command == "push_to_date" or command == 'ptd':
            t = self.get_task_by_name_timeframe_or_id(args[0], time.time())
            if t is not None:
                try:
                    comp_str = "set_time " + str(t.id) + ',' + str(convert_date_to_epoch(args[1]))
                except ValueError as e:
                    print(e)

        elif command == "exit" or command == 'e':
            exit()

        elif command == "show" or command == 's':
            if self.clear_before_printing:
                self.clear()
            if len(args) == 1:
                self.show(int(args[0]))
            else:
                self.show()

        elif command == "set_unit" or command == 'su':
            comp_str = "set_unit " + args[0]

        elif command == "unit" or command == 'u':
            print(str(self.unit)+" seconds")

        elif command == "display" or command == 'd':
            if time.time() - self.last_check_off < 100 and input("You sure? ") == 'y':
                result = random.randint(0, 100)
                print(result)
                if result <= self.chance:
                    display_image(self.homework+'/'+random_file(self.homework))
                self.last_check_off = 0

        elif command == "info" or command == 'i':
            tasks = self.get_tasks_by_name(args[0]) if not args[0].isnumeric() else [self.get_task_by_id(int(args[0]))]
            if len(tasks) == 0 or tasks[0] is None:
                print("No tasks exist with the name or id '" + args[0] + "'.")
            else:
                print("Found " + str(len(tasks)) + " task" + ("s by that name." if len(tasks) > 1 else " by that name."))
                for t in tasks:
                    t.print_info()

        elif in_str == 'clear' or in_str == 'c':
            self.clear()

        elif command == 'random' or command == 'r':
            if self.clear_before_printing:
                self.clear()
            if len(args) == 1:
                options = [task for task in self.feed if task.reveal_time < time.time()]
                random.shuffle(options)
                for t in options[0:int(args[0])]:
                    print(t.pretty())
            else:
                print(random.choice([task for task in self.feed if task.reveal_time < time.time()]).pretty())

        elif command == 'chance' or command == 'ch':
            print(self.chance)

        elif command == 'dec' or command == 'decrease':
            self.decrease_chance(int(args[0]))

        elif in_str != '':
            print("No command detected. Did you mean 'nt "+in_str+"'?")

        return str(time.time()) + ' ' + comp_str if comp_str != '' else comp_str

    def clear(self):
        for i in range(os.get_terminal_size().lines):
            print()

    def act_on_human_input(self, in_str):
        comp_str = ''
        try:
            comp_str = self.process_human_input(in_str)
        except Exception as e:
            print("Bad input, try again.")
            print(e)
        if comp_str != '':
            try:
                self.act_on_computer_input(comp_str)
            except Exception:
                exit("Something went wrong in processing that, logs may be damaged.")
            try:
                log(comp_str, self.path)
            except Exception:
                exit("Error while logging, shutting down to protect records.")

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
        elif command == "check_off":
            self.check_off(int(args[0]))
        elif command == "remove2":
            self.remove(id=int(args[0]))

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

    def get_task_by_name_timeframe_or_id(self, name_or_id: str, before: float):
        if name_or_id.isnumeric():
            return self.get_task_by_id(int(name_or_id))
        for task in self.feed:
            if task.name == name_or_id and task.reveal_time < before:
                return task
        return None

    def get_tasks_by_name(self, name: str):
        out = []
        for task in self.feed:
            if task.name == name:
                out.append(task)
        return out

    def show(self, from_time=0) -> None:
        for task in self.feed:
            if task.reveal_time < time.time()+from_time*self.unit:
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

    def print_info(self):
        print("=====TASK INFO=====")
        print("    NAME: '" + self.name + "'")
        print("      ID: " + str(self.id))
        print("  REVEAL: " + str(self.reveal_time))
        print("DATETIME: " + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.reveal_time)))
        print("  REPEAT: " + ("never" if self.interval == -1 else str(self.interval / (60 * 60 * 24)) + " days"))
        print("===================")
