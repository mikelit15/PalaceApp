from Deck import Deck
from Card import Card
from AI import AI
from Player import Player

class Game:
    deck = Deck()
    player = Player("User")
    ai = AI()
    
    def startGame(self):
        deck.shuffle()
        player.bottom.extend(deck.deal(3))
        ai.bottom.extend(deck.deal(3))