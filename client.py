import socket
import threading
import json
import pygame
import sys

# Game settings
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
PADDLE_WIDTH = 15
PADDLE_HEIGHT = 100
BALL_SIZE = 15
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
FPS = 60

class PongClient:
    def __init__(self, server_host='localhost', server_port=5555):
        self.server_host = server_host
        self.server_port = server_port
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.player_number = None
        self.game_state = None
        self.running = True
        self.connected = False
        
        # Initialize pygame
        pygame.init()
        self.clock = pygame.time.Clock()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Pong Client")
        
        # Load fonts
        self.font = pygame.font.Font(None, 36)
        self.large_font = pygame.font.Font(None, 72)
    
    def connect(self):
        try:
            print(f"Connecting to server at {self.server_host}:{self.server_port}...")
            self.client_socket.connect((self.server_host, self.server_port))
            self.connected = True
            
            # Receive player number
            data = self.client_socket.recv(1024).decode()
            if not data:
                print("No response from server")
                self.connected = False
                return False
                
            response = json.loads(data)
            
            # Check if server is full
            if "error" in response:
                print(f"Server error: {response['error']}")
                self.connected = False
                return False
                
            self.player_number = response["player_number"]
            print(f"Connected as Player {self.player_number}")
            
            # Start receiving game state in a separate thread
            receive_thread = threading.Thread(target=self.receive_game_state)
            receive_thread.daemon = True
            receive_thread.start()
            
            # Request initial game state
            try:
                self.client_socket.send(json.dumps({"request_state": True}).encode())
            except:
                pass  # It's OK if this fails, we'll get the state in the next update cycle
            
            return True
        except ConnectionRefusedError:
            print(f"Connection refused. Is the server running?")
            self.connected = False
            return False
        except Exception as e:
            print(f"Error connecting to server: {e}")
            self.connected = False
            return False
    
    def receive_game_state(self):
        buffer = ""
        tries = 0
        max_tries = 5
        
        # Try to request game state a few times initially
        while self.running and self.connected and self.game_state is None and tries < max_tries:
            try:
                # Request initial game state
                self.client_socket.send(json.dumps({"request_state": True}).encode())
                tries += 1
                print(f"Requesting initial game state (try {tries}/{max_tries})...")
                pygame.time.wait(1000)  # Wait a second between tries
            except:
                pass
        
        while self.running and self.connected:
            try:
                data = self.client_socket.recv(4096).decode()
                if not data:
                    print("Connection closed by server")
                    self.connected = False
                    break
                
                buffer += data
                
                # Process complete JSON messages
                while True:
                    try:
                        # Find a complete JSON object by looking for opening and closing braces
                        obj_start = buffer.find("{")
                        if obj_start == -1:
                            buffer = ""  # Clear invalid data
                            break
                            
                        # Count braces to find the end of the complete JSON object
                        brace_count = 0
                        obj_end = -1
                        
                        for i in range(obj_start, len(buffer)):
                            if buffer[i] == '{':
                                brace_count += 1
                            elif buffer[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    obj_end = i
                                    break
                        
                        if obj_end == -1:
                            # Incomplete JSON, wait for more data
                            break
                            
                        # Extract and process the JSON object
                        json_str = buffer[obj_start:obj_end + 1]
                        buffer = buffer[obj_end + 1:]
                        
                        parsed_state = json.loads(json_str)
                        self.game_state = parsed_state
                        
                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON: {e}")
                        # Remove potentially corrupted data up to the next opening brace
                        next_obj = buffer.find("{", 1)
                        if next_obj != -1:
                            buffer = buffer[next_obj:]
                        else:
                            buffer = ""
                        break
                    except Exception as e:
                        print(f"Error processing game state: {e}")
                        buffer = ""
                        break
                        
            except ConnectionResetError:
                print("Connection reset by server")
                self.connected = False
                break
            except Exception as e:
                print(f"Error receiving game state: {e}")
                self.connected = False
                break
    
    def send_movement(self, direction):
        if not self.connected:
            return
            
        try:
            command = {"move": direction}
            self.client_socket.send(json.dumps(command).encode())
        except:
            print("Error sending movement")
            self.connected = False
    
    def send_restart(self):
        if not self.connected:
            return
            
        try:
            command = {"restart": True}
            self.client_socket.send(json.dumps(command).encode())
        except:
            print("Error sending restart command")
            self.connected = False
    
    def run(self):
        if not self.connect():
            print("Failed to connect to server")
            pygame.time.wait(2000)  # Wait 2 seconds before quitting
            return
        
        # Main game loop
        while self.running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r and self.game_state and self.game_state.get("winner"):
                        self.send_restart()
                    elif event.key == pygame.K_ESCAPE:
                        self.running = False
            
            # Handle keyboard input for paddle movement
            keys = pygame.key.get_pressed()
            if keys[pygame.K_UP]:
                self.send_movement("up")
            elif keys[pygame.K_DOWN]:
                self.send_movement("down")
            
            # Render game
            self.render()
            
            # Control frame rate
            self.clock.tick(FPS)
        
        # Clean up
        if self.connected:
            self.client_socket.close()
        pygame.quit()
        sys.exit()
    
    def render(self):
        # Clear the screen
        self.screen.fill(BLACK)
        
        if not self.connected:
            disconnected_text = self.font.render("Disconnected from server", True, WHITE)
            text_rect = disconnected_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 20))
            retry_text = self.font.render("Please restart the application", True, WHITE)
            retry_rect = retry_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 20))
            self.screen.blit(disconnected_text, text_rect)
            self.screen.blit(retry_text, retry_rect)
        elif self.game_state:
            # Draw paddles
            pygame.draw.rect(self.screen, WHITE, 
                            (0, self.game_state["player1"]["y"], PADDLE_WIDTH, PADDLE_HEIGHT))
            pygame.draw.rect(self.screen, WHITE, 
                            (WINDOW_WIDTH - PADDLE_WIDTH, self.game_state["player2"]["y"], 
                            PADDLE_WIDTH, PADDLE_HEIGHT))
            
            # Draw ball
            pygame.draw.rect(self.screen, WHITE, 
                           (self.game_state["ball"]["x"], self.game_state["ball"]["y"], 
                            BALL_SIZE, BALL_SIZE))
            
            # Draw center line
            for y in range(0, WINDOW_HEIGHT, 20):
                pygame.draw.rect(self.screen, WHITE, (WINDOW_WIDTH // 2 - 2, y, 4, 10))
            
            # Draw scores
            score_1 = self.font.render(str(self.game_state["score"]["player1"]), True, WHITE)
            score_2 = self.font.render(str(self.game_state["score"]["player2"]), True, WHITE)
            self.screen.blit(score_1, (WINDOW_WIDTH // 4, 20))
            self.screen.blit(score_2, (WINDOW_WIDTH * 3 // 4, 20))
            
            # Draw countdown if active
            if self.game_state["countdown"] is not None:
                countdown_text = self.large_font.render(str(self.game_state["countdown"]), True, WHITE)
                text_rect = countdown_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
                self.screen.blit(countdown_text, text_rect)
            
            # Draw winner message if game is over
            if self.game_state["winner"]:
                winner_text = self.large_font.render(f"{self.game_state['winner']} wins!", True, WHITE)
                restart_text = self.font.render("Press R to restart", True, WHITE)
                
                winner_rect = winner_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 50))
                restart_rect = restart_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 50))
                
                self.screen.blit(winner_text, winner_rect)
                self.screen.blit(restart_text, restart_rect)
            
            # Draw player indicator
            player_text = self.font.render(f"You are Player {self.player_number}", True, WHITE)
            self.screen.blit(player_text, (10, WINDOW_HEIGHT - 40))
            
            # Controls reminder
            controls_text = self.font.render("Controls: ↑/↓ arrows to move, ESC to quit", True, WHITE)
            self.screen.blit(controls_text, (WINDOW_WIDTH // 2 - 180, WINDOW_HEIGHT - 40))
        else:
            # Display waiting message when not receiving game state
            waiting_text = self.font.render("Waiting for game state...", True, WHITE)
            text_rect = waiting_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
            self.screen.blit(waiting_text, text_rect)
        
        # Update the display
        pygame.display.flip()


if __name__ == "__main__":
    # Ask for server address
    server_host = input("Enter server IP (default: localhost): ").strip()
    if not server_host:
        server_host = "localhost"
    
    try:
        server_port = int(input("Enter server port (default: 5555): ").strip())
    except:
        server_port = 5555
    
    client = PongClient(server_host, server_port)
    client.run()