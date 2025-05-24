import socket
import threading
import json
import time
import random

# Game settings
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
PADDLE_WIDTH = 15
PADDLE_HEIGHT = 100
BALL_SIZE = 15
BALL_SPEED = 5
TICK_RATE = 1 / 60  # 60 FPS

class PongGame:
    def __init__(self):
        # Game state
        self.ball_x = WINDOW_WIDTH // 2
        self.ball_y = WINDOW_HEIGHT // 2
        self.ball_velocity_x = BALL_SPEED * random.choice([-1, 1])
        self.ball_velocity_y = BALL_SPEED * random.choice([-0.5, 0.5])
        
        self.player1_y = WINDOW_HEIGHT // 2 - PADDLE_HEIGHT // 2
        self.player2_y = WINDOW_HEIGHT // 2 - PADDLE_HEIGHT // 2
        
        self.score_player1 = 0
        self.score_player2 = 0
        
        self.game_active = False
        self.countdown = 3
        self.countdown_timer = None
        self.winner = None

    def update(self):
        if not self.game_active:
            return
            
        # Move the ball
        self.ball_x += self.ball_velocity_x
        self.ball_y += self.ball_velocity_y
        
        # Ball collision with top and bottom walls
        if self.ball_y <= 0 or self.ball_y >= WINDOW_HEIGHT - BALL_SIZE:
            self.ball_velocity_y *= -1
        
        # Ball collision with paddles
        # Player 1 paddle (left)
        if (self.ball_x <= PADDLE_WIDTH and 
            self.ball_y + BALL_SIZE >= self.player1_y and 
            self.ball_y <= self.player1_y + PADDLE_HEIGHT):
            self.ball_velocity_x *= -1.1  # Increase speed slightly
            # Change angle based on where the ball hits the paddle
            paddle_center = self.player1_y + PADDLE_HEIGHT // 2
            offset = (self.ball_y + BALL_SIZE // 2 - paddle_center) / (PADDLE_HEIGHT // 2)
            self.ball_velocity_y = BALL_SPEED * offset
        
        # Player 2 paddle (right)
        if (self.ball_x >= WINDOW_WIDTH - PADDLE_WIDTH - BALL_SIZE and 
            self.ball_y + BALL_SIZE >= self.player2_y and 
            self.ball_y <= self.player2_y + PADDLE_HEIGHT):
            self.ball_velocity_x *= -1.1  # Increase speed slightly
            # Change angle based on where the ball hits the paddle
            paddle_center = self.player2_y + PADDLE_HEIGHT // 2
            offset = (self.ball_y + BALL_SIZE // 2 - paddle_center) / (PADDLE_HEIGHT // 2)
            self.ball_velocity_y = BALL_SPEED * offset
        
        # Ball out of bounds (scoring)
        if self.ball_x < 0:
            self.score_player2 += 1
            self.reset_ball()
            if self.score_player2 >= 5:
                self.winner = "Player 2"
                self.game_active = False
        elif self.ball_x > WINDOW_WIDTH:
            self.score_player1 += 1
            self.reset_ball()
            if self.score_player1 >= 5:
                self.winner = "Player 1"
                self.game_active = False
    
    def reset_ball(self):
        self.ball_x = WINDOW_WIDTH // 2
        self.ball_y = WINDOW_HEIGHT // 2
        self.ball_velocity_x = BALL_SPEED * random.choice([-1, 1])
        self.ball_velocity_y = BALL_SPEED * random.choice([-0.5, 0.5])
        self.game_active = False
        self.countdown = 3
        self.countdown_timer = time.time() + 1
    
    def update_countdown(self):
        if self.countdown_timer and time.time() >= self.countdown_timer:
            self.countdown -= 1
            if self.countdown <= 0:
                self.game_active = True
                self.countdown_timer = None
            else:
                self.countdown_timer = time.time() + 1
    
    def move_paddle(self, player, direction):
        paddle_speed = 15  # Increased from 10
        if player == 1:
            if direction == "up" and self.player1_y > 0:
                self.player1_y -= paddle_speed
            elif direction == "down" and self.player1_y < WINDOW_HEIGHT - PADDLE_HEIGHT:
                self.player1_y += paddle_speed
        elif player == 2:
            if direction == "up" and self.player2_y > 0:
                self.player2_y -= paddle_speed
            elif direction == "down" and self.player2_y < WINDOW_HEIGHT - PADDLE_HEIGHT:
                self.player2_y += paddle_speed
    
    def get_state(self):
        return {
            "ball": {"x": self.ball_x, "y": self.ball_y},
            "player1": {"y": self.player1_y},
            "player2": {"y": self.player2_y},
            "score": {"player1": self.score_player1, "player2": self.score_player2},
            "countdown": self.countdown if not self.game_active and self.countdown_timer else None,
            "winner": self.winner
        }
    
    def restart_game(self):
        self.score_player1 = 0
        self.score_player2 = 0
        self.winner = None
        self.reset_ball()


class PongServer:
    def __init__(self, host='0.0.0.0', port=5555):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.game = PongGame()
        self.clients = []
        self.client_data = {}  # Store player info indexed by client socket
    
    def start(self):
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(2)
        print(f"Server started on {self.host}:{self.port}")
        
        # Start the game loop in a separate thread
        game_thread = threading.Thread(target=self.game_loop)
        game_thread.daemon = True
        game_thread.start()
        
        try:
            # Accept connections and handle clients
            while True:
                client_socket, client_address = self.server_socket.accept()
                print(f"Client connected from {client_address}")
                
                # Assign player number based on connection order
                player_number = len(self.clients) + 1
                if player_number > 2:
                    print(f"Rejecting client {client_address}, server full")
                    client_socket.send(json.dumps({"error": "Server full"}).encode())
                    client_socket.close()
                    continue
                    
                # Send player number to client
                client_socket.send(json.dumps({"player_number": player_number}).encode())
                
                # Add client to list and start handling thread
                self.clients.append(client_socket)
                self.client_data[client_socket] = {
                    "address": client_address,
                    "player_number": player_number
                }
                
                # Start a new thread to handle this client
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket,))
                client_thread.daemon = True
                client_thread.start()
                
                # Start the countdown when first player connects (for testing single player)
                if player_number == 1:
                    print("First player connected. Starting game in 5 seconds...")
                    self.game.countdown = 5
                    self.game.countdown_timer = time.time() + 1
                
                # Start actual game when second player connects
                if player_number == 2:
                    print("Second player connected. Game starting!")
                    self.game.countdown = 3
                    self.game.countdown_timer = time.time() + 1
                
        except KeyboardInterrupt:
            print("Server shutting down...")
        finally:
            self.server_socket.close()
    
    def game_loop(self):
        # Initial delay to make sure the server is fully set up
        time.sleep(1)
        
        last_update_time = time.time()
        
        while True:
            current_time = time.time()
            
            # Update game state
            self.game.update_countdown()
            self.game.update()
            
            # Send game state to all connected clients
            game_state = self.game.get_state()
            state_json = json.dumps(game_state).encode()
            
            # Create a copy of clients list to avoid modification during iteration
            clients_copy = self.clients.copy()
            for client in clients_copy:
                try:
                    client.send(state_json)
                except ConnectionResetError:
                    self.remove_client(client)
                except BrokenPipeError:
                    self.remove_client(client)
                except:
                    # Client disconnected, remove it properly
                    self.remove_client(client)
            
            # Debug info 
            if len(self.clients) > 0 and current_time - last_update_time >= 5:
                print(f"Game state update: {len(self.clients)} client(s) connected")
                print(f"Game active: {self.game.game_active}, Countdown: {self.game.countdown}")
                last_update_time = current_time
            
            # Special case: Single player - make player 2 follow the ball
            if len(self.clients) == 1 and self.game.game_active:
                # Simple AI: Move paddle towards the ball
                paddle_center = self.game.player2_y + PADDLE_HEIGHT // 2
                ball_center = self.game.ball_y + BALL_SIZE // 2
                
                if paddle_center < ball_center - 10:  # Add some threshold to avoid jitter
                    self.game.move_paddle(2, "down")
                elif paddle_center > ball_center + 10:
                    self.game.move_paddle(2, "up")
            
            # Control game speed
            time.sleep(TICK_RATE)
    
    def remove_client(self, client_socket):
        if client_socket in self.clients:
            player_num = self.client_data[client_socket]["player_number"]
            print(f"Client {player_num} disconnected")
            self.clients.remove(client_socket)
            del self.client_data[client_socket]
            try:
                client_socket.close()
            except:
                pass
    
    def handle_client(self, client_socket):
        try:
            player_number = self.client_data[client_socket]["player_number"]
            
            # Send initial game state immediately after connection
            try:
                initial_state = self.game.get_state()
                client_socket.send(json.dumps(initial_state).encode())
            except:
                print("Failed to send initial state")
            
            while True:
                data = client_socket.recv(1024).decode()
                if not data:
                    break
                
                try:
                    command = json.loads(data)
                    if "move" in command:
                        self.game.move_paddle(player_number, command["move"])
                    elif "restart" in command and command["restart"] and self.game.winner:
                        self.game.restart_game()
                    elif "request_state" in command:
                        # Client is requesting game state, send it
                        try:
                            state = self.game.get_state()
                            client_socket.send(json.dumps(state).encode())
                        except:
                            pass
                except json.JSONDecodeError:
                    print(f"Received invalid JSON: {data}")
        except:
            print(f"Error handling client")
        finally:
            self.remove_client(client_socket)


if __name__ == "__main__":
    server = PongServer()
    server.start()