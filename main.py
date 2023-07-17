import kivy
from kivy.app import App
from kivy.uix.label import Label
from Game import Game

class MyApp(App):
    def build(self):
        game = Game.startGame(self)        
        return Label(text=str(game.player.bottom))

if __name__ == '__main__':
    MyApp().run()