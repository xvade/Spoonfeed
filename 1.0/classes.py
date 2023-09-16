import time, re, os
from colorama import Style, Fore, Back


class Item:
    def __init__(self, id: int, name: str, interval=1000000000000, reveal_time=time.time()):
        assert id >= 0
        assert "," not in name
        self.id = id
        self.name = name
        self.reveal_time = reveal_time
        self.interval = interval

    def __str__(self):
        return '-{'+str(self.id)+','+self.name+','+str(self.interval)+','+str(self.reveal_time)+'}'

    def __eq__(self, o):
        return self.id == o.id and self.name == o.name and self.reveal_time == o.reveal_time and self.interval == o.interval

    def pretty(self):
        return '- ' + self.name

    def check_off(self):
        self.reveal_time += self.interval

    def push(self, seconds: int):
        self.reveal_time += seconds

    def advance(self, seconds: int):
        self.reveal_time -= seconds


class SpoonFeed:
    def __init__(self):
        self.the_list = []
        self.unit = 1

    def __str__(self):
        return str([str(i) for i in self.the_list])

    def __eq__(self, o):
        return self.the_list == o.the_list

    def new_item(self, id: int, name: str, interval: int, reveal_time: float):
        self.the_list.append(Item(id, name, interval*self.unit, reveal_time))

    def new_item_log(self, id: int, name: str, interval=1000000000000, reveal_time=time.time(), path='', file_name='edit_log.txt'):
        self.new_item(id, name, interval, reveal_time)
        with open(path+file_name, 'a') as edit_log:
            edit_log.write('new_item,'+str(id)+','+name+','+str(interval)+','+str(reveal_time) + '\n')

    def remove_item(self, id: int):
        for item in self.the_list:
            if item.id == id:
                self.the_list.remove(item)

    def remove_item_log(self, id: int, path='', file_name='edit_log.txt'):
        self.remove_item(id)
        with open(path+file_name, 'a') as edit_log:
            edit_log.write('remove,' + str(id) + '\n')

    def get_item_by_id(self, id: int):
        for i in self.the_list:
            if i.id == id:
                return i

    def get_item_by_name_timeframe(self, name: str, late_bound=time.time(), early_bound=0):
        for i in self.the_list:
            if i.name == name and early_bound <= i.reveal_time <= late_bound:
                return i

    def show_all(self):
        print(Fore.BLACK + Back.WHITE)
        for i in self.the_list:
            print(i.pretty())
        print(Style.RESET_ALL)

    def debug(self):
        for i in self.the_list:
            print(str(i))

    def show(self, seconds_from_now=0):
        for i in self.the_list:
            if i.reveal_time <= time.time() + seconds_from_now:
                print(Fore.BLACK + Back.WHITE + i.pretty()+Style.RESET_ALL)

    def push(self, name: str, now: float, seconds: int):
        self.get_item_by_name_timeframe(name, now).push(seconds*self.unit)

    def push_log(self, name: str, now: float, seconds: int, path='', file_name='edit_log.txt'):
        self.push(name, now, seconds)
        with open(path+file_name, 'a') as edit_log:
            edit_log.write('push,' + name + ',' + str(now) + ',' + str(seconds) + '\n')

    def advance(self, name: str, now: float, seconds: int):
        self.get_item_by_name_timeframe(name, now).advance(self.unit*seconds)

    def advance_log(self, name: str, now: float, seconds: int, path='', file_name='edit_log.txt'):
        self.advance(name, now, seconds)
        with open(path+file_name, 'a') as edit_log:
            edit_log.write('advance,' + name + ',' + str(now) + ',' + str(seconds) + '\n')

    def check_off(self, name: str, now: float):
        self.get_item_by_name_timeframe(name, now).check_off()

    def check_off_log(self, name: str, now: float, path='', file_name='edit_log.txt'):
        self.check_off(name, now)
        with open(path+file_name, 'a') as edit_log:
            edit_log.write('checkoff,' + name + ',' + str(now) + '\n')
        os.system('afplay /System/Library/Sounds/Ping.aiff')

    def change_unit(self, val):
        self.unit = val

    def change_unit_log(self, val, path='', file_name='edit_log.txt'):
        self.change_unit(val)
        with open(path+file_name, 'a') as edit_log:
            edit_log.write('unit,' + str(val) + '\n')

    def eval(self, statement: str):
        command = statement.split(',')[0]
        inputs = statement.split(',')[1:]
        if command == "new_item":
            self.new_item(int(inputs[0]), inputs[1], int(inputs[2]), float(inputs[3]))
        elif command == "remove":
            self.remove_item(int(inputs[0]))
        elif command == "push":
            self.push(inputs[0], float(inputs[1]), int(inputs[2]))
        elif command == "advance":
            self.advance(inputs[0], float(inputs[1]), int(inputs[2]))
        elif command == "checkoff":
            self.check_off(inputs[0], float(inputs[1]))
        elif command == "unit":
            self.change_unit(int(inputs[0]))


