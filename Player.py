from Card import Card

class Player:
    def __init__(self, name):
        self.name = name
        self.hand = []
        self.bottom = []
        self.top = []

    def drawCard(self, deck):
        drawnCards = deck.deal(1)
        self.hand.append(drawnCards)
    
    def getHand(self):
        print(f"{self.name}'s Hand: ")
        for card in self.hand:
            print(card)
    
    def play_card(self):
        if len(self.hand) > 0:
            return self.hand.pop()
        else:
            return None