#!/usr/bin/env python3
import square, tree
import itertools, tkinter

def make_square(master, square_command, row, column):
    place = tree.Place(row=row, column=column)
    result = square.Square(
        master,
        (row + column) & 1,
        lambda: square_command(place)
    )
    result.grid(row=row, column=column)
    return result

class Board(tkinter.Frame):
    '''
    This class represents the game board.
    '''
    def __init__(self, master, board_size, square_command):
        '''
        Arguments:
            master:
                the tkinter master of this game board
            board_size:
                the number of squares in a column or row
            square_command:
                a callable for when a square is clicked that takes one
                parameter, a tree.Place that represents the location of the
                square that was clicked
        '''
        super().__init__(master, padx=5, pady=5)
        self._moves = []
        self._last_choices = ()
        # Create the game board using squares.
        board_size_range = range(board_size)
        self.squares = tuple(
            tuple(
                make_square(self, square_command, row, column)
                for column in board_size_range
            ) for row in board_size_range
        )
    def reset_squares(self, starting_rows):
        '''
        Moves all pieces to their starting positions.
        
        Arguments:
            starting_rows:
                the number of rows that are filled with one player's pieces
                at the start of the game
        '''
        if not 0 < starting_rows <= len(self.squares) // 2:
            raise ValueError("Each player is limited to half the board.")
        # Clear the board.
        for row_spots in self.squares:
            for spot in row_spots:
                spot.state = square.SquareState.EMPTY
                spot.activity = square.SquareActivity.INACTIVE
        self._moves.clear()
        self._last_choices = ()
        # The red pieces are at the top.
        for row, row_spots in itertools.islice(
            enumerate(self.squares),
            starting_rows
        ):
            for spot in itertools.islice(row_spots, (row + 1) % 2, None, 2):
                spot.state = square.SquareState.RED
        # The black pieces are at the bottom.
        for row, row_spots in itertools.islice(
            enumerate(self.squares),
            len(self.squares) - starting_rows,
            None
        ):
            for spot in itertools.islice(row_spots, (row + 1) % 2, None, 2):
                spot.state = square.SquareState.BLACK
    def to_tree_state(self):
        '''
        Converts the current positions of pieces on the board to a tree.State.
        '''
        # Find all positions with red and black pieces.
        positions_red = []
        positions_black = []
        for row, row_spots in enumerate(self.squares):
            for column, spot in enumerate(row_spots):
                if spot.state == square.SquareState.RED:
                    positions_red.append(tree.Place(row, column))
                elif spot.state == square.SquareState.BLACK:
                    positions_black.append(tree.Place(row, column))
        # Create the State.
        return tree.State(
            positions_red=frozenset(positions_red),
            positions_black=frozenset(positions_black)
        )
    def square_at(self, place):
        '''
        Returns the square at the given place. Equivalent to
        `squares[place.row][place.column]`.
        
        Arguments:
            place: a tree.Place
        '''
        if isinstance(place, tree.Place):
            return self.squares[place.row][place.column]
        raise ValueError("The place must be a tree.Place.")
    def deactivate_move(self, move):
        '''
        Blindly sets the squares at place_from, place_to, and place_capture to
        inactive. Does not check other moves.
        
        If place_capture is None, it is ignored.
        
        Arguments:
            move: a tree.Move
        '''
        # We could remove place_from, place_to, and place_capture from display
        # individually, but the nice thing about the tuple is that it can be
        # iterated through.
        for place in move:
            if place is not None:
                self.square_at(place).activity = square.SquareActivity.INACTIVE
    def reactivate_last_move(self):
        '''
        Colors the squares to show the last move. If no moves have been made,
        nothing happens.
        '''
        if self._moves:
            self.square_at(self._moves[-1].place_from).activity = \
                square.SquareActivity.MOVE_FROM
            self.square_at(self._moves[-1].place_to).activity = \
                square.SquareActivity.MOVE_TO
            if self._moves[-1].place_capture:
                self.square_at(self._moves[-1].place_capture).activity = \
                    square.SquareActivity.CAPTURED
    def deactivate_last_move(self):
        '''
        This is the opposite of reactivate_last_move. This function removes the
        square coloring that was showing the last move. If no moves have been
        made, nothing happens.
        '''
        if len(self._moves) >= 1:
            self.deactivate_move(self._moves[-1])
    def activate_choices(self, moves):
        '''
        Displays choices for the user to select.
        
        Arguments:
            moves: an iterable of tree.Move objects
        '''
        for i, move in enumerate(moves):
            if isinstance(move, tree.Move):
                if not isinstance(move.place_from, tree.Place):
                    raise ValueError(
                        "Move {}'s place_from must be a tree.Place.".format(i)
                    )
                if not isinstance(move.place_from, tree.Place):
                    raise ValueError(
                        "Move {}'s place_to must be a tree.Place.".format(i)
                    )
                if move.place_capture is not None and \
                    not isinstance(move.place_capture, tree.Place):
                    raise ValueError(
                        "Move {}'s spot to capture must be a tree.Place or "
                        "None.".format(i)
                    )
            else:
                raise ValueError("Move {} must be a tree.Move.".format(i))
        # First, remove the old choices from display.
        for move in self._last_choices:
            self.deactivate_move(move)
        # Hide the last move.
        self.deactivate_last_move()
        # Display the choices.
        for move in moves:
            self.square_at(move.place_from).activity = \
                square.SquareActivity.MOVE_FROM
            self.square_at(move.place_to).activity = \
                square.SquareActivity.MOVE_TO
            if move.place_capture is not None:
                self.square_at(move.place_capture).activity = \
                    square.SquareActivity.CAPTURED
        # Remember these choices so that they can be reset the next time that
        # this function is called.
        self._last_choices = moves
    def deactivate_choices(self):
        '''
        Removes the choices that were last shown by activate_choices.
        '''
        self.activate_choices(())
    def display_move(self, move):
        '''
        Moves a piece on the board. If a piece is already in place_to, then it
        simply gets overwritten and is lost. This function does not check
        whether the move is legal.
        
        Arguments:
            move: a tree.Move
        '''
        if not isinstance(move, tree.Move):
            raise ValueError("The move must be a tree.Move.")
        # Hide the previous move.
        self.deactivate_last_move()
        # Hide the choices.
        self.deactivate_choices()
        # Move the pieces.
        spot_from = self.square_at(move.place_from)
        self.square_at(move.place_to).state = spot_from.state
        spot_from.state = square.SquareState.EMPTY
        if move.place_capture is not None:
            self.square_at(move.place_capture).state = \
                square.SquareState.EMPTY
        self._moves.append(move)
        # Show the activity.
        self.reactivate_last_move()
    def print_move_history(self):
        if self._moves:
            print("Moves so far:")
            for i, move in enumerate(self._moves, start=1):
                print("{:>3}.".format(i), move)
        else:
            print("Moves so far: none")
