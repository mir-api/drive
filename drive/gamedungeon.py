"""
Mini Dungeon (sin librerías externas)
Controles: w (arriba), s (abajo), a (izquierda), d (derecha), q para salir.
Objetivo: recoger 3 tesoros y salir por la puerta (E).
"""
import random
import os
import sys
import time

WIDTH = 11
HEIGHT = 9
NUM_TREASURES = 3
NUM_MONSTERS = 4

WALL = '#'
FLOOR = '.'
PLAYER = '@'
TREASURE = '$'
MONSTER = 'M'
EXIT = 'E'

def clear():
    # cross-platform clear screen
    os.system('cls' if os.name == 'nt' else 'clear')

def make_empty_map(w, h):
    grid = [[FLOOR for _ in range(w)] for _ in range(h)]
    # add border walls
    for x in range(w):
        grid[0][x] = WALL
        grid[h-1][x] = WALL
    for y in range(h):
        grid[y][0] = WALL
        grid[y][w-1] = WALL
    # add some inner random walls
    for _ in range((w*h)//12):
        x = random.randint(1, w-2)
        y = random.randint(1, h-2)
        grid[y][x] = WALL
    return grid

def find_free_cell(grid):
    h = len(grid)
    w = len(grid[0])
    while True:
        x = random.randint(1, w-2)
        y = random.randint(1, h-2)
        if grid[y][x] == FLOOR:
            return x, y

def place_items(grid):
    treasures = []
    monsters = []
    for _ in range(NUM_TREASURES):
        treasures.append(find_free_cell(grid))
    for _ in range(NUM_MONSTERS):
        monsters.append(find_free_cell(grid))
    exit_pos = find_free_cell(grid)
    player_pos = find_free_cell(grid)
    return player_pos, treasures, monsters, exit_pos

def draw(grid, player, treasures, monsters, exit_pos, hp, score, moves):
    clear()
    h = len(grid)
    w = len(grid[0])
    # make a copy for display
    disp = [row[:] for row in grid]
    ex = exit_pos
    disp[ex[1]][ex[0]] = EXIT
    for tx,ty in treasures:
        disp[ty][tx] = TREASURE
    for mx,my in monsters:
        disp[my][mx] = MONSTER
    px,py = player
    disp[py][px] = PLAYER
    print("Mini Dungeon  — recoge {} tesoros y sal por la E".format(NUM_TREASURES))
    print("HP: {}  |  Tesoros: {}  |  Movimientos: {}".format(hp, score, moves))
    print()
    for row in disp:
        print(''.join(row))
    print()
    print("Controles: w/a/s/d mover, q salir")

def move_pos(pos, direction):
    x,y = pos
    if direction == 'w': y -= 1
    elif direction == 's': y += 1
    elif direction == 'a': x -= 1
    elif direction == 'd': x += 1
    return x,y

def in_bounds(grid, pos):
    x,y = pos
    return 0 <= y < len(grid) and 0 <= x < len(grid[0])

def fight_monster(hp):
    # simple fight: 50% win chance, if lose - lose HP
    roll = random.random()
    if roll < 0.5:
        # player wins but loses a little stamina
        dmg = random.randint(0,1)
        hp -= dmg
        return True, hp, "Derrotaste al monstruo pero perdiste {} HP.".format(dmg)
    else:
        dmg = random.randint(1,3)
        hp -= dmg
        return False, hp, "El monstruo te hirió y perdiste {} HP.".format(dmg)

def main():
    random.seed()
    grid = make_empty_map(WIDTH, HEIGHT)
    player, treasures, monsters, exit_pos = place_items(grid)
    hp = 6
    score = 0
    moves = 0

    while True:
        draw(grid, player, treasures, monsters, exit_pos, hp, score, moves)
        if hp <= 0:
            print("Has muerto. Game over.")
            break
        if score >= NUM_TREASURES and player == exit_pos:
            print("¡Felicidades! Recogiste {} tesoros y saliste. Ganaste.".format(NUM_TREASURES))
            break

        ch = input("Tu movimiento: ").strip().lower()
        if not ch:
            continue
        if ch[0] == 'q':
            print("Saliendo...")
            break
        dirc = ch[0]
        if dirc not in ('w','a','s','d'):
            print("Usa w/a/s/d para moverte.")
            time.sleep(0.3)
            continue

        newp = move_pos(player, dirc)
        if not in_bounds(grid, newp):
            print("No puedes salir del mapa.")
            time.sleep(0.2)
            continue
        nx, ny = newp
        if grid[ny][nx] == WALL:
            print("Hay una pared ahí.")
            time.sleep(0.2)
            continue

        moves += 1
        # check monster
        if (nx,ny) in monsters:
            win, hp, message = fight_monster(hp)
            print(message)
            time.sleep(0.6)
            if win:
                monsters.remove((nx,ny))
            else:
                # if still alive, monster remains; if hp <=0 loop will end next
                pass
            # do not move into the monster tile if you lost the fight
            if not win:
                continue

        # move player
        player = (nx, ny)

        # check treasure
        if player in treasures:
            treasures.remove(player)
            score += 1
            print("Encontraste un tesoro! ({}/{})".format(score, NUM_TREASURES))
            time.sleep(0.6)

        # small random event: trap
        if random.random() < 0.06:
            trap = random.randint(1,2)
            hp -= trap
            print("¡Trampa! Perdiste {} HP.".format(trap))
            time.sleep(0.6)

    print("Partida terminada. Resumen: Movimientos {}, HP final {}, Tesoros {}.".format(moves, hp, score))
    print("Gracias por jugar.")

if __name__ == '__main__':
    main()
