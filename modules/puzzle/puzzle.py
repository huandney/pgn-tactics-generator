import chess
import chess.uci
import json
from operator import methodcaller

engine = chess.uci.popen_engine("Stockfish/Linux/stockfish 7 x64")
engine.uci()
info_handler = chess.uci.InfoHandler()
engine.info_handlers.append(info_handler)

class analysed:
    def __init__(self, move, evaluation):
        self.move = move
        self.evaluation = evaluation

    def sign(self, val):
        if val <= 0:
            return -1
        else:
            return 1

    def sort_val(self):
        if self.evaluation.cp is not None:
            return self.evaluation.cp
        elif self.evaluation.mate is not None:
            return self.sign(self.evaluation.mate) * (abs(self.evaluation.mate) + 1) * 10000
        else:
            return 0

class position_list:
    def __init__(self, position, player_turn=True, best_move=None, evaluation=None):
        self.position = position.copy()
        self.player_turn = player_turn
        self.best_move = best_move
        self.evaluation = evaluation
        self.next_position = None
        self.analysed_legals = []

    def move_list(self):
        if self.next_position is None or self.next_position.ambiguous() or self.next_position.position.is_game_over():
            if self.best_move is not None:
                return [self.best_move.bestmove.uci()]
            else:
                return []
        else:
            return [self.best_move.bestmove.uci()] + self.next_position.move_list()

    def category(self):
        if self.next_position is None:
            if self.position.is_game_over():
                return 'Mate'
            else:
                return 'Material'
        else:
            return self.next_position.category()

    def generate(self):
        print(bcolors.WARNING + str(self.position) + bcolors.ENDC)
        print(bcolors.OKBLUE + 'Material Value: ' + str(self.board_value()) + bcolors.ENDC)
        self.evaluate_best()      
        if self.player_turn:
            self.evaluate_legals()
        if not self.player_turn or (not self.ambiguous() and not self.game_over()):
            print(bcolors.OKGREEN + 
                "Going Deeper: PT " + str(self.player_turn) + 
                " A " + str(self.ambiguous()) + 
                " GO " + str(self.game_over()) + bcolors.ENDC)
            self.next_position.generate()
        else:
            print(bcolors.WARNING + 
                "Not Going Deeper: PT " + str(self.player_turn) + 
                " A " + str(self.ambiguous()) + 
                " GO " + str(self.game_over()) + bcolors.ENDC)

    def is_complete(self, category, color):
        if self.next_position is not None:
            return self.next_position.is_complete(category, color)
        
        if category == 'Material':
            if color:
                if self.board_value() > 2:
                    return True
                else:
                    return False
            else:
                if self.board_value() < -2:
                    return True
                else:
                    return False
        else:
            if self.position.is_game_over():
                return True
            else:
                return False

    def evaluate_best(self, nodes=3500000):
        print(bcolors.OKGREEN + "Evaluating Best Move...")
        engine.position(self.position)
        self.best_move = engine.go(nodes=nodes)
        self.evaluation = info_handler.info["score"][1]
        self.next_position = position_list(self.position.copy(), not self.player_turn)
        self.next_position.position.push(self.best_move.bestmove)
        print("Best Move: " + self.best_move.bestmove.uci() + bcolors.ENDC)
        print(bcolors.OKBLUE + "   CP: " + str(self.evaluation.cp))
        print("   Mate: " + str(self.evaluation.mate) + bcolors.ENDC)

    def evaluate_legals(self, nodes=3500000):
        print(bcolors.OKGREEN + "Evaluating Legal Moves..." + bcolors.ENDC)
        for i in self.position.legal_moves:
            position_copy = self.position.copy()
            position_copy.push(i)
            engine.position(position_copy)
            engine.go(nodes=nodes)
            self.analysed_legals.append(analysed(i, info_handler.info["score"][1]))
        self.analysed_legals = sorted(self.analysed_legals, key=methodcaller('sort_val'))
        for i in self.analysed_legals[:3]:
            print(bcolors.OKGREEN + "Move: " + str(i.move.uci()) + bcolors.ENDC)
            print(bcolors.OKBLUE + "   CP: " + str(i.evaluation.cp))
            print("   Mate: " + str(i.evaluation.mate))
        print("... and " + str(max(0, len(self.analysed_legals) - 3)) + " more moves" + bcolors.ENDC)

    def board_value(self):
        total = 0
        for i in chess.SQUARES:
            square = self.position.piece_at(i)
            base_val = 0
            if square is not None:
                if square.piece_type == chess.KNIGHT:
                    base_val = 3
                elif square.piece_type == chess.BISHOP:
                    base_val = 3
                elif square.piece_type == chess.ROOK:
                    base_val = 5.5
                elif square.piece_type == chess.QUEEN:
                    base_val = 9

                if square.color:
                    sign = 1
                else:
                    sign = -1

                total += sign * base_val
        return total

    def ambiguous(self):
        if len(self.analysed_legals) <= 1:
            return False
        elif len(self.analysed_legals) > 1:
            if self.analysed_legals[0].evaluation.cp is not None:
                if self.analysed_legals[1].evaluation.cp is not None:
                    if abs(self.analysed_legals[0].evaluation.cp - self.analysed_legals[1].evaluation.cp) < 250 or self.analysed_legals[1].evaluation.cp < -250:
                        return True
                    else:
                        return False
                else:
                    return False
            if self.analysed_legals[0].evaluation.mate is not None:
                if self.analysed_legals[1].evaluation.mate is not None:
                    if self.analysed_legals[0].evaluation.mate < 0 and self.analysed_legals[1].evaluation.mate < 0:
                        return True
                    else:
                        return False
        return False

    def game_over(self):
        return self.next_position.position.is_game_over()

class puzzle:
    def __init__(self, last_pos, last_move, game_id):
        self.last_pos = last_pos.copy()
        self.last_move = last_move
        self.game_id = game_id
        last_pos.push(last_move)
        self.positions = position_list(last_pos)

    def to_dict(self):
        return {
            'game_id': self.game_id,
            'category': self.positions.category(),
            'last_pos': self.last_pos.fen(),
            'last_move': self.last_move.uci(),
            'move_list': self.positions.move_list()
            }

    def color(self):
        return self.positions.position.turn

    def is_complete(self):
        return self.positions.is_complete(self.positions.category(), self.color())

    def generate(self):
        self.positions.generate()
        if self.is_complete():
            print(bcolors.OKGREEN + "Puzzle is complete" + bcolors.ENDC)
        else:
            print(bcolors.FAIL + "Puzzle incomplete" + bcolors.ENDC)

    def category(self):
        return self.positions.category()

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'