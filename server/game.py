import json
import threading
import time

from common.game_logic import GameLogic


class Game:

    def __init__(self, admin_user):
        self.ticks = 0
        self.players = []
        self.started = False
        self.running = False
        self.add_player(admin_user)
        self.admin_user = admin_user
        self.game_logic = None

    def start(self):
        self.started = True
        self.running = True
        self.game_logic = GameLogic()

        for player in self.players:
            player.snake = self.game_logic.add_snake()

        self.game_logic.spawn_apples()
        self.game_logic.get_json()

        payload = {
            'level_size': {'width': self.game_logic.level.dimensions[0], 'height': self.game_logic.level.dimensions[1]},
            'snakes': [],
            'apples': [],
            'blocks': []
        }

        for snake in self.game_logic.level.snakes:
            payload['snakes'].append({'id': snake.id,
                                      'x': snake.body[0][0], 'y': snake.body[0][1],
                                     'dir': snake.direction})

        for apple in self.game_logic.level.apples:
            payload['apples'].append({'x': apple.position[0], 'y': apple.position[1]})

        for block in self.game_logic.level.blocks:
            payload['blocks'].append({'x': block.position[0], 'y': block.position[1]})

        for player in self.players:
            payload['player_snake'] = player.snake.id
            message = json.dumps({
                'type': 'init',
                'payload': payload
            })
            player.user.socket.send(message)


        self.send_to_all(json.dumps({'type': 'countdown', 'payload': 3}))
        time.sleep(1)
        self.send_to_all(json.dumps({'type': 'countdown', 'payload': 2}))
        time.sleep(1)
        self.send_to_all(json.dumps({'type': 'countdown', 'payload': 1}))
        time.sleep(1)
        self.send_to_all(json.dumps({'type': 'countdown', 'payload': 0}))

        threading.Thread(target=lambda: self.run()).start()

    def stop(self):
        self.running = False

    def add_player(self, user):
        if self.started:
            return
        self.players.append(Player(user))
        user.socket.listeners.append(self.handle_message)

    def send_to_all(self, message):
        for player in self.players:
            player.user.socket.send(message)

    def handle_message(self, socket, message):
        player = next(filter(lambda x: x.user.socket == socket, self.players), None)

        if not player:
            return

        # If message is falsy, connection has been lost
        if not message:
            self.players.remove(player)
            if player.snake in self.game_logic.level.snakes:
                self.game_logic.level.snakes.remove(player.snake)
            return

        try:
            message = json.loads(message)
        except json.decoder.JSONDecodeError:
            # Invalid JSON format - ignore message
            return

        if player.user == self.admin_user:
            # Message was from administrator
            
            if message['type'] == 'start_game' and not self.started:
                self.start()
            elif message['type'] == 'restart' and self.started and not self.running:
                self.start()

        if self.running:
            if message['type'] == 'move':
                self.game_logic.player_move(player.snake, int(message['payload']))
            if message['type'] == 'poop':
                self.game_logic.player_poop(player.snake)

    def tick(self):
        self.ticks += 1
        if self.ticks % 50 == 0:
            self.game_logic.level.dimensions = (self.game_logic.level.dimensions[0] + 2, self.game_logic.level.dimensions[1] + 2)
        self.game_logic.tick()
        self.game_logic.spawn_apples()

        payload = self.game_logic.get_json()
        message = json.dumps({
            'type': 'tick',
            'payload': payload
        })
        self.send_to_all(message)

        if not len(self.game_logic.level.snakes):
            # No more snakes - GAME OVER
            self.send_to_all(json.dumps({
                'type': 'game_over'
            }))
            self.running = False

    def run(self):
        last_tick = 0
        while self.running:
            cur = time.time()
            diff = cur - last_tick
            if diff >= 0.12:
                last_tick = cur
                self.tick()
            #elif diff > 0.01:
            #    time.sleep(diff - 0.01)


class Player:

    snake = None

    def __init__(self, user):
        self.user = user