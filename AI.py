from Card import Card

class AI:
    def __init__(self):
        self.hand = []
        self.bottom = []
        self.top = []

    def drawCard(self, deck):
        drawnCards = deck.deal(1)
        self.hand.append(drawnCards)
    
    def getHand(self):
        print(f"AI's Hand: ")
        for card in self.hand:
            print(card)
    
    def play_card(self):
        if len(self.hand) > 0:
            return self.hand.pop()
        else:
            return None