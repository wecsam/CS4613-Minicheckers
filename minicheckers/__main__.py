#!/usr/bin/env python3
import game, square, tree
import tkinter

print("Mini-Checkers Game by David Tsai")
print("CS 4613 Artificial Intelligence")
print("Prof. Edward Wong")
print("April 2018\n")
root = tkinter.Tk()
root.title("Mini-Checkers")
root.resizable(width=False, height=False)
square.load_images()
application = game.Game(master=root)
application.pack()
root.bind("<F2>", lambda event: application.print_move_history())
print("Press F2 in the game window for a list of moves so far in the game.\n")
root.mainloop()
