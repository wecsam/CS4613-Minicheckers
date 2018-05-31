#!/usr/bin/env python3
import common
import atexit, collections, enum, itertools, math, multiprocessing.pool, \
    os.path, pickle, sys, threading, time
sys.setrecursionlimit(3200)
# Limit searching to 14.7 seconds. The project directions impose a limit of 15.
SearchTimeLimit = 14.7

GameEnd = enum.Enum("GameEnd", "NOT_ENDED WIN_RED WIN_BLACK DRAW")
UTILITY_VALUES_TERMINAL = {
    GameEnd.WIN_RED: math.inf,
    GameEnd.WIN_BLACK: -math.inf,
    GameEnd.DRAW: 0.0
}
AIDifficulty = enum.Enum("AIDifficulty", "EASY MEDIUM HARD")
HEURISTIC_WEIGHTS = {
    # Generation 0 - set by exponentiating math.log(18) and dividing by 100
    AIDifficulty.EASY: (0.6979, 0.2415, 0.0835, 0.0289, 0.01, 0.0035),
    # Generation 1 - set by trial and error
    # (0.7465, 0.6698, 0.0000, 0.0699, -1.1656, -0.2536)
    # Generation 2 - set by trial and error - easier than Generation 1
    AIDifficulty.MEDIUM: (0.5495, 0.7160, 0.1225, 0.3750, -0.1995, 1.4420),
    # Generation 3 - set by trial and error - easier than Generation 2
    # (-0.6690, 0.8046, 0.7504, 0.7504, -1.4844, -0.1894)
    # Generation 4 - set by trial and error
    AIDifficulty.HARD: (0.4174, 0.8370, 0.0456, 0.1986, 0.1112, 0.3588)
}
# Place is a pair of ints.
Place = collections.namedtuple("Place", ("row", "column"))
# Vector is a pair of ints.
Vector = collections.namedtuple("Vector", ("delta_row", "delta_column"))
# State is a pair of frozensets of Places.
State = collections.namedtuple("State", ("positions_red", "positions_black"))
# Move is a tuple of three Places.
Move = collections.namedtuple(
    "Move",
    ("place_from", "place_to", "place_capture")
)

VECTORS_RED = (
    Vector(delta_row=1, delta_column=-1),
    Vector(delta_row=1, delta_column=1)
)
VECTORS_BLACK = (
    Vector(delta_row=-1, delta_column=-1),
    Vector(delta_row=-1, delta_column=1)
)

stops = collections.deque()

class Statistics:
    '''
    This class keeps track of the statistics that the project directions say to
    output every time that the alpha-beta search function is invoked.
    '''
    def __init__(self, max_depth=0):
        # The maximum depth of the tree that was seen
        self.max_depth = max_depth
        # The total number of nodes that were generated
        self.nodes = 1
        # The number of times that pruning occurred in the max_value function
        self.prunes_in_max = 0
        # The number of times that pruning occurred in the min_value function
        self.prunes_in_min = 0
    def accumulate(self, other):
        '''
        Combines another instance of Statistics with this one.
        '''
        self.max_depth = max(self.max_depth, other.max_depth)
        self.nodes += other.nodes
        self.prunes_in_max += other.prunes_in_max
        self.prunes_in_min += other.prunes_in_min

def add_vector(place, vector):
    '''
    Adds a Vector to a Place.
    '''
    return Place(
        row=place.row+vector.delta_row,
        column=place.column+vector.delta_column
    )
def move_result(state, move):
    '''
    Applies a move to a state and returns the new state.
    '''
    cache_key = (state, move)
    try:
        return move_result._cache[cache_key]
    except KeyError:
        pass
    if move.place_from in state.positions_red:
        positions_red = \
            state.positions_red - {move.place_from} | {move.place_to}
        positions_black = state.positions_black - {move.place_capture}
    else:
        positions_red = state.positions_red - {move.place_capture}
        positions_black = \
            state.positions_black - {move.place_from} | {move.place_to}
    result = \
        State(positions_red=positions_red, positions_black=positions_black)
    move_result._cache[cache_key] = result
    return result
def on_board(place, board_size):
    '''
    Returns whether the given place is on the game board.
    
    Arguments:
        place: an instance of Place
        board_size: the number of squares in a row or column on the board
    '''
    return 0 <= place.row < board_size and 0 <= place.column < board_size
def moves_from_place(board_size, state, place_from):
    '''
    Returns a tuple of legal moves from the given place. This function does not
    consider whether a capture is possible elsewhere on the board. If any of
    the legal moves, assuming that no capture is possible elsewhere on the
    board is a capture, then only legal captures will be included. No moves
    that result in a piece leaving the game board will be included.
    
    Arguments:
        board_size: the number of squares in a row or column on the board
        state: an instance of State, which contains the current positions
        place_from: an instance of Place from which these moves will be
    '''
    captures = False
    result = []
    offsets = ()
    place_from_red = False
    # We assume that no spot is occupied by both players.
    # We assume that red moves down and that black moves up.
    if place_from in state.positions_red:
        offsets = VECTORS_RED
        place_from_red = True
    elif place_from in state.positions_black:
        offsets = VECTORS_BLACK
    # Follow each vector. According to the rules, if we can capture a piece,
    # we are compelled to do so.
    for offset in offsets:
        # Add this vector to place_from to get the destination.
        place_to = add_vector(place_from, offset)
        # Make sure that the destination is on the board.
        if on_board(place_to, board_size):
            place_to_red = place_to in state.positions_red
            if place_to_red or place_to in state.positions_black:
                if place_from_red != place_to_red:
                    # There is already a piece there, and it is a different
                    # color than the piece that is being moved. Add the vector
                    # again to get the destination for a capture.
                    place_capture = place_to
                    place_to = add_vector(place_to, offset)
                    if on_board(place_to, board_size) and \
                        place_to not in state.positions_red and \
                        place_to not in state.positions_black:
                        # The space is empty. The capture is possible.
                        if not captures:
                            # Because we are compelled to capture, we can just
                            # forget about all the other moves. They are no
                            # longer legal.
                            captures = True
                            result.clear()
                        result.append(
                            Move(place_from, place_to, place_capture)
                        )
            elif not captures:
                # There is no piece there. We are not being forced to capture.
                result.append(Move(place_from, place_to, None))
    return tuple(result)
def legal_moves(board_size, state, turn_red):
    '''
    Returns a dictionary of all legal moves that the current player can make
    from the given positions of the pieces. The key is the origin of a move,
    and the value is a tuple of instances of Move.
    
    Arguments:
        board_size: the number of squares in a row or column on the board
        state: an instance of State, which contains the current positions
        turn_red: True if it is the red player's turn, False if it the black's
    '''
    cache_key = (board_size, state, turn_red)
    try:
        return legal_moves._cache[cache_key]
    except KeyError:
        pass
    captures_all = False
    result = {}
    for place_from in (
        state.positions_red if turn_red else state.positions_black
    ):
        # Get the possible moves from this position, ignoring whether captures
        # possible elsewhere on the board.
        moves = moves_from_place(board_size, state, place_from)
        if moves:
            # Recall that moves_from_place will either return all captures or
            # no captures. To see whether all the moves are captures or not,
            # we only have to check the first move.
            captures = moves[0].place_capture is not None
            if captures == captures_all:
                # One of two things is true:
                # - We are already only looking for captures, and these moves
                #   are captures.
                # - We are not looking for captures, and these moves are not
                #   captures.
                # In either case, we can simply add these moves to the results.
                result[place_from] = moves
            elif captures:
                # We were not looking for captures, but these moves are
                # captures. Up to this point, the results were not captures,
                # so we must get rid of them.
                result.clear()
                # We can then add these moves to the results.
                result[place_from] = moves
                # Let's also remember that we are now only looking for
                # captures.
                captures_all = True
    legal_moves._cache[cache_key] = result
    return result
def legal_moves_as_tuple(*args, **kwargs):
    '''
    This function does the same thing as legal_moves, except that the return
    value is a single tuple of all the legal moves, rather than a dictionary
    that is organized by the origins of the moves.
    '''
    cache_key = (args, tuple(kwargs.items()))
    try:
        return legal_moves_as_tuple._cache[cache_key]
    except KeyError:
        pass
    result = tuple(
        itertools.chain.from_iterable(legal_moves(*args, **kwargs).values())
    )
    legal_moves_as_tuple._cache[cache_key] = result
    return result
def game_ended(board_size, state):
    '''
    Checks whether the state is terminal (i.e. the game is over).
    '''
    if not state.positions_black:
        return GameEnd.WIN_RED
    if not state.positions_red:
        return GameEnd.WIN_BLACK
    # Check for legal moves that either player can make.
    if not legal_moves(board_size, state, False) and \
        not legal_moves(board_size, state, True):
        # If there are no legal moves, whoever has more pieces wins.
        if len(state.positions_black) > len(state.positions_red):
            return GameEnd.WIN_BLACK
        if len(state.positions_black) < len(state.positions_red):
            return GameEnd.WIN_RED
        return GameEnd.DRAW
    return GameEnd.NOT_ENDED
def log_fraction_safe(numerator, denominator, if_top_zero, if_bottom_zero):
    if numerator == denominator:
        return 0.0
    if numerator == 0:
        return if_top_zero
    if denominator == 0:
        return if_bottom_zero
    return math.log(numerator / denominator)
def evaluate_state(board_size, state, turn_red):
    '''
    This is the heuristic evaluation function for cutting off the alpha-beta
    search. It attempts to estimate the utility value of a state. Higher values
    favor the red player, and lower values favor the black player.
    '''
    limit = (board_size // 2) ** 2 + math.ceil(board_size / 2) ** 2
    middle = (board_size - 1) / 2.0
    num_pieces_red = len(state.positions_red)
    num_pieces_black = len(state.positions_black)
    moves_red = legal_moves_as_tuple(board_size, state, True)
    moves_black = legal_moves_as_tuple(board_size, state, False)
    num_moves_red = len(moves_red)
    num_moves_black = len(moves_black)
    num_captures_red = \
        len(moves_red) if moves_red and moves_red[0].place_capture else 0
    num_captures_black = \
        len(moves_black) if moves_black and moves_black[0].place_capture else 0
    # For every red piece, check whether the two spots to the left and right in
    # the row above are occupied (or not even on the board). Then, do the same
    # for the black pieces.
    num_friends_red, num_friends_black = (
        sum(
            1 for place_to in (
                add_vector(place_from, offset)
                for offset in offsets
                for place_from in positions
            ) if not on_board(place_to, board_size) or
                place_to in state.positions_black or
                place_to in state.positions_red
        )
        for positions, offsets in (
            (state.positions_red, VECTORS_BLACK),
            (state.positions_black, VECTORS_RED)
        )
    )
    # Compute a float for the utility value.
    weights = iter(evaluate_state.weights)
    return (
        # The best heuristic is the difference in the number of pieces of each
        # player. If the red player has more pieces, the red player is winning,
        # so the utility value should be higher. The log of the ratio of the
        # numbers of pieces accomplishes this. It is best to have several times
        # the number of pieces as your opponent. A ratio of 1 results in a 0.
        # A ratio with more red pieces results in a positive number. A ratio
        # with more black pieces results in a negative number.
        log_fraction_safe(num_pieces_red, num_pieces_black, -limit, limit) *
        next(weights) +
        # Consider the difference in the number of pieces that cannot be
        # captured either because the spaces behind them are occupied or
        # because they are on the edge of the board. If both spaces are blocked
        # or not on the board, the piece is counted twice.
        log_fraction_safe(num_friends_red, num_friends_black, -limit, limit) *
        next(weights) +
        # Consider the number of moves where the player can capture.
        log_fraction_safe(num_captures_red, num_captures_black, -limit, limit) *
        next(weights) +
        # Consider the number of moves in general.
        log_fraction_safe(num_moves_red, num_moves_black, -limit, limit) *
        next(weights) +
        # Keep pieces near the player's home row.
        sum(
            middle - p.row
            for p in itertools.chain(
                state.positions_red,
                state.positions_black
            )
        ) / middle * next(weights) +
        # Control the middle columns of the board.
        (
            sum(middle - abs(p.column - middle) for p in state.positions_red) -
            sum(middle - abs(p.column - middle) for p in state.positions_black)
        ) / middle * next(weights)
    )
def cutoff_test(cutoff_depth, board_size, state, turn_red, depth):
    # Check whether the game has ended.
    terminal = game_ended(board_size, state)
    try:
        return UTILITY_VALUES_TERMINAL[terminal]
    except KeyError:
        pass
    # Limit the depth.
    if depth >= cutoff_depth:
        return evaluate_state(board_size, state, turn_red)
    return None
def actions(
    moves,
    cutoff_depth,
    stop,
    turn_red,
    depth,
    board_size,
    state,
    alpha,
    beta
):
    '''
    Generates the available moves and the utility value for each of them.
    '''
    for v_move_new in moves:
        v_new, _, statistics_new = minimax_value(
            cutoff_depth,
            stop,
            turn_red,
            depth,
            board_size,
            move_result(state, v_move_new),
            alpha,
            beta
        )
        if stop.is_set():
            break
        yield v_new, v_move_new, statistics_new
def iactions(
    moves,
    cutoff_depth,
    stop,
    turn_red,
    depth,
    board_size,
    state,
    alpha,
    beta
):
    '''
    This is like actions, but a pool of workers is used to speed things up.
    Also, there is no longer any guarantee that the moves will be yielded in
    the order that they are in in the moves argument.
    '''
    for v_move_new, (v_new, _, statistics_new) in iactions.pool.imap(
        lambda v_move_new: (
            v_move_new,
            minimax_value(
                cutoff_depth,
                stop,
                turn_red,
                depth,
                board_size,
                move_result(state, v_move_new),
                alpha,
                beta
            )
        ),
        moves
    ):
        if stop.is_set():
            break
        yield v_new, v_move_new, statistics_new
def minimax_value(
    cutoff_depth,
    stop,
    turn_red,
    depth,
    board_size,
    state,
    alpha,
    beta
):
    '''
    When turn_red is True, this function is called from alpha_beta_search or
    min_value when it is the red player's turn. Higher utility values favor the
    red player.
    
    When turn_red is False, this function is called from alpha_beta_search or
    turn_red when it is the black player's turn. Lower utility values favor
    the black player.
    
    Arguments:
        cutoff_depth:
            The depth of the search tree at which to stop expanding nodes and
            to use the evaluation function
        stop:
            A threading.Event, which, when set, will cause the search to stop.
            After this is set, do not use the return values from this function.
        turn_red:
            True if it is the red player's turn
        depth:
            The depth of the search tree so far (should be 0 for the root)
        board_size:
            The number of squares in a row or column on the board
        state:
            A State from which the move should be made
        alpha, beta:
            Used for alpha-beta pruning (should be -inf and inf for the root)
    '''
    statistics = Statistics(depth)
    if stop.is_set():
        return 0.0, None, statistics
    # Check for a cached result.
    cache_key = \
        (turn_red, board_size, state, alpha, beta, evaluate_state.weights)
    try:
        return minimax_value._cache[cache_key]
    except KeyError:
        pass
    # If we are too deep or we reached a terminal state, do not expand.
    v = cutoff_test(cutoff_depth, board_size, state, turn_red, depth)
    if v is not None:
        return v, None, statistics
    # If turn_red is True, find the action that results in the maximum utility
    # value. If turn_red is False, find the action the results in the minimum
    # utility value.
    v = UTILITY_VALUES_TERMINAL[
        GameEnd.WIN_BLACK if turn_red else GameEnd.WIN_RED
    ]
    v_move = None
    moves = legal_moves_as_tuple(board_size, state, turn_red)
    # If this is the root node and there is only one legal move, just do it.
    if depth == 0 and len(moves) == 1:
        return 0.0, moves[0], statistics
    # Evaluate each move.
    for v_new, v_move_new, statistics_new in (
        # If iactions does not guarantee order, it is not deterministic.
        iactions if depth == 0 else actions
    )(
        moves,
        cutoff_depth,
        stop,
        not turn_red,
        depth + 1,
        board_size,
        state,
        alpha,
        beta
    ):
        # If turn_red is True, maximize the minimum utility value.
        # If turn_red is False, minimize the maximum utility value.
        statistics.accumulate(statistics_new)
        if turn_red:
            if v_new >= v:
                v = v_new
                v_move = v_move_new
            # Check for the opportunity to prune.
            if v >= beta:
                statistics.prunes_in_max += 1
                # Instead of returning like in the textbook, just break.
                break
            alpha = max(alpha, v)
        else:
            if v_new <= v:
                v = v_new
                v_move = v_move_new
            # Check for the opportunity to prune.
            if v <= alpha:
                statistics.prunes_in_min += 1
                # Instead of returning like in the textbook, just break.
                break
            beta = min(beta, v)
    # If no actions are possible, this turn is forfeited.
    if not v_move:
        # Don't move any pieces and just go to the other player's turn.
        v_new, _, statistics_new = minimax_value(
            cutoff_depth,
            stop,
            not turn_red,
            depth + 1,
            board_size,
            state,
            alpha,
            beta
        )
        statistics.accumulate(statistics_new)
        return v_new, None, statistics_new
    # Cache the result if the cutoff was not reached.
    if statistics.max_depth < cutoff_depth and not stop.is_set():
        minimax_value._cache[cache_key] = (v, v_move, statistics)
    return v, v_move, statistics
def max_value(cutoff_depth, stop, *args, **kwargs):
    return minimax_value(cutoff_depth, stop, True, *args, **kwargs)
def min_value(cutoff_depth, stop, *args, **kwargs):
    return minimax_value(cutoff_depth, stop, False, *args, **kwargs)
def alpha_beta_gradual_depth(
    result_destination,
    result_protection,
    stop,
    stop_next,
    *minimax_value_args
):
    '''
    Repeatedly runs minimax_value, increasing the cutoff depth each time. After
    each run, a tuple of length 2 is appended to result_destination. The first
    item in the tuple is the cutoff depth, and the second is the return value
    of minimax_value when given that cutoff depth.
    
    Arguments:
        result_destination:
            a list
        result_protection:
            a threading.Condition to protect result_destination
        stop:
            a threading.Event, which, when set, will cause the search to stop
            after a brief delay
        stop_next:
            a threading.Event, which, when set, will cause the search to stop
            after the next result is obtained
        *minimax_value_args:
            a tuple of arguments, except cutoff_depth and stop, to pass to
            minimax_value (in other words, all the arguments after stop)
    '''
    cache_key = (minimax_value_args, evaluate_state.weights)
    try:
        result = alpha_beta_gradual_depth._cache[cache_key]
    except KeyError:
        # Use the default starting cutoff depth.
        starting = alpha_beta_gradual_depth.cutoff_depth_start
    else:
        # Put this result in.
        with result_protection:
            result_destination.clear()
            result_destination.append(result)
            result_protection.notify()
        # Set the starting cutoff depth to the next level.
        starting = result[0] + 2
    # Gradually increase the depth limit.
    for cutoff_depth in range(
        starting,
        alpha_beta_gradual_depth.cutoff_depth_stop,
        2
    ):
        if stop.is_set():
            break
        # Run minimax_value.
        result = (
            cutoff_depth,
            minimax_value(cutoff_depth, stop, *minimax_value_args)
        )
        # If stop is set, then the result may be invalid. Break now and do not
        # add this result to the queue or save it in the cache.
        if stop.is_set():
            break
        # Save the result in the cache.
        alpha_beta_gradual_depth._cache[cache_key] = result
        # Put this result in the queue.
        with result_protection:
            result_destination.clear()
            result_destination.append(result)
            result_protection.notify()
        # If the cutoff was not reached, there is no need to continue.
        if result[1][2].max_depth < cutoff_depth:
            break
        # If we have been asked to stop after the last result, then stop.
        if stop_next.is_set():
            break
def alpha_beta_search(board_size, state, turn_red, job_id=None):
    '''
    Finds the best move for the current player to make. Use game_ended to check
    whether the game has ended before calling this function. It is assumed that
    the current player has legal moves.
    
    Arguments:
        board_size:
            The number of squares in a row or column on the board
        state:
            A State from which the move should be made
        turn_red:
            True if it is the red player's turn
        job_id:
            This value is not used by this function. It is only put in the
            return value.
    
    Returns:
        A tuple of length 2 where the first element is job_id and the second
        element is the Move that the AI picked
    '''
    start_time = time.perf_counter()
    # Set the maximum length of the result queue because we only care about the
    # last result (the result where the cutoff depth is the deepest).
    result_destination = []
    result_protection = threading.Condition()
    # Do the gradual deepening in another thread.
    stop = threading.Event()
    stop_next = threading.Event()
    p = threading.Thread(
        name="Alpha-Beta Gradual Deepening #" + str(job_id),
        target=alpha_beta_gradual_depth,
        args=(
            result_destination,
            result_protection,
            stop,
            stop_next,
            turn_red,
            0,
            board_size,
            state,
            UTILITY_VALUES_TERMINAL[GameEnd.WIN_BLACK],
            UTILITY_VALUES_TERMINAL[GameEnd.WIN_RED]
        )
    )
    # Wait up to the time limit.
    stops.append(stop)
    p.start()
    print("Thinking until the time limit...\r", end="")
    p.join(SearchTimeLimit)
    stops.remove(stop)
    if stop.is_set():
        return job_id, None
    stop_next.set()
    # Make sure that one result is found.
    print("Waiting for at least one result...\r", end="")
    with result_protection:
        result_protection.wait_for(lambda: result_destination)
        cutoff_depth, (v, v_move, statistics) = result_destination[-1]
    # If the thread is still running, tell it to stop.
    if p.is_alive():
        stop.set()
    # Return the results.
    print(
        "Got {}'s move in {:>7.4f} seconds: {:>3} of {:>3} levels, "
        "{:>8} nodes, {:>5} prunes in MAX-VALUE, {:>5} prunes in MIN-VALUE: "
        "final utility value = {:>7.3f}".format(
            "R" if turn_red else "B",
            time.perf_counter() - start_time,
            statistics.max_depth,
            cutoff_depth,
            statistics.nodes,
            statistics.prunes_in_max,
            statistics.prunes_in_min,
            v
        )
    )
    return job_id, v_move
def stop_all():
    '''
    Stops all ongoing alpha-beta searches. Each will return a move if one has
    already been found; otherwise, it will return None. In either case, the
    return value should not be used. Start a new alpha-beta search if needed.
    '''
    for stop in stops:
        stop.set()
def set_difficulty(difficulty):
    '''
    Sets the difficulty of the AI player.
    
    Arguments:
        difficulty: a member of the AIDifficulty enum
    '''
    evaluate_state.weights = HEURISTIC_WEIGHTS[difficulty]

iactions.pool = multiprocessing.pool.ThreadPool()
# Set the default difficulty.
set_difficulty(AIDifficulty.HARD)
# Set the minimum and maximum cutoff depths.
alpha_beta_gradual_depth.cutoff_depth_start = 6
alpha_beta_gradual_depth.cutoff_depth_stop = 3064
# These caches do not need to be saved to a file.
legal_moves._cache = {}
move_result._cache = {}
legal_moves_as_tuple._cache = {}
# Load and save these caches.
CachesToPersist = (
    (minimax_value, common.resource("tree.minimax.pickle")),
    (alpha_beta_gradual_depth, common.resource("tree.search.pickle"))
)
def _cache_load():
    for function, filename in CachesToPersist:
        try:
            with open(filename, "rb") as f:
                function._cache = pickle.load(f)
        except (EOFError, OSError):
            function._cache = {}
def _cache_save():
    for function, filename in CachesToPersist:
        try:
            with open(filename, "wb") as f:
                pickle.dump(function._cache, f)
        except OSError as e:
            print("Warning: unable to save", repr(filename), "-", e)
_cache_load()
atexit.register(_cache_save)
