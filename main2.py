import sys
import random
import json
import socket
import threading
import struct
import time
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, \
    QLabel, QDialog, QGridLayout, QRadioButton, QButtonGroup, QSpacerItem, QSizePolicy
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt, QCoreApplication, QTimer, pyqtSignal, QObject, QMetaObject, \
    pyqtSlot
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

class SignalCommunicator(QObject):
    updateOpponentBottomCardsSignal = pyqtSignal(int, list)
    updateOpponentTopCardsSignal = pyqtSignal(int, list)
    updateOpponentHandSignal = pyqtSignal(int, list)
    updateDeckSignal = pyqtSignal(dict)
    startGameSignal = pyqtSignal()
    updateHandButtonsSignal = pyqtSignal(list, QHBoxLayout)
    proceedWithGameSetupSignal = pyqtSignal()

class Server:
    def __init__(self, host, port, communicator):
        self.host = host
        self.port = port
        self.communicator = communicator
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(1)
        self.controller = None  # Initialize controller attribute
        print(f"Server listening on {self.host}:{self.port}")
        self.client_socket, self.client_address = self.server_socket.accept()
        print(f"Connection from {self.client_address}")

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
            return
        if data['action'] == 'confirm_top_cards':
            player_index = int(data['player_index'])
            self.communicator.updateOpponentBottomCardsSignal.emit(player_index, data['bottomCards'])
            self.communicator.updateOpponentTopCardsSignal.emit(player_index, data['topCards'])
            self.communicator.updateOpponentHandSignal.emit(player_index, data['hand'])
            self.controller.checkBothPlayersConfirmed()
        elif data['action'] == 'start_game':
            self.controller.proceedWithGameSetup()
        elif data['action'] == 'playCard':
            self.controller.receive_game_state(data)
        elif data['action'] == 'play_again_request':
            self.controller.playAgainRequested.emit()

    def send_to_client(self, data):
        if self.client_socket:
            try:
                serialized_data = json.dumps(data).encode('utf-8')
                msg_len = struct.pack('>I', len(serialized_data))
                print(f"Sending data to client: {data}")
                self.client_socket.sendall(msg_len + serialized_data)
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
        data = json.loads(message)
        print(f"Received data: {data}")
        return data

    def recvall(self, sock, n):
        data = b''
        # print(n)
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                return None
            data += packet
            # print("len data", len(data))
        return data

    def close(self):
        if self.client_socket:
            self.client_socket.close()
        if self.server_socket:
            self.server_socket.close()


class Client:
    def __init__(self, host, port, communicator):
        self.host = host
        self.port = port
        self.communicator = communicator
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.controller = None  # Initialize controller attribute
        try:
            self.client_socket.connect((self.host, self.port))
            print("Connected to the server")
            threading.Thread(target=self.handle_server).start()
        except Exception as e:
            print(f"Failed to connect to the server: {e}")
            self.client_socket = None  # Ensure socket is None on failure

    def handle_server(self):
        while self.client_socket:  # Ensure the socket is valid
            try:
                data = self.receive_data(self.client_socket)
                if data:
                    self.process_server_data(data)
                else:
                    print("No data received in handle_server")
            except ConnectionResetError:
                print("Connection reset by server")
                break
            except ConnectionAbortedError:
                print("Connection aborted by server")
                break
            except Exception as e:
                print(f"Unexpected error: {e}")
                break
        if self.client_socket:  # Close socket if it's still valid
            self.client_socket.close()

    def process_server_data(self, data):
        if data is None:
            print("Received None data from server")
            return
        if data['action'] == 'confirm_top_cards':
            player_index = int(data['player_index'])
            self.communicator.updateOpponentBottomCardsSignal.emit(player_index, data['bottomCards'])
            self.communicator.updateOpponentTopCardsSignal.emit(player_index, data['topCards'])
            self.communicator.updateOpponentHandSignal.emit(player_index, data['hand'])
            self.controller.checkBothPlayersConfirmed()
        elif data['action'] == 'deck sync':
            self.communicator.updateDeckSignal.emit(data)
        elif data['action'] == 'start_game':
            self.controller.proceedWithGameSetup()
        elif data['action'] == 'playCard':
            self.controller.receive_game_state(data)
        elif data['action'] == 'play_again_request':
            self.controller.playAgainRequested.emit()

    def send_to_server(self, data):
        if self.client_socket:
            try:
                serialized_data = json.dumps(data).encode('utf-8')
                msg_len = struct.pack('>I', len(serialized_data))
                print(f"Sending data to server: {data}")
                self.client_socket.sendall(msg_len + serialized_data)
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
        data = json.loads(message)
        print(f"Received data: {data}")
        return data

    def recvall(self, sock, n):
        data = b''
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                return None
            data += packet
        return data

    def close(self):
        if self.client_socket:  # Ensure the socket is valid before closing
            self.client_socket.close()
            self.client_socket = None

class GameOverDialog(QDialog):
    playAgainSignal = pyqtSignal()
    mainMenuSignal = pyqtSignal()
    exitSignal = pyqtSignal()

    def __init__(self, winner_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Game Over")
        self.setGeometry(805, 350, 300, 200)

        layout = QVBoxLayout()

        label = QLabel(f"Game Over! {winner_name} wins!")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        buttonBox = QHBoxLayout()
        playAgainButton = QPushButton("Play Again")
        playAgainButton.clicked.connect(self.playAgain)
        mainMenuButton = QPushButton("Main Menu")
        mainMenuButton.clicked.connect(self.mainMenu)
        exitButton = QPushButton("Exit")
        exitButton.clicked.connect(self.exitGame)
        buttonBox.addWidget(playAgainButton)
        buttonBox.addWidget(mainMenuButton)
        buttonBox.addWidget(exitButton)
        layout.addLayout(buttonBox)

        self.setLayout(layout)

    def playAgain(self):
        self.playAgainSignal.emit()
        self.accept()

    def mainMenu(self):
        self.mainMenuSignal.emit()
        self.accept()

    def exitGame(self):
        self.exitSignal.emit()
        QCoreApplication.instance().quit()

class HomeScreen(QWidget):
    def __init__(self, communicator):
        super().__init__()
        self.communicator = communicator
        self.controller = None
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
    
    def returnToMainMenu(self):
        self.show()
        if self.controller:
            self.controller.view.close()
    
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
            self.controller = GameController(numPlayers, difficulty_level)  # Start game with selected number of players and difficulty level
            self.controller.mainMenuRequested.connect(self.returnToMainMenu)
            self.controller.view.show()

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
        self.server = Server('localhost', 5555, self.communicator)  # Pass communicator to Server
        self.controller = GameController(numPlayers=2, difficulty='medium', connection=self.server, is_host=True)  # 2 players for online
        self.server.controller = self.controller  # Set the controller attribute in the server
        self.controller.mainMenuRequested.connect(self.returnToMainMenu)
        self.controller.view.show()

    def joinLobby(self):
        self.onlineDialog.accept()
        self.hide()
        self.client = Client('localhost', 5555, self.communicator)  # Pass communicator to Client
        self.controller = GameController(numPlayers=2, difficulty='medium', connection=self.client, is_host=False)  # 2 players for online
        self.client.controller = self.controller  # Set the controller attribute in the client
        self.controller.mainMenuRequested.connect(self.returnToMainMenu)
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

class GameView(QWidget):
    def __init__(self, controller, player_type, communicator, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.player_type = player_type
        self.communicator = communicator
        self.initUI()

        # Connect signals to slots
        self.communicator.updateOpponentBottomCardsSignal.connect(self.updateOpponentBottomCards)
        self.communicator.updateOpponentTopCardsSignal.connect(self.updateOpponentTopCards)
        self.communicator.updateOpponentHandSignal.connect(self.updateOpponentHand)
        self.communicator.updateHandButtonsSignal.connect(self.updateHandButtons)

    def initUI(self):
        self.setWindowTitle(f'Palace Card Game - {self.player_type}')
        self.setWindowIcon(QIcon(r"_internal\palaceData\palace.ico"))
        self.setGeometry(250, 75, 1100, 900)  # Set the size of the window

        self.layout = QGridLayout()

        # Disconnect Button (row 0, column 0)
        # self.disconnectButton = QPushButton("Disconnect")
        # self.disconnectButton.clicked.connect(self.controller.handleMainMenu)
        # self.layout.addWidget(self.disconnectButton, 0, 0, alignment=Qt.AlignmentFlag.AlignCenter)

        # Opponent Hand (row 0, column 1)
        self.opponentHandLayout = QHBoxLayout()
        self.layout.addLayout(self.opponentHandLayout, 0, 1, alignment=Qt.AlignmentFlag.AlignCenter)

        # Opponent Hand Label (row 1, column 1)
        self.opponentHandLabel = QLabel(f"{'Player 2' if self.player_type == 'Player 1' else 'Player 1'}'s Hand")
        self.opponentHandLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.opponentHandLabel, 1, 1, alignment=Qt.AlignmentFlag.AlignCenter)

        # Opponent Top Cards (row 2, column 1)
        self.opponentTopCardsLayout = QHBoxLayout()
        self.layout.addLayout(self.opponentTopCardsLayout, 2, 1, alignment=Qt.AlignmentFlag.AlignCenter)

        # Opponent Bottom Cards (row 3, column 1)
        self.opponentBottomCardsLayout = QHBoxLayout()
        self.layout.addLayout(self.opponentBottomCardsLayout, 3, 1, alignment=Qt.AlignmentFlag.AlignCenter)

        # Spacer (row 4, column 1)
        spacer1 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.layout.addItem(spacer1, 4, 1)

        # Center layout setup (row 5, column 1)
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
        self.consoleLayout.addWidget(self.deckLabel, alignment=Qt.AlignmentFlag.AlignLeft)
        self.consoleLayout.addWidget(self.pileLabel, alignment=Qt.AlignmentFlag.AlignCenter)
        self.consoleLayout.addItem(spacer)
        self.consoleLayout.addWidget(self.pickUpPileButton, alignment=Qt.AlignmentFlag.AlignRight)

        self.centerContainer = QWidget()
        self.centerContainer.setLayout(self.consoleLayout)
        self.centerContainer.setFixedWidth(500)  # Adjust width as necessary

        self.centerLayout = QVBoxLayout()
        self.centerLayout.addWidget(QLabel(""))
        self.centerLayout.addWidget(self.currentPlayerLabel, alignment=Qt.AlignmentFlag.AlignCenter)
        self.centerLayout.addWidget(self.centerContainer, alignment=Qt.AlignmentFlag.AlignCenter)
        self.centerLayout.addWidget(QLabel(""))
        self.centerLayout.addWidget(QLabel(""))

        self.layout.addLayout(self.centerLayout, 5, 1, alignment=Qt.AlignmentFlag.AlignCenter)

        # Spacer (row 6, column 1)
        spacer2 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.layout.addItem(spacer2, 6, 1)

        # Player Bottom Cards (row 7, column 1)
        self.bottomCardsLayout = QHBoxLayout()
        self.layout.addLayout(self.bottomCardsLayout, 7, 1, alignment=Qt.AlignmentFlag.AlignCenter)

        # Player Top Cards (row 8, column 1)
        self.topCardsLayout = QHBoxLayout()
        self.layout.addLayout(self.topCardsLayout, 8, 1, alignment=Qt.AlignmentFlag.AlignCenter)

        # Player Hand Label (row 9, column 1)
        self.playerHandLabel = QLabel(f"{self.player_type}'s Hand")
        self.playerHandLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.playerHandLabel, 9, 1, alignment=Qt.AlignmentFlag.AlignCenter)

        # Player Hand (row 10, column 1)
        self.playerHandLayout = QHBoxLayout()
        self.layout.addLayout(self.playerHandLayout, 10, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Confirm/Place Button (row 11, column 1)
        buttonsContainerLayout = QVBoxLayout()
        self.confirmButton = QPushButton("Confirm")
        self.confirmButton.setEnabled(False)
        self.confirmButton.setFixedWidth(240)
        self.confirmButton.clicked.connect(self.confirmTopCardSelection)
        self.placeButton = QPushButton("Select A Card")
        self.placeButton.setEnabled(False)
        self.confirmButton.setFixedWidth(240)
        self.placeButton.clicked.connect(self.controller.placeCard)
        self.placeButton.setVisible(False)

        buttonsContainerLayout.addWidget(self.confirmButton, alignment=Qt.AlignmentFlag.AlignCenter)
        buttonsContainerLayout.addWidget(self.placeButton, alignment=Qt.AlignmentFlag.AlignCenter)
        self.layout.addLayout(buttonsContainerLayout, 11, 1, alignment=Qt.AlignmentFlag.AlignCenter)

        # Adjust the width of the center console column
        self.layout.setColumnMinimumWidth(1, 500)

        self.setLayout(self.layout)

    def updateHandButtons(self, hand, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
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
            if self.controller.topCardSelectionPhase:
                button.mousePressEvent = lambda event, idx=idx, btn=button: self.selectTopCard(idx, btn)
            else:
                try:
                    button.mousePressEvent = lambda event, idx=idx, btn=button: self.controller.prepareCardPlacement(idx, btn)
                except IndexError:
                    return
            self.controller.playCardButtons.append(button)
            layout.addWidget(button)

    def updateOpponentHand(self, playerIndex, hand):
        self.controller.players[playerIndex].hand = hand
        self.updateOpponentHandButtons(hand)
        
    def updateOpponentTopCards(self, playerIndex, topCards):
        self.controller.players[playerIndex].topCards = topCards
        self.updateOpponentTopCardButtons(topCards)
        
    def updateOpponentBottomCards(self, playerIndex, bottomCards):
        self.controller.players[playerIndex].bottomCards = bottomCards
        self.updateOpponentBottomCardButtons(bottomCards)
    
    def updatePlayerHandButtons(self, hand):
        self.updateHandButtons(hand, self.playerHandLayout)
    
    def updateOpponentHandButtons(self, hand):
        self.updateHandButtons(hand, self.opponentHandLayout)

    def updatePlayerTopCardButtons(self, topCards):
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

    def updatePlayerBottomCardButtons(self, bottomCards):
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
        if self.controller.is_host:
            player_index = 0
        else:
            player_index = 1
        player = self.controller.players[player_index]
        for card, _ in self.chosenCards:
            player.topCards.append((card[0], card[1], True, False))
        for card, cardIndex in sorted(self.chosenCards, key=lambda x: x[1], reverse=True):
            del player.hand[cardIndex]

        if self.controller.is_host:
            self.updatePlayerBottomCardButtons(player.bottomCards)
            self.updatePlayerTopCardButtons(player.topCards)
            self.updatePlayerHandButtons(player.hand)
            self.controller.connection.send_to_client({
                'action': 'confirm_top_cards',
                'player_index': player_index,
                'topCards': player.topCards,
                'bottomCards': player.bottomCards,
                'hand': player.hand
            })
        else:
            self.updatePlayerBottomCardButtons(player.bottomCards)
            self.updatePlayerTopCardButtons(player.topCards)
            self.updatePlayerHandButtons(player.hand)
            self.controller.connection.send_to_server({
                'action': 'confirm_top_cards',
                'player_index': player_index,
                'topCards': player.topCards,
                'bottomCards': player.bottomCards,
                'hand': player.hand
            })
        self.confirmButton.setDisabled(True)
        self.disablePlayerHand()
    
    def updateUI(self, currentPlayer, deckSize, pile):
        if self.controller.topCardSelectionPhase:
            self.currentPlayerLabel.setText(f"Select your 3 Top cards...")
            self.confirmButton.setEnabled(len(self.chosenCards) == 3)
        else:
            self.confirmButton.setVisible(False)
            self.placeButton.setVisible(True)
            self.deckLabel.setVisible(True)
            self.currentPlayerLabel.setVisible(True)
            self.pickUpPileButton.setVisible(True)
            self.currentPlayerLabel.setText("Current Player: ")
            self.pileLabel.setText("Pile: Empty")
            self.pileLabel.setFixedSize(BUTTON_WIDTH, BUTTON_HEIGHT)
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
            self.enableOpponentHandNotClickable()
       
    def revealCard(self, cardLabel, card):
        pixmap = QPixmap(fr"_internal/palaceData/cards/{card[0].lower()}_of_{card[1].lower()}.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        cardLabel.setPixmap(pixmap)

    def showTopCardSelection(self):
        self.chosenCards = []
        self.cardButtons = []

    def selectTopCard(self, cardIndex, button):
        if self.controller.is_host:
            playerIndex = 0 
        else:
            playerIndex = 1
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

    def enablePlayerHand(self):
        for i in range(self.playerHandLayout.count()):
            widget = self.playerHandLayout.itemAt(i).widget()
            if widget:
                widget.setEnabled(True)

    def disablePlayerHand(self):
        for i in range(self.playerHandLayout.count()):
            widget = self.playerHandLayout.itemAt(i).widget()
            if widget:
                widget.setEnabled(False)

    def enableOpponentHandNotClickable(self):
        for i in range(self.opponentHandLayout.count()):
            widget = self.opponentHandLayout.itemAt(i).widget()
            if widget:
                widget.setEnabled(True)
                widget.mousePressEvent = lambda event: None  # Ensure opponent's cards are not clickable

    def closeEvent(self, event):
        self.controller.closeConnections()
        event.accept()
    
class GameController(QObject):
    playAgainRequested = pyqtSignal()
    mainMenuRequested = pyqtSignal()
    exitRequested = pyqtSignal()

    def __init__(self, numPlayers, difficulty, connection=None, is_host=False):
        super().__init__()
        self.numPlayers = numPlayers
        self.difficulty = difficulty
        self.is_host = is_host
        if connection is None:
            self.communicator = SignalCommunicator()
        else:
            self.communicator = connection.communicator
        self.communicator.startGameSignal.connect(self.proceedWithGameSetup)
        self.communicator.proceedWithGameSetupSignal.connect(self.proceedWithGameSetupOnMainThread)
        if is_host:
            self.player_type = "Player 1" 
        else:
            self.player_type = "Player 2"
        self.view = GameView(self, self.player_type, self.communicator)
        self.players = [Player("Player 1"), Player("Player 2")]
        self.deck = []
        self.pile = []
        self.currentPlayerIndex = 0
        self.selectedCards = []
        self.playCardButtons = []
        self.topCardSelectionPhase = True
        self.connection = connection
        self.setupGame()

        self.communicator.updateDeckSignal.connect(self.receive_deck_from_server)

        # Connect play again, main menu, and exit signals
        self.playAgainRequested.connect(self.handlePlayAgain)
        self.mainMenuRequested.connect(self.handleMainMenu)
        self.exitRequested.connect(QCoreApplication.instance().quit)

        self.playAgainCount = 0

    
    def showGameOverDialog(self, winner_name):
        dialog = GameOverDialog(winner_name, self.view)
        dialog.playAgainSignal.connect(self.requestPlayAgain)
        dialog.mainMenuSignal.connect(self.mainMenuRequested)
        dialog.exitSignal.connect(self.exitRequested)
        dialog.exec()

    def requestPlayAgain(self):
        self.playAgainCount += 1
        if self.playAgainCount == 2:  # Both players have requested to play again
            self.playAgainCount = 0
            self.resetGame()
            self.setupGame()
        else:
            if self.is_host:
                self.connection.send_to_client({'action': 'play_again_request'}) 
            else:
                self.connection.send_to_server({'action': 'play_again_request'})

    def handlePlayAgain(self):
        self.playAgainCount += 1
        if self.playAgainCount == 2:
            self.playAgainCount = 0
            self.resetGame()
            self.setupGame()

    def handleMainMenu(self):
        self.closeConnections()
        self.view.close()
        self.mainMenuRequested.emit()

    def resetGame(self):
        self.deck = []
        self.pile = []
        self.currentPlayerIndex = 0
        self.selectedCards = []
        self.playCardButtons = []
        self.topCardSelectionPhase = True
        self.players = [Player("Player 1"), Player("Player 2")]
        self.view.clearSelectionLayout()
    
    def startGameLoop(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.gameLoop)
        self.timer.start(1000)  # Run the game loop every second

    def gameLoop(self):
        currentPlayer = self.players[self.currentPlayerIndex]
        self.view.updateUI(currentPlayer, len(self.deck), self.pile)

    def pickUpPile(self):
        if not self.pile:
            return
        currentPlayer = self.players[self.currentPlayerIndex]
        currentPlayer.pickUpPile(self.pile)
        print(f"{currentPlayer.name} picks up the pile")
        self.view.pileLabel.setText("Pile: Empty")
        currentPlayer.sevenSwitch = False
        self.updateUI()
        self.send_game_state()
        self.changeTurn()
        self.view.placeButton.setText("Opponent's Turn...")

    def setupGame(self):
        if self.is_host:
            self.deck = self.createDeck()
            random.shuffle(self.deck)
            self.dealInitialCards(self.players[0])
            self.dealInitialCards(self.players[1])
            self.send_deck_to_client()
            self.view.updatePlayerHandButtons(self.players[0].hand)
        else:
            self.view.updatePlayerHandButtons(self.players[1].hand)
        self.view.showTopCardSelection()

    def proceedWithGameSetup(self):
        self.communicator.proceedWithGameSetupSignal.emit()

    def proceedWithGameSetupOnMainThread(self):
        self.topCardSelectionPhase = False
        self.updateUI()
        if self.player_type == "Player 2":
            self.view.disablePlayerHand()
        self.startGameLoop()

    def createDeck(self):
        suits = ['diamonds', 'hearts', 'clubs', 'spades']
        return [(rank, suit, False, False) for rank in RANKS for suit in suits]

    def dealInitialCards(self, player):
        player.bottomCards = [(card[0], card[1], False, True) for card in self.deck[:3]]
        player.hand = self.deck[3:9]
        self.deck = self.deck[9:]

    def send_deck_to_client(self):
        data = {'action': 'deck sync', 
                'deck': self.deck, 
                'player2bot': self.players[1].bottomCards,
                'player2top': self.players[1].topCards,
                'player2hand': self.players[1].hand
            }
        self.connection.send_to_client(data)
                
    def receive_deck_from_server(self, data):
        self.deck = data['deck']
        self.players[1].bottomCards = data['player2bot']
        self.players[1].topCards = data['player2top']
        self.players[1].hand = data['player2hand']
        self.view.updatePlayerHandButtons(self.players[1].hand)
        self.view.placeButton.setText("Opponent's Turn...")

    def checkBothPlayersConfirmed(self):
        time.sleep(1)
        if all(player.topCards for player in self.players):
            print("Both players have confirmed their top cards.")
            self.send_start_game_signal()
            self.proceedWithGameSetup()
    
    def send_start_game_signal(self):
        data = {'action': 'start_game', 'game_state': ""}
        if self.is_host:
            self.connection.send_to_client(data)
        else:
            self.connection.send_to_server(data)
    
    def updateUI(self):
        currentPlayer = self.players[self.currentPlayerIndex]
        if not self.topCardSelectionPhase:
            self.view.updateUI(currentPlayer, len(self.deck), self.pile)
            self.view.placeButton.setText("Select A Card")
            self.view.pickUpPileButton.setDisabled(False)
            if self.is_host:
                self.view.updatePlayerHandButtons(self.players[0].hand)
                self.view.updateOpponentHandButtons(self.players[1].hand)
                self.view.updatePlayerTopCardButtons(self.players[0].topCards)
                self.view.updateOpponentTopCardButtons(self.players[1].topCards)
                self.view.updatePlayerBottomCardButtons(self.players[0].bottomCards)
                self.view.updateOpponentBottomCardButtons(self.players[1].bottomCards)
            else:
                self.view.updatePlayerHandButtons(self.players[1].hand)
                self.view.updateOpponentHandButtons(self.players[0].hand)
                self.view.updatePlayerTopCardButtons(self.players[1].topCards)
                self.view.updateOpponentTopCardButtons(self.players[0].topCards)
                self.view.updatePlayerBottomCardButtons(self.players[1].bottomCards)
                self.view.updateOpponentBottomCardButtons(self.players[0].bottomCards)

    def prepareCardPlacement(self, cardIndex, cardLabel):
        card = self.players[self.currentPlayerIndex].hand[cardIndex]
        if (card, cardLabel) in self.selectedCards:
            self.selectedCards.remove((card, cardLabel))
            cardLabel.setStyleSheet("border: 0px solid black; background-color: transparent;") 
        else:
            self.selectedCards.append((card, cardLabel))
            cardLabel.setStyleSheet("border: 0px solid black; background-color: blue;") 

        # Enable all buttons with the same rank, disable the rest
        selectedCardRank = card[0]
        if not self.selectedCards:
            for i in range(self.view.playerHandLayout.count()):
                lbl = self.view.playerHandLayout.itemAt(i).widget()
                handCard = self.players[self.currentPlayerIndex].hand[i]
                if handCard[3] or self.isCardPlayable(handCard):  
                    lbl.setEnabled(True)
        else:
            for i in range(self.view.playerHandLayout.count()):
                lbl = self.view.playerHandLayout.itemAt(i).widget()
                handCard = self.players[self.currentPlayerIndex].hand[i]
                if handCard[0] == selectedCardRank or (handCard, lbl) in self.selectedCards:
                    lbl.setEnabled(True)
                elif not handCard[3]:  
                    lbl.setEnabled(False)
        self.view.placeButton.setEnabled(len(self.selectedCards) > 0)  
        if self.view.placeButton.text() == "Place":
            self.view.placeButton.setText("Select A Card")
        else:
            self.view.placeButton.setText("Place")

    def isCardPlayable(self, card):
        if self.pile:
            topCard = self.pile[-1]
        else:
            topCard = None
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

        if pickUp:
            topCard = self.pile[-1]
            pixmap = QPixmap(fr"_internal/palaceData/cards/{topCard[0].lower()}_of_{topCard[1].lower()}.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.view.pileLabel.setPixmap(pixmap)
            QCoreApplication.processEvents()
            time.sleep(1)
            self.pickUpPile()
            for card in reversed(player.hand):
                if card[3]:
                    player.bottomCards.append(player.hand.pop(player.hand.index(card)))
            self.view.updatePlayerHandButtons(player.hand)
            self.view.updatePlayerBottomCardButtons(player.bottomCards)
            self.view.placeButton.setText("Opponent's Turn...")
            self.send_game_state()
            self.changeTurn()
            return

        self.selectedCards = []
        print(f"{player.name} plays {', '.join([f'{card[0]} of {card[1]}' for card in playedCards])}")

        while len(player.hand) < 3 and self.deck:
            player.hand.append(self.deck.pop(0))

        self.view.updatePlayerHandButtons(player.hand)

        if self.checkFourOfAKind():
            print("Four of a kind! Clearing the pile.")
            self.pile.clear()
            self.view.pileLabel.setText("Bombed")
            self.updateUI()
            gameOver = self.checkGameState()
            self.send_game_state()
            if gameOver:
                self.showGameOverDialog(player.name)
                return
            return
        if '2' in [card[0] for card in playedCards]:
            self.players[self.currentPlayerIndex].sevenSwitch = False
            topCard = self.pile[-1]
            pixmap = QPixmap(fr"_internal/palaceData/cards/{topCard[0].lower()}_of_{topCard[1].lower()}.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.view.pileLabel.setPixmap(pixmap)
            self.updateUI()
            gameOver = self.checkGameState()
            self.send_game_state()
            if gameOver:
                self.showGameOverDialog(player.name)
                return
        elif '10' in [card[0] for card in playedCards]:
            self.pile.clear()
            self.players[self.currentPlayerIndex].sevenSwitch = False
            self.view.pileLabel.setText("Bombed")
            self.updateUI()
            gameOver = self.checkGameState()
            self.send_game_state()
            if gameOver:
                self.showGameOverDialog(player.name)
                return
        else:
            if '7' in [card[0] for card in playedCards]:
                self.players[self.currentPlayerIndex].sevenSwitch = True
            else:
                self.players[self.currentPlayerIndex].sevenSwitch = False
            self.view.placeButton.setEnabled(False)
            topCard = self.pile[-1]
            pixmap = QPixmap(fr"_internal/palaceData/cards/{topCard[0].lower()}_of_{topCard[1].lower()}.png").scaled(CARD_WIDTH, CARD_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.view.pileLabel.setPixmap(pixmap)
            self.updateUI()
            gameOver = self.checkGameState()
            self.send_game_state()
            if gameOver:
                self.showGameOverDialog(player.name)
                return
            self.changeTurn()
            self.view.placeButton.setText("Opponent's Turn...")

    def changeTurn(self):
        self.currentPlayerIndex = (self.currentPlayerIndex + 1) % len(self.players)
        self.selectedCards = []
        self.updateUI()
        self.view.disablePlayerHand()
        self.view.pickUpPileButton.setEnabled(False)

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
                    self.view.updatePlayerHandButtons(currentPlayer.hand)
                    self.view.updatePlayerTopCardButtons(currentPlayer.topCards)
                else:
                    self.view.updateOpponentHandButtons(currentPlayer.hand)
                    self.view.updateOpponentTopCardButtons(currentPlayer.topCards)
            elif currentPlayer.bottomCards:
                currentPlayer.hand = currentPlayer.bottomCards
                currentPlayer.bottomCards = []
                if self.currentPlayerIndex == 0:
                    self.view.updatePlayerHandButtons(currentPlayer.hand)
                    self.view.updatePlayerBottomCardButtons(currentPlayer.bottomCards)
                else:
                    self.view.updateOpponentHandButtons(currentPlayer.hand)
                    self.view.updateOpponentBottomCardButtons(currentPlayer.bottomCards)
            elif not currentPlayer.bottomCards:
                placeholder = QLabel()
                placeholder.setFixedSize(BUTTON_HEIGHT, BUTTON_WIDTH)
                currentPlayer.hand.append(placeholder)
                self.timer.stop()
                self.view.pickUpPileButton.setDisabled(True)
                self.view.placeButton.setDisabled(True)
                for button in self.playCardButtons:
                    button.setDisabled(True)
                print(f"{currentPlayer.name} wins!")
                gameOver = True
        return gameOver

    def updatePlayableCards(self):
        currentPlayer = self.players[self.currentPlayerIndex]
        for i in range(self.view.playerHandLayout.count()):
            lbl = self.view.playerHandLayout.itemAt(i).widget()
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
        self.view.placeButton.setText("Select a Card")
        self.view.pickUpPileButton.setEnabled(True)
        self.updatePlayableCards()

    def serialize_game_state(self):
        return {
            'action': 'playCard',
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
            'seven': self.players[self.currentPlayerIndex].sevenSwitch,
            'currentPlayerIndex': (self.currentPlayerIndex + 1) % len(self.players),
            'topCardSelectionPhase': self.topCardSelectionPhase
        }

    def deserialize_game_state(self, data):
        self.currentPlayerIndex = data['currentPlayerIndex']
        self.players[self.currentPlayerIndex].sevenSwitch = data['seven']
        print(self.players[self.currentPlayerIndex].sevenSwitch)
        self.players[0].hand = data['players'][0]['hand']
        self.players[0].topCards = data['players'][0]['topCards']
        self.players[0].bottomCards = data['players'][0]['bottomCards']
        self.players[1].hand = data['players'][1]['hand']
        self.players[1].topCards = data['players'][1]['topCards']
        self.players[1].bottomCards = data['players'][1]['bottomCards']
        self.deck = data['deck']
        self.pile = data['pile']
        self.topCardSelectionPhase = data['topCardSelectionPhase']
        if self.currentPlayerIndex == 1:
            self.communicator.updateHandButtonsSignal.emit(self.players[0].hand, self.view.opponentHandLayout)
        else:
            self.communicator.updateHandButtonsSignal.emit(self.players[1].hand, self.view.opponentHandLayout)
    
    def closeConnections(self):
        if self.connection:
            self.connection.close()
       
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
    communicator = SignalCommunicator()
    homeScreen = HomeScreen(communicator)
    homeScreen.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()