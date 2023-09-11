from classes import *
from hood import *
import re
from tqdm import tqdm
from colorama import Fore, Style
import random


def test_all():
    open('test_logs.txt', 'w').close()
    attempts = []
    fails = []
    test(item_init, attempts, fails)
    test(item_eq, attempts, fails)
    test(item_str, attempts, fails)
    test(item_pretty, attempts, fails)
    test(item_check_off, attempts, fails)
    test(item_push, attempts, fails)
    test(item_advance, attempts, fails)
    test(spoonfeed_init, attempts, fails)
    test(spoonfeed_str, attempts, fails)
    test(spoonfeed_new_item, attempts, fails)
    test(spoonfeed_eq, attempts, fails)
    test(spoonfeed_new_item_log, attempts, fails)
    test(spoonfeed_remove_item, attempts, fails)
    test(spoonfeed_remove_item_log, attempts, fails)
    test(spoonfeed_get_item_by_id, attempts, fails)
    test(spoonfeed_change_unit, attempts, fails)

    if len(fails) != 0:
        fail_message = "Test " if len(fails) == 1 else "Tests "
        for i in range(len(fails)-1):
            fail_message += fails[i] + ", "
        fail_message += fails[len(fails)-1] + " failed. Shutting down to avoid data loss."
        exit(fail_message)
    else:
        print(Fore.GREEN + "All tests passed.")
        print(Style.RESET_ALL)

    os.system('afplay /System/Library/Sounds/Hero.aiff')
    return attempts, fails


def test(func, attempts, fails):
    attempts.append(func.__name__)
    if not func():
        fails.append(func.__name__)


def item_init(show_progress=False):
    # noinspection PyBroadException
    try:
        mi = Item(0, "")
        assert mi.id == 0
        assert mi.name == ''
        assert mi.interval == 1000000000000
        assert mi.reveal_time - time.time() <= 100
        for i in tqdm(range(100), "testing classes.py/Item/__init__"):
            mi = Item(i, "s df", i, i)
            assert mi.id == i
            assert mi.name == 's df'
            assert mi.interval == i
            assert mi.reveal_time == i
        return True
    except:
        return False


def item_eq():
    try:
        for i in tqdm(range(100), "testing classes.py/Item/__eq__"):
            mi = Item(i, str(i), i, i)
            oi = Item(i, str(i), i, i)
            assert mi == mi
            assert oi == mi
        return True
    except:
        return False


def item_str():
    try:
        for i in tqdm(range(100), "testing classes.py/Item/__str__"):
            mi = Item(i, "a s", i, i)
            assert item_from_str(str(mi)) == mi
        return True
    except:
        return False


def item_pretty():
    try:
        for i in tqdm(range(100), "testing classes.py/Item/pretty"):
            mi = Item(i, "beauti ful", i, i)
            assert mi.pretty() == "- beauti ful"
        return True
    except:
        return False


def item_check_off():
    try:
        for i in tqdm(range(100), "testing classes.py/Item/check_off"):
            oi = Item(i, "beaut iful", i, i)
            mi = Item(i, "beaut iful", i, i)
            ni = Item(i, "beaut iful", i, 2*i)
            assert mi == oi
            mi.check_off()
            assert mi == ni
        return True
    except:
        return False


def item_push():
    try:
        for i in tqdm(range(100), "testing classes.py/Item/push"):
            mi = Item(i, "beautifu l", i, i)
            ni = Item(i, "beautifu l", i, 6*i)
            amt = 5*i
            mi.push(amt)
            assert mi == ni
        return True
    except:
        return False


def item_advance():
    try:
        for i in tqdm(range(100), "testing classes.py/Item/advance"):
            mi = Item(i, "be aut iful", i, 2*i)
            ni = Item(i, "be aut iful", i, i)
            amt = i
            mi.advance(amt)
            assert mi == ni
        return True
    except:
        return False


def spoonfeed_init():
    try:
        print(Style.RESET_ALL)
        sf = SpoonFeed()
        assert sf.the_list == []
        return True
    except:
        return False


def spoonfeed_str():
    try:
        for j in tqdm(range(100), "testing classes.py/SpoonFeed/__str__"):
            sf = SpoonFeed()
            assert str(sf) == str([str(i) for i in sf.the_list])
        return True
    except:
        return False


def spoonfeed_new_item():
    try:
        for j in tqdm(range(100), "testing classes.py/SpoonFeed/new_item"):
            sf = SpoonFeed()
            the_list = [Item(i * random.randint(1, 10), 'a d f', i * random.randint(1, 10), i * random.randint(1, 10)) for i in range(100)]
            for i in the_list:
                sf.new_item(i.id, i.name, i.interval, i.reveal_time)
            assert sf.the_list == the_list
        return True
    except:
        return False


def spoonfeed_eq():
    try:
        for i in tqdm(range(100), "testing classes.py/SpoonFeed/__eq__"):
            sf = SpoonFeed()
            assert sf == sf
            of = SpoonFeed()
            assert sf == of
            sf.new_item(i, '', i, i)
            assert not sf == of
            of.new_item(i, '', i, i)
            assert sf == of
        return True
    except:
        return False


def spoonfeed_new_item_log():
    try:
        for j in tqdm(range(100), "testing classes.py/SpoonFeed/new_item_log"):
            sf = SpoonFeed()
            for i in range(100):
                sf.new_item_log(random.randint(1, 10)*i, 'a s d f', random.randint(1, 10)*i, random.randint(1, 10)*i, '', 'test_logs.txt')
            with open('test_logs.txt', 'r') as file:
                text = file.readlines()
            of = SpoonFeed()
            for line in text:
                of.eval(line)
            assert of == sf
            open('test_logs.txt', 'w').close()

        return True
    except:
        return False


def spoonfeed_remove_item():
    try:
        for j in tqdm(range(100), "testing classes.py/SpoonFeed/remove_item"):
            sf = SpoonFeed()
            sf.new_item(0, ' ', 1, 1)
            sf.new_item(1, ' ', 1, 1)
            sf.remove_item(0)
            assert len(sf.the_list) == 1
            assert sf.get_item_by_id(1) is not None

        return True
    except:
        return False


def spoonfeed_remove_item_log():
    try:
        for j in tqdm(range(100), "testing classes.py/SpoonFeed/remove_item_log"):
            sf = SpoonFeed()
            for i in range(100):
                sf.new_item_log(i, 'a s d f', random.randint(1, 10)*i, random.randint(1, 10)*i, '', 'test_logs.txt')
                if i % 2 == 0:
                    sf.remove_item_log(i, '', 'test_logs.txt')
            with open('test_logs.txt', 'r') as file:
                text = file.readlines()
            of = SpoonFeed()
            for line in text:
                of.eval(line)
            assert of == sf
            open('test_logs.txt', 'w').close()

        return True
    except:
        return False


def spoonfeed_get_item_by_id():
    try:
        for j in tqdm(range(100), "testing classes.py/SpoonFeed/get_item_by_id"):
            sf = SpoonFeed()
            sf.new_item(0, ' ', 1, 1)
            sf.new_item(1, ' ', 1, 1)
            assert sf.get_item_by_id(1) == Item(1, ' ', 1, 1)
        return True
    except:
        return False


def spoonfeed_push():
    pass


def spoonfeed_push_log():
    pass


def spoonfeed_advance():
    pass


def spoonfeed_advance_log():
    pass


def spoonfeed_check_off():
    pass


def spoonfeed_check_off_log():
    pass


def spoonfeed_change_unit():
    try:
        sf = SpoonFeed()
        sf.new_item(0, 'unit_tester', 0, 0)
        assert sf.unit == 1
        sf.push('unit_tester', 1000000, 100)
        assert sf.get_item_by_id(0).reveal_time == 100
        sf.change_unit(5)
        assert sf.unit == 5
        sf.push('unit_tester', 1000000, 100)
        assert sf.get_item_by_id(0).reveal_time == 600
        sf.change_unit(2)
        sf.advance('unit_tester', 100000, 100)
        assert sf.get_item_by_id(0).reveal_time == 400
        return True
    except:
        return False


def spoonfeed_change_unit_log():
    pass
