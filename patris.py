import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import random
import time
import pulser as pl
import pulser_simulation as plsim
import argparse


# Game Constants
COLS = 10
ROWS = 20
COLOR_MAP = {
    0: 'black',      # Empty
    1: 'cyan',       # I
    2: 'yellow',     # O
    3: 'purple',     # T
    4: 'orange',     # L
    5: 'blue',       # J
    6: 'green',      # S
    7: 'red'         # Z
}

# Tetromino Shapes (same as before)
SHAPES = [
    [[(0, 0), (1, 0), (2, 0), (3, 0)], [(0, 0), (0, 1), (0, 2), (0, 3)]],  # I
    [[(0, 0), (1, 0), (0, 1), (1, 1)]],                                  # O
    [[(1, 0), (0, 1), (1, 1), (2, 1)], [(1, 0), (1, 1), (2, 1), (1, 2)],
     [(0, 1), (1, 1), (2, 1), (1, 2)], [(1, 0), (0, 1), (1, 1), (1, 2)]],# T
    [[(0, 0), (0, 1), (0, 2), (1, 2)], [(0, 1), (1, 1), (2, 1), (0, 2)],
     [(1, 0), (1, 1), (1, 2), (0, 0)], [(2, 0), (0, 1), (1, 1), (2, 1)]],# L
    [[(1, 0), (1, 1), (1, 2), (0, 2)], [(0, 0), (0, 1), (1, 1), (2, 1)],
     [(0, 0), (1, 0), (0, 1), (0, 2)], [(0, 1), (1, 1), (2, 1), (2, 2)]],# J
    [[(1, 0), (2, 0), (0, 1), (1, 1)], [(0, 0), (0, 1), (1, 1), (1, 2)]],# S
    [[(0, 0), (1, 0), (1, 1), (2, 1)], [(1, 0), (0, 1), (1, 1), (0, 2)]] # Z
]

class TetrisGame:
    def __init__(self, quantum: bool = False):
        self.grid = np.zeros((ROWS, COLS), dtype=int)
        self.current_piece = self.new_piece()
        self.score = 0
        self.timer = 60.0
        self.game_over = False
        self.quantum = quantum
        self.last_update = time.time()
        self.registerlay = pl.register.RectangularLatticeLayout(ROWS, COLS, 5, 5)
        self.reg = None

        self.fig, self.ax = plt.subplots()
        self.fig.subplots_adjust(right=0.85)
        self.img = self.ax
        self.timer_text = self.fig.text(0.88, 0.9, f"Time: {int(self.timer)}")
        self.score_text = self.fig.text(0.88, 0.85, f"Score: {self.score}")
        self.fig.canvas.mpl_connect('key_press_event', self.on_key)

    def new_piece(self):
        shape_idx = random.randint(0, 6)
        return {
            'shape': SHAPES[shape_idx][0],
            'rotations': SHAPES[shape_idx],
            'rotation': 0,
            'color': shape_idx + 1,  # Colors start from 1
            'x': COLS//2 - 2,
            'y': 0
        }

    def trap_to_coords(self, trap_id):
        """Convert trap index to (x, y) grid coordinates"""
        x = trap_id % COLS
        y = ROWS - 1 - (trap_id // COLS)
        return (x, y)

    def coords_to_trap(self, x, y):
        """Convert grid coordinates to trap index"""
        return (ROWS - 1 - y) + ROWS * x

    def get_block_coordinates(self):
        """Return all active block coordinates (both grid and current piece)"""
        blocks = []
        # Grid blocks
        for y in range(ROWS):
            for x in range(COLS):
                if self.grid[y, x] > 0:
                    blocks.append((x, y))

        if not self.game_over:
            for dx, dy in self.current_piece['shape']:
                x = self.current_piece['x'] + dx
                y = self.current_piece['y'] + dy
                if 0 <= x < COLS and 0 <= y < ROWS:
                    blocks.append((x, y))
        return blocks
    def get_activated_traps(self):
        """Returns list of activated trap indices (0-based)"""
        activated = []

        for y in range(ROWS):
            for x in range(COLS):
                if self.grid[y][x] != 0:
                    # Convert to trap index (0 = bottom-left, ROWS*COLS-1 = top-right)

                    trap_id = self.coords_to_trap(x, y)# (ROWS - 1 - y) * COLS + x
                    activated.append(trap_id)

        # Add current piece blocks
        if not self.game_over:
            for dx, dy in self.current_piece['shape']:
                x = self.current_piece['x'] + dx
                y_piece = self.current_piece['y'] + dy
                if 0 <= x < COLS and 0 <= y_piece < ROWS:
                    # Convert piece position to trap index
                    trap_id = self.coords_to_trap(x, y_piece) #(ROWS - 1 - y_piece) * COLS + x
                    activated.append(trap_id)
        return list(set(activated))  # Remove duplicates

    def check_collision(self, x, y, shape):
        for dx, dy in shape:
            col = x + dx
            row = y + dy
            if col < 0 or col >= COLS or row >= ROWS:
                return True
            if row >= 0 and self.grid[row, col]:
                return True
        return False

    def rotate_piece(self):
        piece = self.current_piece
        next_rotation = (piece['rotation'] + 1) % len(piece['rotations'])
        new_shape = piece['rotations'][next_rotation]

        if not self.check_collision(piece['x'], piece['y'], new_shape):
            piece['shape'] = new_shape
            piece['rotation'] = next_rotation

    def clear_lines(self):
        full_rows = np.all(self.grid > 0, axis=1)
        lines_cleared = np.sum(full_rows)
        if lines_cleared > 0:
            self.grid = np.vstack([np.zeros((lines_cleared, COLS), dtype=int),
                                 self.grid[~full_rows]])
            self.timer += lines_cleared * 5
            self.score += lines_cleared * 100
    
    def dumb_sequence(self):
        if self.reg is not None:
            seq = pl.Sequence(self.reg, device=pl.MockDevice)
            seq.declare_channel("ch0", "rydberg_global")
            simple_pulser = pl.Pulse.ConstantPulse(duration=4000, amplitude=0.5, detuning=-5,phase=0)
            seq.add(simple_pulser, "ch0")
            emu = plsim.QutipEmulator.from_sequence(seq)
            emu.run()


    def update(self):
        if self.game_over:
            return None

        current_time = time.time()
        dt = current_time - self.last_update
        if self.quantum:
            self.dumb_sequence()
        self.last_update = current_time
        self.timer -= dt

        if self.timer <= 0:
            self.game_over = True
            return

        # Auto-move down every 0.5 seconds
        if current_time % 0.5 < dt:
            if not self.check_collision(self.current_piece['x'], 
                                      self.current_piece['y'] + 1,
                                      self.current_piece['shape']):
                self.current_piece['y'] += 1
            else:
                # Lock piece in place
                for dx, dy in self.current_piece['shape']:
                    x = self.current_piece['x'] + dx
                    y = self.current_piece['y'] + dy
                    if 0 <= x < COLS and 0 <= y < ROWS:
                        self.grid[y, x] = self.current_piece['color']

                self.clear_lines()
                self.current_piece = self.new_piece()

                if self.check_collision(self.current_piece['x'],
                                      self.current_piece['y'],
                                      self.current_piece['shape']):
                    self.game_over = True

    def on_key(self, event):
        if self.game_over:
            return

        piece = self.current_piece
        if event.key == 'left':
            if not self.check_collision(piece['x'] - 1, piece['y'], piece['shape']):
                piece['x'] -= 1
        elif event.key == 'right':
            if not self.check_collision(piece['x'] + 1, piece['y'], piece['shape']):
                piece['x'] += 1
        elif event.key == 'up':
            self.rotate_piece()
        elif event.key == 'down':
            if not self.check_collision(piece['x'], piece['y'] + 1, piece['shape']):
                piece['y'] += 1

        self.redraw()

    def redraw(self):

        activated_traps = self.get_activated_traps()
        self.reg = self.registerlay.define_register(*activated_traps)
        self.ax.clear()
        self.img = self.reg.draw(with_labels=False, show = False, custom_ax=self.ax)
        self.ax.axis("auto")
        self.ax.set_xlim(-50, 60)
        self.ax.set_ylim(-50, 60)
        self.timer_text.set_text(f"Time: {max(0, int(self.timer))}")
        self.score_text.set_text(f"Score: {self.score}")

        if self.game_over:
            self.ax.text(COLS/2, ROWS/2, "GAME OVER", 
                        ha='center', va='center', color='green', fontsize=20)
        self.fig.canvas.draw_idle()

    def get_register(self)->pl.Register:
        activated_traps = self.get_activated_traps()
        return self.registerlay.define_register(*activated_traps)


def animate(frame):
    game.update()
    game.redraw()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Do you want to play quantum PATRIS?")
    parser.add_argument('--quantum', action='store_true', help='Enable the quantum feature')

    args = parser.parse_args()

    print(f"Quantum feature enabled: {args.quantum}")
    game = TetrisGame(quantum=args.quantum)
    ani = animation.FuncAnimation(game.fig, animate, interval=500)
    plt.show()