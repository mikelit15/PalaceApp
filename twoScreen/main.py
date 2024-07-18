import sys
import random
import json
import socket
import threading
import struct
import time
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, \
    QLabel, QDialog, QGridLayout, QRadioButton, QButtonGroup, QSpacerItem, QSizePolicy
from PyQt6.QtGui import QFontMetrics, QPixmap, QIcon
from PyQt6.QtCore import Qt, QCoreApplication, QTimer
import qdarktheme

# Dark Mode Styling
Dark = qdarktheme.load_stylesheet(
    theme="dark",
    custom_colors={
        "[dark]": {
            "primary": "#0078D4",
            "background": "#202124",
            "border": "#8A8A8A",
            "background>popup": "#252626",
        }
    },
) + """
    QMessageBox QLabel {
        color: #E4E7EB;
    }
    QDialog {
        background-color: #252626;
    }
    QComboBox:disabled {
        background-color: #1A1A1C; 
        border: 1px solid #3B3B3B;
        color: #3B3B3B;  
    }
    QPushButton {
    background-color: #0078D4; 
    color: #FFFFFF;           
    border: 1px solid #8A8A8A; 
    }
    QPushButton:hover {
        background-color: #669df2; 
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 #80CFFF, stop:1 #004080);
    }
    QPushButton:pressed {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                    stop:0 #004080, stop:1 #001B3D);
    }
    QPushButton:disabled {
        background-color: #202124; 
        border: 1px solid #3B3B3B;
        color: #FFFFFF;   
    }
"""

RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
VALUES = {'3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 'J': 10, 'Q': 11, 'K': 12, 'A': 13, '2': 14, '10': 15}
CARD_WIDTH = 56
CARD_HEIGHT = 84
BUTTON_WIDTH = 66
BUTTON_HEIGHT = 87

class Server:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(1)
        print(f"Server listening on {self.host}:{self.port}")
        self.client_socket, self.client_address = self.server_socket.accept()
        print(f"Connection from {self.client_address}")
        self.controller = None  # Initialize the controller attribute

        # Start a thread to handle client communication
        threading.Thread(target=self.handle_client).start()

    def handle_client(self):
        while True:
            try:
                data = self.receive_data(self.client_socket)
                if data:
                    self.process_client_data(data)
            except ConnectionResetError:
                print("Connection reset by client")
                break
            except ConnectionAbortedError:
                print("Connection aborted by client")
                break
            except Exception as e:
                print(f"Unexpected error: {e}")
                break
        self.client_socket.close()

    def process_client_data(self, data):
        if data is None:
            print("Received None data from client")
            return
        if data['action'] == 'confirm_top_cards':
            player_index = data['player_index']
            self.controller.players[player_index].topCards = data['topCards']
            self.controller.players[player_index].hand = data['hand']
            self.controller.checkBothPlayersConfirmed()

    def send_to_client(self, data):
        if self.client_socket:
            try:
                serialized_data = json.dumps(data).encode('utf-8')
                self.client_socket.sendall(struct.pack('>I', len(serialized_data)) + serialized_data)
            except Exception as e:
                print(f"Error sending data to client: {e}")
        else:
            print("Client socket is not connected")

    def receive_data(self, sock):
        raw_msglen = self.recvall(sock, 4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        message = self.recvall(sock, msglen)
        if message is None:
            return None
        return json.loads(message)

    def recvall(self, sock, n):
        data = b''
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                return None
            data += packet
        return data

    def close(self):
        self.client_socket.close()
        self.server_socket.close()

class Client:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client_socket.connect((self.host, self.port))
            print("Connected to the server")
            threading.Thread(target=self.handle_server).start()
        except Exception as e:
            print(f"Failed to connect to the server: {e}")

    def handle_server(self):
        while True:
            try:
                data = self.receive_data(self.client_socket)
                if data:
                    self.process_server_data(data)
            except ConnectionResetError:
                print("Connection reset by server")
                break
            except ConnectionAbortedError:
                print("Connection aborted by server")
                break
            except Exception as e:
                print(f"Unexpected error: {e}")
                break
        self.client_socket.close()

    def process_server_data(self, data):
        if data is None:
            print("Received None data from server")
            return
        if data['action'] == 'confirm_top_cards':
            player_index = data['player_index']
            self.controller.players[player_index].topCards = data['topCards']
            self.controller.players[player_index].hand = data['hand']
            self.controller.checkBothPlayersConfirmed()

    def send_to_server(self, data):
        if self.client_socket:
            try:
                serialized_data = json.dumps(data).encode('utf-8')
                self.client_socket.sendall(struct.pack('>I', len(serialized_data)) + serialized_data)
            except Exception as e:
                print(f"Error sending data to server: {e}")
        else:
            print("Client socket is not connected")

    def receive_data(self, sock):
        raw_msglen = self.recvall(sock, 4)
        if not raw_msglen:
            return None
        msglen = struct.unpack('>I', raw_msglen)[0]
        message = self.recvall(sock, msglen)
        if message is None:
            return None
        return json.loads(message)

    def recvall(self, sock, n):
        data = b''
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                return None
            data += packet
        return data

    def close(self):
        self.client_socket.close()

class HomeScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Palace')
        self.setWindowIcon(QIcon(r"_internal\palaceData\palace.ico"))
        self.setGeometry(660, 215, 600, 500)
        layout = QVBoxLayout()
        title = QLabel("Palace")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 36px; font-weight: bold;")
        layout.addWidget(title)

        buttonLayout = QVBoxLayout()

        buttonLayout.addWidget(QLabel(""))
        buttonLayout.addWidget(QLabel(""))

        playButton = QPushButton("Play")
        playButton.setFixedHeight(40)
        playButton.setFixedWidth(275)
        playButton.clicked.connect(self.showPlayerSelectionDialog)
        buttonLayout.addWidget(playButton)

        buttonLayout.addWidget(QLabel(""))

        onlineButton = QPushButton("Online")
        onlineButton.clicked.connect(self.playOnline)
        onlineButton.setFixedWidth(225)
        buttonLayout.addWidget(onlineButton, alignment=Qt.AlignmentFlag.AlignCenter)

        buttonLayout.addWidget(QLabel(""))
        
        rulesButton = QPushButton("Rules")
        rulesButton.clicked.connect(self.showRules)
        rulesButton.setFixedWidth(225)
        buttonLayout.addWidget(rulesButton, alignment=Qt.AlignmentFlag.AlignCenter)

        buttonLayout.addWidget(QLabel(""))

        exitButton = QPushButton("Exit")
        exitButton.clicked.connect(QCoreApplication.instance().quit)
        exitButton.setFixedWidth(225)
        buttonLayout.addWidget(exitButton, alignment=Qt.AlignmentFlag.AlignCenter)

        buttonLayout.addWidget(QLabel(""))

        buttonContainer = QWidget()
        buttonContainer.setLayout(buttonLayout)
        layout.addWidget(buttonContainer, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)
        
    def showPlayerSelectionDialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Number of Players")
        dialog.setGeometry(805, 350, 300, 200)

        layout = QVBoxLayout()

        label = QLabel("How many players?")
        layout.addWidget(label)

        self.radioGroup = QButtonGroup(dialog)
        radioButton2 = QRadioButton("Player vs. CPU")
        radioButton2.setFixedWidth(107)
        radioButton3 = QRadioButton("Player vs. CPU vs. CPU")
        radioButton3.setFixedWidth(150)
        radioButton4 = QRadioButton("Player vs. CPU vs. CPU vs. CPU")
        radioButton4.setFixedWidth(193)

        self.radioGroup.addButton(radioButton2, 2)
        self.radioGroup.addButton(radioButton3, 3)
        self.radioGroup.addButton(radioButton4, 4)

        layout.addWidget(radioButton2)
        layout.addWidget(radioButton3)
        layout.addWidget(radioButton4)
        layout.addWidget(QLabel(""))

        difficultyLabel = QLabel("Select AI Difficulty:")
        layout.addWidget(difficultyLabel)

        self.difficultyGroup = QButtonGroup(dialog)
        easyButton = QRadioButton("Easy")
        easyButton.setFixedWidth(55)
        mediumButton = QRadioButton("Medium")
        mediumButton.setFixedWidth(75)
        hardButton = QRadioButton("Hard")
        hardButton.setFixedWidth(57)
        impossibleButton = QRadioButton("Impossible")
        impossibleButton.setFixedWidth(115)

        self.difficultyGroup.addButton(easyButton, 1)
        self.difficultyGroup.addButton(mediumButton, 2)
        self.difficultyGroup.addButton(hardButton, 3)
        self.difficultyGroup.addButton(impossibleButton, 3)

        layout.addWidget(easyButton)
        layout.addWidget(mediumButton)
        layout.addWidget(hardButton)
        layout.addWidget(impossibleButton)
        layout.addWidget(QLabel(""))
        
        buttonBox = QHBoxLayout()
        okButton = QPushButton("OK")
        cancelButton = QPushButton("Cancel")
        okButton.clicked.connect(lambda: self.startGameWithSelectedPlayers(dialog))
        cancelButton.clicked.connect(dialog.reject)
        buttonBox.addWidget(okButton)
        buttonBox.addWidget(cancelButton)
        layout.addLayout(buttonBox)

        dialog.setLayout(layout)
        dialog.exec()

    def startGameWithSelectedPlayers(self, dialog):
        numPlayers = self.radioGroup.checkedId()
        difficulty = self.difficultyGroup.checkedId()
        if numPlayers in [2, 3, 4]:
            dialog.accept()
            self.hide()
            difficulty_map = {1: 'easy', 2: 'medium', 3: 'hard'}
            difficulty_level = difficulty_map.get(difficulty, 'medium')
            controller = GameController(numPlayers, difficulty_level)  # Start game with selected number of players and difficulty level
            controller.view.show()

    def playOnline(self):
        self.onlineDialog = QDialog(self)
        self.onlineDialog.setWindowTitle("Online Multiplayer")
        self.onlineDialog.setGeometry(835, 400, 250, 150)
        layout = QVBoxLayout()

        hostButton = QPushButton("Host Lobby")
        hostButton.clicked.connect(self.hostLobby)
        layout.addWidget(hostButton)

        layout.addWidget(QLabel())

        joinButton = QPushButton("Join Lobby")
        joinButton.clicked.connect(self.joinLobby)
        layout.addWidget(joinButton)

        layout.addWidget(QLabel())

        closeButton = QPushButton("Close")
        closeButton.setFixedWidth(75)
        closeButton.clicked.connect(self.onlineDialog.accept)
        layout.addWidget(closeButton, alignment=Qt.AlignmentFlag.AlignCenter)

        self.onlineDialog.setLayout(layout)
        self.onlineDialog.exec()

    def hostLobby(self):
        self.onlineDialog.accept()
        self.hide()
        self.server = Server('localhost', 5555)  # Adjust IP and port as needed
        self.controller = GameController(numPlayers=2, difficulty='medium', connection=self.server, is_host=True)  # 2 players for online
        self.server.controller = self.controller  # Set the controller attribute in the server
        self.controller.view.show()

    def joinLobby(self):
        self.onlineDialog.accept()
        self.hide()
        self.client = Client('localhost', 5555)  # Adjust IP and port as needed
        self.controller = GameController(numPlayers=2, difficulty='medium', connection=self.client, is_host=False)  # 2 players for online
        self.controller.view.show()

    def showRules(self):
        rulesDialog = QDialog(self)
        rulesDialog.setWindowTitle("Rules")
        rulesDialog.setGeometry(560, 100, 800, 300)
        rulesDialog.setWindowIcon(QIcon(r"_internal\palaceData\palace.ico"))
        layout = QVBoxLayout()
        rulesLabel = QLabel(
            """<h2>The Pack</h2>
        <ul>
            <li>2-4 players use one standard deck of 52 cards.</li>
        </ul>
        <h2>Rank of Cards</h2>
        <ul>
            <li>A-K-Q-J-9-8-7-6-5-4-3</li>
            <li>The 2 and 10 are special cards that reset the deck.</li>
            <li>The 7 is a special card that reverses the rank hierarchy, the next player ONLY must play a card rank 7 or lower.</li>
        </ul>
        <h2>Object of the Game</h2>
        <ul>
            <li>Play your cards in a pile using ascending order, and the first player to run out of cards wins.</li>
        </ul>
        <h2>The Deal</h2>
        <ul>
            <li>Deal three cards face down to each player. Players are not allowed to look at these cards and must place them
            face down in three columns in front of each player.</li>
            <li>Deal six cards to each player face down. Players may look at these cards in their hand.</li>
            <li>Players select three cards from their hand and place them face up on the three face down cards in front of them.
            Typically, higher value cards are placed face up.</li>
            <li>Place the remaining cards from the deck face down in the center of the table to form the Draw pile.</li>
        </ul>
        <h2>The Play</h2>
        <ul>
            <li>The player with the agreed worst average top cards is the first player and the second player is clockwise or counter clockwise
            with the second worst average top cards.</li>
            <li>The first player plays any card from their hand. You can play multiple cards on your turn, as long as they're all equal to or
            higher than the top pile card.</li>
            <li>Once you have have finished your turn, draw cards from the Draw pile to maintain three cards in your hand at all times.</li>
            <li>You must play a card if you can or pick up the current pile and add it to your hand.</li>
            <li>On their turn, a player can play any 2 card which resets the top pile card to 2, starting the sequence all over.</li>
            <li>On their turn, a player can play the 10 on any card, but it puts the pile into a bomb pile instead of resetting the sequence. The
            player who put the 10 down then draws up to three cards and plays any card.</li>
            <li>If four of the same rank are played in a row, either by one player or multiple players, it clears the pile. Place it in the bomb pile,
            as these cards are out of the game. The player that played the fourth card can then play any card from their hand.</li>
            <li>Play continues around the table until the deck is depleted.</li>
            <li>Once the deck is depleted, players rely solely on the cards in their hand. Keep playing until there are no cards left in your
            hand.</li>
            <li>When it's your turn and you don't have a hand, play one card from your face-up cards in front of you.</li>
            <li>When it's your turn and you've played all your face-up cards, pick a card that's face-down on the table. Don't look at it to choose.
            Simply flip it over. If it plays on the current card by being equal or higher, you can play it. If not, you must pick up the discard pile.</li>
            <li>If you pick up the discard pile, you must play those before continuing to play your face-down cards.</li>
            <li>First player to finish all cards in hand, face-up cards, and face-down cards, wins the game.</li>
        </ul>
        <ul>
            <li>
        </ul>
        """
        )
        rulesLabel.setTextFormat(Qt.TextFormat.RichText)
        rulesLabel.setWordWrap(True)
        rulesLabel.setFixedWidth(800)
        layout.addWidget(rulesLabel)
        closeButton = QPushButton("Close")
        closeButton.clicked.connect(rulesDialog.accept)
        layout.addWidget(closeButton)
        rulesDialog.setLayout(layout)
        rulesDialog.exec()

class Player:
    def __init__(self, name):
        self.name = name
        self.hand = []
        self.bottomCards = []
        self.topCards = []
        self.sevenSwitch = False  # Flag to restrict playable cards to 7 and lower or 2/10 for one turn

    def playCard(self, cardIndex, pile):
        card = self.hand.pop(cardIndex)
        if card[2]:
            card = (card[0], card[1], False, False)
        pile.append(card)
        return card

    def addToHand(self, cards):
        self.hand.extend(cards)

    def pickUpPile(self, pile):
        self.hand.extend(pile)
        pile.clear()

    def hasPlayableCards(self, topPile):
        if self.sevenSwitch:
            return any(VALUES[card[0]] <= 7 or card[0] in ['2', '10'] for card in self.hand)
        else:
            return any(card[0] == '2' or VALUES[card[0]] >= VALUES[topPile[-1][0]] for card in self.hand)

class RealPlayer(Player):
    def __init__(self, name, socket):
        super().__init__(name)
        self.socket = socket

    def send(self, data):
        try:
            self.socket.sendall(data.encode('utf-8'))
        except Exception as e:
            print(f"Error sending data: {e}")

    def receive(self):
        try:
            data = self.socket.recv(1024).decode('utf-8')
            return data
        except Exception as e:
            print(f"Error receiving data: {e}")
            return None

class GameView(QWidget):
    def __init__(self, controller, player_type, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.player_type = player_type
        self.playCardButtons = []
        self.initUI()

    def initUI(self):
        self.setWindowTitle(f'Palace Card Game - {self.player_type}')
        self.setWindowIcon(QIcon(r"_internal\palaceData\palace.ico"))
        self.setGeometry(250, 75, 500, 500)
        self.setFixedSize(1100, 900)

        self.layout = QGridLayout()

        # Center
        self.deckLabel = QLabel()  # Initialize the deck label
        self.deckLabel.setFixedWidth(190)
        self.deckLabel.setVisible(False)
        self.pileLabel = QLabel("\t     Select your 3 Top cards...")
        self.pileLabel.setStyleSheet("border: 0px solid black; background-color: transparent;")
        self.pickUpPileButton = QPushButton("Pick Up Pile")
        self.pickUpPileButton.setFixedWidth(125)
        self.pickUpPileButton.setVisible(False)
        self.pickUpPileButton.clicked.connect(self.controller.pickUpPile)
        self.currentPlayerLabel = QLabel("")

        spacer = QSpacerItem(60, 1, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.consoleLayout = QHBoxLayout()
        self.consoleLayout.addWidget(self.deckLabel, alignment=Qt.AlignmentFlag.AlignCenter)
        self.consoleLayout.addWidget(self.pileLabel, alignment=Qt.AlignmentFlag.AlignCenter)
        self.consoleLayout.addItem(spacer)
        self.consoleLayout.addWidget(self.pickUpPileButton, alignment=Qt.AlignmentFlag.AlignCenter)

        self.centerLayout = QVBoxLayout()
        self.centerLayout.addWidget(QLabel(""))
        self.centerLayout.addWidget(self.currentPlayerLabel, alignment=Qt.AlignmentFlag.AlignCenter)
        self.centerLayout.addLayout(self.consoleLayout)
        self.centerLayout.addWidget(QLabel(""))
        self.centerLayout.addWidget(QLabel(""))

        self.layout.addLayout(self.centerLayout, 4, 4)

        # Player (Bottom)
        self.playerHandLabel = QLabel("Player's Hand")
        self.playerHandLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.playerHandLayout = QHBoxLayout()
        self.topCardsLayout = QHBoxLayout()
        self.bottomCardsLayout = QHBoxLayout()

        self.playerContainer = QVBoxLayout()
        self.playerContainer.addLayout(self.bottomCardsLayout)
        self.playerContainer.addLayout(self.topCardsLayout)
        self.playerContainer.addWidget(self.playerHandLabel)
        self.playerContainer.addLayout(self.playerHandLayout)

        self.layout.addLayout(self.playerContainer, 8, 4)

        # Opponent (Top)
        self.opponentHandLabel = QLabel("Opponent's Hand")
        self.opponentHandLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.opponentHandLayout = QHBoxLayout()
        self.opponentTopCardsLayout = QHBoxLayout()
        self.opponentBottomCardsLayout = QHBoxLayout()

        self.opponentContainer = QVBoxLayout()
        self.opponentContainer.addLayout(self.opponentHandLayout)
        self.opponentContainer.addWidget(self.opponentHandLabel)
        self.opponentContainer.addLayout(self.opponentTopCardsLayout)
        self.opponentContainer.addLayout(self.opponentBottomCardsLayout)

        self.layout.addLayout(self.opponentContainer, 0, 4)

        # Play card buttons layout
        self.confirmButton = QPushButton("Confirm")
        self.confirmButton.setEnabled(False)
        self.confirmButton.clicked.connect(self.confirmTopCardSelection)
        self.layout.addWidget(self.confirmButton, 10, 4)

        self.placeButton = QPushButton("Select A Card")
        self.placeButton.setEnabled(False)
        self.placeButton.clicked.connect(self.controller.placeCard)
        self.placeButton.setVisible(False)
        self.layout.addWidget(self.placeButton, 10, 4)

        self.setLayout(self.layout)

    def updateHand(self, hand, layout, isPlayer=True):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if isPlayer:
            self.controller.playCardButtons = []

        for idx, card in enumerate(hand):
            button = QLabel()
            button.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
            button.setStyleSheet("border: 0px solid black; background-color: transparent;")
            if not card[3]:  # Check if isBottomCard is False
                pixmap = QPixmap(fr"_internal\palaceData\cards\{card[0].lower()}_of_{card[1].lower()}.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                button.setPixmap(pixmap)
            else:
                pixmap = QPixmap(r"_internal\palaceData\cards\back.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                button.setPixmap(pixmap)
            button.setAlignment(Qt.AlignmentFlag.AlignCenter)

            if isPlayer:
                if self.controller.topCardSelectionPhase:
                    button.mousePressEvent = lambda event, idx=idx, btn=button: self.selectTopCard(idx, btn)
                else:
                    try:
                        button.mousePressEvent = lambda event, idx=idx, btn=button: self.controller.prepareCardPlacement(idx, btn)
                    except IndexError:
                        return
                self.controller.playCardButtons.append(button)
            layout.addWidget(button)

    def updatePlayerHand(self, hand):
        self.updateHand(hand, self.playerHandLayout, isPlayer=True)

    def updateOpponentHand(self, hand):
        self.updateHand(hand, self.opponentHandLayout, isPlayer=False)

    def updateTopCardButtons(self, topCards):
        # Clear the layout
        for i in reversed(range(self.topCardsLayout.count())):
            self.topCardsLayout.itemAt(i).widget().deleteLater()

        for card in topCards:
            button = QLabel()
            button.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
            button.setStyleSheet("border: 0px solid black; background-color: transparent;")
            pixmap = QPixmap(f"_internal\palaceData\cards\{card[0].lower()}_of_{card[1].lower()}.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            button.setPixmap(pixmap)
            button.setAlignment(Qt.AlignmentFlag.AlignCenter)
            button.setDisabled(True)
            self.topCardsLayout.addWidget(button)
        if not topCards:
            self.placeholder = QLabel()
            self.placeholder.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
            self.topCardsLayout.addWidget(self.placeholder)

    def updateOpponentTopCardButtons(self, topCards):
        for i in reversed(range(self.opponentTopCardsLayout.count())):
            self.opponentTopCardsLayout.itemAt(i).widget().deleteLater()

        for card in topCards:
            button = QLabel()
            button.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
            button.setStyleSheet("border: 0px solid black; background-color: transparent;")
            pixmap = QPixmap(f"_internal\palaceData\cards\{card[0].lower()}_of_{card[1].lower()}.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            button.setPixmap(pixmap)
            button.setAlignment(Qt.AlignmentFlag.AlignCenter)
            button.setDisabled(True)
            self.opponentTopCardsLayout.addWidget(button)
        if not topCards:
            self.placeholder = QLabel()
            self.placeholder.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
            self.opponentTopCardsLayout.addWidget(self.placeholder)

    def updateBottomCardButtons(self, bottomCards):
        # Clear the layout
        for i in reversed(range(self.bottomCardsLayout.count())):
            self.bottomCardsLayout.itemAt(i).widget().deleteLater()

        for card in bottomCards:
            button = QLabel()
            button.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
            button.setStyleSheet("border: 0px solid black; background-color: transparent;")
            pixmap = QPixmap(r"_internal\palaceData\cards\back.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            button.setPixmap(pixmap)
            button.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.bottomCardsLayout.addWidget(button)
        if not bottomCards:
            self.placeholder = QLabel()
            self.placeholder.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
            self.bottomCardsLayout.addWidget(self.placeholder)

    def updateOpponentBottomCardButtons(self, bottomCards):
        for i in reversed(range(self.opponentBottomCardsLayout.count())):
            self.opponentBottomCardsLayout.itemAt(i).widget().deleteLater()

        for card in bottomCards:
            button = QLabel()
            button.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
            button.setStyleSheet("border: 0px solid black; background-color: transparent;")
            pixmap = QPixmap(r"_internal\palaceData\cards\back.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            button.setPixmap(pixmap)
            button.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.opponentBottomCardsLayout.addWidget(button)
        if not bottomCards:
            self.placeholder = QLabel()
            self.placeholder.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
            self.opponentBottomCardsLayout.addWidget(self.placeholder)

    def confirmTopCardSelection(self):
        player_index = 0 if self.controller.is_host else 1
        player = self.controller.players[player_index]
        for card, _ in self.chosenCards:
            player.topCards.append((card[0], card[1], True, False))
        for card, cardIndex in sorted(self.chosenCards, key=lambda x: x[1], reverse=True):
            del player.hand[cardIndex]

        if self.controller.is_host:
            self.updateTopCardButtons(player.topCards)
            self.updatePlayerHand(player.hand)
            self.controller.connection.send_to_client({
                'action': 'confirm_top_cards',
                'player_index': player_index,
                'topCards': player.topCards,
                'hand': player.hand
            })
        else:
            self.updateTopCardButtons(player.topCards)
            self.updatePlayerHand(player.hand)
            self.controller.connection.send_to_server({
                'action': 'confirm_top_cards',
                'player_index': player_index,
                'topCards': player.topCards,
                'hand': player.hand
            })

        self.controller.checkBothPlayersConfirmed()
    
    def updateUI(self, currentPlayer, deckSize, pile):
        if self.controller.topCardSelectionPhase:
            self.currentPlayerLabel.setText(f"Select your 3 Top cards...")
            self.confirmButton.setEnabled(len(self.chosenCards) == 3)
        else:
            self.currentPlayerLabel.setText(f"Current Player: {currentPlayer.name}")

            if deckSize:
                self.deckLabel.setText(f"Draw Deck:\n\n{deckSize} cards remaining")
            else:
                self.deckLabel.setText("Draw Deck:\n\nEmpty")

            if pile:
                topCard = pile[-1]
                pixmap = QPixmap(fr"_internal/palaceData/cards/{topCard[0].lower()}_of_{topCard[1].lower()}.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.pileLabel.setPixmap(pixmap)

            self.placeButton.setEnabled(len(self.controller.selectedCards) > 0)

    def revealCard(self, cardLabel, card):
        pixmap = QPixmap(fr"_internal/palaceData/cards/{card[0].lower()}_of_{card[1].lower()}.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        cardLabel.setPixmap(pixmap)

    def showTopCardSelection(self, player):
        self.chosenCards = []
        self.cardButtons = []

    def selectTopCard(self, cardIndex, button):
        playerIndex = 0 if self.controller.is_host else 1
        card = self.controller.players[playerIndex].hand[cardIndex]
        if (card, cardIndex) in self.chosenCards:
            self.chosenCards.remove((card, cardIndex))
            button.setStyleSheet("border: 0px solid black; background-color: transparent;")
        else:
            if len(self.chosenCards) < 3:
                self.chosenCards.append((card, cardIndex))
                button.setStyleSheet("border: 0px solid black; background-color: blue;")
        self.confirmButton.setEnabled(len(self.chosenCards) == 3)

    def clearSelectionLayout(self):
        self.chosenCards = []
        self.cardButtons = []

    def setPlayerHandEnabled(self, enabled):
        for i in range(self.playerHandLayout.count()):
            widget = self.playerHandLayout.itemAt(i).widget()
            if widget:
                widget.setEnabled(enabled)

class GameController:
    def __init__(self, numPlayers, difficulty, connection=None, is_host=False):
        self.numPlayers = numPlayers
        self.difficulty = difficulty
        self.is_host = is_host
        player_type = "Player 1" if is_host else "Player 2"
        self.view = GameView(self, player_type)
        self.players = []
        self.deck = []
        self.pile = []
        self.currentPlayerIndex = 0
        self.selectedCards = []
        self.playCardButtons = []
        self.topCardSelectionPhase = True
        self.connection = connection
        self.setupGame()

    def startGameLoop(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.gameLoop)
        self.timer.start(1000)  # Run the game loop every second

    def gameLoop(self):
        currentPlayer = self.players[self.currentPlayerIndex]
        if isinstance(currentPlayer, RealPlayer):
            self.view.updateUI(currentPlayer, len(self.deck), self.pile)

    def pickUpPile(self):
        if not self.pile:
            return
        currentPlayer = self.players[self.currentPlayerIndex]
        currentPlayer.pickUpPile(self.pile)
        print(f"{currentPlayer.name} picks up the pile")
        self.view.pileLabel.setText("Pile: Empty")
        currentPlayer.sevenSwitch = False

        self.view.updatePlayerHand(currentPlayer.hand)
        self.view.updateBottomCardButtons(currentPlayer.bottomCards)
        self.updateUI()
        self.changeTurn()

    def setupGame(self):
        if self.is_host:
            self.players.append(Player("Player"))  # Host player
            self.players.append(Player("Opponent"))  # Opponent
            self.deck = self.createDeck()
            random.shuffle(self.deck)
            self.send_deck_to_client()
            self.dealInitialCards()
            self.view.updatePlayerHand(self.players[0].hand)
            self.view.updateOpponentHand(self.players[1].hand)
            self.view.showTopCardSelection(self.players[0])
        else:
            self.players.append(Player("Opponent"))  # Opponent
            self.players.append(Player("Player"))  # Joining player
            self.receive_deck_from_server()
            self.view.updatePlayerHand(self.players[1].hand)
            self.view.updateOpponentHand(self.players[0].hand)
            self.view.showTopCardSelection(self.players[1])

    def proceedWithGameSetup(self):
        for index, player in enumerate(self.players):
            if index == 0:
                self.view.updateBottomCardButtons(player.bottomCards)
                self.view.updateTopCardButtons(player.topCards)
            else:
                self.view.updateOpponentBottomCardButtons(player.bottomCards)
                self.view.updateOpponentTopCardButtons(player.topCards)
        self.topCardSelectionPhase = False
        self.updateUI()
        self.startGameLoop()

    def createDeck(self):
        suits = ['diamonds', 'hearts', 'clubs', 'spades']
        return [(rank, suit, False, False) for rank in RANKS for suit in suits]

    def dealInitialCards(self):
        for player in self.players:
            player.bottomCards = [(card[0], card[1], False, True) for card in self.deck[:3]]
            player.hand = self.deck[3:9]
            self.deck = self.deck[9:]

    def send_deck_to_client(self):
        if self.connection and isinstance(self.connection, Server):
            data = self.deck
            self.connection.send_to_client(data)

    def receive_deck_from_server(self):
        if self.connection and isinstance(self.connection, Client):
            try:
                raw_data = self.connection.client_socket.recv(4096)
                if raw_data:
                    data = raw_data.decode('utf-8')
                    self.deck = json.loads(data)
                    self.dealInitialCards()
                    self.view.updatePlayerHand(self.players[1].hand)  # Update for the host player
                    self.view.updateOpponentHand(self.players[0].hand)  # Update for the joining player
                else:
                    print("No data received from server")
            except ConnectionResetError:
                print("Connection reset by server during deck reception")
            except ConnectionAbortedError:
                print("Connection aborted by server during deck reception")
            except Exception as e:
                print(f"Unexpected error during deck reception: {e}")

    def checkBothPlayersConfirmed(self):
        if all(player.topCards for player in self.players):
            print("Awfaw")
            for index, player in enumerate(self.players):
                if index == 0:
                    self.view.updateBottomCardButtons(player.bottomCards)
                    self.view.updateTopCardButtons(player.topCards)
                else:
                    self.view.updateOpponentBottomCardButtons(player.bottomCards)
                    self.view.updateOpponentTopCardButtons(player.topCards)
            self.topCardSelectionPhase = False
            self.updateUI()
            self.startGameLoop()
    
    def updateUI(self):
        currentPlayer = self.players[self.currentPlayerIndex]
        if not self.topCardSelectionPhase:
            self.view.updateUI(currentPlayer, len(self.deck), self.pile)
            if isinstance(currentPlayer, RealPlayer):
                self.view.placeButton.setText("Select A Card")
                self.view.pickUpPileButton.setDisabled(False)
                self.view.updatePlayerHand(currentPlayer.hand)
                if not self.topCardSelectionPhase:
                    self.updatePlayableCards()

    def prepareCardPlacement(self, cardIndex, cardLabel):
        card = self.players[self.currentPlayerIndex].hand[cardIndex]
        if (card, cardLabel) in self.selectedCards:
            self.selectedCards.remove((card, cardLabel))
            cardLabel.setStyleSheet("border: 0px solid black; background-color: transparent;")
        else:
            self.selectedCards.append((card, cardLabel))
            cardLabel.setStyleSheet("border: 0px solid black; background-color: blue;")
        self.view.placeButton.setEnabled(len(self.selectedCards) > 0)
        if self.view.placeButton.text() == "Place":
            self.view.placeButton.setText("Select A Card")
        else:
            self.view.placeButton.setText("Place")

    def isCardPlayable(self, card):
        topCard = self.pile[-1] if self.pile else None
        if self.players[self.currentPlayerIndex].sevenSwitch:
            return VALUES[card[0]] <= 7 or card[0] in ['2', '10']
        if not topCard:
            return True
        return card[0] == '2' or card[0] == '10' or VALUES[card[0]] >= VALUES[topCard[0]]

    def placeCard(self):
        player = self.players[self.currentPlayerIndex]
        playedCards = []
        pickUp = False

        for card, button in sorted(self.selectedCards, key=lambda x: player.hand.index(x[0])):
            if card[3] and not self.isCardPlayable(card):
                playedCards.append(card)
                for i, card in enumerate(playedCards):
                    self.pile.append(player.hand.pop(player.hand.index(playedCards[i])))
                    self.pile[-1] = (card[0], card[1], card[2], False)
                    self.view.revealCard(button, card)
                pickUp = True
                button.setParent(None)
                button.deleteLater()
            else:
                playedCards.append(card)
                for i, card in enumerate(playedCards):
                    if card[3]:
                        playedCards[i] = (card[0], card[1], card[2], False)
                player.playCard(player.hand.index(card), self.pile)
                self.view.revealCard(button, card)
                button.setParent(None)
                button.deleteLater()

        self.send_game_state()

        if pickUp:
            topCard = self.pile[-1]
            pixmap = QPixmap(fr"_internal/palaceData/cards/{topCard[0].lower()}_of_{topCard[1].lower()}.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.view.pileLabel.setPixmap(pixmap)
            QCoreApplication.processEvents()
            time.sleep(1.5)
            self.pickUpPile()
            for card in reversed(player.hand):
                if card[3]:
                    player.bottomCards.append(player.hand.pop(player.hand.index(card)))
            self.view.updatePlayerHand(player.hand)
            self.view.updateBottomCardButtons(player.bottomCards)
            self.view.setPlayerHandEnabled(False)
            self.view.placeButton.setText("AI Turn...")
            return

        self.selectedCards = []
        print(f"{player.name} plays {', '.join([f'{card[0]} of {card[1]}' for card in playedCards])}")

        while len(player.hand) < 3 and self.deck:
            player.hand.append(self.deck.pop(0))

        self.view.updatePlayerHand(player.hand)
        self.updatePlayableCards()

        if self.checkFourOfAKind():
            print("Four of a kind! Clearing the pile.")
            self.pile.clear()
            self.view.pileLabel.setText("Bombed")
            self.updateUI()
            gameOver = self.checkGameState()
            return

        if '2' in [card[0] for card in playedCards]:
            self.players[self.currentPlayerIndex].sevenSwitch = False
            topCard = self.pile[-1]
            pixmap = QPixmap(fr"_internal/palaceData/cards/{topCard[0].lower()}_of_{topCard[1].lower()}.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.view.pileLabel.setPixmap(pixmap)
            self.updateUI()
            gameOver = self.checkGameState()
            if gameOver:
                return
        elif '10' in [card[0] for card in playedCards]:
            self.pile.clear()
            self.players[self.currentPlayerIndex].sevenSwitch = False
            self.view.pileLabel.setText("Bombed")
            self.updateUI()
            gameOver = self.checkGameState()
            if gameOver:
                return
        else:
            if '7' in [card[0] for card in playedCards]:
                self.players[(self.currentPlayerIndex + 1) % len(self.players)].sevenSwitch = True
            else:
                self.players[(self.currentPlayerIndex + 1) % len(self.players)].sevenSwitch = False
            self.view.placeButton.setEnabled(False)
            topCard = self.pile[-1]
            pixmap = QPixmap(fr"_internal/palaceData/cards/{topCard[0].lower()}_of_{topCard[1].lower()}.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.view.pileLabel.setPixmap(pixmap)
            self.updateUI()
            gameOver = self.checkGameState()
            if gameOver:
                return
            self.changeTurn()
            self.view.setPlayerHandEnabled(False)
            self.view.placeButton.setText("AI Turn...")

    def changeTurn(self):
        self.currentPlayerIndex = (self.currentPlayerIndex + 1) % len(self.players)
        self.selectedCards = []
        self.updateUI()

    def checkFourOfAKind(self):
        if len(self.pile) < 4:
            return False
        return len(set(card[0] for card in self.pile[-4:])) == 1

    def checkGameState(self):
        gameOver = False
        currentPlayer = self.players[self.currentPlayerIndex]
        if not currentPlayer.hand and not self.deck:
            if currentPlayer.topCards:
                currentPlayer.hand = currentPlayer.topCards
                currentPlayer.topCards = []
                if self.currentPlayerIndex == 0:
                    self.view.updatePlayerHand(currentPlayer.hand)
                    self.view.updateTopCardButtons(currentPlayer.topCards)
                else:
                    self.view.updateOpponentHand(currentPlayer.hand)
                    self.view.updateOpponentTopCardButtons(currentPlayer.topCards)
            elif currentPlayer.bottomCards:
                currentPlayer.hand = currentPlayer.bottomCards
                currentPlayer.bottomCards = []
                if self.currentPlayerIndex == 0:
                    self.view.updatePlayerHand(currentPlayer.hand)
                    self.view.updateBottomCardButtons(currentPlayer.bottomCards)
                else:
                    self.view.updateOpponentHand(currentPlayer.hand)
                    self.view.updateOpponentBottomCardButtons(currentPlayer.bottomCards)
            elif not currentPlayer.bottomCards:
                placeholder = QLabel()
                placeholder.setFixedSize(BUTTON_HEIGHT, BUTTON_WIDTH)
                currentPlayer.hand.append(placeholder)
                self.timer.stop()
                self.view.currentPlayerLabel.setText(f"{currentPlayer.name} wins!")
                self.view.pickUpPileButton.setDisabled(True)
                self.view.placeButton.setDisabled(True)
                for button in self.view.playCardButtons:
                    button.setDisabled(True)
                print(f"{currentPlayer.name} wins!")
                gameOver = True
        return gameOver

    def updatePlayableCards(self):
        currentPlayer = self.players[0]
        for i, lbl in enumerate(self.playCardButtons):
            handCard = currentPlayer.hand[i]
            if handCard[3] or self.isCardPlayable(handCard):
                lbl.setEnabled(True)
            else:
                lbl.setEnabled(False)
    
    def send_game_state(self):
        if self.connection:
            data = self.serialize_game_state()
            if isinstance(self.connection, Server):
                self.connection.send_to_client(data)
            else:
                self.connection.send_to_server(data)

    def receive_game_state(self, data):
        self.deserialize_game_state(data)
        self.updateUI()

    def serialize_game_state(self):
        return json.dumps({
            'players': [
                {
                    'hand': self.players[0].hand,
                    'topCards': self.players[0].topCards,
                    'bottomCards': self.players[0].bottomCards
                },
                {
                    'hand': self.players[1].hand,
                    'topCards': self.players[1].topCards,
                    'bottomCards': self.players[1].bottomCards
                }
            ],
            'deck': self.deck,
            'pile': self.pile,
            'currentPlayerIndex': self.currentPlayerIndex,
            'topCardSelectionPhase': self.topCardSelectionPhase
        })

    def deserialize_game_state(self, data):
        game_state = json.loads(data)
        self.players[0].hand = game_state['players'][0]['hand']
        self.players[0].topCards = game_state['players'][0]['topCards']
        self.players[0].bottomCards = game_state['players'][0]['bottomCards']
        self.players[1].hand = game_state['players'][1]['hand']
        self.players[1].topCards = game_state['players'][1]['topCards']
        self.players[1].bottomCards = game_state['players'][1]['bottomCards']
        self.deck = game_state['deck']
        self.pile = game_state['pile']
        self.currentPlayerIndex = game_state['currentPlayerIndex']
        self.topCardSelectionPhase = game_state['topCardSelectionPhase']



def main():
    global scalingFactorWidth
    global scalingFactorHeight
    app = QApplication(sys.argv)
    app.setStyleSheet(Dark)
    screen = app.primaryScreen()
    screenSize = screen.size()
    screenWidth = screenSize.width()
    screenHeight = screenSize.height()
    scalingFactorWidth = screenWidth / 1920
    scalingFactorHeight = screenHeight / 1080
    homeScreen = HomeScreen()
    homeScreen.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
