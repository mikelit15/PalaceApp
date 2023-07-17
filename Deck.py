import random
from Card import Card

class Deck:
    def __init__(self):
        self.cards = []
        self.create_deck()

    def create_deck(self):
        suits = ["Spades", "Hearts", "Diamonds", "Clubs"]
        ranks = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]

        self.cards = [Card(suit, rank) for suit in suits for rank in ranks]

    def shuffle(self):
        random.shuffle(self.cards)

    def deal(self, numCards):
        dealtCards = []
        for x in range(numCards):
            dealtCards.append(self.cards.pop())
        return dealtCards
    
    def __str__(self):
        return f"Deck: {len(self.cards)} cards remaining"

