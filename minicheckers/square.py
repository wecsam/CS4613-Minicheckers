#!/usr/bin/env python3
import common
import enum, tkinter

SquareState = enum.Enum("SquareState", "EMPTY RED BLACK")
SquareActivity = enum.Enum(
    "SquareActivity",
    "INACTIVE MOVE_FROM MOVE_TO CAPTURED"
)

images = {}
def load_images():
    '''
    Images cannot be loaded until tkinter.Tk() is called, so they cannot be
    loaded when this module is loaded. Instead, this function should be called
    after tkinter.Tk() is called.
    '''
    images[SquareState.EMPTY] = ""
    images[SquareState.RED] = \
        tkinter.PhotoImage(file=common.resource("red.png"))
    images[SquareState.BLACK] = \
        tkinter.PhotoImage(file=common.resource("black.png"))

class Square(tkinter.Frame):
    '''
    This class represents one square on the game board. Don't forget to call
    load_images() before instantiating this class.
    '''
    def __init__(self, master, shaded, command=None):
        '''
        Arguments:
            master: the tkinter master of this square
            shaded: whether this square should be shaded
            command: a callable to handle when this square is clicked
        '''
        # This frame gives the button its height and width.
        super().__init__(master, width=100, height=100)
        self.pack_propagate(False)
        # This button displays the actual image and responds to clicks.
        self._button = tkinter.Button(self, command=command)
        self._button.pack(expand="yes", fill="both")
        # Shade the square.
        self._activity = SquareActivity.INACTIVE
        self.shaded = shaded
        self.state = SquareState.EMPTY
    @property
    def state(self):
        return self._state
    @state.setter
    def state(self, state):
        try:
            image=images[state]
        except KeyError:
            raise ValueError("Unknown square state", state) from None
        else:
            self._button.configure(image=image)
            self._state = state
    @property
    def activity(self):
        return self._activity
    @activity.setter
    def activity(self, activity):
        if activity == SquareActivity.INACTIVE:
            background = "#ccc" if self.shaded else "#fff"
        elif activity == SquareActivity.MOVE_FROM:
            background = "#ff0"
        elif activity == SquareActivity.MOVE_TO:
            background = "#0c0"
        elif activity == SquareActivity.CAPTURED:
            background = "#f44"
        else:
            raise ValueError("Unknown square activity", activity)
        self._button.configure(background=background)
        self._activity = activity
    @property
    def shaded(self):
        return self._shaded
    @shaded.setter
    def shaded(self, shaded):
        self._shaded = bool(shaded)
        self.activity = self.activity
