import pygame
import sys
import math
import time
from datetime import datetime
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *

# --- 定数 ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
SKY_COLOR = (0.5, 0.8, 1.0, 1)
CAPTION = "MinepAIycraft"
GROUND_SIZE = 20
VIEW_DISTANCE = 14
MAX_REACH = 6
WORLD_MIN_Y = -4
WORLD_MAX_Y = 8
LOG_PATH = "minepAIycraft.log"

# --- ブロックの定義 ---
VERTICES = ((0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5), (-0.5, -0.5, -0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, -0.5, 0.5), (-0.5, 0.5, 0.5))
SURFACES = ((0, 1, 2, 3), (3, 2, 7, 6), (6, 7, 5, 4), (4, 5, 1, 0), (1, 5, 7, 2), (4, 0, 3, 6))
EDGES = (
    (0, 1), (1, 2), (2, 3), (3, 0),
    (4, 5), (5, 7), (7, 6), (6, 4),
    (0, 4), (1, 5), (2, 7), (3, 6),
)
COLORS = {"grass": (0.3, 0.8, 0.2), "dirt": (0.6, 0.4, 0.2)}
CUBE_LIST = None
BLOCKS = set()
BLOCKS_PLACED = 0
BLOCKS_REMOVED = 0
SESSION_START = time.time()

def draw_cube():
    glCallList(CUBE_LIST)

def draw_cube_edges():
    glColor3f(0.0, 0.0, 0.0)
    glBegin(GL_LINES)
    for edge in EDGES:
        for vertex_index in edge:
            glVertex3fv(VERTICES[vertex_index])
    glEnd()

# --- プレイヤー/カメラ ---
PLAYER_HEIGHT = 1.8
PLAYER_RADIUS = 0.3
EYE_HEIGHT = 1.6
CROUCH_HEIGHT = 1.2
CROUCH_EYE_HEIGHT = 1.0
MOVE_SPEED = 0.1
CROUCH_SPEED = 0.05
MOUSE_SENSITIVITY = 0.1
GRAVITY = -0.01
JUMP_VELOCITY = 0.18

class Camera:
    def __init__(self):
        self.rotation = [0, 0] # [yaw, pitch]

class Player:
    def __init__(self):
        self.position = [0.0, 0.0, 0.0] # 足元座標
        self.velocity_y = 0.0
        self.on_ground = False
        self.crouching = False

camera = Camera()
player = Player()

# --- ゲームエンジン ver1.3 (操作) ---

def init_gl():
    """ OpenGLの初期化 """
    build_cube_list()
    glViewport(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(45, (SCREEN_WIDTH / SCREEN_HEIGHT), 0.1, 100.0)
    glMatrixMode(GL_MODELVIEW)
    glClearColor(*SKY_COLOR)
    glEnable(GL_DEPTH_TEST)
    glLineWidth(1.0)

def build_cube_list():
    global CUBE_LIST
    CUBE_LIST = glGenLists(1)
    glNewList(CUBE_LIST, GL_COMPILE)
    glBegin(GL_QUADS)
    for i, surface in enumerate(SURFACES):
        glColor3fv(COLORS["grass"] if i == 4 else COLORS["dirt"])
        for vertex_index in surface:
            glVertex3fv(VERTICES[vertex_index])
    glEnd()
    glEndList()

def init_world():
    BLOCKS.clear()
    for x in range(-GROUND_SIZE // 2, GROUND_SIZE // 2):
        for z in range(-GROUND_SIZE // 2, GROUND_SIZE // 2):
            BLOCKS.add((x, -1, z))

def log_event(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(f"[{timestamp}] {message}")

def apply_camera_transform():
    """ カメラの変形を適用する """
    glLoadIdentity()
    glRotatef(camera.rotation[1], 1, 0, 0) # Pitch
    glRotatef(camera.rotation[0], 0, 1, 0) # Yaw
    glTranslatef(-player.position[0], -(player.position[1] + get_eye_height()), -player.position[2])

def get_player_height():
    return CROUCH_HEIGHT if player.crouching else PLAYER_HEIGHT

def get_eye_height():
    return CROUCH_EYE_HEIGHT if player.crouching else EYE_HEIGHT

def get_view_direction():
    yaw_rad = math.radians(camera.rotation[0])
    pitch_rad = math.radians(camera.rotation[1])
    dir_x = math.sin(yaw_rad) * math.cos(pitch_rad)
    dir_y = -math.sin(pitch_rad)
    dir_z = -math.cos(yaw_rad) * math.cos(pitch_rad)
    return (dir_x, dir_y, dir_z)

def intbound(s, ds):
    if ds > 0:
        return (math.floor(s + 1) - s) / ds
    if ds < 0:
        return (s - math.floor(s)) / (-ds)
    return float("inf")

def raycast_blocks(origin, direction, max_dist):
    ox, oy, oz = origin
    dx, dy, dz = direction
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length <= 0.0:
        return (None, None)
    dx /= length
    dy /= length
    dz /= length

    px = ox + 0.5
    py = oy + 0.5
    pz = oz + 0.5
    vx = math.floor(px)
    vy = math.floor(py)
    vz = math.floor(pz)

    step_x = 1 if dx > 0 else -1 if dx < 0 else 0
    step_y = 1 if dy > 0 else -1 if dy < 0 else 0
    step_z = 1 if dz > 0 else -1 if dz < 0 else 0

    t_max_x = intbound(px, dx)
    t_max_y = intbound(py, dy)
    t_max_z = intbound(pz, dz)
    t_delta_x = abs(1 / dx) if dx != 0 else float("inf")
    t_delta_y = abs(1 / dy) if dy != 0 else float("inf")
    t_delta_z = abs(1 / dz) if dz != 0 else float("inf")

    prev = None
    t = 0.0
    while t <= max_dist:
        if (vx, vy, vz) in BLOCKS:
            return ((vx, vy, vz), prev)
        if t_max_x < t_max_y:
            if t_max_x < t_max_z:
                prev = (vx, vy, vz)
                vx += step_x
                t = t_max_x
                t_max_x += t_delta_x
            else:
                prev = (vx, vy, vz)
                vz += step_z
                t = t_max_z
                t_max_z += t_delta_z
        else:
            if t_max_y < t_max_z:
                prev = (vx, vy, vz)
                vy += step_y
                t = t_max_y
                t_max_y += t_delta_y
            else:
                prev = (vx, vy, vz)
                vz += step_z
                t = t_max_z
                t_max_z += t_delta_z

        if (vx < -GROUND_SIZE // 2 or vx >= GROUND_SIZE // 2 or
            vz < -GROUND_SIZE // 2 or vz >= GROUND_SIZE // 2 or
            vy < WORLD_MIN_Y or vy > WORLD_MAX_Y):
            return (None, None)
    return (None, None)

def get_target_block():
    eye = (player.position[0], player.position[1] + get_eye_height(), player.position[2])
    direction = get_view_direction()
    hit, _ = raycast_blocks(eye, direction, MAX_REACH)
    return hit

def get_player_aabb(pos):
    min_x = pos[0] - PLAYER_RADIUS
    max_x = pos[0] + PLAYER_RADIUS
    min_y = pos[1]
    max_y = pos[1] + get_player_height()
    min_z = pos[2] - PLAYER_RADIUS
    max_z = pos[2] + PLAYER_RADIUS
    return (min_x, max_x, min_y, max_y, min_z, max_z)

def block_aabb(x, y, z):
    return (x - 0.5, x + 0.5, y - 0.5, y + 0.5, z - 0.5, z + 0.5)

def aabb_overlap(a, b):
    return (a[0] < b[1] and a[1] > b[0] and
            a[2] < b[3] and a[3] > b[2] and
            a[4] < b[5] and a[5] > b[4])

def iter_nearby_blocks(aabb):
    min_x = math.floor(aabb[0] - 0.5)
    max_x = math.floor(aabb[1] + 0.5)
    min_y = math.floor(aabb[2] - 0.5)
    max_y = math.floor(aabb[3] + 0.5)
    min_z = math.floor(aabb[4] - 0.5)
    max_z = math.floor(aabb[5] + 0.5)
    for x in range(min_x, max_x + 1):
        if x < -GROUND_SIZE // 2 or x >= GROUND_SIZE // 2:
            continue
        for y in range(min_y, max_y + 1):
            if y < WORLD_MIN_Y or y > WORLD_MAX_Y:
                continue
            for z in range(min_z, max_z + 1):
                if z < -GROUND_SIZE // 2 or z >= GROUND_SIZE // 2:
                    continue
                if (x, y, z) in BLOCKS:
                    yield (x, y, z)

def resolve_collisions(dx, dy, dz):
    # X
    if dx != 0.0:
        player.position[0] += dx
        aabb = get_player_aabb(player.position)
        for bx, by, bz in iter_nearby_blocks(aabb):
            baabb = block_aabb(bx, by, bz)
            if aabb_overlap(aabb, baabb):
                if dx > 0:
                    player.position[0] = baabb[0] - PLAYER_RADIUS
                else:
                    player.position[0] = baabb[1] + PLAYER_RADIUS
                aabb = get_player_aabb(player.position)
    # Z
    if dz != 0.0:
        player.position[2] += dz
        aabb = get_player_aabb(player.position)
        for bx, by, bz in iter_nearby_blocks(aabb):
            baabb = block_aabb(bx, by, bz)
            if aabb_overlap(aabb, baabb):
                if dz > 0:
                    player.position[2] = baabb[4] - PLAYER_RADIUS
                else:
                    player.position[2] = baabb[5] + PLAYER_RADIUS
                aabb = get_player_aabb(player.position)
    # Y
    if dy != 0.0:
        player.position[1] += dy
        aabb = get_player_aabb(player.position)
        for bx, by, bz in iter_nearby_blocks(aabb):
            baabb = block_aabb(bx, by, bz)
            if aabb_overlap(aabb, baabb):
                if dy > 0:
                    player.position[1] = baabb[2] - get_player_height()
                    player.velocity_y = 0.0
                else:
                    player.position[1] = baabb[3]
                    player.velocity_y = 0.0
                    player.on_ground = True
                aabb = get_player_aabb(player.position)

def handle_input():
    """ ユーザー入力を処理する """
    keys = pygame.key.get_pressed()
    player.crouching = keys[K_LSHIFT] or keys[K_RSHIFT]
    
    # マウスの動き
    dx, dy = pygame.mouse.get_rel()
    camera.rotation[0] += dx * MOUSE_SENSITIVITY
    camera.rotation[1] += dy * MOUSE_SENSITIVITY
    camera.rotation[1] = max(-89, min(89, camera.rotation[1]))
    
    # Yawをラジアンに変換
    yaw_rad = math.radians(camera.rotation[0])
    
    # 正しい前方・右方ベクトルを計算
    # OpenGLの-Z方向が前方であることを考慮する
    fwd_x_comp = math.sin(yaw_rad)
    fwd_z_comp = -math.cos(yaw_rad)
    
    right_x_comp = math.cos(yaw_rad)
    right_z_comp = math.sin(yaw_rad)

    # WASDキーでの移動
    move_dx = 0.0
    move_dz = 0.0
    speed = CROUCH_SPEED if player.crouching else MOVE_SPEED
    if keys[K_w]: # 前進
        move_dx += fwd_x_comp * speed
        move_dz += fwd_z_comp * speed
    if keys[K_s]: # 後退
        move_dx -= fwd_x_comp * speed
        move_dz -= fwd_z_comp * speed
    if keys[K_a]: # 左へ平行移動
        move_dx -= right_x_comp * speed
        move_dz -= right_z_comp * speed
    if keys[K_d]: # 右へ平行移動
        move_dx += right_x_comp * speed
        move_dz += right_z_comp * speed

    if keys[K_SPACE] and player.on_ground:
        player.velocity_y = JUMP_VELOCITY
        player.on_ground = False

    return move_dx, move_dz

def draw_ground():
    """ 地面を描画する """
    center_x = player.position[0]
    center_z = player.position[2]
    for (x, y, z) in BLOCKS:
        if abs(x - center_x) > VIEW_DISTANCE:
            continue
        if abs(z - center_z) > VIEW_DISTANCE:
            continue
        glPushMatrix()
        glTranslatef(x, y, z)
        draw_cube()
        glPopMatrix()

def draw_target_block_outline(target):
    if target is None:
        return
    glPushMatrix()
    glTranslatef(target[0], target[1], target[2])
    glScalef(1.001, 1.001, 1.001)
    draw_cube_edges()
    glPopMatrix()

def draw_crosshair():
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glDisable(GL_DEPTH_TEST)
    glLineWidth(2.0)
    glColor3f(0.0, 0.0, 0.0)
    cx = SCREEN_WIDTH * 0.5
    cy = SCREEN_HEIGHT * 0.5
    gap = 4
    length = 8
    glBegin(GL_LINES)
    glVertex2f(cx - length, cy)
    glVertex2f(cx - gap, cy)
    glVertex2f(cx + gap, cy)
    glVertex2f(cx + length, cy)
    glVertex2f(cx, cy - length)
    glVertex2f(cx, cy - gap)
    glVertex2f(cx, cy + gap)
    glVertex2f(cx, cy + length)
    glEnd()
    glLineWidth(1.0)
    glEnable(GL_DEPTH_TEST)
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def is_supported(pos):
    foot_y = pos[1]
    support_y = foot_y - 0.001
    for (x, y, z) in BLOCKS:
        if abs((y + 0.5) - support_y) > 0.01:
            continue
        if abs(pos[0] - x) <= (0.5 - 0.001 + PLAYER_RADIUS):
            if abs(pos[2] - z) <= (0.5 - 0.001 + PLAYER_RADIUS):
                return True
    return False

def can_place_block(pos):
    if pos is None:
        return False
    x, y, z = pos
    if x < -GROUND_SIZE // 2 or x >= GROUND_SIZE // 2:
        return False
    if z < -GROUND_SIZE // 2 or z >= GROUND_SIZE // 2:
        return False
    if y < WORLD_MIN_Y or y > WORLD_MAX_Y:
        return False
    if (x, y, z) in BLOCKS:
        return False
    player_aabb = get_player_aabb(player.position)
    block_aabb_vals = block_aabb(x, y, z)
    if aabb_overlap(player_aabb, block_aabb_vals):
        return False
    return True

def main():
    """ ゲームのメイン処理 """
    global BLOCKS_PLACED, BLOCKS_REMOVED, SESSION_START
    BLOCKS_PLACED = 0
    BLOCKS_REMOVED = 0
    SESSION_START = time.time()
    pygame.init()
    pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), DOUBLEBUF | OPENGL)
    pygame.display.set_caption(CAPTION)
    
    # マウスを非表示 & ウィンドウ内に固定
    pygame.mouse.set_visible(False)
    pygame.event.set_grab(True)
    
    init_gl()
    init_world()
    log_event("Session start")
    clock = pygame.time.Clock()

    def shutdown_and_exit():
        duration = time.time() - SESSION_START
        log_event(
            "Session end"
            f" | duration={duration:.1f}s"
            f" | placed={BLOCKS_PLACED}"
            f" | removed={BLOCKS_REMOVED}"
            f" | pos=({player.position[0]:.2f},{player.position[1]:.2f},{player.position[2]:.2f})"
        )
        pygame.quit()
        sys.exit()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                shutdown_and_exit()
            if event.type == KEYDOWN and event.key == K_r:
                player.position = [0.0, 0.0, 0.0]
                player.velocity_y = 0.0
                player.on_ground = False
                log_event("Respawn")
            if event.type == MOUSEBUTTONDOWN:
                eye = (player.position[0], player.position[1] + get_eye_height(), player.position[2])
                direction = get_view_direction()
                hit, prev = raycast_blocks(eye, direction, MAX_REACH)
                if event.button == 3:
                    if hit is not None and hit in BLOCKS:
                        BLOCKS.discard(hit)
                        BLOCKS_REMOVED += 1
                if event.button == 1:
                    if can_place_block(prev):
                        BLOCKS.add(prev)
                        BLOCKS_PLACED += 1

        move_dx, move_dz = handle_input()
        if player.crouching and player.on_ground and (move_dx != 0.0 or move_dz != 0.0):
            next_pos = [player.position[0] + move_dx, player.position[1], player.position[2] + move_dz]
            if not is_supported(next_pos):
                move_dx = 0.0
                move_dz = 0.0

        player.on_ground = False
        player.velocity_y += GRAVITY
        resolve_collisions(move_dx, player.velocity_y, move_dz)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        apply_camera_transform()
        draw_ground()
        target = get_target_block()
        draw_target_block_outline(target)
        draw_crosshair()
        
        pygame.display.flip()
        clock.tick(60) # 60 FPSに制限


if __name__ == '__main__':
    main()
