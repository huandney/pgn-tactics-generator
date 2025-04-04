import logging
from operator import methodcaller

import chess
import chess.engine

from modules.bcolors.bcolors import bcolors
from modules.puzzle.analysed import analysed


class position_list:
    def __init__(self, position, engine, info_handler, player_turn=True, best_move=None, evaluation=None, strict=True):
        self.position = position.copy()
        self.engine = engine
        self.info_handler = info_handler
        self.player_turn = player_turn
        self.best_move = best_move
        self.evaluation = evaluation
        self.next_position = None
        self.analysed_legals = []
        self.strict = strict

    def move_list(self):
        # If there is no better move, return empty list
        if self.best_move is None:
            return []
            
        # If it is the losing side's turn (player_turn=False) and this would be the last move
        # in the sequence, simply do not include it in the list
        if not self.player_turn and (self.next_position is None or 
                                    self.next_position.ambiguous() or 
                                    self.next_position.position.is_game_over()):
            return []
        
        # Normal case - this move should be included
        if self.next_position is None or self.next_position.ambiguous() or self.next_position.position.is_game_over():
            return [self.best_move.move.uci()]
        else:
            return [self.best_move.move.uci()] + self.next_position.move_list()

    def category(self):
        if self.next_position is None:
            if self.position.is_game_over():
                return 'Mate'
            else:
                return 'Material'
        else:
            return self.next_position.category()

    def generate(self, depth):
        logging.debug(bcolors.WARNING + str(self.position) + bcolors.ENDC)
        logging.debug(bcolors.OKBLUE + 'Material Value: ' + str(self.material_difference()) + bcolors.ENDC)
        has_best = self.evaluate_best(depth)
        if self.player_turn:
            self.evaluate_legals(depth)
        if has_best and not self.ambiguous() and not self.game_over():
            logging.debug(bcolors.OKGREEN + "Going Deeper:")
            logging.debug("   Ambiguous: " + str(self.ambiguous()))
            logging.debug("   Game Over: " + str(self.game_over()))
            logging.debug("   Has Best Move: " + str(has_best) + bcolors.ENDC)
            self.next_position.generate(depth)
        else:
            logging.debug(bcolors.WARNING + "Not Going Deeper:")
            logging.debug("   Ambiguous: " + str(self.ambiguous()))
            logging.debug("   Game Over: " + str(self.game_over()))
            logging.debug("   Has Best Move: " + str(has_best) + bcolors.ENDC)

    def evaluate_best(self, depth):
        logging.debug(bcolors.OKGREEN + "Evaluating Best Move...")

        self.best_move = self.engine.play(self.position, chess.engine.Limit(depth=depth), info=chess.engine.INFO_ALL)

        if self.best_move.move is not None:
            self.evaluation = self.best_move.info['score'].relative
            self.next_position = position_list(self.position.copy(),
                                               self.engine,
                                               self.info_handler,
                                               not self.player_turn,
                                               strict=self.strict)
            self.next_position.position.push(self.best_move.move)
            logging.debug("Best Move: " + self.best_move.move.uci() + bcolors.ENDC)
            logging.debug(bcolors.OKBLUE + "   CP: " + str(self.evaluation.score()))
            logging.debug("   Mate: " + str(self.evaluation.mate()) + bcolors.ENDC)
            return True
        else:
            logging.debug(bcolors.FAIL + "No best move!" + bcolors.ENDC)
            return False

    def evaluate_legals(self, depth):
        logging.debug(bcolors.OKGREEN + "Evaluating Legal Moves..." + bcolors.ENDC)
        for i in self.position.legal_moves:
            position_copy = self.position.copy()
            position_copy.push(i)

            info = self.engine.analyse(position_copy, chess.engine.Limit(depth=depth))
            self.analysed_legals.append(analysed(i, info["score"].relative))

        self.analysed_legals = sorted(self.analysed_legals, key=methodcaller('sort_val'))
        for i in self.analysed_legals[:3]:
            logging.debug(bcolors.OKGREEN + "Move: " + str(i.move.uci()) + bcolors.ENDC)
            logging.debug(bcolors.OKBLUE + "   CP: " + str(i.evaluation.score()))
            logging.debug("   Mate: " + str(i.evaluation.mate()))
        logging.debug("... and " + str(max(0, len(self.analysed_legals) - 3)) + " more moves" + bcolors.ENDC)

    def material_difference(self):
        return sum(v * (len(self.position.pieces(pt, True)) - len(self.position.pieces(pt, False))) for v, pt in
                   zip([0, 3, 3, 5.5, 9], chess.PIECE_TYPES))

    def material_count(self):
        return chess.popcount(self.position.occupied)

    def is_complete(self, category, color, first_node, first_val):
        if self.next_position is not None:
            if ((category == 'Mate' and not self.ambiguous())
                    or (category == 'Material' and self.next_position.next_position is not None)):
                return self.next_position.is_complete(category, color, False, first_val)

        if category == 'Material':
            if color:
                if (self.material_difference() > 0.2
                        and abs(self.material_difference() - first_val) > 0.1
                        and first_val < 2
                        and self.evaluation.mate() is None
                        and self.material_count() > 6):
                    return True
                else:
                    return False
            else:
                if (self.material_difference() < -0.2
                        and abs(self.material_difference() - first_val) > 0.1
                        and first_val > -2
                        and self.evaluation.mate() is None
                        and self.material_count() > 6):
                    return True
                else:
                    return False
        else:
            if self.position.is_game_over() and self.material_count() > 6:
                return True
            else:
                return False

    def ambiguous(self):
        # If strict == False then it will generate more tactics but  more ambiguous
        move_number = 1 if self.strict else 2
        if len(self.analysed_legals) > 1:
            if (self.analysed_legals[0].evaluation.score() is not None
                    and self.analysed_legals[1].evaluation.score() is not None):
                if (self.analysed_legals[0].evaluation.score() > -210
                        or self.analysed_legals[move_number].evaluation.score() < -90):
                    return True
            if (self.analysed_legals[0].evaluation.mate() is not None
                    and self.analysed_legals[1].evaluation.mate() is not None):
                if (self.analysed_legals[0].evaluation.mate() < 1
                        and self.analysed_legals[1].evaluation.mate() < 1):
                    return True
            if self.analysed_legals[0].evaluation.is_mate() and not self.analysed_legals[1].evaluation.is_mate():
                if self.analysed_legals[1].evaluation.score() < -200:
                    return True
        return False

    def game_over(self):
        return self.next_position.position.is_game_over()
