from classes import *
from multiprocessing import Process
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import tkinter as tk
from PIL import ImageTk, Image
import random
import os
import datetime
import subprocess


screen_width = 1440
screen_height = 900


def log(log_str, path):
    with open(path, 'a') as log_book:
        log_book.write(log_str + '\n')


def random_file(path: str):
    file = random.choice(os.listdir(path))
    while file.startswith('.'):
        file = random.choice(os.listdir(path))
    return file


def display_image(path: str):
    disp = Process(target=_display_image, args=[path])
    disp.start()


def _display_image(path: str = None):
    root = tk.Tk()
    pil_image = Image.open(path)

    if pil_image.height > screen_height:
        scale = pil_image.width/pil_image.height
        pil_image = pil_image.resize((int(900*scale), 900))

    if pil_image.width > screen_width:
        scale = pil_image.height/pil_image.width
        pil_image = pil_image.resize((1440, int(1440*scale)))

    image = ImageTk.PhotoImage(pil_image)

    root.geometry(str(pil_image.width)+'x'+str(pil_image.height))
    canvas = tk.Canvas(root, width=pil_image.width, height=pil_image.height)
    canvas.pack()
    canvas.create_image(pil_image.width/2, pil_image.height/2, image=image)
    root.after(10000, lambda: root.destroy())
    root.mainloop()


def initialize(sf):
    with open(sf.path) as logs:
        for line in logs.readlines():
            sf.act_on_computer_input(line)


def convert_date_to_epoch(date):
    try:
        ymd = [int(i) for i in date.split('-')]
        return datetime.datetime(ymd[0], ymd[1], ymd[2]).timestamp()
    except Exception:
        raise ValueError('Invalid date format, dates should be formatted as YYYY-MM-DD')

