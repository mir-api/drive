"""
PixelLife Evolution Simulator
Autor: Andrés (adaptado por ChatGPT)
Descripción:
- Mundo de celdas (grid). Cada celda puede tener 0 o 1 individuo.
- Individuos tienen genoma simple (RGB color + fuerza, movilidad, cooperacion, give_way).
- Se mueven, pelean, se reproducen, mutan, consumen energía.
- Estadísticas en pantalla (especie dominante por color, poblacion, avg fuerza, mutaciones).
Controles:
- SPACE : pausa / resume
- R     : reset
- S     : guardar screenshot (exporta png)
- +/-   : velocidad (ticks por frame)
- M     : alterna mostrar estadísticas detalladas
"""

import pygame, random, math, time
from collections import defaultdict, Counter

# ========== Config ==========
WINDOW_W, WINDOW_H = 800, 600
GRID_W, GRID_H = 200, 150            # grid cells
CELL_SIZE = max(1, min(8, WINDOW_W // GRID_W))  # cell size (auto)
FPS = 60
INITIAL_FILL = 0.12                  # fraction of cells initially occupied
TICK_PER_FRAME = 1

# Genetic / simulation tuning
BASE_ENERGY = 100
MOVE_COST = 1
REPRODUCE_COST = 30
ATTACK_COST = 5
ENERGY_GAIN_ON_KILL = 40
MUTATION_RATE = 0.08                 # chance per gene to mutate
MUTATION_MAG = 0.12                  # mutation magnitude (fractional)
MIN_ENERGY_TO_REPRODUCE = 80
MAX_AGE = 9999

SHOW_STATS = True

# ========== Helpers ==========
def clamp(v, a, b): return max(a, min(b, v))
def mix(a, b): return (a + b) / 2.0

def color_to_gene(rgb):
    # convert 0-255 rgb to 0-1 floats in genome
    return [c / 255.0 for c in rgb]

def gene_to_color(g):
    return (int(clamp(g[0],0,1)*255), int(clamp(g[1],0,1)*255), int(clamp(g[2],0,1)*255))

def mutate_value(x, mag):
    # x in 0..1, mag fraction
    delta = random.uniform(-mag, mag)
    return clamp(x + delta, 0.0, 1.0)

# ========== Agent ==========
class Agent:
    __slots__ = ("x","y","r","g","b","strength","mobility","cooperation","give_way","energy","age","id")
    _id_counter = 0
    def __init__(self, x,y, genome=None):
        self.x = x; self.y = y
        Agent._id_counter += 1
        self.id = Agent._id_counter
        if genome:
            self.r,self.g,self.b = genome["r"],genome["g"],genome["b"]
            self.strength = genome["strength"]
            self.mobility = genome["mobility"]
            self.cooperation = genome["cooperation"]
            self.give_way = genome["give_way"]
        else:
            # random init
            self.r,self.g,self.b = random.random(), random.random(), random.random()
            self.strength = random.random()
            self.mobility = random.random()
            self.cooperation = random.random()
            self.give_way = random.random()*0.5  # giving way less common
        self.energy = BASE_ENERGY * (0.6 + random.random()*0.8)
        self.age = 0

    def genome(self):
        return {
            "r": self.r, "g": self.g, "b": self.b,
            "strength": self.strength,
            "mobility": self.mobility,
            "cooperation": self.cooperation,
            "give_way": self.give_way
        }

    def color(self):
        return gene_to_color((self.r,self.g,self.b))

    def step_energy_cost(self):
        # energy used each tick, depends on mobility and strength
        return 0.2 + self.mobility*0.5 + self.strength*0.3

    def try_mutate(self):
        # mutate all genes with some probability
        changed = False
        if random.random() < MUTATION_RATE:
            self.r = mutate_value(self.r, MUTATION_MAG); changed = True
        if random.random() < MUTATION_RATE:
            self.g = mutate_value(self.g, MUTATION_MAG); changed = True
        if random.random() < MUTATION_RATE:
            self.b = mutate_value(self.b, MUTATION_MAG); changed = True
        if random.random() < MUTATION_RATE:
            self.strength = clamp(self.strength + random.uniform(-MUTATION_MAG, MUTATION_MAG), 0.0, 1.0); changed = True
        if random.random() < MUTATION_RATE:
            self.mobility = clamp(self.mobility + random.uniform(-MUTATION_MAG, MUTATION_MAG), 0.0, 1.0); changed = True
        if random.random() < MUTATION_RATE:
            self.cooperation = clamp(self.cooperation + random.uniform(-MUTATION_MAG, MUTATION_MAG), 0.0, 1.0); changed = True
        if random.random() < MUTATION_RATE:
            self.give_way = clamp(self.give_way + random.uniform(-MUTATION_MAG, MUTATION_MAG), 0.0, 1.0); changed = True
        return changed

# ========== World ==========
class World:
    def __init__(self, w, h, fill=INITIAL_FILL):
        self.w, self.h = w, h
        self.grid = [[None for _ in range(h)] for __ in range(w)]
        self.agents = []
        self.tick = 0
        self.recent_mutations = 0
        self.event_log = []
        self.populate_random(fill)

    def pos_in_bounds(self, x,y):
        return 0 <= x < self.w and 0 <= y < self.h

    def populate_random(self, fill):
        self.grid = [[None for _ in range(self.h)] for __ in range(self.w)]
        self.agents.clear()
        for x in range(self.w):
            for y in range(self.h):
                if random.random() < fill:
                    a = Agent(x,y)
                    self.grid[x][y] = a
                    self.agents.append(a)

    def clear(self):
        self.grid = [[None for _ in range(self.h)] for __ in range(self.w)]
        self.agents.clear()

    def neighbors(self, x,y):
        dirs = [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,1),(-1,1),(1,-1)]
        for dx,dy in dirs:
            nx,ny = x+dx,y+dy
            if self.pos_in_bounds(nx,ny):
                yield nx,ny

    def step(self):
        self.tick += 1
        self.recent_mutations = 0
        random.shuffle(self.agents)  # randomize order to avoid bias
        to_remove = []
        to_add = []
        for agent in list(self.agents):
            # Skip agents that may have died earlier in this tick
            if agent.energy <= 0:
                if agent not in to_remove:
                    to_remove.append(agent)
                continue

            # base aging and metabolism
            agent.age += 1
            agent.energy -= agent.step_energy_cost()
            if agent.energy <= 0:
                to_remove.append(agent)
                continue

            # Decide whether to move
            if random.random() < agent.mobility:
                # choose a target neighbor (including staying chance)
                choices = [(agent.x, agent.y)] + list(self.neighbors(agent.x, agent.y))
                tx,ty = random.choice(choices)
                if (tx,ty) == (agent.x, agent.y):
                    pass
                else:
                    occupant = self.grid[tx][ty]
                    if occupant is None:
                        # move
                        self.grid[agent.x][agent.y] = None
                        agent.x, agent.y = tx,ty
                        self.grid[tx][ty] = agent
                        agent.energy -= MOVE_COST
                    else:
                        # interaction: decide give way or fight or reproduce
                        # if one gives way, swap or stay
                        if random.random() < agent.give_way:
                            # agent gives way: stays and loses small energy
                            agent.energy -= 0.5
                        elif random.random() < occupant.give_way:
                            # occupant gives way -> occupant moves away if possible
                            moved = False
                            for nx,ny in self.neighbors(occupant.x, occupant.y):
                                if self.grid[nx][ny] is None:
                                    self.grid[occupant.x][occupant.y] = None
                                    occupant.x, occupant.y = nx,ny
                                    self.grid[nx][ny] = occupant
                                    moved = True
                                    break
                            # now move agent into freed cell if freed
                            if moved and self.grid[tx][ty] is None:
                                self.grid[agent.x][agent.y] = None
                                agent.x, agent.y = tx,ty
                                self.grid[tx][ty] = agent
                                agent.energy -= MOVE_COST
                        else:
                            # fight or reproduce depending on cooperation and compatibility
                            compat = color_similarity(agent, occupant)
                            if random.random() < (agent.cooperation * occupant.cooperation * compat):
                                # reproduce (create child in a nearby empty cell if possible)
                                empty = None
                                for nx,ny in self.neighbors(agent.x, agent.y):
                                    if self.grid[nx][ny] is None:
                                        empty = (nx,ny); break
                                if empty:
                                    child = reproduce(agent, occupant, empty[0], empty[1])
                                    to_add.append(child)
                                    agent.energy -= REPRODUCE_COST
                                    occupant.energy -= REPRODUCE_COST/1.5
                                    # small chance of mutation
                                    if child.try_mutate():
                                        self.recent_mutations += 1
                                else:
                                    # no space -> fight instead
                                    if fight(agent, occupant):
                                        # agent wins -> occupant dies
                                        to_remove.append(occupant)
                                        agent.energy += ENERGY_GAIN_ON_KILL
                                    else:
                                        to_remove.append(agent)
                            else:
                                # fight: chance proportional to strength + energy
                                if fight(agent, occupant):
                                    to_remove.append(occupant)
                                    agent.energy += ENERGY_GAIN_ON_KILL
                                else:
                                    to_remove.append(agent)

            # death by age (optional)
            if agent.age > MAX_AGE:
                to_remove.append(agent)

        # apply removals and additions
        for dead in to_remove:
            try:
                if self.grid[dead.x][dead.y] is dead:
                    self.grid[dead.x][dead.y] = None
            except Exception:
                pass
            if dead in self.agents:
                self.agents.remove(dead)
        for child in to_add:
            if self.grid[child.x][child.y] is None:
                self.grid[child.x][child.y] = child
                self.agents.append(child)

        # occasional global events
        if self.tick % 2000 == 0:
            # small random event: starvation or small meteor
            if random.random() < 0.5:
                self.event_log.append(f"{self.tick}: Meteoro - zona afectada")
                self._meteor_event()
            else:
                self.event_log.append(f"{self.tick}: Sequía - energía reducida temporalmente")
                self._drought_event()

    def _meteor_event(self):
        # kill random patch
        cx = random.randrange(self.w); cy = random.randrange(self.h)
        radius = random.randint(3, 12)
        killed = 0
        for x in range(max(0,cx-radius), min(self.w, cx+radius+1)):
            for y in range(max(0,cy-radius), min(self.h, cy+radius+1)):
                if self.grid[x][y]:
                    killed += 1
                    try:
                        self.agents.remove(self.grid[x][y])
                    except ValueError:
                        pass
                    self.grid[x][y] = None
        self.event_log.append(f"  {killed} individuos muertos por meteoro")

    def _drought_event(self):
        # reduce everyone's energy a bit
        for a in self.agents:
            a.energy -= random.uniform(5,20)

    def count_species_by_color(self, bucket=8):
        # bucketize colors to find dominant tones
        ctr = Counter()
        for a in self.agents:
            key = (int(a.r*bucket), int(a.g*bucket), int(a.b*bucket))
            ctr[key] += 1
        if not ctr: return None,0
        k,c = ctr.most_common(1)[0]
        # approximate color back
        return (int(k[0]*255/(bucket-1 if bucket>1 else 1)),
                int(k[1]*255/(bucket-1 if bucket>1 else 1)),
                int(k[2]*255/(bucket-1 if bucket>1 else 1))), c

# ========== Interaction functions ==========
def color_similarity(a,b):
    # cosine similarity between color vectors
    da = (a.r, a.g, a.b)
    db = (b.r, b.g, b.b)
    dot = da[0]*db[0] + da[1]*db[1] + da[2]*db[2]
    mag_a = math.sqrt(da[0]*da[0]+da[1]*da[1]+da[2]*da[2]) + 1e-9
    mag_b = math.sqrt(db[0]*db[0]+db[1]*db[1]+db[2]*db[2]) + 1e-9
    return clamp(dot/(mag_a*mag_b), 0.0, 1.0)

def fight(a,b):
    # returns True if 'a' wins against 'b'
    score_a = a.strength*1.5 + (a.energy / (BASE_ENERGY*1.5))
    score_b = b.strength*1.5 + (b.energy / (BASE_ENERGY*1.5))
    prob_a = score_a / (score_a + score_b + 1e-9)
    # small randomness
    return random.random() < prob_a

def reproduce(a,b, x,y):
    # create child genome as averages + slight random noise
    child = Agent(x,y, genome={
        "r": mix(a.r,b.r),
        "g": mix(a.g,b.g),
        "b": mix(a.b,b.b),
        "strength": mix(a.strength, b.strength),
        "mobility": mix(a.mobility, b.mobility),
        "cooperation": mix(a.cooperation, b.cooperation),
        "give_way": mix(a.give_way, b.give_way),
    })
    # child initial energy smaller
    child.energy = (a.energy + b.energy) * 0.15
    return child

# ========== Rendering / UI ==========
def draw_world(screen, world):
    # draw agents as colored rects (pixels/cells)
    for x in range(world.w):
        col = world.grid[x]
        for y in range(world.h):
            a = col[y]
            if a:
                rect = pygame.Rect(x*CELL_SIZE, y*CELL_SIZE, CELL_SIZE, CELL_SIZE)
                screen.fill(a.color(), rect)

def draw_overlay(screen, world, font, paused, speed, show_detailed):
    # stats box
    surf = pygame.Surface((320, 140))
    surf.set_alpha(200)
    surf.fill((20,20,20))
    screen.blit(surf, (8,8))
    small = font
    lines = []
    lines.append(f"Tick: {world.tick}   Agents: {len(world.agents)}  Speed: {speed}x")
    dom_color, dom_count = world.count_species_by_color()
    if dom_color:
        lines.append(f"Dominant color count: {dom_count}")
    else:
        lines.append("Dominant color: -")
    # averages
    if world.agents:
        avg_str = sum(a.strength for a in world.agents)/len(world.agents)
        avg_mob = sum(a.mobility for a in world.agents)/len(world.agents)
        avg_coop= sum(a.cooperation for a in world.agents)/len(world.agents)
    else:
        avg_str=avg_mob=avg_coop=0
    lines.append(f"Avg strength: {avg_str:.2f}  mobility: {avg_mob:.2f}")
    lines.append(f"Avg cooperation: {avg_coop:.2f}  recent mutations: {world.recent_mutations}")
    if paused:
        lines.append("PAUSED (SPACE to resume)")
    else:
        lines.append("Running (SPACE to pause)")
    if show_detailed:
        # top species colors histogram (bucket)
        ctr = Counter()
        for a in world.agents:
            key = (int(a.r*6), int(a.g*6), int(a.b*6))
            ctr[key] += 1
        top = ctr.most_common(5)
        for k,c in top:
            # decode approx color
            col = (int(k[0]*255/6), int(k[1]*255/6), int(k[2]*255/6))
            lines.append(f"color {col} : {c}")
    # render lines
    y = 12
    for L in lines:
        surf_text = small.render(L, True, (230,230,230))
        screen.blit(surf_text, (12, 12 + y))
        y += 18
    # draw dominant color box
    if dom_color:
        pygame.draw.rect(screen, dom_color, pygame.Rect(8+320-36, 8+12, 28, 28))
    # events on bottom-left
    e_y = WINDOW_H - 64
    for e in world.event_log[-4:]:
        ev_surf = small.render(e, True, (220,200,200))
        screen.blit(ev_surf, (10, e_y))
        e_y += 16

# ========== Main ==========
def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("PixelLife Evolution Simulator")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 14)

    world = World(GRID_W, GRID_H)
    paused = False
    speed = 1
    show_detailed = False

    last_screenshot = 0

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_r:
                    world = World(GRID_W, GRID_H)
                elif event.key == pygame.K_s:
                    # screenshot
                    fname = f"pixellife_screenshot_{int(time.time())}.png"
                    pygame.image.save(screen, fname)
                    last_screenshot = time.time()
                    print(f"Saved screenshot: {fname}")
                elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                    speed = min(8, speed+1)
                elif event.key == pygame.K_MINUS:
                    speed = max(1, speed-1)
                elif event.key == pygame.K_m:
                    show_detailed = not show_detailed

        if not paused:
            for _ in range(speed):
                world.step()

        # draw background (dark)
        screen.fill((8,8,9))

        draw_world(screen, world)
        draw_overlay(screen, world, font, paused, speed, show_detailed)

        # small footer
        footer = font.render("SPACE pause | R reset | S screenshot | +/- speed | M toggle details", True, (120,120,120))
        screen.blit(footer, (8, WINDOW_H-22))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()
