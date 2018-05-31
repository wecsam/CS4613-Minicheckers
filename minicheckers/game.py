#!/usr/bin/env python3
import board, common, tree
import threading, tkinter, tkinter.messagebox
BOARD_SIZE = 6

def radio_boolean(master, variable, false_text, true_text, heading=None):
    '''
    Creates two radio buttons whose values are False and True. The radio button
    whose value is False will go first. The heading and both radio buttons will
    be packed in the master widget.
    
    Arguments:
        master:
            the tkinter master widget
        variable:
            the tkinter BooleanVar that will always be set to the value of the
            currently-selected radio button
        false_text:
            the text that will go next to the radio button whose value is False
        true_text:
            the text that will go next to the radio button whose value is True
        heading:
            some optional text that will go before the radio buttons
    '''
    if heading is not None:
        tkinter.Label(master, text=heading, anchor="w").pack(fill="both")
    tkinter.Radiobutton(
        master,
        text=false_text,
        variable=variable,
        value=False,
        anchor="w"
    ).pack(fill="both")
    tkinter.Radiobutton(
        master,
        text=true_text,
        variable=variable,
        value=True,
        anchor="w"
    ).pack(fill="both")
def alert(title, text):
    tkinter.messagebox.showinfo(title, text)

class Game(tkinter.Frame):
    def __init__(self, master=None):
        super().__init__(master, padx=5, pady=5)
        self._move_to = {}
        self._legal_moves = {}
        # These sets and locks manage simultaneous ongoing alpha-beta searches.
        self._cpu_next_id = 0
        self._cpu_lock = threading.RLock()
        self._cpu_to_ignore = set()
        self._cpu_running = set()
        # Start in the game over state so that the user can change options
        # before clicking New Game.
        self._game_over = True
        # This lock will be used to prevent simultaneous inputs from the user
        # and from the AI.
        self._lock_input = threading.RLock()
        # Create the game board.
        self._board = board.Board(self, BOARD_SIZE, self.square_command)
        self._board.grid(row=0, column=0)
        # Create the control panel.
        self._controls = tkinter.Frame(self, padx=5, pady=5)
        self._controls.grid(row=0, column=1)
        # Create the human/CPU toggles. The default, according to the project
        # directions, is that red is the computer and that black is the human.
        self._cpu_red = tkinter.BooleanVar()
        self._cpu_red.set(True)
        self._cpu_red.trace("w", self.handle_turn_change)
        radio_boolean(
            self._controls,
            self._cpu_red,
            "Human",
            "Computer",
            "Red is..."
        )
        self._cpu_black = tkinter.BooleanVar()
        self._cpu_black.set(False)
        self._cpu_black.trace("w", self.handle_turn_change)
        radio_boolean(
            self._controls,
            self._cpu_black,
            "Human",
            "Computer",
            "Black is..."
        )
        # Create the turn toggle. The instructions say that the human should be
        # able to choose whether to play first or second, but we will default
        # to the human playing first. If the human wants to play second, he or
        # she can simply flip this toggle.
        self._turn_black = tkinter.BooleanVar()
        self._turn_black.set(True)
        self._turn_black.trace("w", self.handle_turn_change)
        radio_boolean(
            self._controls,
            self._turn_black,
            "Red to move",
            "Black to move",
            "Current turn:"
        )
        # Create the difficulty selector.
        self._difficulty = tkinter.StringVar()
        self._difficulty.set(tree.AIDifficulty.HARD.name) # the default is HARD
        self._difficulty.trace("w", self.handle_difficulty_change)
        self._difficulty_controls = (
            tkinter.Label(
                self._controls,
                text="Difficulty:",
                anchor="w"
            ),
            tkinter.Radiobutton(
                self._controls,
                text="Easy",
                variable=self._difficulty,
                value=tree.AIDifficulty.EASY.name,
                anchor="w"
            ),
            tkinter.Radiobutton(
                self._controls,
                text="Medium",
                variable=self._difficulty,
                value=tree.AIDifficulty.MEDIUM.name,
                anchor="w"
            ),
            tkinter.Radiobutton(
                self._controls,
                text="Hard",
                variable=self._difficulty,
                value=tree.AIDifficulty.HARD.name,
                anchor="w"
            )
        )
        for w in self._difficulty_controls:
            w.pack(fill="both")
        # Create the New Game button.
        tkinter.Button(
            self._controls,
            text="New Game",
            command=self.new_game
        ).pack(pady=10)
        # Create the status label.
        self._label_status = tkinter.Label(
            self._controls,
            text="Start a game!",
            anchor="w"
        )
        self._label_status.pack(fill="both")
    def destroy(self, *args, **kwargs):
        super().destroy(*args, **kwargs)
        self.cpu_ignore_running()
    @property
    def turn_black(self):
        '''
        Returns whether it is the black player's turn. If it is the red
        player's turn, then the result is False.
        '''
        return self._turn_black.get()
    @turn_black.setter
    def turn_black(self, value):
        '''
        This function lets you set whose turn it is. Pass in True to make it
        the black player's turn, or pass in False to make it the red player's
        turn. This automatically triggers a refresh of the legal moves.
        '''
        # The refresh is triggered automatically because we registered the
        # refresh function as a callback to _turn_black in __init__.
        self._turn_black.set(value)
    @property
    def cpu_red(self):
        return self._cpu_red.get()
    @cpu_red.setter
    def cpu_red(self, value):
        self._cpu_red.set(value)
    @property
    def cpu_black(self):
        return self._cpu_black.get()
    @cpu_black.setter
    def cpu_black(self, value):
        self._cpu_black.set(value)
    @property
    def turn_cpu(self):
        '''
        Returns True in either case:
        - It is the black player's turn, and the black player is the computer.
        - It is the red player's turn, and the red player is the computer.
        '''
        return self.cpu_black if self.turn_black else self.cpu_red
    def new_game(self):
        '''
        Starts a new game.
        '''
        with self._lock_input:
            print(
                "New game!",
                "Black" if self.turn_black else "Red", "moves first."
            )
            self._game_over = False
            self._board.reset_squares(2)
            self.handle_turn_change()
    def take_turn(self):
        '''
        If it is the black player's turn, this will make it the red player's
        turn. If it is the red player's turn, this will make it the black
        player's turn. This automatically triggers a refresh of the legal
        moves.
        '''
        self.turn_black = not self.turn_black
    def refresh_legal_moves(self):
            current_state = self._board.to_tree_state()
            self._legal_moves = tree.legal_moves(
                BOARD_SIZE,
                current_state,
                not self.turn_black
            )
            return current_state
    def handle_turn_change(self, *args):
        # This is the callback for when the current player changes or a player
        # is switched from being a computer to being a human or back.
        if not self._game_over:
            # Stop the AI.
            self.cpu_ignore_running()
            # Refresh the legal moves for the current player.
            current_state = self.refresh_legal_moves()
            # Check whether the game is over.
            game_ended = tree.game_ended(BOARD_SIZE, current_state)
            if game_ended == tree.GameEnd.NOT_ENDED:
                # Make sure that there are legal moves for the current player.
                # If there are not, then this player forfeits his or her turn.
                if not self._legal_moves:
                    self.take_turn()
                    # This function is not automatically triggered in this
                    # case, so we just call it explicitly.
                    current_state = self.refresh_legal_moves()
                # If the current player is the computer, do the AI stuff.
                if self.turn_cpu:
                    self.cpu_start(current_state)
            elif game_ended == tree.GameEnd.WIN_RED:
                self._game_over = True
                print("Game over: red victory")
                alert("Game Over", "Red wins!")
            elif game_ended == tree.GameEnd.WIN_BLACK:
                self._game_over = True
                print("Game over: black victory")
                alert("Game Over", "Black wins!")
            else:
                self._game_over = True
                print("Game over: draw")
                alert("Game Over", "Draw.")
            # Update the text in the status label below the New Game button.
            self._label_status.config(
                text="Game over" if self._game_over else (
                    "Thinking" if self.turn_cpu else "Ready"
                )
            )
            # Disable the difficulty controls if the computer is playing.
            state = \
                "disabled" \
                if self.turn_cpu and not self._game_over else \
                "normal"
            for w in self._difficulty_controls:
                w.config(state=state)
    def handle_difficulty_change(self, *args):
        # This is the callback for when the user changes the AI difficulty.
        tree.set_difficulty(tree.AIDifficulty[self._difficulty.get()])
    def do_move(self, move):
        # Move the pieces on the board.
        if move is not None:
            self._board.display_move(move)
        # Change whose turn it is. This checks whether the game is over because
        # the refresh function that is bound to the turn change checks it.
        self.take_turn()
    def cpu_start(self, current_state):
        # Get the next job ID number.
        with self._cpu_lock:
            job_id = self._cpu_next_id
            self._cpu_next_id += 1
            self._cpu_running.add(job_id)
        # Run the alpha-beta search in another thread.
        # This keeps the UI thread responsive.
        threading.Thread(
            target=common.return_passer,
            name="Alpha-Beta Search #" + str(job_id),
            args=(
                tree.alpha_beta_search,
                self.cpu_callback,
                BOARD_SIZE,
                current_state,
                not self.turn_black,
                job_id
            )
        ).start()
    def cpu_ignore_running(self):
        '''
        Causes all results from all AI jobs that are currently running to be
        ignored when they finish.
        '''
        with self._cpu_lock:
            if self._cpu_running:
                print("Canceling jobs:", self._cpu_running)
                # Ignore the results of all running jobs.
                self._cpu_to_ignore |= self._cpu_running
                # Stop the AI.
                tree.stop_all()
    def cpu_callback(self, result):
        # This is the callback function for the AI making its move.
        job_id, move = result
        with self._lock_input:
            # Check whether this job's results should be ignored.
            with self._cpu_lock:
                self._cpu_running.remove(job_id)
                try:
                    self._cpu_to_ignore.remove(job_id)
                except KeyError:
                    pass
                else:
                    # This job's results should be ignored.
                    print("The results from job", job_id, "were ignored.")
                    return
            # This job's results should not be ignored.
            self.do_move(move)
    def square_command(self, place_from):
        # This is the callback function for the user clicking on a square.
        with self._lock_input:
            if self._game_over:
                alert("Game Over", "Click the New Game button to play.")
            else:
                # Check that the current player is a human.
                if self.turn_cpu:
                    alert("No Touching", "The computer is thinking.")
                else:
                    # Check whether this was previously remembered as a square
                    # to which the user is moving a piece.
                    move = self._move_to.get(place_from, None)
                    self._move_to.clear()
                    if move is None:
                        # This is not the destination of a move.
                        # Look for legal moves from here.
                        moves = self._legal_moves.get(place_from, ())
                        # Display them for the user.
                        self._board.activate_choices(moves)
                        # Remember the destinations of the moves from here.
                        for move in moves:
                            self._move_to[move.place_to] = move
                    else:
                        # This is the destination of a move.
                        self.do_move(move)
    def print_move_history(self):
        self._board.print_move_history()
