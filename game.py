import pygame
import os
import sys
import random

#basic screen setup
screen_width, screen_height = 960, 704
tile_size = 64
fps = 60

#physics
gravity = 0.8
jump_speed = -22
player_move_speed = 7
enemy_move_speed = 2

#animation speed
anim_speed = 0.15

#level dimensions
level_columns = 80
level_rows = 12

#colors
background_color = (40, 40, 60)
text_color = (255, 255, 255)
ui_overlay_color = (0, 0, 0, 200)

#sprite sheet slices
#player
player_idle_rect  = (0, 0, 96, 96)
player_walk1_rect = (96, 0, 96, 96)
player_walk2_rect = (192, 0, 96, 96)
player_jump_rect  = (288, 0, 96, 96)

#tiles
tile_grass_rect = (64, 0, 64, 64)
tile_dirt_rect  = (64, 64, 64, 64)

#items and objects
item_gem_rect  = (512, 192, 64, 64)
item_key_rect  = (512, 256, 64, 64)
tile_door_rect = (512, 320, 64, 128)
enemy_rect = (64, 320, 64, 64)


#classes

class WorldObject(pygame.sprite.Sprite):
    #just a generic class for static things like walls or gems
    def __init__(self, x, y, image, type_tag):
        super().__init__()
        self.image = image
        self.rect = self.image.get_rect(topleft=(x, y))
        self.type = type_tag


class PatrollingEnemy(pygame.sprite.Sprite):
    #enemy that walks on a platform
    def __init__(self, x, y, image, platform_rect):
        super().__init__()
        self.image = image
        self.rect = self.image.get_rect(topleft=(x, y))
        self.speed = enemy_move_speed
        
        #boundaries for the enemy
        self.min_x = platform_rect.left
        self.max_x = platform_rect.right

    def update(self):
        self.rect.x += self.speed
        if self.rect.right > self.max_x or self.rect.left < self.min_x:
            self.speed *= -1


class PlayerCharacter(pygame.sprite.Sprite):
    #handles the player
    def __init__(self, x, y, sprite_sheet, wall_group, item_group, enemy_group):
        super().__init__()
        self.sprite_sheet = sprite_sheet
        self.load_animation_frames()

        self.frame_index = 0.0
        self.state = 'idle'
        self.facing_right = True

        self.image = self.animations['idle_r'][0]
        self.rect = self.image.get_rect(topleft=(x, y))

        self.speed = pygame.math.Vector2(0, 0)
        self.on_ground = False

        #keep track of collision
        self.walls = wall_group
        self.items = item_group
        self.enemies = enemy_group

        #game state
        self.has_key = False
        self.gems_collected = 0
        self.won = False
        self.dead = False

    def slicer(self, rect):
        #slices from the sheets
        surf = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
        surf.blit(self.sprite_sheet, (0, 0), rect)
        return pygame.transform.scale(surf, (64, 64))

    def load_animation_frames(self):
        #organizes the animation
        self.animations = {
            'idle_r': [], 'run_r': [], 'jump_r': [],
            'idle_l': [], 'run_l': [], 'jump_l': []
        }

        idle = self.slicer(player_idle_rect)
        run1 = self.slicer(player_walk1_rect)
        run2 = self.slicer(player_walk2_rect)
        jump = self.slicer(player_jump_rect)

        #right
        self.animations['idle_r'] = [idle]
        self.animations['run_r'] = [run1, run2]
        self.animations['jump_r'] = [jump]

        #left (flipped)
        self.animations['idle_l'] = [pygame.transform.flip(idle, True, False)]
        self.animations['run_l'] = [pygame.transform.flip(run1, True, False),
                                    pygame.transform.flip(run2, True, False)]
        self.animations['jump_l'] = [pygame.transform.flip(jump, True, False)]

    def animate(self):
        if self.speed.y != 0:
            self.state = 'jump'
        elif self.speed.x != 0:
            self.state = 'run'
        else:
            self.state = 'idle'

        suffix = '_r' if self.facing_right else '_l'
        key = self.state + suffix

        #loop through frames
        self.frame_index += anim_speed
        if self.frame_index >= len(self.animations[key]):
            self.frame_index = 0.0

        self.image = self.animations[key][int(self.frame_index)]

    def process_input(self):
        #keyboard controls
        keys = pygame.key.get_pressed()
        self.speed.x = 0

        if keys[pygame.K_LEFT]:
            self.speed.x = -player_move_speed
            self.facing_right = False
        if keys[pygame.K_RIGHT]:
            self.speed.x = player_move_speed
            self.facing_right = True
        
        if keys[pygame.K_SPACE] and self.on_ground:
            self.speed.y = jump_speed
            self.on_ground = False

    def update(self):
        if self.dead or self.won:
            return

        self.process_input()
        self.animate()

        #apply gravity
        self.speed.y += gravity

        #check horizontal collisions
        self.rect.x += self.speed.x
        collided = pygame.sprite.spritecollide(self, self.walls, False)
        for wall in collided:
            if self.speed.x > 0:
                self.rect.right = wall.rect.left
            elif self.speed.x < 0:
                self.rect.left = wall.rect.right

        #move y and check vertical collisions
        self.rect.y += self.speed.y
        self.on_ground = False
        collided = pygame.sprite.spritecollide(self, self.walls, False)
        for wall in collided:
            if self.speed.y > 0:
                self.rect.bottom = wall.rect.top
                self.speed.y = 0
                self.on_ground = True
            elif self.speed.y < 0:
                self.rect.top = wall.rect.bottom
                self.speed.y = 0

        #handle pickups
        pickups = pygame.sprite.spritecollide(self, self.items, False)
        for item in pickups:
            if item.type == 'gem':
                item.kill()
                self.gems_collected += 1
            elif item.type == 'key':
                item.kill()
                self.has_key = True
            elif item.type == 'door':
                if self.has_key:
                    self.won = True

        #check enemy hits
        if pygame.sprite.spritecollideany(self, self.enemies):
            self.dead = True

        #fell off the world
        if self.rect.y > screen_height + 100:
            self.dead = True


class WorldCamera:
    def __init__(self, world_w, world_h):
        self.camera = pygame.Rect(0, 0, world_w, world_h)
        self.world_w = world_w
        self.world_h = world_h
        self.x = float(self.camera.x)
        self.y = float(self.camera.y)
        self.lerp = 0.08  #smoothness

    def apply(self, sprite):
        #offsets a sprite based on camera position
        return sprite.rect.move(self.camera.topleft)

    def update(self, target_sprite):
        #calculate the camera position
        target_x = -target_sprite.rect.x + screen_width // 2
        target_y = -target_sprite.rect.y + screen_height // 2

        #stop camera at world ends
        max_x = -(self.world_w - screen_width)
        max_y = -(self.world_h - screen_height)

        target_x = min(0, max(max_x, target_x))
        target_y = min(0, max(max_y, target_y))

        #smooth movement
        self.x += (target_x - self.x) * self.lerp
        self.y += (target_y - self.y) * self.lerp

        self.camera.x = int(self.x)
        self.camera.y = int(self.y)


class PlatformerGame:
    #main game class handling the game
    def __init__(self):
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.mixer.init()
        pygame.init()

        self.screen = pygame.display.set_mode((screen_width, screen_height))
        pygame.display.set_caption("Jungle Escape")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 40, bold=True)
        self.title_font = pygame.font.SysFont("Arial", 60, bold=True)

        self.music_playing = False
        self.load_assets()
        self.generate_random_level()
        self.state = "PLAYING"

        self.screen_rect = pygame.Rect(0, 0, screen_width, screen_height)
        self.last_gem_count = -1
        self.gem_text_surface = None
        self._last_key_state = None
        self.key_text_surface = None

    def load_assets(self):
        #loading images and sounds from the assets folder
        base_dir = os.path.dirname(__file__)
        assets_dir = os.path.join(base_dir, 'assets')

        self.character_sheet = pygame.image.load(
            os.path.join(assets_dir, 'platformerPack_character.png')).convert_alpha()
        tilesheet = pygame.image.load(
            os.path.join(assets_dir, 'platformPack_tilesheet.png')).convert_alpha()
        
        self.background = None
        bg_path = os.path.join(assets_dir, 'background.jpg')
        
        #load background
        
        bg_image = pygame.image.load(bg_path).convert()
        self.background = pygame.transform.scale(bg_image, (screen_width, screen_height))
            
        #load music
        music_path = os.path.join(assets_dir, 'music.ogg')
        
        pygame.mixer.music.load(music_path)
        pygame.mixer.music.set_volume(0.5)
        pygame.mixer.music.play(-1)
        self.music_playing = True

        def cut(sheet, rect):
            #cuts a small sprite out of the big sheet
            surface = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
            surface.blit(sheet, (0, 0), rect)
            return surface

        self.tile_images = {
            'grass': cut(tilesheet, tile_grass_rect),
            'dirt':  cut(tilesheet, tile_dirt_rect),
            'gem':   cut(tilesheet, item_gem_rect),
            'key':   cut(tilesheet, item_key_rect),
            'door':  cut(tilesheet, tile_door_rect),
            'enemy': cut(tilesheet, enemy_rect),
        }

    def generate_random_level(self):
        #builds a new map layout using a grid system
        grid = [['.' for _ in range(level_columns)] for _ in range(level_rows)]
        platforms = []

        cursor_x, cursor_y = 0, level_rows - 4
        #start platform
        for x in range(6):
            grid[cursor_y][x] = 'X'
        grid[cursor_y - 1][1] = 'P' #player start
        cursor_x = 6

        #procedurally generate platforms
        while cursor_x < level_columns - 6:
            gap = random.randint(2, 4)
            length = random.randint(4, 9)
            dy = random.randint(-2, 2)
            new_y = max(4, min(level_rows - 3, cursor_y + dy))

            if cursor_x + gap + length >= level_columns:
                length = level_columns - (cursor_x + gap) - 1

            start_x = cursor_x + gap
            for i in range(length):
                grid[new_y][start_x + i] = 'X'
                #fill space below platform with dirt
                for d in range(new_y + 1, level_rows):
                    grid[d][start_x + i] = 'D'

            platforms.append({'x': start_x, 'y': new_y, 'len': length})
            cursor_x += gap + length
            cursor_y = new_y

        #place key and door
        if platforms:
            eligible_platforms = platforms[:-1] if len(platforms) >= 2 else platforms
            key_platform = random.choice(eligible_platforms)
            key_x = key_platform['x'] + random.randint(0, key_platform['len'] - 1)
            grid[key_platform['y'] - 1][key_x] = 'K'

            last_platform = platforms[-1]
            grid[last_platform['y'] - 1][last_platform['x'] + last_platform['len'] - 1] = 'L' #L for Lock/Door

            #place enemies
            enemy_spawned = False
            for p in platforms:
                if p == key_platform or p == last_platform:
                    continue

                #force at least one enemy
                if not enemy_spawned:
                    mid = p['x'] + p['len'] // 2
                    grid[p['y'] - 1][mid] = 'E'
                    enemy_spawned = True
                    continue
                
                #random chance for more enemies
                if p['len'] > 5 and random.random() < 0.4:
                    mid = p['x'] + p['len'] // 2
                    if grid[p['y'] - 1][mid] == '.':
                        grid[p['y'] - 1][mid] = 'E'

            #place gems
            gem_positions = []
            for p in platforms:
                x = p['x'] + random.randint(0, p['len'] - 1)
                y = p['y'] - 1
                if grid[y][x] == '.' and len(gem_positions) < 4:
                    grid[y][x] = 'C' #C for Collectible
                    gem_positions.append((x,y))

            #extra random gems
            for p in platforms:
                if random.random() < 0.3:
                    gx = p['x'] + random.randint(0, p['len'] - 1)
                    if grid[p['y'] - 1][gx] == '.':
                        grid[p['y'] - 1][gx] = 'C'

        self.level_grid = grid
        self._build_level_from_grid(grid)

    def _build_level_from_grid(self, grid):
        #takes the grid characters and turns them into actual game sprites
        self.all_sprites = pygame.sprite.Group()
        self.walls = pygame.sprite.Group()
        self.items = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()

        map_pixel_width = len(grid[0]) * tile_size
        map_pixel_height = len(grid) * tile_size
        self.camera = WorldCamera(map_pixel_width, map_pixel_height)

        for row_index, row in enumerate(grid):
            for col_index, char in enumerate(row):
                world_x = col_index * tile_size
                world_y = row_index * tile_size

                if char == 'P':
                    self.player = PlayerCharacter(world_x, world_y, self.character_sheet,
                                                  self.walls, self.items, self.enemies)
                    self.all_sprites.add(self.player)

                elif char == 'X':
                    block = WorldObject(world_x, world_y, self.tile_images['grass'], 'wall')
                    self.walls.add(block)
                    self.all_sprites.add(block)

                elif char == 'D':
                    dirt = WorldObject(world_x, world_y, self.tile_images['dirt'], 'wall')
                    self.walls.add(dirt)
                    self.all_sprites.add(dirt)

                elif char == 'C':
                    gem = WorldObject(world_x, world_y, self.tile_images['gem'], 'gem')
                    self.items.add(gem)
                    self.all_sprites.add(gem)

                elif char == 'K':
                    key = WorldObject(world_x, world_y, self.tile_images['key'], 'key')
                    self.items.add(key)
                    self.all_sprites.add(key)

                elif char == 'L':
                    #door is taller than other tiles, adjust y
                    door = WorldObject(world_x, world_y - tile_size, self.tile_images['door'], 'door')
                    self.items.add(door)
                    self.all_sprites.add(door)

                elif char == 'E':
                    enemy = PatrollingEnemy(world_x, world_y, self.tile_images['enemy'],pygame.Rect(world_x - 100, world_y, 200, 64))
                    enemy.min_x = world_x - 64
                    enemy.max_x = world_x + 128
                    self.enemies.add(enemy)
                    self.all_sprites.add(enemy)

    def _draw_pause_overlay(self, title_text, subtitle_text):
        #draws the "Game Over" or "Win" screen with a transparent background
        overlay = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        overlay.fill(ui_overlay_color)
        self.screen.blit(overlay, (0, 0))

        title_surf = self.title_font.render(title_text, True, text_color)
        subtitle_surf = self.font.render(subtitle_text, True, (200, 200, 200))
        options_surf = self.font.render("[R]etry  [N]ew Level  [Q]uit", True, (255, 255, 0))

        self.screen.blit(title_surf, title_surf.get_rect(center=(screen_width // 2, screen_height // 2 - 60)))
        self.screen.blit(subtitle_surf, subtitle_surf.get_rect(center=(screen_width // 2, screen_height // 2)))
        self.screen.blit(options_surf, options_surf.get_rect(center=(screen_width // 2, screen_height // 2 + 80)))



def main():

    game = PlatformerGame()

    while True:
        game.clock.tick(fps)

        #handle quitting or restarting
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if game.state != "PLAYING" and event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    pygame.quit()
                    sys.exit()
                elif event.key == pygame.K_r:
                    #reload current level
                    game._build_level_from_grid(game.level_grid)
                    game.state = "PLAYING"
                    if game.music_playing:
                        pygame.mixer.music.play(-1)
                elif event.key == pygame.K_n:
                    #make a new random level
                    game.generate_random_level()
                    game.state = "PLAYING"
                    if game.music_playing:
                        pygame.mixer.music.play(-1)

        #game logic updates
        if game.state == "PLAYING":
            game.player.update()
            game.enemies.update()
            game.camera.update(game.player)

            if game.player.dead:
                game.state = "GAMEOVER"
                if game.music_playing:
                    pygame.mixer.music.stop()
            elif game.player.won:
                game.state = "WIN"
                if game.music_playing:
                    pygame.mixer.music.stop()

        #draw everything
        if game.background:
            game.screen.blit(game.background, (0, 0))
        else:
            game.screen.fill(background_color)

        for sprite in game.all_sprites:
            screen_rect = game.camera.apply(sprite)
            #optimization
            if game.screen_rect.colliderect(screen_rect):
                game.screen.blit(sprite.image, screen_rect)

        #gem count
        if game.player.gems_collected != game.last_gem_count:
            game.gem_text_surface = game.font.render(f"Gems: {game.player.gems_collected}", True, text_color)
            game.last_gem_count = game.player.gems_collected
        if game.gem_text_surface:
            game.screen.blit(game.gem_text_surface, (20, 20))

        #key icon/text
        if game.player.has_key != game._last_key_state:
            key_color = (255, 255, 0) if game.player.has_key else (150, 150, 150)
            game.key_text_surface = game.font.render("KEY", True, key_color)
            game._last_key_state = game.player.has_key
        if game.key_text_surface:
            game.screen.blit(game.key_text_surface, (20, 70))

        #end game screens
        if game.state in ("GAMEOVER", "WIN"):
            title = "YOU DIED" if game.state == "GAMEOVER" else "VICTORY!"
            subtitle = "Try Again?" if game.state == "GAMEOVER" else f"Gems: {game.player.gems_collected}"
            game._draw_pause_overlay(title, subtitle)

        pygame.display.flip()


if __name__ == "__main__":
    main()