#low-level
import sys
import math
import os
import time
import random
#mid-level
import hashlib
import asyncio
import json
from glob import glob
#3rd-party
import websockets
from pypresence import AioClient, Client, InvalidPipe
import pygame
from pygame.locals import *
#me
from lenums import *

pygame.init()

#globals
SIZE = WIDTH, HEIGHT = 960, 720
HALFSIZE = HALFWIDTH, HALFHEIGHT = WIDTH // 2, HEIGHT // 2
BOUNDS = BW, BH = HALFWIDTH * 3, HALFHEIGHT * 3
PLAYER = PW, PH = 16, 16
SPEED = 2
SENSE = 0.3
FPS = 200

pressed = {}

keys = {
    K_UP: Button.UP,
    K_w: Button.UP,
    K_DOWN: Button.DOWN,
    K_s: Button.DOWN,
    K_LEFT: Button.LEFT,
    K_a: Button.LEFT,
    K_RIGHT: Button.RIGHT,
    K_d: Button.RIGHT,
    K_RETURN: Button.START,
    K_SPACE: Button.FIRE,
    K_LSHIFT: Button.SHIELD,
    K_e: Button.PICKUP
}

pygame.event.set_blocked((ACTIVEEVENT, VIDEORESIZE, VIDEOEXPOSE, USEREVENT))

myfont = pygame.font.SysFont('Courier New', 18)
texts = {
    'choose-map': 'Choose a map. Press start to select.',
    'waiting-for-server': 'Waiting for server...',
    'waiting-for-bg': 'Waiting for server owner to choose arena...',
    'intro': 'Welcome to Unplanned!',
    'controls-1': 'Controls: WASD or left joystick to move;',
    'controls-2': 'player aims towards mouse or in right joystick direction.',
    'controls-3': 'Click or right button to shoot; right click or left button to aim.',
    'controls-4': 'Escape or select to quit. C or (B) while playing to copy game ID.',
    'start-1': 'Press 1 or (A) to start your own server,',
    'start-2': 'or 2 or (B) to join the server whose ID is in your clipboard,',
    'start-3': 'or 3 or (X) to join someone else\'s server through Discord.'
}
texts = {i: myfont.render(j, True, (255, 255, 255)) for i, j in texts.items()}

def text(t, pos, y=None):
    SCREEN.blit(texts.get(t, t), pos if y is None else (pos, y))

if sys.platform.startswith('win32'):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
LOOP = asyncio.get_event_loop()

#duck-type-fix the register_event function
async def register_event(self, event: str, func: callable, args: dict = {}):
    if not callable(func):
        raise TypeError
    await self.subscribe(event, args)
    self._events[event.lower()] = func

AioClient.on_event = Client.on_event
AioClient.register_event = register_event
RPC = AioClient('584670770807046144', loop=LOOP,
                pipe=sys.argv[1] if len(sys.argv) > 1 else 0)
status = {
    'pid': os.getpid(),
    'large_image': 'black_hole'
}

SCREEN = pygame.display.set_mode(SIZE)
if pygame.joystick.get_count():
    joy = pygame.joystick.Joystick(0)
    joy.init()
else:
    joy = None
pygame.scrap.init()

inputmode = InputMode.KEYANDMOUSE

class Player(pygame.sprite.Sprite):
    health = 200
    xv = 0
    yv = 0
    direction = 0
    mdir = 0 #only for use by controller
    ammo = [
        300, #light
        100, #shell
        200, #medium
        50, #heavy
        20, #explosive
    ]
    weapon = None
    inventory = [None, None, None, None, None] # 5 slots
    _weaponidx = 0

    @property
    def weaponidx(self):
        return self._weaponidx
    @weaponidx.setter
    def weaponidx(self, value):
        value = value % 5
        self._weaponidx = value
        if self.weapon is not None:
            self.weapon.kill()
        self.weapon = self.inventory[value]
        weapons.add(self.weapon)

    def __init__(self, pid):
        super().__init__()
        if pid is None:
            self.id = id(self)
        else:
            self.id = pid
        pressed[self.id] = set()
        self.image = pygame.Surface(PLAYER)
        self.rect = self.image.get_rect()
        self.rect.center = (HALFWIDTH, HALFHEIGHT)
        self.sx, self.sy = self.rect.center#0, 0
        self.weapon = None
        #self.color = (
        #    random.randint(128, 255),
        #    random.randint(128, 255),
        #    random.randint(128, 255)
        #)
        self.color = (0xff, 0x6a, 0)
        self.image.fill(self.color)
        #temp
        self.inventory = [
            WEAPONS['AssaultRifle'](self),
            WEAPONS['Shotgun'](self),
            WEAPONS['Minigun'](self),
            WEAPONS['Sniper'](self),
            WEAPONS['RocketLauncher'](self)
        ]
        self.weaponidx = 0

    @property
    def rectpos(self):
        return self.rect.center

    @property
    def spos(self):
        return (self.sx, self.sy)

    def collided(self, xory):
        r = self.rect.copy()
        r.center = (self.sx, self.sy)
        if xory == 'x' and self.xv == 0 or xory == 'y' and self.yv == 0:
            return
        if xory == 'x':
            direction = abs(self.xv) // self.xv
            if abs(self.sx - HALFWIDTH) > BW:
                self.sx = direction * BW + HALFWIDTH
        else:
            direction = abs(self.yv) // self.yv
            if abs(self.sy - HALFHEIGHT) > BH:
                self.sy = direction * BH + HALFHEIGHT
        for o in obstacles:
            if (
                r.x < o.x + o.w and r.y < o.y + o.h
                and r.x + r.w > o.x and r.y + r.h > o.y
            ):
                if xory == 'x':
                    self.sx -= direction * min(
                        abs(o.x - r.x - r.w),
                        abs(r.x - o.x - o.w)
                    )
                else:
                    self.sy -= direction * min(
                        abs(o.y - r.y - r.h),
                        abs(r.y - o.y - o.h)
                    )
                break

    def update(self):
        ## movement and collision
        if self.xv != 0:
            self.xv *= 0.75
            if self.xv < 0.01:
                self.xv = 0
        if self.yv != 0:
            self.yv *= 0.75
            if self.yv < 0.01:
                self.yv = 0
        if Button.FORTH in pressed[self.id]:
            self.xv = SPEED * math.cos(self.mdir)
            self.yv = SPEED * math.sin(self.mdir)
        else:
            if Button.UP in pressed[self.id]:
                self.yv = -SPEED
            if Button.DOWN in pressed[self.id]:
                self.yv = SPEED
            if Button.LEFT in pressed[self.id]:
                self.xv = -SPEED
            if Button.RIGHT in pressed[self.id]:
                self.xv = SPEED
        if Button.SHIELD in pressed[self.id]:
            self.xv /= 2
            self.yv /= 2
        self.xv = math.ceil(self.xv * 1000) / 1000
        self.yv = math.ceil(self.yv * 1000) / 1000
        self.sx += self.xv
        self.collided('x')
        self.sy += self.yv
        self.collided('y')
        self.sx = round(self.sx, 3)
        self.sy = round(self.sy, 3)
        if self.id == player.sprite.id:
            if abs(self.sx - HALFWIDTH) > WIDTH:
                self.rect.centerx = (
                    self.sx
                    - abs(self.sx)
                    // self.sx
                    * WIDTH
                )
            elif self.rect.centerx != HALFWIDTH:
                self.rect.centerx = HALFWIDTH
            if abs(self.sy - HALFHEIGHT) > HEIGHT:
                self.rect.centery = (
                    self.sy
                    - abs(self.sy)
                    // self.sy
                    * HEIGHT
                )
            elif self.rect.centery != HALFHEIGHT:
                self.rect.centery = HALFHEIGHT
        else:
            self.rect.centerx = (
                player.sprite.rect.centerx
                + self.sx
                - player.sprite.sx
            )
            self.rect.centery = (
                player.sprite.rect.centery
                + self.sy
                - player.sprite.sy
            )
        self.rect.centerx = round(self.rect.centerx)
        self.rect.centery = round(self.rect.centery)
        self.image.fill(self.color)
        pygame.draw.line(
            self.image,
            tuple(255 - i for i in self.color),
            (PW // 2, PH // 2),
            (
                PW // 2 + PW * math.cos(self.direction),
                PH // 2 + PW * math.sin(self.direction)
            )
        )

    def __repr__(self):
        return '<(pid: {})>'.format(self.id)

def convert_pos(self):
    self.rect.centerx = HALFWIDTH + (
        self.sx - abs(player.sprite.sx)
        // player.sprite.sx * WIDTH - HALFWIDTH
        if abs(player.sprite.sx - HALFWIDTH) > WIDTH
        else self.sx - player.sprite.sx
    )
    self.rect.centery = HALFHEIGHT + (
        self.sy - abs(player.sprite.sy)
        // player.sprite.sy * HEIGHT - HALFHEIGHT
        if abs(player.sprite.sy - HALFHEIGHT) > HEIGHT
        else self.sy - player.sprite.sy
    )

class Bullet(pygame.sprite.Sprite):
    damage = None
    speed = None
    size = None
    inaccuracy = 0

    @property
    def area(self):
        return self.weight == BulletType.EXPLOSIVE

    def __init__(self, myplayer, direction=None):
        super().__init__()
        self.image = pygame.Surface((self.size, self.size))
        self.image.fill((255, 255, 255))
        self.rect = self.image.get_rect()
        self.player = myplayer
        self.sx, self.sy = self.player.spos
        self.direction = direction or self.player.direction

    def update(self):
        if self.rect.width != self.size and not self.areaframes > 0:
            self.kill()
            return
        if self.rect.width != self.size:
            self.areaframes -= 1
            convert_pos(self)
            return
        for i in range(self.speed):
            self.sx += math.cos(self.direction)
            self.sy += math.sin(self.direction)
            convert_pos(self)
            r = pygame.Rect(0, 0, self.size, self.size)
            r.center = (self.sx, self.sy)
            if (
                r.collidelist(obstacles) != -1
                or abs(self.sx - HALFWIDTH) > BW
                or abs(self.sy - HALFHEIGHT) > BH
            ):
                if self.area:
                    self.explode()
                    return
                else:
                    self.kill()
                    return
            coll = pygame.sprite.spritecollideany(self, players)
            if coll and coll != self.player:
                if self.area:
                    self.explode()
                    return
                elif hasattr(self, 'spread'):
                    coll.health -= self.damage // self.amount
                    self.kill()
                    return
                else:
                    coll.health -= self.damage
                    self.kill()
                    return

    def explode(self):
        self.image = pygame.Surface((PW * 4, PH * 4))
        self.image.fill((255, 255, 255))
        rect = self.image.get_rect()
        rect.center = self.rect.center
        self.rect = rect
        self.areaframes = 10
        for i in pygame.sprite.spritecollide(self, players, False):
            i.health -= self.damage

def looking_at_pos(rect, pos, direction):
    if 0 < direction < math.pi / 2 \
       or math.pi < direction < math.pi * 3 / 2:
        #get slope of bounding lines between top right and bottom left
        left = ((rect.y - pos[1])               # +--X
                / (rect.x + rect.w - pos[0]))   # +--+
        right = ((rect.y + rect.h - pos[1]) # +--+
                 / (rect.x - pos[0]))       # X--+
    elif math.pi / 2 < direction < math.pi \
         or math.pi * 3 / 2 < direction < math.pi * 2:
        #get slope of bounding lines between top left and bottom right
        left = ((rect.y - pos[1])   # X--+
                / (rect.x - pos[0]))# +--+
        right = ((rect.y + rect.h - pos[1])     # +--+
                 / (rect.x + rect.w - pos[0]))  # +--X
    #get bounding directions from slopes
    left = math.atan(left)
    right = math.atan(right)
    #if the direction is in bounds, it's looking.
    return left <= spr.direction <= right \
           or right <= spr.direction <= left

class Weapon(pygame.sprite.Sprite):
    bullet = Bullet
    lastfire = 0
    delay = 0
    ammo = 0
    reload = 0
    reloading = 0
    original = None
    pivot = (0, 0)
    name = None

    @staticmethod
    def img(name):
        return pygame.image.load(os.path.join(
            os.path.dirname(__file__), 'weapons', name
        ))

    def __init__(self, myplayer):
        super().__init__()
        if not isinstance(myplayer, Player):
            self.sx, self.sy = myplayer
            convert_pos(self)
        else:
            self.player = myplayer
            if getattr(self.player, 'weapon', None) is not None:
                self.player.weapon.kill()
            self.player.weapon = self

    def update(self):
        as_weapon = hasattr(self, 'player')
        if as_weapon:
            direc = -math.degrees(self.player.direction)
        else:
            direc = 0
        self.image = pygame.transform.rotate(self.original, direc)
        self.rect = self.image.get_rect()
        if as_weapon:
            self.update_as_weapon(direc)
        else:
            self.update_as_item()

    def update_as_item(self):
        convert_pos(self)
        for spr in pygame.sprite.spritecollide(self, players, False):
            try:
                idx = spr.weapons.index(None)
            except ValueError:
                if Button.PICKUP in pressed[spr.id] \
                   and looking_at_pos(self.rect, spr.spos, spr.direction):
                    #do the pickup!
                    spr.weapons[spr.weaponidx] = self #set the slot
                    spr.weaponidx = spr.weaponidx #call the setter
                    break
            else:
                spr.weapons[idx] = self
                break

    def update_as_weapon(self, direc):
        self.rect.center = self.player.rectpos \
                           + self.pivot.rotate(-direc)
        if not self.ammo > 0 and time.time() - self.reloading > self.reload:
            self.ammo = type(self).ammo
        if (
            Button.FIRE in pressed[player.sprite.id]
            and self.player.id == player.sprite.id
        ):
            newfire = time.time()
            if (
                newfire - self.lastfire >= self.delay
                and (self.ammo > 0 or type(self).ammo <= 0)
                and player.sprite.ammo[self.bullet.weight] > 0
            ):
                self.lastfire = newfire
                direction = self.player.direction
                if Button.SHIELD in pressed[self.player.id]:
                    direction += random.uniform(
                        -self.bullet.inaccuracy,
                        self.bullet.inaccuracy
                    ) / 2
                else:
                    direction += random.uniform(
                        -self.bullet.inaccuracy,
                        self.bullet.inaccuracy
                    )
                if hasattr(self.bullet, 'spread'):
                    for i in range(
                        self.bullet.amount // -2,
                        self.bullet.amount // 2 + 1
                    ):
                        if Button.SHIELD in pressed[self.player.id]:
                            tdirection = direction + self.bullet.spread * i / 2
                        else:
                            tdirection = direction + self.bullet.spread * i
                        sockmsgs.put_nowait({
                            'op': MiscOpcode.BULLET_ADD,
                            'data': tdirection
                        })
                else:
                    sockmsgs.put_nowait({
                        'op': MiscOpcode.BULLET_ADD,
                        'data': direction
                    })
                if type(self).ammo > 0:
                    self.ammo -= 1
                    if not self.ammo > 0:
                        self.reloading = time.time()
                player.sprite.ammo[self.bullet.weight] -= 1
        if (
            Button.SHIELD in pressed[self.player.id]
            and player.sprite.id == self.player.id
        ):
            #if isinstance(self, Sniper):
            totheright = totheleft = self.player.direction
            if hasattr(self.bullet, 'spread'):
                totheright += self.bullet.spread * self.bullet.amount / 4
                totheleft -= self.bullet.spread * self.bullet.amount / 4
            totheright += self.bullet.inaccuracy / 2
            totheleft -= self.bullet.inaccuracy / 2
            pygame.draw.line(
                SCREEN, (255, 255, 255),
                self.rect.center,
                (
                    self.rect.centerx
                    + WIDTH * math.cos(totheright),
                    self.rect.centery
                    + WIDTH * math.sin(totheright)
                )
            )
            pygame.draw.line(
                SCREEN, (255, 255, 255),
                self.rect.center,
                (
                    self.rect.centerx
                    + WIDTH * math.cos(totheleft),
                    self.rect.centery
                    + WIDTH * math.sin(totheleft)
                )
            )

### BULLETS ###
with open('bullets.json') as f:
    BULLETS = json.load(f)
for i, j in BULLETS.items():
    j['inaccuracy'] = math.radians(j['inaccuracy'])
    if 'spread' in j:
        j['spread'] = math.radians(j['spread'])
    BULLETS[i] = type(i, (Bullet,), j)

### WEAPONS ###
with open('weapons.json') as f:
    WEAPONS = json.load(f)
for i, j in WEAPONS.items():
    cls = j.pop('class', None)
    j['name'] = i
    j['original'] = Weapon.img(j['original'])
    if isinstance(j['delay'], str):
        j['delay'] = eval(j['delay'], {}, {})
    j['pivot'] = pygame.math.Vector2(j['pivot'])
    j['bullet'] = BULLETS[j['bullet']]
    WEAPONS[i] = type(i, (WEAPONS.get(cls, Weapon),), j)

player = pygame.sprite.GroupSingle()
players = pygame.sprite.Group()
weapons = pygame.sprite.Group()
bullets = pygame.sprite.Group()

sockmsgs = asyncio.Queue()

def getpbyid(pid):
    for p in players.sprites():
        if p.id == pid:
            return p
    return None

async def rpc():
    if RPC is not None:
        await RPC.set_activity(**status)

obstacles = None

async def sockrecv(ws):
    global obstacles
    try:
        deeta = await ws.recv()
        deeta = json.loads(deeta)
        assert deeta['op'] == SockMsg.YOU
        player.sprite = Player(deeta['pid'])
        players.add(player.sprite)
        async for msg in ws:
            deeta = json.loads(msg)
            if deeta['op'] == SockMsg.BYE:
                raise SystemExit
            if deeta['op'] == SockMsg.ADD:
                print(msg)
                if deeta['pid'] != player.sprite.id:
                    players.add(Player(deeta['pid']))
                    pressed[deeta['pid']] = set()
                status['party_size'] = [len(players), len(players) + 1]
                continue
            if deeta['op'] == SockMsg.BAC:
                with open(deeta['data']) as f:
                    raw = json.load(f)
                obstacles = []
                for dx, dy in {
                    (0, 0), #center center
                    (WIDTH, 0), #right center
                    (-WIDTH, 0), #left center
                    (0, HEIGHT), #top center
                    (0, -HEIGHT), #bottom center
                    (WIDTH, HEIGHT), #top right
                    (WIDTH, -HEIGHT), #bottom right
                    (-WIDTH, HEIGHT), #top left
                    (-WIDTH, -HEIGHT), #bottom left
                }:
                    obstacles.extend(
                        pygame.Rect(
                            WIDTH // 480 * i[0] + HALFWIDTH + dx,
                            HALFHEIGHT - HEIGHT // 360 * i[1] + dy,
                            WIDTH // 480 * i[2], HEIGHT // 360 * i[3]
                        )
                        for i in raw
                        if not isinstance(i, str)
                    )
                continue
            p = getpbyid(deeta['pid'])
            if 'pos' in deeta and deeta['pid'] != player.sprite.id:
                p.sx, p.sy = deeta['pos']
            if deeta['op'] == SockMsg.DEL:
                if p:
                    p.kill()
                    p.weapon.kill()
                    del pressed[deeta['pid']]
                    if deeta['pid'] == player.sprite.id:
                        raise SystemExit
                status['party_size'] = [len(players), len(players) + 1]
                continue
            if deeta['op'] == Button.ROT:
                if p:
                    p.direction = deeta['data']
                continue
            if deeta['op'] == Button.FORTH:
                if p:
                    if deeta['data'] is not None:
                        pressed[deeta['pid']].add(Button.FORTH)
                        p.mdir = deeta['data']
                    else:
                        pressed[deeta['pid']].discard(Button.FORTH)
                continue
            if deeta['op'] == MiscOpcode.BULLET_ADD:
                if p:
                    bullets.add(p.weapon.bullet(p, deeta['data']))
                continue
            if deeta['op'] == MiscOpcode.WEAPON_SET:
                if p:
                    p.weaponidx = deeta['data']
                continue
            # assume button press
            button = Button(deeta['op'])
            if deeta['data']:
                pressed.get(deeta['pid'], set()).discard(button)
            else:
                pressed.get(deeta['pid'], set()).add(button)
    except asyncio.CancelledError:
        return
    except Exception:
        import traceback
        traceback.print_exc()
        return

async def heartbeat(ws):
    try:
        while 1:
            sockmsgs.put_nowait({
                'op': MiscOpcode.WEAPON_SET,
                'pos': player.sprite.spos,
                'data': player.sprite.weaponidx
            })
            await asyncio.sleep(1/FPS)
    except asyncio.CancelledError:
        return

async def socksend(ws):
    try:
        while 1:
            await ws.send(json.dumps(await sockmsgs.get(),
                                     separators=(',', ':')))
    except asyncio.CancelledError:
        return

async def rpcupdater():
    try:
        while 1:
            await rpc()
            await asyncio.sleep(2)
    except asyncio.CancelledError:
        return

def setdir(x, y, look=True):
    if not (x or y):
        return
    try:
        direction = math.atan(abs(y) / abs(x))
    except ZeroDivisionError:
        direction = 0
    if x > 0:
        if y < 0: #Q4
            direction = 2*math.pi - direction
    elif x < 0:
        if y > 0: #Q2
            direction = math.pi - direction
        elif y < 0: #Q3
            direction = math.pi + direction
        else: #straight left
            direction = math.pi
    else:
        if y > 0: #straight up
            direction = math.pi / 2
        elif y < 0: #straight down
            direction = math.pi * 3 / 2
    direction = round(direction, 3)
    if look:
        player.sprite.direction = direction
    sockmsgs.put_nowait({
        'op': Button.ROT if look else Button.FORTH,
        'data': direction,
        'pos': player.sprite.spos
    })

def newwep():
    sockmsgs.put_nowait({
        'op': MiscOpcode.WEAPON_SET,
        'data': random.choice(tuple(WEAPONS.keys())),
        'pos': player.sprite.spos
    })

async def main():
    global inputmode, SENSE, obstacles, RPC
    try:
        await RPC.start()
    except (AttributeError, InvalidPipe) as exc:
        RPC = None
        print(type(exc).__name__, exc, sep=': ')
    try:
        status['state'] = 'In Intro'
        await rpc()
        SCREEN.fill((0, 0, 0))
        text('intro', 5, 5)
        text('controls-1', 5, texts['intro'].get_height() * 1 + 5)
        text('controls-2', 5, texts['intro'].get_height() * 2 + 5)
        text('controls-3', 5, texts['intro'].get_height() * 3 + 5)
        text('controls-4', 5, texts['intro'].get_height() * 4 + 5)
        text('start-1', 5, texts['intro'].get_height() * 5 + 5)
        text('start-2', 5, texts['intro'].get_height() * 6 + 5)
        if RPC is not None:
            text('start-3', 5, texts['intro'].get_height() * 7 + 5)
        pygame.event.set_allowed((QUIT, KEYDOWN, JOYBUTTONDOWN))
        pygame.scrap.init()
        pygame.display.flip()
        server = None
        while server is None:
            for event in pygame.event.get():
                if event.type == QUIT:
                    raise SystemExit
                if event.type == KEYDOWN:
                    if event.key == K_1:
                        server = ''
                    if event.key == K_2:
                        server = (pygame.scrap.get(SCRAP_TEXT) or b'')\
                                 .decode().strip('\0').strip()
                        if not server:
                            server = None
                    if event.key == K_3 and RPC is not None:
                        server = ...
                if event.type == JOYBUTTONDOWN:
                    if event.button == 0: #A
                        server = ''
                    if event.button == 1: #B
                        server = (pygame.scrap.get(SCRAP_TEXT) or b'')\
                                 .decode().strip('\0').strip()
                        if not server:
                            server = None
                    if event.button == 2 and RPC is not None: #X
                        server = ...
            await asyncio.sleep(1/FPS)
        SCREEN.fill((0, 0, 0))
        text(
            'waiting-for-server',
            HALFWIDTH - texts['waiting-for-server'].get_width() // 2,
            HALFHEIGHT - texts['waiting-for-server'].get_height() // 2
        )
        pygame.display.flip()
        if server is ...:
            # Discord
            status['state'] = 'Looking for Game'
            await rpc()
            fut = LOOP.create_future()
            def handler(secret):
                fut.set_result(secret['secret'])
            await RPC.register_event('ACTIVITY_JOIN', handler)
            async def waiting():
                try:
                    pygame.event.set_allowed(QUIT)
                    while 1:
                        for event in pygame.event.get(QUIT):
                            raise SystemExit
                        await asyncio.sleep(0.5)
                except asyncio.CancelledError:
                    return
            task = LOOP.create_task(waiting())
            server = await fut
            task.cancel()
        elif not server:
            async with websockets.connect('ws://localhost:61273') as ws:
                server = await ws.recv()
        async with websockets.connect('ws://localhost:61273/' + server) as ws:
            recv = LOOP.create_task(sockrecv(ws))
            send = LOOP.create_task(socksend(ws))
            rpcu = LOOP.create_task(rpcupdater())
            status['party_id'] = hashlib.sha256(server.encode()).hexdigest()
            pygame.event.set_allowed(QUIT)
            while not player.sprite:
                for event in pygame.event.get(QUIT):
                    raise SystemExit
                await asyncio.sleep(0.5)
            if player.sprite.id == 0:
                status['state'] = 'Choosing Arena'
                status['party_size'] = [1, 2]
                status['join'] = server
                pygame.event.set_allowed((
                    QUIT, KEYDOWN, JOYHATMOTION, JOYBUTTONDOWN
                ))
                backdrops = [
                    os.path.join(os.path.dirname(__file__), 'backdrops', i)
                    for i in os.listdir(os.path.join(
                        os.path.dirname(__file__), 'backdrops'
                    ))
                ]
                backdrop = None
                idx = 0
                SCREEN.fill((0, 0, 0))
                with open(backdrops[idx]) as f:
                    obstacles = [pygame.Rect(
                        WIDTH // 480 * i[0] + HALFWIDTH,
                        HALFHEIGHT - HEIGHT // 360 * i[1],
                        WIDTH // 480 * i[2], HEIGHT // 360 * i[3]
                    ) for i in json.load(f) if not isinstance(i, str)]
                for o in obstacles:
                    pygame.draw.rect(SCREEN, (255, 255, 255), o)
                text('choose-map', 5, 5)
                pygame.display.flip()
                flipped = False
                while backdrop is None:
                    direction = 0
                    for event in pygame.event.get():
                        if event.type == QUIT:
                            pygame.quit()
                            raise SystemExit
                        if event.type == KEYDOWN:
                            button = keys.get(event.key, None)
                            if button is None:
                                continue
                            if button == Button.RIGHT:
                                direction = 1
                            if button == Button.LEFT:
                                direction = -1
                            if button == Button.START:
                                backdrop = backdrops[idx]
                        if event.type in {JOYHATMOTION, JOYBUTTONDOWN}:
                            if event.type == JOYHATMOTION:
                                direction = event.value[0]
                            if event.type == JOYBUTTONDOWN:
                                if event.button == 5:
                                    direction = 1
                                if event.button == 4:
                                    direction = -1
                                if event.button == 7:
                                    backdrop = backdrops[idx]
                    if not direction and joy:
                        direction = (
                            round(joy.get_axis(0))
                            or round(joy.get_axis(2))
                            or round(joy.get_axis(4))
                        )
                    if direction and flipped:
                        direction = 0
                    elif flipped:
                        flipped = False
                    elif direction and not flipped:
                        flipped = True
                    idx += direction
                    idx %= len(backdrops)
                    if direction:
                        SCREEN.fill((0, 0, 0))
                        with open(backdrops[idx]) as f:
                            obstacles = [pygame.Rect(
                                WIDTH // 480 * i[0] + HALFWIDTH,
                                HALFHEIGHT - HEIGHT // 360 * i[1],
                                WIDTH // 480 * i[2], HEIGHT // 360 * i[3]
                            ) for i in json.load(f) if not isinstance(i, str)]
                        for o in obstacles:
                            pygame.draw.rect(SCREEN, (255, 255, 255), o)
                        text('choose-map', 5, 5)
                        pygame.display.flip()
                    await asyncio.sleep(1/FPS)
                sockmsgs.put_nowait({
                    'op': SockMsg.BAC,
                    'data': backdrop
                })
            else:
                status['state'] = 'Waiting for Arena'
                SCREEN.fill((0, 0, 0))
                text(
                    'waiting-for-bg',
                    HALFWIDTH - texts['waiting-for-bg'].get_width() // 2,
                    HALFHEIGHT - texts['waiting-for-bg'].get_height() // 2
                )
                pygame.event.set_allowed(QUIT)
                pygame.display.flip()
                while obstacles is None:
                    for event in pygame.event.get(QUIT):
                        raise SystemExit
                    await asyncio.sleep(0.5)
            status['state'] = 'Playing'
            status['start'] = round(time.time())
            ppress = pressed[player.sprite.id]
            pygame.event.set_allowed((
                JOYAXISMOTION, JOYBUTTONDOWN, JOYBUTTONUP, JOYHATMOTION,
                KEYDOWN, KEYUP, MOUSEBUTTONDOWN, MOUSEBUTTONUP, MOUSEMOTION,
                QUIT
            ))
            while 1:
                for event in pygame.event.get():
                    if event.type == QUIT:
                        raise SystemExit
                    if event.type in {JOYAXISMOTION, JOYBUTTONDOWN,
                                      JOYHATMOTION, JOYBUTTONUP}:
                        inputmode = InputMode.CONTROLLER
                    if event.type in {KEYDOWN, KEYUP, MOUSEBUTTONDOWN,
                                      MOUSEBUTTONUP, MOUSEMOTION}:
                        inputmode = InputMode.KEYANDMOUSE
                    if inputmode == InputMode.KEYANDMOUSE:
                        if event.type == KEYDOWN:
                            if event.key == K_ESCAPE:
                                raise SystemExit
                            if event.key == K_TAB:
                                newwep()
                                continue
                            if event.key == K_c:
                                pygame.scrap.put(SCRAP_TEXT, server.encode())
                            try:
                                ppress.add(keys[event.key])
                                sockmsgs.put_nowait({
                                    'op': keys[event.key], 'data': False,
                                    'pos': player.sprite.spos
                                })
                            except KeyError: #ironic
                                pass
                        if event.type == KEYUP:
                            try:
                                ppress.discard(keys[event.key])
                                sockmsgs.put_nowait({
                                    'op': keys[event.key], 'data': True,
                                    'pos': player.sprite.spos
                                })
                            except KeyError:
                                pass
                        if event.type == MOUSEBUTTONDOWN:
                            if event.button == 1:
                                sockmsgs.put_nowait({
                                    'op': Button.FIRE, 'data': False,
                                    'pos': player.sprite.spos
                                })
                            if event.button == 3:
                                sockmsgs.put_nowait({
                                    'op': Button.SHIELD, 'data': False,
                                    'pos': player.sprite.spos
                                })
                            if event.button == 4: #scroll up
                                sockmsgs.put_nowait({
                                    'op': MiscOpcode.WEAPON_SET,
                                    'pos': player.sprite.spos,
                                    'data': player.sprite.weaponidx - 1
                                })
                            if event.button == 5: #scroll down
                                sockmsgs.put_nowait({
                                    'op': MiscOpcode.WEAPON_SET,
                                    'pos': player.sprite.spos,
                                    'data': player.sprite.weaponidx + 1
                                })
                        if event.type == MOUSEBUTTONUP:
                            if event.button == 1:
                                sockmsgs.put_nowait({
                                    'op': Button.FIRE, 'data': True,
                                    'pos': player.sprite.spos
                                })
                            if event.button == 3:
                                sockmsgs.put_nowait({
                                    'op': Button.SHIELD, 'data': True,
                                    'pos': player.sprite.spos
                                })
                        if event.type == MOUSEMOTION:
                            x, y = event.pos
                            x -= player.sprite.rect.centerx
                            y -= player.sprite.rect.centery
                            setdir(x, y)
                    if inputmode == InputMode.CONTROLLER:
                        if event.type == JOYAXISMOTION:
                            if event.axis == 0: #left joystick horizontal
                                if math.hypot(event.value,
                                              joy.get_axis(1)) > SENSE:
                                    setdir(event.value, joy.get_axis(1), False)
                                elif Button.FORTH in ppress:
                                    sockmsgs.put_nowait({
                                        'op': Button.FORTH,
                                        'data': None,
                                        'pos': player.sprite.spos
                                    })
                            elif event.axis == 1: #left joystick vertical
                                if math.hypot(joy.get_axis(0),
                                              event.value) > SENSE:
                                    setdir(joy.get_axis(0), event.value, False)
                                elif Button.FORTH in ppress:
                                    sockmsgs.put_nowait({
                                        'op': Button.FORTH,
                                        'data': None,
                                        'pos': player.sprite.spos
                                    })
                            elif event.axis == 2: #trigger axis
                                if round(event.value) < 0: #right trigger
                                    SENSE = 0.5
                                elif round(event.value) > 0: #left trigger
                                    SENSE = 0.1
                                else:
                                    SENSE = 0.3
                            elif event.axis == 3: #right joystick vertical
                                x, y = joy.get_axis(4), event.value
                                if math.hypot(x, y) < SENSE:
                                    x, y = 0, 0
                                setdir(x, y)
                            elif event.axis == 4: #right joystick horizontal
                                x, y = event.value, joy.get_axis(3)
                                if math.hypot(x, y) < SENSE:
                                    x, y = 0, 0
                                setdir(x, y)
                        if event.type == JOYBUTTONDOWN:
                            if event.button == 6: #select
                                raise SystemExit
                            if event.button == 1: #B
                                pygame.scrap.put(SCRAP_TEXT, server.encode())
                            if event.button == 3: #Y
                                newwep()
                            if event.button == 4: #left bumper
                                if Button.SHIELD not in ppress:
                                    sockmsgs.put_nowait({
                                        'op': Button.SHIELD, 'data': False,
                                        'pos': player.sprite.spos
                                    })
                            if event.button == 5: #right bumper
                                if Button.FIRE not in ppress:
                                    sockmsgs.put_nowait({
                                        'op': Button.FIRE, 'data': False,
                                        'pos': player.sprite.spos
                                    })
                        if event.type == JOYBUTTONUP:
                            if event.button == 4: #left bumper
                                if Button.SHIELD in ppress:
                                    sockmsgs.put_nowait({
                                        'op': Button.SHIELD, 'data': True,
                                        'pos': player.sprite.spos
                                    })
                            if event.button == 5: #right bumper
                                if Button.FIRE in ppress:
                                    sockmsgs.put_nowait({
                                        'op': Button.FIRE, 'data': True,
                                        'pos': player.sprite.spos
                                    })
                        if event.type == JOYHATMOTION:
                            if event.hat == 0: #should be the only hat
                                sockmsgs.put_nowait({
                                    'op': MiscOpcode.WEAPON_SET,
                                    'pos': player.sprite.spos,
                                    'data': player.sprite.weaponidx
                                            + event.value[0]
                                })
                SCREEN.fill((0, 0, 0))
                players.update()
                weapons.update()
                bullets.update()
                for i in obstacles:
                    pygame.draw.rect(
                        SCREEN, (255, 255, 255),
                        (
                            i[0] + HALFWIDTH - (
                                player.sprite.sx
                                if abs(player.sprite.sx - HALFWIDTH) <= WIDTH
                                else BW
                            ),
                            i[1] + HALFHEIGHT - (
                                player.sprite.sy
                                if abs(player.sprite.sy - HALFHEIGHT) <= HEIGHT
                                else BH
                            ),
                            i[2], i[3]
                        )
                    )
                players.draw(SCREEN)
                weapons.draw(SCREEN)
                bullets.draw(SCREEN)
                SCREEN.blit(myfont.render(
                    'HP: {}/{}'.format(
                        player.sprite.health,
                        Player.health
                    ),
                    False, (255, 0, 128)
                ), (0, 0))
                SCREEN.blit(myfont.render(
                    str(player.sprite.ammo),
                    False, (255, 0, 128)
                ), (0, HEIGHT - texts['intro'].get_height()))
                pygame.display.flip()
                await asyncio.sleep(1/FPS)
    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        pygame.quit()
        try:
            recv.cancel()
            send.cancel()
            rpcu.cancel()
        except NameError:
            pass
        return
try:
    LOOP.run_until_complete(main())
finally:
    if RPC:
        RPC.close()
